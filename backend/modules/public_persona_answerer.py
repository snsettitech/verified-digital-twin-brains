from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from modules.agent import (
    _build_query_ranked_profile_seed_rows,
    _extract_inline_citation_ids,
    _merge_twin_row_settings,
    _strip_inline_source_refs,
)
from modules.fastpath_intent_router import classify_fastpath_intent
from modules.grounding_policy import get_grounding_policy
import modules.inference_router as inference_router
from modules.observability import supabase
from modules.public_profile_pack import _safe_dict, build_public_profile_pack

logger = logging.getLogger(__name__)

PUBLIC_PERSONA_MAX_CONTEXT_SNIPPETS = max(
    4,
    int(os.getenv("PUBLIC_PERSONA_MAX_CONTEXT_SNIPPETS", "8")),
)


@dataclass
class PublicPersonaAnswer:
    response: str
    citations: List[str] = field(default_factory=list)
    contexts: List[Dict[str, Any]] = field(default_factory=list)
    dialogue_mode: str = "QA_FACT"
    intent_label: str = "factual_with_evidence"
    workflow_intent: str = "answer"
    module_ids: List[str] = field(default_factory=list)
    render_strategy: str = "source_faithful"
    query_class: str = "factual"
    quote_intent: bool = False
    answerability_state: str = "direct"
    source_tier: str = "canonical"
    review_required: bool = False
    review_reason: Optional[str] = None
    planner_action: str = "answer"
    skipped_reason: str = "not_applicable"
    provider_used: str = field(default_factory=inference_router.get_active_provider)
    model_used: str = field(default_factory=inference_router.get_active_model)
    evidence_block_type: str = ""
    debug_flags: Dict[str, Any] = field(default_factory=dict)


def build_smalltalk_response(query: str, settings: Optional[Dict[str, Any]] = None) -> str:
    q_lower = str(query or "").lower().strip()
    if any(marker in q_lower for marker in ("thank you", "thanks")):
        return "You're welcome."
    if q_lower in {"ok", "okay", "cool", "sounds good", "got it", "understood"}:
        return "Sounds good."
    if any(marker in q_lower for marker in ("how are you", "how's your day", "hows your day")):
        return "Doing well. How can I help?"
    if q_lower in {"hi", "hello", "hey", "hi!", "hello!", "hey!"}:
        if settings:
            public_profile = settings.get("public_profile") or {}
            conversation_profile = _safe_dict(public_profile.get("conversation_profile"))
            display_name = _display_name_from_settings(settings)
            capability_intro = _clean_text(conversation_profile.get("capability_intro"))
            help_areas = _conversation_help_areas(settings)
            if capability_intro:
                return f"Hi, it's {display_name}'s AI. {capability_intro} What would you like to dig into?"
            if help_areas:
                help_text = ", ".join(help_areas[:3])
                return f"Hi, it's {display_name}'s AI. I can help with {help_text}. What's on your mind?"
            bio_raw = str(public_profile.get("bio") or "").strip()
            if bio_raw:
                sentences = [s.strip() for s in bio_raw.split(".") if s.strip()]
                bio_excerpt = ". ".join(sentences[:2]) + "." if len(sentences) >= 2 else bio_raw
                return f"Hi, it's {display_name}'s AI. {bio_excerpt} What would you like to talk about?"
        return "Hey! Great to chat with you."
    return "Hi. How can I help?"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _default_provider_meta() -> Dict[str, str]:
    return {
        "provider": inference_router.get_active_provider(),
        "model": inference_router.get_active_model(),
    }


def _conversation_help_areas(settings: Optional[Dict[str, Any]]) -> List[str]:
    public_profile = _safe_dict((settings or {}).get("public_profile"))
    conversation_profile = _safe_dict(public_profile.get("conversation_profile"))
    help_areas = conversation_profile.get("help_areas")
    if isinstance(help_areas, list):
        normalized = [str(item).strip() for item in help_areas if str(item).strip()]
        if normalized:
            return normalized[:6]
    expertise = public_profile.get("areas_of_expertise")
    if isinstance(expertise, list):
        normalized = [str(item).strip() for item in expertise if str(item).strip()]
        if normalized:
            return normalized[:6]
    return []


def _display_name_from_settings(settings: Optional[Dict[str, Any]]) -> str:
    public_profile = _safe_dict((settings or {}).get("public_profile"))
    return (
        _clean_text(public_profile.get("display_name"))
        or _clean_text((settings or {}).get("name"))
        or "this persona"
    )


def _first_sentence(text: Any) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    if not parts:
        return ""
    first = parts[0].strip()
    if (
        len(parts) > 1
        and first.lower().endswith((" mr.", " mrs.", " ms.", " dr.", " prof.", " sr.", " jr."))
    ):
        first = f"{first} {parts[1].strip()}".strip()
    return first


def _sanitize_profile_sentence(text: Any, display_name: str) -> str:
    sentence = _first_sentence(text)
    if not sentence:
        return ""
    sentence = re.sub(
        r"\[(?:[0-9a-f]{8,}(?:-[0-9a-f]{4,})+)(?:[;,](?:[0-9a-f]{8,}(?:-[0-9a-f]{4,})+))*\]",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    sentence = re.sub(r"\s+", " ", sentence).strip(" .")
    lowered = sentence.lower()
    if not sentence or lowered.startswith("digital twin"):
        return ""
    if lowered.startswith(("he ", "she ", "they ")):
        return ""
    if display_name and lowered == display_name.lower():
        return ""
    return f"{sentence}."


def _is_quote_intent(query: str) -> bool:
    return bool(get_grounding_policy(query).get("quote_intent"))


def _merge_context_snippets(
    existing: List[Dict[str, Any]],
    incoming: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not isinstance(incoming, list):
        return existing

    seen = {
        f"{(row.get('source_id') or '').strip()}::{(row.get('text') or '').strip()[:180]}"
        for row in existing
        if isinstance(row, dict)
    }
    merged = list(existing)

    for row in incoming:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        source_id = str(row.get("source_id") or "").strip()
        sig = f"{source_id}::{text[:180]}"
        if sig in seen:
            continue
        normalized_row: Dict[str, Any] = {"source_id": source_id, "text": text}
        for key in ("section_title", "section_path", "chunk_type", "block_type", "seed_type"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                normalized_row[key] = value.strip()
        raw_stats = row.get("retrieval_stats")
        if isinstance(raw_stats, dict):
            normalized_row["retrieval_stats"] = dict(raw_stats)
        for key in ("score", "vector_score"):
            value = row.get(key)
            if isinstance(value, (int, float)):
                normalized_row[key] = float(value)
        citation_ids = row.get("citation_ids")
        if isinstance(citation_ids, list):
            normalized_row["citation_ids"] = [str(item).strip() for item in citation_ids if str(item).strip()]
        for key in ("source_name", "strategy_name", "title", "is_answer_text"):
            if key in row:
                normalized_row[key] = row.get(key)
        merged.append(normalized_row)
        seen.add(sig)
        if len(merged) >= PUBLIC_PERSONA_MAX_CONTEXT_SNIPPETS:
            break

    return merged


def _load_public_twin_settings(twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("twins")
            .select("id, name, description, settings, created_at, updated_at")
            .eq("id", twin_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.debug("Public twin settings load failed for %s: %s", twin_id, exc)
        return None

    row = (result.data or [None])[0]
    if not isinstance(row, dict):
        return None
    return _merge_twin_row_settings(row)


def _load_public_profile_pack(twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("twins")
            .select("id, name, settings, status, created_at, updated_at")
            .eq("id", twin_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.debug("Public profile pack load failed for %s: %s", twin_id, exc)
        return None

    row = (result.data or [None])[0]
    if not isinstance(row, dict):
        return None
    try:
        return build_public_profile_pack(row)
    except Exception as exc:
        logger.debug("Public profile pack build failed for %s: %s", twin_id, exc)
        return None


def _load_public_identity_snapshot(twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("twins")
            .select("id, name, description, settings")
            .eq("id", twin_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.debug("Public identity snapshot load failed for %s: %s", twin_id, exc)
        return None

    row = (result.data or [None])[0]
    if not isinstance(row, dict):
        return None

    settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
    public_profile = settings.get("public_profile") if isinstance(settings.get("public_profile"), dict) else {}

    display_name = (
        str(public_profile.get("display_name") or "").strip()
        or str(settings.get("name") or "").strip()
        or str(row.get("name") or "").strip()
    )
    headline = str(public_profile.get("headline") or settings.get("tagline") or "").strip()
    role = str(public_profile.get("role") or "").strip()
    organization = str(public_profile.get("organization") or "").strip()
    bio = (
        str(public_profile.get("bio") or "").strip()
        or str(settings.get("public_intro") or "").strip()
        or str(settings.get("description") or "").strip()
        or str(row.get("description") or "").strip()
    )

    if not display_name:
        return None

    areas_of_expertise = public_profile.get("areas_of_expertise")
    if not isinstance(areas_of_expertise, list):
        areas_of_expertise = []
    contributions = public_profile.get("contributions")
    if not isinstance(contributions, list):
        contributions = []
    key_achievements = public_profile.get("key_achievements")
    if not isinstance(key_achievements, list):
        key_achievements = []
    work_experience = public_profile.get("work_experience")
    if not isinstance(work_experience, list):
        work_experience = []
    conversation_profile = _safe_dict(public_profile.get("conversation_profile"))

    return {
        "display_name": display_name,
        "headline": headline,
        "role": role,
        "organization": organization,
        "occupation": str(public_profile.get("occupation") or "").strip(),
        "short_description": str(public_profile.get("short_description") or "").strip(),
        "bio": bio,
        "areas_of_expertise": [str(a).strip() for a in areas_of_expertise if str(a).strip()],
        "contributions": [str(item).strip() for item in contributions if str(item).strip()],
        "key_achievements": [str(item).strip() for item in key_achievements if str(item).strip()],
        "work_experience": [item for item in work_experience if isinstance(item, dict)],
        "conversation_profile": conversation_profile,
    }


def _public_profile_display_name(settings: Dict[str, Any]) -> str:
    public_profile = settings.get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}
    identity_pack = settings.get("persona_identity_pack")
    identity_pack = identity_pack if isinstance(identity_pack, dict) else {}
    return (
        _clean_text(settings.get("name"))
        or _clean_text(public_profile.get("display_name"))
        or _clean_text(identity_pack.get("display_name") or identity_pack.get("preferred_name"))
    )


def _manual_public_profile_seed_rows(
    settings: Dict[str, Any],
    query: str,
    *,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    public_profile = settings.get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}
    identity_pack = settings.get("persona_identity_pack")
    identity_pack = identity_pack if isinstance(identity_pack, dict) else {}
    display_name = _public_profile_display_name(settings)
    if not display_name:
        return []

    seed_rows: List[Dict[str, Any]] = []

    def _add_row(seed_type: str, raw_text: Any, *, source_name: str) -> None:
        citation_ids = _extract_inline_citation_ids(raw_text)
        text = _strip_inline_source_refs(raw_text)
        text = _clean_text(text)
        if not text:
            return
        if not text.endswith((".", "!", "?")):
            text = f"{text}."
        seed_rows.append(
            {
                "text": text,
                "source_id": citation_ids[0] if citation_ids else "",
                "citation_ids": citation_ids,
                "source_name": source_name,
                "block_type": "answer_text",
                "is_answer_text": True,
                "strategy_name": "canonical_profile_seed",
                "seed_type": seed_type,
                "title": f"{display_name} profile",
            }
        )

    occupation = _clean_text(public_profile.get("occupation"))
    role = _clean_text(public_profile.get("role") or identity_pack.get("role"))
    organization = _clean_text(public_profile.get("organization") or identity_pack.get("organization"))
    headline = _clean_text(public_profile.get("headline") or identity_pack.get("headline"))
    short_description = _clean_text(public_profile.get("short_description"))
    bio = _clean_text(public_profile.get("bio") or identity_pack.get("biography"))

    if occupation:
        _add_row("summary", f"{display_name} is {occupation}", source_name="Canonical public profile")
    elif role and organization:
        _add_row("summary", f"{display_name} is the {role} at {organization}", source_name="Canonical public profile")
    elif role:
        _add_row("summary", f"{display_name} is the {role}", source_name="Canonical public profile")
    if headline:
        _add_row("headline", headline, source_name="Canonical public profile")
    if short_description:
        _add_row("summary", short_description, source_name="Canonical public profile")
    if bio:
        _add_row("bio", bio, source_name="Canonical public biography")

    response_seeds = public_profile.get("public_response_seeds")
    if isinstance(response_seeds, list):
        for item in response_seeds[:8]:
            if not isinstance(item, dict):
                continue
            question = _clean_text(item.get("question"))
            answer = _clean_text(item.get("answer") or item.get("text"))
            if not answer:
                continue
            raw_text = f"Q: {question}\nA: {answer}" if question else answer
            _add_row("qa", raw_text, source_name=_clean_text(item.get("title")) or "Prepared public answer")

    for item in public_profile.get("contributions") or []:
        _add_row("contribution", item, source_name="Public contributions")
    for item in public_profile.get("key_achievements") or []:
        _add_row("achievement", item, source_name="Public achievements")

    for job in public_profile.get("work_experience") or []:
        if not isinstance(job, dict):
            continue
        description = _clean_text(job.get("description"))
        role_value = _clean_text(job.get("role") or job.get("title"))
        company = _clean_text(job.get("company") or job.get("organization"))
        start_year = _clean_text(job.get("start_year"))
        end_year = _clean_text(job.get("end_year"))
        years = ""
        if start_year and end_year:
            years = f" from {start_year} to {end_year}"
        elif start_year:
            years = f" since {start_year}"
        elif end_year:
            years = f" until {end_year}"
        if description:
            _add_row("work", description, source_name="Public work history")
        elif role_value and company:
            _add_row("work", f"{display_name} worked as {role_value} at {company}{years}", source_name="Public work history")

    query_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", _clean_text(query).lower())
        if len(token) > 2
    }

    def _score_row(row: Dict[str, Any]) -> Tuple[int, int]:
        text = _clean_text(row.get("text")).lower()
        overlap = sum(1 for token in query_tokens if token in text)
        seed_type = _clean_text(row.get("seed_type")).lower()
        bonus = 0
        if any(token in query_tokens for token in {"background", "career", "journey", "politics", "political", "experience"}):
            if seed_type in {"qa", "work", "contribution", "bio"}:
                bonus += 2
        if any(token in query_tokens for token in {"who", "about", "role", "title", "office"}):
            if seed_type in {"summary", "bio", "headline"}:
                bonus += 2
        return (overlap + bonus, len(text))

    deduped = _merge_context_snippets([], seed_rows)
    ranked = sorted(deduped, key=_score_row, reverse=True)
    return ranked[: max(1, limit)]


def _manual_public_pack_seed_rows(
    profile_pack: Dict[str, Any],
    query: str,
    *,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    display_name = _clean_text(profile_pack.get("name"))
    if not display_name:
        return []

    seed_rows: List[Dict[str, Any]] = []

    def _add_row(seed_type: str, raw_text: Any, *, source_name: str) -> None:
        citation_ids = _extract_inline_citation_ids(raw_text)
        text = _strip_inline_source_refs(raw_text)
        text = _clean_text(text)
        if not text:
            return
        if not text.endswith((".", "!", "?")):
            text = f"{text}."
        seed_rows.append(
            {
                "text": text,
                "source_id": citation_ids[0] if citation_ids else "",
                "citation_ids": citation_ids,
                "source_name": source_name,
                "block_type": "answer_text",
                "is_answer_text": True,
                "strategy_name": "canonical_profile_pack",
                "seed_type": seed_type,
                "title": f"{display_name} public pack",
            }
        )

    occupation = _clean_text(profile_pack.get("occupation"))
    headline = _clean_text(profile_pack.get("headline"))
    short_description = _clean_text(profile_pack.get("short_description"))
    bio = _clean_text(profile_pack.get("bio"))
    if occupation:
        _add_row("summary", f"{display_name} is {occupation}", source_name="Public profile pack")
    if headline:
        _add_row("headline", headline, source_name="Public profile pack")
    if short_description:
        _add_row("summary", short_description, source_name="Public profile pack")
    if bio:
        _add_row("bio", bio, source_name="Public profile pack")

    for item in profile_pack.get("contributions") or []:
        _add_row("contribution", item, source_name="Public contributions")
    for item in profile_pack.get("key_achievements") or []:
        _add_row("achievement", item, source_name="Public achievements")
    for item in profile_pack.get("areas_of_expertise") or []:
        _add_row("expertise", item, source_name="Public expertise")

    for job in profile_pack.get("work_experience") or []:
        if not isinstance(job, dict):
            continue
        description = _clean_text(job.get("description"))
        role_value = _clean_text(job.get("role") or job.get("title"))
        company = _clean_text(job.get("company") or job.get("organization"))
        start_year = _clean_text(job.get("start_year"))
        end_year = _clean_text(job.get("end_year"))
        years = ""
        if start_year and end_year:
            years = f" from {start_year} to {end_year}"
        elif start_year:
            years = f" since {start_year}"
        elif end_year:
            years = f" until {end_year}"
        if description:
            _add_row("work", description, source_name="Public work history")
        elif role_value and company:
            _add_row("work", f"{display_name} worked as {role_value} at {company}{years}", source_name="Public work history")

    for edu in profile_pack.get("education") or []:
        if not isinstance(edu, dict):
            continue
        description = _clean_text(edu.get("description"))
        institution = _clean_text(edu.get("institution"))
        degree = _clean_text(edu.get("degree"))
        field = _clean_text(edu.get("field"))
        if description:
            _add_row("education", description, source_name="Public education")
        elif institution or degree or field:
            parts = [part for part in [degree, field, institution] if part]
            _add_row("education", f"{display_name} studied {', '.join(parts)}", source_name="Public education")

    query_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", _clean_text(query).lower())
        if len(token) > 2
    }

    def _score_row(row: Dict[str, Any]) -> Tuple[int, int]:
        text = _clean_text(row.get("text")).lower()
        overlap = sum(1 for token in query_tokens if token in text)
        seed_type = _clean_text(row.get("seed_type")).lower()
        bonus = 0
        if any(token in query_tokens for token in {"background", "career", "journey", "politics", "political", "experience"}):
            if seed_type in {"work", "contribution", "bio", "achievement"}:
                bonus += 2
        if any(token in query_tokens for token in {"who", "about", "role", "title", "office"}):
            if seed_type in {"summary", "bio", "headline"}:
                bonus += 2
        return (overlap + bonus, len(text))

    deduped = _merge_context_snippets([], seed_rows)
    ranked = sorted(deduped, key=_score_row, reverse=True)
    return ranked[: max(1, limit)]


def _public_profile_seed_rows(
    settings: Dict[str, Any],
    query: str,
    *,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    ranked = _build_query_ranked_profile_seed_rows(settings, query, limit=limit)
    if ranked:
        return ranked[:limit]
    return _manual_public_profile_seed_rows(settings, query, limit=limit)


def _public_profile_direct_answer(seed_rows: List[Dict[str, Any]], *, display_name: str) -> str:
    parts: List[str] = []
    for row in seed_rows[:2]:
        text = _clean_text(row.get("text"))
        if not text:
            continue
        if display_name:
            text = re.sub(rf"^{re.escape(display_name)}\s+is\b", "I am", text, flags=re.IGNORECASE)
            text = re.sub(rf"^{re.escape(display_name)}\s+was\b", "I was", text, flags=re.IGNORECASE)
            text = re.sub(rf"^{re.escape(display_name)}\s+has been\b", "I have been", text, flags=re.IGNORECASE)
            text = re.sub(rf"^{re.escape(display_name)}\s+served\b", "I served", text, flags=re.IGNORECASE)
            text = re.sub(rf"^{re.escape(display_name)}\s+worked\b", "I worked", text, flags=re.IGNORECASE)
            text = re.sub(rf"^{re.escape(display_name)}\s+joined\b", "I joined", text, flags=re.IGNORECASE)
            text = re.sub(rf"\b{re.escape(display_name)}\s+is\b", "I am", text, flags=re.IGNORECASE)
            text = re.sub(rf"\b{re.escape(display_name)}\s+was\b", "I was", text, flags=re.IGNORECASE)
            text = re.sub(rf"\b{re.escape(display_name)}\s+has been\b", "I have been", text, flags=re.IGNORECASE)
            text = re.sub(rf"\b{re.escape(display_name)}\s+served\b", "I served", text, flags=re.IGNORECASE)
            text = re.sub(rf"\b{re.escape(display_name)}\s+worked\b", "I worked", text, flags=re.IGNORECASE)
            text = re.sub(rf"\b{re.escape(display_name)}\s+joined\b", "I joined", text, flags=re.IGNORECASE)
        text = re.sub(r"^He\s+", "I ", text, flags=re.IGNORECASE)
        text = re.sub(r"^She\s+", "I ", text, flags=re.IGNORECASE)
        if text and not re.match(r"^(I|My)\b", text):
            text = f"Based on my public profile, {text[0].lower() + text[1:]}" if len(text) > 1 else text
        parts.append(text)
    return " ".join(part for part in parts if part).strip()


def _build_evidence_lines(seed_rows: List[Dict[str, Any]], *, limit: int = 4) -> List[str]:
    evidence_lines: List[str] = []
    for idx, row in enumerate(seed_rows[:limit], 1):
        text = _clean_text(row.get("text"))
        if text:
            evidence_lines.append(f"[{idx}] {text}")
    return evidence_lines


def _collect_allowed_source_ids(seed_rows: List[Dict[str, Any]]) -> List[str]:
    allowed_source_ids: List[str] = []
    for row in seed_rows:
        citation_ids = row.get("citation_ids")
        if isinstance(citation_ids, list):
            for cid in citation_ids:
                clean_cid = _clean_text(cid)
                if clean_cid and clean_cid not in allowed_source_ids:
                    allowed_source_ids.append(clean_cid)
        source_id = _clean_text(row.get("source_id"))
        if source_id and source_id not in allowed_source_ids:
            allowed_source_ids.append(source_id)
    return allowed_source_ids


async def rewrite_public_background_fastpath(
    *,
    display_name: str,
    seed_rows: List[Dict[str, Any]],
) -> str:
    evidence_lines = _build_evidence_lines(seed_rows, limit=4)
    if not evidence_lines:
        return ""

    prompt = f"""You are rewriting public profile facts into a cleaner first-person answer for {display_name or 'this profile'}.
Use only the provided facts. Do not add outside knowledge, motives, or unsupported transitions.

Requirements:
- Return 1 or 2 concise sentences.
- Write in first person.
- Keep the wording natural and conversational.
- Preserve only facts that are explicitly supported by the evidence.
- Do not mention citations, evidence blocks, or "public profile" unless needed.

PUBLIC FACTS:
{chr(10).join(evidence_lines)}

Return STRICT JSON:
{{
  "answer": "string"
}}
"""

    try:
        payload, _meta = await inference_router.invoke_json(
            [{"role": "system", "content": prompt}],
            task="planner",
            temperature=0,
            max_tokens=220,
        )
        answer = _clean_text(payload.get("answer"))
        if answer:
            return answer
    except Exception as exc:
        logger.debug("Background fastpath rewrite failed for %s: %s", display_name, exc)
    return ""


async def _finalize_public_persona_answer(
    *,
    query: str,
    display_name: str,
    draft: str,
    seed_rows: List[Dict[str, Any]],
) -> Tuple[str, Dict[str, str]]:
    cleaned_draft = _clean_text(draft)
    evidence_lines = _build_evidence_lines(seed_rows, limit=4)
    if not cleaned_draft or not evidence_lines:
        return cleaned_draft, _default_provider_meta()

    prompt = f"""You are polishing a public persona answer for {display_name or 'this profile'}.
Use only the supported facts below. Do not add outside knowledge, inferred motives, or unsupported chronology.

Requirements:
- Return only the final answer text.
- Keep it to 1 or 2 concise sentences.
- Write in first person.
- Keep the answer direct and natural.
- Stay close to the supported facts and the draft answer.
- Do not mention citations, evidence blocks, or "public profile".

USER QUESTION:
{query}

SUPPORTED FACTS:
{chr(10).join(evidence_lines)}

DRAFT ANSWER:
{cleaned_draft}
"""

    try:
        rewritten, route_meta = await inference_router.invoke_text(
            [{"role": "system", "content": prompt}],
            task="realizer",
            temperature=0.1,
            max_tokens=180,
            preferred_provider="gemini",
        )
        provider_used = str(route_meta.get("provider") or "").lower()
        if provider_used not in {"gemini", "openai"}:
            return cleaned_draft, _default_provider_meta()
        final_text = _clean_text(rewritten)
        if not final_text:
            return cleaned_draft, _default_provider_meta()
        return final_text, {
            "provider": provider_used or "gemini",
            "model": str(route_meta.get("model") or inference_router.get_active_model()),
        }
    except Exception as exc:
        logger.debug("Public persona Gemini finalizer failed for %s: %s", display_name, exc)
        return cleaned_draft, _default_provider_meta()


async def _build_public_fastpath_answer(twin_id: str, intent: str) -> Optional[PublicPersonaAnswer]:
    snapshot = _load_public_identity_snapshot(twin_id)
    profile_pack = _load_public_profile_pack(twin_id) if intent == "identity_background" and not snapshot else None
    if not snapshot and not profile_pack:
        return None

    display_name = (
        _clean_text((profile_pack or {}).get("name"))
        or (snapshot or {}).get("display_name")
        or "this public profile"
    )
    role = (snapshot or {}).get("role", "")
    organization = (snapshot or {}).get("organization", "")
    headline = (snapshot or {}).get("headline", "")
    bio_sentence = _sanitize_profile_sentence((snapshot or {}).get("bio") or (profile_pack or {}).get("bio"), display_name)
    provider_meta = _default_provider_meta()
    conversation_profile = _safe_dict((snapshot or {}).get("conversation_profile") or (profile_pack or {}).get("conversation_profile"))
    capability_intro = _clean_text(conversation_profile.get("capability_intro"))
    authenticity_disclosure = _clean_text(conversation_profile.get("authenticity_disclosure"))
    help_areas = _clean_unique_strings(
        conversation_profile.get("help_areas")
        or (snapshot or {}).get("areas_of_expertise")
        or (profile_pack or {}).get("areas_of_expertise")
        or [],
        limit=6,
    )

    descriptor = ""
    if role and organization:
        descriptor = f"{role} at {organization}"
    elif role:
        descriptor = role
    elif headline:
        descriptor = headline

    if intent == "authenticity_disclosure":
        base = authenticity_disclosure or f"I'm a public digital version of {display_name}."
        if descriptor and descriptor.lower() not in base.lower():
            base = f"{base.rstrip('.')} I speak from the perspective of {descriptor}."
        return PublicPersonaAnswer(
            response=base,
            dialogue_mode="IDENTITY_FACT",
            intent_label="meta_or_system",
            query_class="identity",
            skipped_reason="public_fastpath",
            provider_used=provider_meta["provider"],
            model_used=provider_meta["model"],
        )

    if intent == "identity_role":
        if role and organization:
            base = f"I serve as {role} at {organization}."
        elif role:
            base = f"I serve as {role}."
        elif headline:
            base = f"I'm associated with {headline}."
        else:
            base = "I'm associated with this public profile."
        return PublicPersonaAnswer(
            response=base,
            dialogue_mode="IDENTITY_FACT",
            intent_label="meta_or_system",
            query_class="identity",
            skipped_reason="public_fastpath",
            provider_used=provider_meta["provider"],
            model_used=provider_meta["model"],
        )

    if intent == "identity_background":
        seed_rows: List[Dict[str, Any]] = []
        if snapshot:
            snapshot_settings = {
                "name": display_name,
                "public_profile": {
                    "occupation": snapshot.get("occupation"),
                    "headline": headline,
                    "short_description": snapshot.get("short_description"),
                    "role": role,
                    "organization": organization,
                    "bio": snapshot.get("bio"),
                    "areas_of_expertise": snapshot.get("areas_of_expertise"),
                    "contributions": snapshot.get("contributions"),
                    "key_achievements": snapshot.get("key_achievements"),
                    "work_experience": snapshot.get("work_experience"),
                },
            }
            seed_rows = _merge_context_snippets(
                seed_rows,
                _manual_public_profile_seed_rows(snapshot_settings, "background career politics public life", limit=4),
            )
        if isinstance(profile_pack, dict) and not seed_rows:
            seed_rows = _merge_context_snippets(
                seed_rows,
                _manual_public_pack_seed_rows(profile_pack, "background career politics public life", limit=4),
            )
        biography_rows = [
            row for row in seed_rows
            if _clean_text(row.get("seed_type")).lower() in {"bio", "work", "contribution", "achievement", "education"}
        ]
        draft = await rewrite_public_background_fastpath(
            display_name=display_name,
            seed_rows=biography_rows or seed_rows,
        )
        if not draft:
            draft = _public_profile_direct_answer(biography_rows or seed_rows, display_name=display_name)
        if not draft and bio_sentence:
            draft = bio_sentence
        if not draft:
            draft = "My public background is summarized in this profile."
        finalized, provider_meta = await _finalize_public_persona_answer(
            query="What is your background?",
            display_name=display_name,
            draft=draft,
            seed_rows=biography_rows or seed_rows,
        )
        return PublicPersonaAnswer(
            response=finalized or draft,
            contexts=biography_rows or seed_rows,
            dialogue_mode="IDENTITY_FACT",
            intent_label="meta_or_system",
            query_class="identity",
            answerability_state="derivable",
            source_tier="canonical",
            skipped_reason="public_fastpath",
            provider_used=provider_meta["provider"],
            model_used=provider_meta["model"],
            evidence_block_type="canonical_profile_seed",
        )

    if intent == "scope_help":
        if capability_intro:
            base = capability_intro
            if bio_sentence:
                base = f"{base} {bio_sentence}"
        elif help_areas:
            topic_list = ", ".join(help_areas[:4])
            base = f"I can help with {topic_list}."
            if len(help_areas) > 4:
                base += f" I can also talk about {', '.join(help_areas[4:7])}."
            if bio_sentence:
                base = f"{base} {bio_sentence}"
        else:
            scope = descriptor or "the areas this profile is known for"
            base = f"I can help you think through {scope} from this perspective."
            if bio_sentence:
                base = f"{base} {bio_sentence}"
        return PublicPersonaAnswer(
            response=base,
            dialogue_mode="IDENTITY_FACT",
            intent_label="meta_or_system",
            query_class="identity",
            source_tier="canonical",
            skipped_reason="public_fastpath",
            provider_used=provider_meta["provider"],
            model_used=provider_meta["model"],
        )

    base = f"I'm {display_name}"
    if descriptor:
        base += f", {descriptor}"
    base += "."
    if bio_sentence:
        base = f"{base} {bio_sentence}"
    return PublicPersonaAnswer(
        response=base,
        dialogue_mode="IDENTITY_FACT",
        intent_label="meta_or_system",
        query_class="identity",
        source_tier="canonical",
        skipped_reason="public_fastpath",
        provider_used=provider_meta["provider"],
        model_used=provider_meta["model"],
    )


async def _answer_from_public_profile(
    twin_id: str,
    query: str,
    *,
    query_policy: Optional[Dict[str, Any]] = None,
) -> Optional[PublicPersonaAnswer]:
    if _is_quote_intent(query):
        return None

    query_policy = query_policy if isinstance(query_policy, dict) else {}
    query_class = _clean_text(query_policy.get("query_class")).lower() or "factual"
    normalized_query = _clean_text(query).lower()
    if query_class not in {"identity", "factual", "analytical"}:
        return None

    profile_pack = _load_public_profile_pack(twin_id)
    settings = _load_public_twin_settings(twin_id)
    if not isinstance(profile_pack, dict) and not isinstance(settings, dict):
        return None

    display_name = _clean_text((profile_pack or {}).get("name")) or (
        _public_profile_display_name(settings) if isinstance(settings, dict) else ""
    )
    seed_rows: List[Dict[str, Any]] = []
    if isinstance(profile_pack, dict):
        seed_rows = _merge_context_snippets(seed_rows, _manual_public_pack_seed_rows(profile_pack, query, limit=6))
    if isinstance(settings, dict):
        seed_rows = _merge_context_snippets(seed_rows, _public_profile_seed_rows(settings, query, limit=6))
    if not seed_rows:
        return None

    evidence_lines = _build_evidence_lines(seed_rows, limit=6)
    allowed_source_ids = _collect_allowed_source_ids(seed_rows)
    if not evidence_lines:
        return None

    prompt = f"""You are answering on behalf of a public digital twin profile for {display_name or 'this profile'}.
Use only the provided canonical public profile evidence. Do not use outside knowledge.

Decide if the question can be answered from the public profile evidence alone.
- If yes, produce a factual draft answer grounded only in the evidence.
- For biography, background, career, politics, or experience questions, synthesize cautiously from the evidence instead of refusing.
- If the evidence only partially answers the question, answer with what the public profile shows.
- If the evidence does not support an answer, return answerable false.

USER QUESTION:
{query}

PROFILE EVIDENCE:
{chr(10).join(evidence_lines)}

ALLOWED SOURCE IDS:
{json.dumps(allowed_source_ids)}

Return STRICT JSON:
{{
  "answerable": true,
  "answer": "string",
  "citations": ["source_id"],
  "answerability_state": "direct"
}}
"""

    try:
        payload, _meta = await inference_router.invoke_json(
            [{"role": "system", "content": prompt}],
            task="planner",
            temperature=0,
            max_tokens=380,
        )
        answerable = bool(payload.get("answerable"))
        draft = _clean_text(payload.get("answer"))
        citations = [
            cid for cid in (payload.get("citations") or [])
            if isinstance(cid, str) and _clean_text(cid) and cid in allowed_source_ids
        ][:4]
        answerability_state = _clean_text(payload.get("answerability_state")).lower() or "direct"
        if answerable and draft:
            finalized, provider_meta = await _finalize_public_persona_answer(
                query=query,
                display_name=display_name,
                draft=draft,
                seed_rows=seed_rows,
            )
            return PublicPersonaAnswer(
                response=finalized or draft,
                citations=citations,
                contexts=seed_rows,
                dialogue_mode="QA_FACT",
                intent_label="factual_with_evidence",
                module_ids=["procedural.profile_qa.public"],
                query_class=query_class,
                quote_intent=False,
                answerability_state=answerability_state if answerability_state in {"direct", "derivable"} else "derivable",
                source_tier="canonical",
                skipped_reason="public_profile_first_answer",
                provider_used=provider_meta["provider"],
                model_used=provider_meta["model"],
                evidence_block_type="canonical_profile_seed",
                debug_flags={"public_profile_first_answer": True},
            )
    except Exception as exc:
        logger.debug("Public profile QA composition failed for %s: %s", twin_id, exc)

    biography_like_query = query_class == "identity" or any(
        marker in normalized_query
        for marker in (
            "about you",
            "background",
            "career",
            "experience",
            "journey",
            "politic",
            "public life",
            "role",
            "title",
            "office",
            "who are",
            "who is",
            "how did you get",
            "how you got",
            "how did",
            "what do you do",
            "what is your background",
        )
    )
    if not biography_like_query:
        return None

    draft = _public_profile_direct_answer(seed_rows, display_name=display_name)
    if not draft:
        return None
    finalized, provider_meta = await _finalize_public_persona_answer(
        query=query,
        display_name=display_name,
        draft=draft,
        seed_rows=seed_rows,
    )
    return PublicPersonaAnswer(
        response=finalized or draft,
        citations=allowed_source_ids[:4],
        contexts=seed_rows,
        dialogue_mode="QA_FACT",
        intent_label="factual_with_evidence",
        module_ids=["procedural.profile_qa.public"],
        query_class=query_class,
        quote_intent=False,
        answerability_state="derivable",
        source_tier="canonical",
        skipped_reason="public_profile_first_answer",
        provider_used=provider_meta["provider"],
        model_used=provider_meta["model"],
        evidence_block_type="canonical_profile_seed",
        debug_flags={"public_profile_first_answer": True},
    )


async def maybe_answer_public_persona_query(
    twin_id: str,
    query: str,
    *,
    query_policy: Optional[Dict[str, Any]] = None,
    action_like_query: bool = False,
) -> Optional[PublicPersonaAnswer]:
    effective_query_policy = query_policy if isinstance(query_policy, dict) else get_grounding_policy(query)

    if effective_query_policy.get("is_smalltalk"):
        settings = _load_public_twin_settings(twin_id)
        provider_meta = _default_provider_meta()
        return PublicPersonaAnswer(
            response=build_smalltalk_response(query, settings=settings),
            dialogue_mode="SMALLTALK",
            intent_label="meta_or_system",
            module_ids=["procedural.style.smalltalk"],
            query_class=str(effective_query_policy.get("query_class") or "smalltalk"),
            source_tier="canonical",
            skipped_reason="public_smalltalk",
            provider_used=provider_meta["provider"],
            model_used=provider_meta["model"],
        )

    fastpath = classify_fastpath_intent(query)
    if fastpath.get("matched"):
        answer = await _build_public_fastpath_answer(
            twin_id,
            str(fastpath.get("intent") or "").strip(),
        )
        if answer:
            return answer

    if action_like_query:
        return None

    return await _answer_from_public_profile(
        twin_id,
        query,
        query_policy=effective_query_policy,
    )


async def maybe_build_public_persona_fallback(
    twin_id: str,
    query: str,
) -> Optional[PublicPersonaAnswer]:
    settings = _load_public_twin_settings(twin_id)
    if not isinstance(settings, dict):
        return None

    seed_rows = _public_profile_seed_rows(settings, query, limit=5)
    if not seed_rows:
        return None

    evidence_lines = _build_evidence_lines(seed_rows, limit=5)
    allowed_source_ids = _collect_allowed_source_ids(seed_rows)
    if not evidence_lines:
        return None

    prompt = f"""You are answering on behalf of a public digital twin profile.
Use only the provided canonical profile evidence. Do not use outside knowledge.
Draft a concise answer in first person as the profile.

USER QUESTION:
{query}

PROFILE EVIDENCE:
{chr(10).join(evidence_lines)}

ALLOWED SOURCE IDS:
{json.dumps(allowed_source_ids)}

Return STRICT JSON:
{{
  "answer_points": ["point 1", "point 2"],
  "citations": ["source_id"],
  "answerability_state": "derivable"
}}

Rules:
- Maximum 2 answer points.
- If the evidence is thin, answer cautiously from what is available instead of saying you do not know.
- Cite only IDs from ALLOWED SOURCE IDS.
"""

    try:
        payload, _meta = await inference_router.invoke_json(
            [{"role": "system", "content": prompt}],
            task="planner",
            temperature=0,
            max_tokens=350,
        )
        answer_points = [
            _clean_text(item)
            for item in (payload.get("answer_points") or [])
            if _clean_text(item)
        ][:2]
        citations = [
            cid for cid in (payload.get("citations") or [])
            if isinstance(cid, str) and cid.strip() and cid in allowed_source_ids
        ][:3]
        answerability_state = _clean_text(payload.get("answerability_state")).lower() or "derivable"
        if answer_points:
            draft = " ".join(answer_points)
            display_name = _public_profile_display_name(settings)
            finalized, provider_meta = await _finalize_public_persona_answer(
                query=query,
                display_name=display_name,
                draft=draft,
                seed_rows=seed_rows,
            )
            return PublicPersonaAnswer(
                response=finalized or draft,
                citations=citations,
                contexts=seed_rows,
                dialogue_mode="QA_FACT",
                intent_label="factual_with_evidence",
                workflow_intent="answer",
                module_ids=["procedural.fallback.public_profile_seed"],
                query_class=str(get_grounding_policy(query).get("query_class") or "factual"),
                quote_intent=_is_quote_intent(query),
                answerability_state=answerability_state if answerability_state in {"direct", "derivable"} else "derivable",
                source_tier="canonical",
                skipped_reason="public_profile_seed_fallback",
                provider_used=provider_meta["provider"],
                model_used=provider_meta["model"],
                evidence_block_type="canonical_profile_seed",
            )
    except Exception as exc:
        logger.debug("Public profile fallback composition failed for %s: %s", twin_id, exc)

    fallback_points = [str(seed_rows[0].get("text") or "").strip()]
    if len(seed_rows) > 1:
        fallback_points.append(str(seed_rows[1].get("text") or "").strip())
    draft = " ".join(part for part in fallback_points if part)
    if not draft:
        return None
    display_name = _public_profile_display_name(settings)
    finalized, provider_meta = await _finalize_public_persona_answer(
        query=query,
        display_name=display_name,
        draft=draft,
        seed_rows=seed_rows,
    )
    return PublicPersonaAnswer(
        response=finalized or draft,
        citations=allowed_source_ids[:3],
        contexts=seed_rows,
        dialogue_mode="QA_FACT",
        intent_label="factual_with_evidence",
        workflow_intent="answer",
        module_ids=["procedural.fallback.public_profile_seed"],
        query_class=str(get_grounding_policy(query).get("query_class") or "factual"),
        quote_intent=_is_quote_intent(query),
        answerability_state="derivable",
        source_tier="canonical",
        skipped_reason="public_profile_seed_fallback",
        provider_used=provider_meta["provider"],
        model_used=provider_meta["model"],
        evidence_block_type="canonical_profile_seed",
    )
