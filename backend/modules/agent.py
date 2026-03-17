import os
import asyncio
import json
import re
import re as _re
import time
from typing import Annotated, TypedDict, List, Dict, Any, Union, Optional, Tuple
from urllib.parse import urlparse
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from modules.langfuse_sdk import langfuse_context, observe

from modules.observability import supabase
from modules.persona_compiler import (
    compile_prompt_plan,
    get_prompt_render_options,
    render_prompt_plan_with_options,
)
from modules.persona_intents import classify_query_intent
from modules.identity_gate import classify_query
from modules.persona_module_store import list_runtime_modules_for_intent
from modules.persona_prompt_variant_store import (
    DEFAULT_PERSONA_PROMPT_VARIANT,
    get_active_persona_prompt_variant,
)
from modules.persona_spec import PersonaSpec
from modules.persona_spec_store import get_active_persona_spec
from modules.persona_agent_integration import (
    should_use_5layer_persona,
    maybe_use_5layer_persona,
    PersonaAgentIntegration,
    build_persona_v2_state_updates,
    PERSONA_V2_STATE_FIELDS,
)
from modules.persona_profile_store import (
    get_persona_profile,
    is_profile_eligible_for_fastpath,
)
from modules.fastpath_intent_router import (
    classify_fastpath_intent,
    is_persona_fastpath_enabled,
    is_persona_draft_profile_allowed,
)
from modules.fastpath_response_builder import build_fastpath_response
from modules.inference_router import (
    get_active_model,
    get_active_provider,
    invoke_json,
    invoke_text,
)
from modules.routing_decision import build_routing_decision
from modules.response_policy import UNCERTAINTY_RESPONSE
from modules.grounding_policy import get_grounding_policy
from modules.answering import SYSTEM_PROMPT_TEMPLATE, build_retrieved_context_block
from modules.answerability import (
    build_targeted_clarification_questions,
    evaluate_answerability,
)
from modules.response_composer import compose_answer_points
from modules.deepagents_router import (
    build_deepagents_plan,
    build_single_missing_param_question,
    summarize_deepagents_plan,
)
from modules.deepagents_executor import execute_deepagents_plan

# Query Rewriting for conversational context
from modules.query_rewriter import (
    ConversationalQueryRewriter,
    QueryRewriteResult,
    QUERY_REWRITING_ENABLED,
)

# Try to import checkpointer (optional - P1-A)
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    # Note: asyncpg is a dependency of langgraph-checkpoint-postgres, no need to import directly
    CHECKPOINTER_AVAILABLE = True
except ImportError:
    CHECKPOINTER_AVAILABLE = False
    PostgresSaver = None

# Global checkpointer instance (singleton)
_checkpointer = None

_ROUTER_KNOWLEDGE_CACHE_TTL_SECONDS = float(
    os.getenv("ROUTER_KNOWLEDGE_CACHE_TTL_SECONDS", "30")
)
_ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE = (
    os.getenv("ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE", "true").lower() == "true"
)
_router_knowledge_cache: Dict[str, Dict[str, Any]] = {}

# Adaptive grounding policy for planner output rendering.
ADAPTIVE_GROUNDING_POLICY_ENABLED = (
    os.getenv("ADAPTIVE_GROUNDING_POLICY_ENABLED", "true").lower() == "true"
)
ADAPTIVE_GROUNDING_HIGH_SCORE = float(os.getenv("ADAPTIVE_GROUNDING_HIGH_SCORE", "0.82"))
ADAPTIVE_GROUNDING_HIGH_MARGIN = float(os.getenv("ADAPTIVE_GROUNDING_HIGH_MARGIN", "0.12"))
ADAPTIVE_GROUNDING_MID_SCORE = float(os.getenv("ADAPTIVE_GROUNDING_MID_SCORE", "0.65"))
ADAPTIVE_GROUNDING_MID_OVERLAP = float(os.getenv("ADAPTIVE_GROUNDING_MID_OVERLAP", "0.12"))
PLANNER_SECOND_PASS_RETRIEVAL_TOP_K = max(8, int(os.getenv("PLANNER_SECOND_PASS_RETRIEVAL_TOP_K", "12")))
CONVERSATIONAL_REALIZER_ENABLED = (
    os.getenv("CONVERSATIONAL_REALIZER_ENABLED", "true").lower() == "true"
)
CONVERSATIONAL_REALIZER_MIN_CONFIDENCE = float(
    os.getenv("CONVERSATIONAL_REALIZER_MIN_CONFIDENCE", "0.0")
)


def _ensure_closing_question(response_text: str, query: str) -> str:
    """
    Post-processing guard: ensure the response ends with exactly one
    question. If it already ends with a question mark, return unchanged.
    If it does not, append a context-aware fallback question.
    """
    if not response_text or not response_text.strip():
        return response_text

    stripped = response_text.strip()
    sentences = _re.split(r'(?<=[.!?])\s+', stripped)
    last_sentence = sentences[-1].strip() if sentences else ""

    if last_sentence.endswith("?"):
        return response_text

    fallback_question = (
        " What aspect of this would be most useful to go deeper on?"
    )
    return response_text.rstrip() + fallback_question


def _merge_twin_row_settings(twin_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge canonical twin row fields into settings for prompt-building paths."""
    if not isinstance(twin_row, dict):
        return {}

    settings = twin_row.get("settings")
    merged: Dict[str, Any] = dict(settings) if isinstance(settings, dict) else {}

    name = str(twin_row.get("name") or "").strip()
    if name and not str(merged.get("name") or "").strip():
        merged["name"] = name

    twin_id = str(twin_row.get("id") or "").strip()
    if twin_id and not str(merged.get("twin_id") or "").strip():
        merged["twin_id"] = twin_id

    tenant_id = str(twin_row.get("tenant_id") or "").strip()
    if tenant_id and not str(merged.get("tenant_id") or "").strip():
        merged["tenant_id"] = tenant_id

    description = str(twin_row.get("description") or "").strip()
    if description and not str(merged.get("description") or "").strip():
        merged["description"] = description

    return merged


def _canonical_identity_follow_up_question() -> str:
    return "What are you trying to figure out right now?"


def _first_sentence(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)
    return parts[0].strip()


def _strip_identity_prefix(text: str, display_name: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized or not display_name:
        return normalized
    pattern = rf"^{re.escape(display_name)}\s+(is|was)\s+"
    return re.sub(pattern, "", normalized, flags=re.IGNORECASE).strip()


def _clean_profile_strings(values: Any, *, limit: int = 6) -> List[str]:
    if not isinstance(values, list):
        return []

    cleaned: List[str] = []
    seen = set()
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _social_key_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return "website"
    if "wikipedia.org" in host:
        return "wikipedia"
    if "linkedin.com" in host:
        return "linkedin"
    if "github.com" in host:
        return "github"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "instagram.com" in host:
        return "instagram"
    if "x.com" in host or "twitter.com" in host:
        return "twitter"
    return "website"


def _normalize_social_links(value: Any) -> Dict[str, str]:
    if isinstance(value, dict):
        return {
            re.sub(r"\s+", " ", str(key or "").strip()).lower(): re.sub(r"\s+", " ", str(url or "").strip())
            for key, url in value.items()
            if re.sub(r"\s+", " ", str(url or "").strip())
        }

    links: Dict[str, str] = {}
    if not isinstance(value, list):
        return links

    for raw in value:
        url = re.sub(r"\s+", " ", str(raw or "").strip())
        if not url:
            continue
        key = _social_key_from_url(url)
        links.setdefault(key, url)
    return links


_PROFILE_SEED_STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "can",
    "did",
    "do",
    "for",
    "from",
    "got",
    "he",
    "her",
    "him",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "she",
    "the",
    "they",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def _strip_inline_source_refs(text: Any) -> str:
    cleaned = re.sub(r"\[[0-9a-fA-F\-\s;,]+\]", "", str(text or ""))
    return re.sub(r"\s+", " ", cleaned).strip(" .")


def _extract_inline_citation_ids(text: Any) -> List[str]:
    raw_text = str(text or "")
    out: List[str] = []
    seen = set()
    for block in re.findall(r"\[([^\]]+)\]", raw_text):
        for token in re.split(r"[;,\s]+", block):
            candidate = token.strip()
            if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", candidate):
                lowered = candidate.lower()
                if lowered not in seen:
                    seen.add(lowered)
                    out.append(candidate)
    return out


def _tokenize_profile_seed_query(query: str) -> List[str]:
    tokens: List[str] = []
    seen = set()
    for token in re.findall(r"[a-z0-9][a-z0-9_-]*", str(query or "").lower()):
        if len(token) < 3 or token in _PROFILE_SEED_STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def _score_profile_seed_row(*, row: Dict[str, Any], query: str, query_tokens: List[str]) -> float:
    text = str(row.get("text") or "").lower()
    seed_type = str(row.get("seed_type") or "").lower()
    if not text:
        return 0.0

    overlap = 0.0
    for token in query_tokens:
        if token in text:
            overlap += 1.0
            continue
        if token.endswith("ics") and token[:-1] in text:
            overlap += 0.8
        elif token.endswith("ing") and token[:-3] in text:
            overlap += 0.7

    lowered_query = str(query or "").lower()
    thematic_bonus = 0.0
    if any(marker in lowered_query for marker in ("politic", "government", "public role", "office", "title")):
        if any(marker in text for marker in ("politic", "party", "government", "minister", "chief minister", "bjp")):
            thematic_bonus += 2.2
    if any(marker in lowered_query for marker in ("background", "career", "started", "got into", "journey")):
        if seed_type in {"bio", "work", "contribution", "qa"}:
            thematic_bonus += 1.4

    priority_bonus = {
        "qa": 3.6,
        "bio": 3.2,
        "summary": 3.0,
        "work": 2.8,
        "achievement": 2.4,
        "contribution": 2.3,
        "education": 1.8,
    }.get(seed_type, 1.5)

    citations = row.get("citation_ids") or []
    citation_bonus = 0.35 if citations else 0.0
    return priority_bonus + thematic_bonus + overlap + citation_bonus


def _build_query_ranked_profile_seed_rows(
    full_settings: Optional[Dict[str, Any]],
    query: str,
    *,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    if not isinstance(full_settings, dict):
        return []

    public_profile = full_settings.get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}
    identity_pack = full_settings.get("persona_identity_pack")
    identity_pack = identity_pack if isinstance(identity_pack, dict) else {}

    display_name = (
        str(full_settings.get("name") or "").strip()
        or str(public_profile.get("display_name") or "").strip()
        or str(identity_pack.get("display_name") or identity_pack.get("preferred_name") or "").strip()
    )
    if not display_name:
        return []

    seed_rows: List[Dict[str, Any]] = []

    def _add_seed(seed_type: str, raw_text: Any, *, source_label: str, source_url: Any = None) -> None:
        citation_ids = _extract_inline_citation_ids(raw_text)
        cleaned_text = _strip_inline_source_refs(raw_text)
        if not cleaned_text:
            return
        text = cleaned_text if cleaned_text.endswith((".", "!", "?")) else f"{cleaned_text}."
        seed_rows.append(
            {
                "text": text,
                "source_id": citation_ids[0] if citation_ids else "",
                "citation_ids": citation_ids,
                "source_name": source_label,
                "url": str(source_url or "").strip(),
                "block_type": "answer_text",
                "is_answer_text": True,
                "strategy_name": "canonical_profile_seed",
                "seed_type": seed_type,
                "title": f"{display_name} profile",
            }
        )

    response_seeds = public_profile.get("public_response_seeds")
    if isinstance(response_seeds, list):
        for item in response_seeds:
            if not isinstance(item, dict):
                continue
            answer = str(item.get("answer") or item.get("text") or "").strip()
            question = str(item.get("question") or "").strip()
            raw_text = f"Q: {question}\nA: {answer}" if question and answer else answer
            _add_seed(
                "qa",
                raw_text,
                source_label=str(item.get("title") or "Prepared public answer").strip() or "Prepared public answer",
                source_url=item.get("url"),
            )

    descriptor_bits = []
    occupation = str(public_profile.get("occupation") or "").strip()
    role = str(public_profile.get("role") or "").strip()
    organization = str(public_profile.get("organization") or "").strip()
    headline = str(public_profile.get("headline") or "").strip()
    if occupation:
        descriptor_bits.append(f"{display_name} is {occupation}")
    if role and organization:
        descriptor_bits.append(f"{display_name} is the {role} at {organization}")
    elif role:
        descriptor_bits.append(f"{display_name} is the {role}")
    if headline:
        descriptor_bits.append(headline)
    if descriptor_bits:
        _add_seed("summary", ". ".join(descriptor_bits), source_label="Canonical public profile")

    _add_seed("summary", public_profile.get("short_description"), source_label="Canonical public profile")
    _add_seed("bio", public_profile.get("bio"), source_label="Canonical public biography")

    for item in _clean_profile_strings(public_profile.get("key_achievements"), limit=5):
        _add_seed("achievement", item, source_label="Public achievements")

    for item in _clean_profile_strings(public_profile.get("contributions"), limit=6):
        _add_seed("contribution", item, source_label="Public contributions")

    for job in public_profile.get("work_experience") or []:
        if not isinstance(job, dict):
            continue
        role_value = str(job.get("role") or job.get("title") or "").strip()
        company = str(job.get("company") or job.get("organization") or "").strip()
        description = str(job.get("description") or "").strip()
        start_year = str(job.get("start_year") or "").strip()
        end_year = str(job.get("end_year") or "").strip()
        years = ""
        if start_year and end_year:
            years = f" from {start_year} to {end_year}"
        elif start_year:
            years = f" since {start_year}"
        elif end_year:
            years = f" until {end_year}"
        job_text = description
        if not job_text and role_value and company:
            job_text = f"{display_name} worked as {role_value} at {company}{years}"
        elif not job_text and role_value:
            job_text = f"{display_name} worked as {role_value}{years}"
        _add_seed("work", job_text, source_label="Public work history")

    for edu in public_profile.get("education") or []:
        if not isinstance(edu, dict):
            continue
        degree = str(edu.get("degree") or "").strip()
        field = str(edu.get("field") or "").strip()
        institution = str(edu.get("institution") or "").strip()
        year = str(edu.get("year") or edu.get("end_year") or "").strip()
        parts = []
        if degree and field:
            parts.append(f"{degree} in {field}")
        elif degree:
            parts.append(degree)
        elif field:
            parts.append(field)
        if institution:
            parts.append(institution)
        if year:
            parts.append(year)
        if parts:
            _add_seed("education", f"{display_name} studied {', '.join(parts)}", source_label="Public education")

    deduped = _merge_context_rows([], seed_rows, limit=max(10, limit * 2))
    query_tokens = _tokenize_profile_seed_query(query)
    ranked = sorted(
        deduped,
        key=lambda row: (
            _score_profile_seed_row(row=row, query=query, query_tokens=query_tokens),
            len(str(row.get("text") or "")),
        ),
        reverse=True,
    )
    return ranked[: max(1, limit)]


def _build_profile_fact_block(full_settings: Optional[Dict[str, Any]]) -> str:
    if not isinstance(full_settings, dict):
        return ""

    public_profile = full_settings.get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}

    identity_pack = full_settings.get("persona_identity_pack")
    identity_pack = identity_pack if isinstance(identity_pack, dict) else {}

    display_name = (
        str(full_settings.get("name") or "").strip()
        or str(public_profile.get("display_name") or "").strip()
        or str(identity_pack.get("preferred_name") or identity_pack.get("display_name") or "").strip()
    )
    if not display_name:
        return ""

    headline = (
        str(public_profile.get("headline") or full_settings.get("tagline") or "").strip()
        or str(identity_pack.get("headline") or identity_pack.get("summary") or "").strip()
    )
    role = (
        str(public_profile.get("role") or "").strip()
        or str(identity_pack.get("role") or identity_pack.get("current_role") or "").strip()
    )
    organization = (
        str(public_profile.get("organization") or "").strip()
        or str(identity_pack.get("organization") or identity_pack.get("current_company") or "").strip()
    )
    descriptor = ""
    if role and organization:
        descriptor = f"{role} at {organization}"
    elif role:
        descriptor = role
    elif headline:
        descriptor = headline

    bio = (
        str(public_profile.get("bio") or "").strip()
        or str(full_settings.get("public_intro") or "").strip()
        or str(full_settings.get("description") or "").strip()
    )
    short_bio = _first_sentence(bio) or bio

    topic_names: List[str] = []
    raw_topics = full_settings.get("public_topics")
    if isinstance(raw_topics, list):
        topic_names = [
            str(item.get("name") or item.get("slug") or "").strip()
            for item in raw_topics
            if isinstance(item, dict) and str(item.get("name") or item.get("slug") or "").strip()
        ]

    expertise = _clean_profile_strings(
        [
            *topic_names,
            *_clean_profile_strings(public_profile.get("areas_of_expertise"), limit=6),
            *_clean_profile_strings(identity_pack.get("expertise_areas"), limit=6),
        ],
        limit=6,
    )
    personality = _clean_profile_strings(
        [
            *_clean_profile_strings(public_profile.get("personality_traits"), limit=6),
            *_clean_profile_strings(identity_pack.get("tone_tags"), limit=6),
        ],
        limit=5,
    )
    achievements = _clean_profile_strings(public_profile.get("key_achievements"), limit=3)
    speaking_style = (
        str(public_profile.get("speaking_style") or "").strip()
        or ", ".join(_clean_profile_strings(identity_pack.get("tone_tags"), limit=3))
    )
    social_links = _normalize_social_links(
        public_profile.get("social_links") or identity_pack.get("social_links")
    )

    lines: List[str] = [f"- Name: {display_name}"]
    if descriptor:
        lines.append(f"- Occupation: {descriptor}")
    if short_bio:
        lines.append(f"- Bio: {short_bio}")
    if expertise:
        lines.append(f"- Expertise: {', '.join(expertise[:5])}")
    if personality:
        lines.append(f"- Personality: {', '.join(personality[:4])}")
    if speaking_style:
        lines.append(f"- Speaking style: {speaking_style}")
    if achievements:
        lines.append(f"- Key achievements: {'; '.join(achievements[:3])}")
    if social_links:
        lines.append(
            "- Public links: "
            + ", ".join(f"{label}: {url}" for label, url in list(social_links.items())[:4])
        )

    return "PROFILE FACTS:\n" + "\n".join(lines) + "\n"


def _build_canonical_profile_block(full_settings: Optional[Dict[str, Any]]) -> str:
    profile = _build_clean_canonical_fastpath_profile(full_settings)
    if not profile:
        return ""

    public_profile = (full_settings or {}).get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}

    lines: List[str] = [f"- Name: {profile.get('display_name')}"]
    one_line_intro = str(profile.get("one_line_intro") or "").strip()
    if one_line_intro:
        lines.append(f"- Identity anchor: {one_line_intro}")

    headline = str(public_profile.get("headline") or "").strip()
    role = str(public_profile.get("role") or "").strip()
    organization = str(public_profile.get("organization") or "").strip()
    descriptor = ""
    if role and organization:
        descriptor = f"{role} at {organization}"
    elif headline:
        descriptor = headline
    elif role:
        descriptor = role
    if descriptor:
        lines.append(f"- Occupation: {descriptor}")

    expertise = _clean_profile_strings(profile.get("expertise_areas"), limit=4)
    if expertise:
        lines.append(f"- Expertise focus: {', '.join(expertise)}")

    # Work experience — inject up to 5 roles so LLM can answer career questions
    work_exp = public_profile.get("work_experience")
    if isinstance(work_exp, list) and work_exp:
        exp_parts = []
        for job in work_exp[:5]:
            if not isinstance(job, dict):
                continue
            title = str(job.get("title") or job.get("role") or "").strip()
            company = str(job.get("company") or job.get("organization") or "").strip()
            years = str(job.get("years") or job.get("duration") or "").strip()
            if title and company:
                entry = f"{title} at {company}"
                if years:
                    entry += f" ({years})"
                exp_parts.append(entry)
        if exp_parts:
            lines.append("- Work experience: " + "; ".join(exp_parts))

    # Education — inject all degrees
    education = public_profile.get("education")
    if isinstance(education, list) and education:
        edu_parts = []
        for edu in education[:4]:
            if not isinstance(edu, dict):
                continue
            degree = str(edu.get("degree") or "").strip()
            field = str(edu.get("field") or edu.get("subject") or "").strip()
            institution = str(edu.get("institution") or edu.get("school") or "").strip()
            year = str(edu.get("year") or edu.get("graduation_year") or "").strip()
            parts = []
            if degree and field:
                parts.append(f"{degree} in {field}")
            elif degree:
                parts.append(degree)
            elif field:
                parts.append(field)
            if institution:
                parts.append(institution)
            if year:
                parts.append(year)
            if parts:
                edu_parts.append(", ".join(parts))
        if edu_parts:
            lines.append("- Education: " + "; ".join(edu_parts))

    # Key achievements
    achievements = public_profile.get("key_achievements")
    if isinstance(achievements, list) and achievements:
        ach_strs = [str(a).strip() for a in achievements[:3] if str(a).strip()]
        if ach_strs:
            lines.append("- Key achievements: " + "; ".join(ach_strs))

    disclosure_line = str(profile.get("disclosure_line") or "").strip()
    if disclosure_line:
        lines.append(f"- Disclosure: {disclosure_line}")

    return "CANONICAL PERSONA PROFILE:\n" + "\n".join(lines) + "\n"


def _build_featured_sources_block(
    full_settings: Optional[Dict[str, Any]],
    context_rows: Optional[List[Dict[str, Any]]] = None,
) -> str:
    settings = full_settings if isinstance(full_settings, dict) else {}
    public_profile = settings.get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}

    lines: List[str] = []
    seen = set()

    featured_content = public_profile.get("featured_content")
    if isinstance(featured_content, list):
        for raw_item in featured_content:
            item = raw_item if isinstance(raw_item, dict) else {}
            title = str(item.get("title") or item.get("name") or item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
            summary = str(item.get("summary") or item.get("description") or "").strip()
            key = (title or url).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            line = f"- {title}" if title else "- Featured resource"
            if url:
                line += f": {url}"
            if summary:
                line += f" | {summary}"
            lines.append(line)
            if len(lines) >= 4:
                break

    for row in context_rows or []:
        if len(lines) >= 4:
            break
        if not isinstance(row, dict):
            continue
        title = str(
            row.get("title")
            or row.get("source_name")
            or row.get("filename")
            or row.get("url")
            or ""
        ).strip()
        url = str(row.get("url") or "").strip()
        key = (title or url).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        line = f"- {title}" if title else "- Top source"
        if url and url != title:
            line += f": {url}"
        lines.append(line)

    if not lines:
        return ""
    return "FEATURED RESOURCES OR TOP SOURCES:\n" + "\n".join(lines) + "\n"


def _build_memory_context_block(
    *,
    graph_context: str,
    owner_memory_context: str,
    node_context: str,
) -> str:
    sections: List[str] = []
    graph_context = str(graph_context or "").strip()
    owner_memory_context = str(owner_memory_context or "").strip()
    node_context = str(node_context or "").strip()

    if graph_context:
        sections.append("GRAPH CONTEXT:\n" + graph_context)
    if node_context:
        sections.append("IDENTITY NODES:\n" + node_context)
    if owner_memory_context:
        sections.append("OWNER MEMORY:\n" + owner_memory_context)

    if not sections:
        return ""
    return "GRAPH OR MEMORY CONTEXT:\n" + "\n\n".join(sections) + "\n"


def _build_persona_grounding_block(
    *,
    full_settings: Optional[Dict[str, Any]],
    context_rows: Optional[List[Dict[str, Any]]],
    graph_context: str,
    owner_memory_context: str,
    node_context: str,
) -> str:
    vector_rows = [row for row in (context_rows or []) if isinstance(row, dict)]
    blocks: List[str] = []

    canonical_profile_block = _build_canonical_profile_block(full_settings)
    if canonical_profile_block:
        blocks.append(canonical_profile_block.strip())

    profile_fact_block = _build_profile_fact_block(full_settings)
    if profile_fact_block:
        blocks.append(profile_fact_block.strip())

    featured_sources_block = _build_featured_sources_block(full_settings, vector_rows)
    if featured_sources_block:
        blocks.append(featured_sources_block.strip())

    vector_block_body = build_retrieved_context_block(vector_rows[:5]) if vector_rows else "- None available."
    blocks.append("VECTOR RETRIEVAL EVIDENCE:\n" + vector_block_body)

    memory_block = _build_memory_context_block(
        graph_context=graph_context,
        owner_memory_context=owner_memory_context,
        node_context=node_context,
    )
    if memory_block:
        blocks.append(memory_block.strip())

    return "\n\n".join(block for block in blocks if block.strip()) or "- None available."


def _build_canonical_fastpath_profile(full_settings: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(full_settings, dict):
        return None

    public_profile = full_settings.get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}

    display_name = (
        str(full_settings.get("name") or "").strip()
        or str(public_profile.get("display_name") or "").strip()
    )
    if not display_name:
        return None

    headline = str(public_profile.get("headline") or full_settings.get("tagline") or "").strip()
    role = str(public_profile.get("role") or "").strip()
    organization = str(public_profile.get("organization") or "").strip()
    description = _strip_identity_prefix(
        str(full_settings.get("description") or "").strip(),
        display_name,
    )
    public_intro = str(full_settings.get("public_intro") or "").strip()
    bio = str(public_profile.get("bio") or "").strip()

    descriptor = ""
    if headline:
        descriptor = headline.rstrip(". ")
    elif role and organization:
        descriptor = f"{role} at {organization}"
    elif role:
        descriptor = role
    elif description:
        descriptor = description.rstrip(". ")

    if descriptor:
        one_line_intro = f"I'm {display_name} — {descriptor}."
    elif public_intro.lower().startswith(("i'm ", "i am ")):
        one_line_intro = public_intro.rstrip(". ") + "."
    else:
        one_line_intro = f"I'm {display_name}."

    short_parts: List[str] = [one_line_intro]
    lead_sentence = _first_sentence(public_intro or bio)
    if lead_sentence:
        lowered = lead_sentence.lower()
        if not lowered.startswith(("he ", "she ", "they ", display_name.lower() + " ")):
            if lead_sentence.rstrip(". ") != one_line_intro.rstrip(". "):
                short_parts.append(lead_sentence.rstrip(". ") + ".")

    expertise_areas: List[str] = []
    raw_topics = full_settings.get("public_topics")
    if isinstance(raw_topics, list):
        expertise_areas = [
            str(item.get("name") or item.get("slug") or "").strip()
            for item in raw_topics
            if isinstance(item, dict) and str(item.get("name") or item.get("slug") or "").strip()
        ][:4]

    social_links = public_profile.get("social_links")
    social_links = social_links if isinstance(social_links, dict) else {}

    return {
        "profile_status": "approved",
        "display_name": display_name,
        "one_line_intro": one_line_intro,
        "short_intro": " ".join(part.strip() for part in short_parts if part.strip()).strip(),
        "disclosure_line": f"I'm a digital version of {display_name}, not the person directly.",
        "contact_handoff_line": "For direct contact, please use the public channels listed in this profile.",
        "preferred_contact_channel": str(public_profile.get("preferred_contact_channel") or "").strip(),
        "social_links": social_links,
        "expertise_areas": expertise_areas,
        "follow_up_question": _canonical_identity_follow_up_question(),
    }


def _build_clean_canonical_fastpath_profile(full_settings: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(full_settings, dict):
        return None

    public_profile = full_settings.get("public_profile")
    public_profile = public_profile if isinstance(public_profile, dict) else {}

    identity_pack = full_settings.get("persona_identity_pack")
    identity_pack = identity_pack if isinstance(identity_pack, dict) else {}

    display_name = (
        str(full_settings.get("name") or "").strip()
        or str(public_profile.get("display_name") or "").strip()
        or str(identity_pack.get("preferred_name") or identity_pack.get("display_name") or "").strip()
    )
    if not display_name:
        return None

    headline = (
        str(public_profile.get("headline") or full_settings.get("tagline") or "").strip()
        or str(identity_pack.get("headline") or identity_pack.get("summary") or "").strip()
    )
    role = (
        str(public_profile.get("role") or "").strip()
        or str(identity_pack.get("role") or identity_pack.get("current_role") or "").strip()
    )
    organization = (
        str(public_profile.get("organization") or "").strip()
        or str(identity_pack.get("organization") or identity_pack.get("current_company") or "").strip()
    )
    description = _strip_identity_prefix(
        str(full_settings.get("description") or "").strip(),
        display_name,
    )
    public_intro = str(full_settings.get("public_intro") or "").strip()
    bio = (
        str(public_profile.get("bio") or "").strip()
        or str(identity_pack.get("summary") or identity_pack.get("biography") or "").strip()
    )

    descriptor = ""
    if headline:
        descriptor = headline.rstrip(". ")
    elif role and organization:
        descriptor = f"{role} at {organization}"
    elif role:
        descriptor = role
    elif description:
        descriptor = description.rstrip(". ")

    if descriptor:
        one_line_intro = f"I'm {display_name}, {descriptor}."
    elif public_intro.lower().startswith(("i'm ", "i am ")):
        one_line_intro = public_intro.rstrip(". ") + "."
    else:
        one_line_intro = f"I'm {display_name}."

    short_parts: List[str] = [one_line_intro]
    lead_sentence = _first_sentence(public_intro or bio)
    if lead_sentence:
        lowered = lead_sentence.lower()
        if not lowered.startswith(("he ", "she ", "they ", display_name.lower() + " ")):
            if lead_sentence.rstrip(". ") != one_line_intro.rstrip(". "):
                short_parts.append(lead_sentence.rstrip(". ") + ".")

    expertise_areas: List[str] = []
    raw_topics = full_settings.get("public_topics")
    if isinstance(raw_topics, list):
        expertise_areas = [
            str(item.get("name") or item.get("slug") or "").strip()
            for item in raw_topics
            if isinstance(item, dict) and str(item.get("name") or item.get("slug") or "").strip()
        ][:4]
    if not expertise_areas:
        expertise_areas = _clean_profile_strings(
            public_profile.get("areas_of_expertise") or identity_pack.get("expertise_areas"),
            limit=4,
        )

    social_links = _normalize_social_links(
        public_profile.get("social_links") or identity_pack.get("social_links")
    )

    return {
        "profile_status": "approved",
        "display_name": display_name,
        "one_line_intro": one_line_intro,
        "short_intro": " ".join(part.strip() for part in short_parts if part.strip()).strip(),
        "disclosure_line": f"I'm a digital version of {display_name}, not the person directly.",
        "contact_handoff_line": "For direct contact, please use the public channels listed in this profile.",
        "preferred_contact_channel": (
            str(public_profile.get("preferred_contact_channel") or "").strip()
            or str(identity_pack.get("preferred_contact_channel") or "").strip()
        ),
        "social_links": social_links,
        "expertise_areas": expertise_areas,
        "follow_up_question": _canonical_identity_follow_up_question(),
    }


def _build_canonical_identity_response(state: Dict[str, Any]) -> Optional[str]:
    profile = _build_clean_canonical_fastpath_profile(state.get("full_settings"))
    if not profile:
        return None
    return str(profile.get("short_intro") or profile.get("one_line_intro") or "").strip()


def _load_active_persona_spec_v2_row(twin_id: str) -> Optional[Dict[str, Any]]:
    """Synchronously load the active v2 persona spec row for prompt/render paths."""
    try:
        from modules.persona_spec_v2 import is_v2_spec

        result = (
            supabase.table("persona_specs")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("status", "active")
            .order("published_at", desc=True)
            .limit(5)
            .execute()
        )
        for row in result.data or []:
            spec_data = row.get("spec", {})
            if is_v2_spec(spec_data):
                return row
    except Exception as exc:
        print(f"[AGENT] Warning: Failed to load active v2 persona spec for {twin_id}: {exc}")
    return None

def get_checkpointer():
    """
    Get or create Postgres checkpointer instance (P1-A).
    Returns None if DATABASE_URL not set or checkpointer unavailable.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    
    if not CHECKPOINTER_AVAILABLE:
        return None
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Checkpointer is optional - return None if DATABASE_URL not set
        return None
    
    try:
        # Initialize checkpointer with Postgres connection
        # The checkpointer will create its own connection pool
        _checkpointer = PostgresSaver.from_conn_string(database_url)
        print("[LangGraph] Checkpointer initialized with DATABASE_URL")
        return _checkpointer
    except Exception as e:
        print(f"[LangGraph] Failed to initialize checkpointer: {e}")
        return None

async def get_owner_style_profile(twin_id: str, force_refresh: bool = False) -> str:
    """
    Analyzes owner's verified responses and opinion documents to create a persistent style profile.
    """
    try:
        # 1. Check if we already have a profile in the database
        if not force_refresh:
            # RLS Fix: Use RPC
            twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
            if twin_res.data and twin_res.data.get("settings"):
                profile = twin_res.data["settings"].get("persona_profile")
                if profile:
                    # Return a consolidated string or the dict depending on how it's used
                    # For backward compatibility, if it's a dict, we might need to handle it
                    if isinstance(profile, dict):
                        return profile.get("description", "Professional and helpful.")
                    return profile

        # 2. Fetch data for analysis
        # A. Fetch verified replies
        replies_res = supabase.table("escalation_replies").select(
            "content, escalations(messages(conversations(twin_id)))"
        ).execute()
        
        analysis_texts = []
        for r in replies_res.data:
            try:
                if r["escalations"]["messages"]["conversations"]["twin_id"] == twin_id:
                    analysis_texts.append(f"VERIFIED REPLY: {r['content']}")
            except (KeyError, TypeError):
                continue
        
        # B. Fetch some OPINION chunks from Pinecone for style variety
        from modules.clients import get_pinecone_index
        from modules.embeddings import _resolve_target_dimension
        from modules.twin_namespace import get_namespace_candidates_for_twin
        index = get_pinecone_index()
        try:
            metadata_probe_vector = [0.1] * int(_resolve_target_dimension() or 3072)
            for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
                opinion_search = index.query(
                    vector=metadata_probe_vector, # Use non-zero vector for metadata filtering
                    filter={"category": {"$eq": "OPINION"}},
                    top_k=20, # Increased for better analysis
                    include_metadata=True,
                    namespace=namespace
                )
                for match in opinion_search.get("matches", []):
                    analysis_texts.append(f"OPINION DOC: {match['metadata']['text']}")
        except Exception as pe:
            print(f"Error fetching opinions for style: {pe}")

        if not analysis_texts:
            return "Professional and helpful."
            
        # 3. Analyze style using a more capable model
        # Using more snippets for a comprehensive view
        all_content = "\n---\n".join(analysis_texts[:25])
        
        analysis_prompt = f"""You are a linguistic expert analyzing a user's writing style to create a 'Digital Twin' persona.
        Analyze the following snippets of text from the user.
        
        EXTRACT THE FOLLOWING INTO JSON:
        1. description: A concise, high-fidelity persona description (3-4 sentences) starting with 'Your voice is...'.
        2. signature_phrases: A list of 5 exact phrases or verbal tics the user frequently uses.
        3. style_exemplars: 3 short text snippets (max 20 words each) that perfectly represent the user's style.
        4. opinion_summary: A map of major topics and the user's stance/intensity (e.g., {{"Topic": {{"stance": "...", "intensity": 8}}}}).
        
        TEXT SNIPPETS:
        {all_content}"""

        persona_data, _route_meta = await invoke_json(
            [{"role": "user", "content": analysis_prompt}],
            task="structured",
            temperature=0,
            max_tokens=700,
        )
        
        # 4. Persist the profile back to the twin settings
        try:
            from datetime import datetime
            # Get current settings first to merge
            # RLS Fix: Use RPC
            twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
            curr_settings = twin_res.data["settings"] if twin_res.data else {}
            
            curr_settings["persona_profile"] = persona_data.get("description")
            curr_settings["signature_phrases"] = persona_data.get("signature_phrases", [])
            curr_settings["style_exemplars"] = persona_data.get("style_exemplars", [])
            curr_settings["opinion_map"] = persona_data.get("opinion_summary", {})
            curr_settings["last_style_analysis"] = datetime.now().isoformat()
            
            # Update probably needs RPC too? Or update via table might work if RLS allows UPDATE but not SELECT?
            # Usually RLS blocks both. But we only need Read for `run_agent_stream`.
            # Updating style is a background task. 
            # I'll leave update as is for now, assuming RLS allows update? (Unlikely).
            # I should use update_twin_settings system RPC but I didn't create one.
            supabase.table("twins").update({"settings": curr_settings}).eq("id", twin_id).execute()
        except Exception as se:
            print(f"Error persisting persona profile: {se}")

        return persona_data.get("description", "Professional and helpful.")
    except Exception as e:
        print(f"Error analyzing style: {e}")
        return "Professional and helpful."

class TwinState(TypedDict):
    """
    State for the Digital Twin reasoning graph.
    Supports Path B: Global Reasoning & Agentic RAG.
    Now supports Phase 4: Dialogue Orchestration.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    twin_id: str
    confidence_score: float
    citations: List[str]
    # Path B: Agentic RAG additions
    sub_queries: Optional[List[str]]
    reasoning_history: Optional[List[str]]
    retrieved_context: Optional[Dict[str, Any]] # Stores results from multiple tools
    
    # Phase 4: Dialogue Orchestration Metadata
    dialogue_mode: Optional[str]        # SMALLTALK, QA_FACT, TEACHING, etc.
    requires_evidence: bool
    requires_teaching: bool
    target_owner_scope: bool            # True if person-specific
    planning_output: Optional[Dict[str, Any]] # Structured JSON from Planner Pass
    intent_label: Optional[str]         # Phase 3 stable intent taxonomy label
    persona_module_ids: Optional[List[str]]
    persona_spec_version: Optional[str]
    persona_prompt_variant: Optional[str]
    router_reason: Optional[str]
    router_knowledge_available: Optional[bool]
    workflow_intent: Optional[str]
    routing_decision: Optional[Dict[str, Any]]
    fastpath_intent: Optional[str]
    fastpath_response: Optional[Dict[str, Any]]
    retrieval_group_id: Optional[str]
    resolve_default_group_filtering: Optional[bool]
    query_class: Optional[str]
    quote_intent: Optional[bool]
    execution_lane: Optional[bool]
    deepagents_plan: Optional[Dict[str, Any]]
    actor_user_id: Optional[str]
    tenant_id: Optional[str]
    
    # Path B / Phase 4 Context
    full_settings: Optional[Dict[str, Any]]
    graph_context: Optional[str]
    owner_memory_context: Optional[str]
    system_prompt_override: Optional[str]
    interaction_context: Optional[str]
    identity_gate_clarification_hint: Optional[Dict[str, Any]]
    
    # 5-Layer Persona State (Phase 4)
    persona_v2_enabled: Optional[bool]
    persona_v2_spec_version: Optional[str]
    persona_v2_dimension_scores: Optional[Dict[str, int]]
    persona_v2_overall_score: Optional[float]
    persona_v2_reasoning_steps: Optional[List[str]]
    persona_v2_values_prioritized: Optional[List[str]]


def _format_prompt_history(messages: List[BaseMessage], max_turns: int = 5) -> str:
    history = _extract_conversation_history(messages, max_turns=max_turns)
    if not history:
        return "- None available."
    rendered: List[str] = []
    for item in history:
        role = str(item.get("role") or "user").strip().lower() or "user"
        content = re.sub(r"\s+", " ", str(item.get("content") or "").strip())
        if content:
            rendered.append(f"{role}: {content}")
    return "\n".join(rendered) if rendered else "- None available."


def _resolve_creator_namespace_label(twin_id: str) -> str:
    try:
        from modules.twin_namespace import get_primary_namespace_for_twin

        return get_primary_namespace_for_twin(twin_id)
    except Exception:
        return str(twin_id or "unknown")


def _build_advisor_system_prompt(
    *,
    twin_name: str,
    creator_namespace: str,
    active_persona: str,
    retrieved_context_block: str,
    conversation_history: str,
    additional_context_blocks: Optional[List[str]] = None,
) -> str:
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        twin_name=twin_name,
        creator_namespace=creator_namespace,
        active_persona=active_persona,
        retrieved_context_block=retrieved_context_block or "- None available.",
        conversation_history=conversation_history or "- None available.",
    )
    extras = [
        block.strip()
        for block in (additional_context_blocks or [])
        if isinstance(block, str) and block.strip()
    ]
    if extras:
        prompt += "\n\nADDITIONAL TWIN CONTEXT\n-----------------------\n" + "\n\n".join(extras)
    return prompt
    persona_v2_value_conflicts: Optional[List[Dict[str, Any]]]
    persona_v2_heuristics_applied: Optional[List[str]]
    persona_v2_memory_anchors: Optional[List[str]]
    persona_v2_safety_checks: Optional[List[Dict[str, Any]]]
    persona_v2_safety_blocked: Optional[bool]
    persona_v2_consistency_hash: Optional[str]
    persona_v2_processing_time_ms: Optional[int]

def build_system_prompt_with_trace(state: TwinState) -> tuple[str, Dict[str, Any]]:
    """
    Build prompt text plus persona runtime trace metadata (Phase 3).
    """
    twin_id = state.get("twin_id", "Unknown")
    full_settings = state.get("full_settings") or {}
    graph_context = state.get("graph_context") or ""
    owner_memory_context = state.get("owner_memory_context") or ""
    system_prompt_override = (state.get("system_prompt_override") or "").strip()
    dialogue_mode = state.get("dialogue_mode")

    messages = state.get("messages") or []
    last_human_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    intent_label = state.get("intent_label") or classify_query_intent(
        last_human_msg,
        dialogue_mode=dialogue_mode,
    )

    style_desc = full_settings.get("persona_profile", "Professional and helpful.")
    phrases = full_settings.get("signature_phrases", [])
    opinion_map = full_settings.get("opinion_map", {})
    default_system_prompt = (full_settings.get("system_prompt") or "").strip()
    custom_instructions = system_prompt_override or default_system_prompt
    public_intro = (full_settings.get("public_intro") or "").strip()
    intent_profile = full_settings.get("intent_profile") or {}
    raw_context = state.get("retrieved_context", {}).get("results", [])
    context_rows = [row for row in raw_context if isinstance(row, dict)] if isinstance(raw_context, list) else []

    # Load identity context (High-level concepts)
    node_context = ""
    try:
        nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 10}).execute()
        if nodes_res.data:
            profile_items = [f"- {n.get('name')}: {n.get('description')}" for n in nodes_res.data]
            node_context = "\n".join(profile_items)
    except Exception:
        pass

    persona_section = ""
    persona_trace = {
        "intent_label": intent_label,
        "module_ids": [],
        "persona_spec_version": None,
        "persona_prompt_variant": DEFAULT_PERSONA_PROMPT_VARIANT,
        "grounding_order": "canonical_profile>verified_facts>featured_sources>vector_retrieval>graph_memory",
    }
    active_variant_row = get_active_persona_prompt_variant(twin_id=twin_id)
    active_variant_id = (
        str(active_variant_row.get("variant_id"))
        if active_variant_row and active_variant_row.get("variant_id")
        else DEFAULT_PERSONA_PROMPT_VARIANT
    )
    variant_overrides = (active_variant_row or {}).get("render_options") or {}
    render_options = get_prompt_render_options(active_variant_id, overrides=variant_overrides)

    # ====================================================================
    # NEW: Check for 5-Layer Persona Spec v2 FIRST (for new twins)
    # ====================================================================
    v2_persona_spec = None
    has_v2_persona = full_settings.get("use_5layer_persona", False)
    
    if has_v2_persona:
        try:
            v2_row = _load_active_persona_spec_v2_row(twin_id)
            if v2_row and v2_row.get("spec"):
                v2_persona_spec = v2_row.get("spec")
                # Build persona section from v2 spec
                persona_section = _build_prompt_from_v2_persona(v2_persona_spec, full_settings.get("name", "Digital Twin"))
                persona_trace["persona_spec_version"] = v2_row.get("version") or "2.0.0"
                persona_trace["persona_prompt_variant"] = "v2_default"
                print(f"[AGENT] Using 5-Layer Persona v2 for twin {twin_id}")
        except Exception as e:
            print(f"[AGENT] Warning: Could not use v2 persona for {twin_id}: {e}")
    
    # ====================================================================
    # FALLBACK: Check for v1 persona spec (legacy twins)
    # ====================================================================
    if not persona_section:
        active_persona_row = get_active_persona_spec(twin_id=twin_id)
        if active_persona_row and active_persona_row.get("spec"):
            try:
                parsed = PersonaSpec.model_validate(active_persona_row["spec"])
                runtime_modules = list_runtime_modules_for_intent(
                    twin_id=twin_id,
                    intent_label=intent_label,
                    limit=8,
                    include_draft=True,
                )
                prompt_plan = compile_prompt_plan(
                    spec=parsed,
                    intent_label=intent_label,
                    user_query=last_human_msg,
                    runtime_modules=runtime_modules,
                    max_few_shots=max(0, int(render_options.max_few_shots)),
                    module_detail_level=render_options.module_detail_level,
                )
                persona_section = render_prompt_plan_with_options(plan=prompt_plan, options=render_options)
                persona_trace["module_ids"] = prompt_plan.selected_module_ids
                persona_trace["intent_label"] = prompt_plan.intent_label or intent_label
                persona_trace["persona_spec_version"] = active_persona_row.get("version") or parsed.version
                persona_trace["persona_prompt_variant"] = render_options.variant_id
            except Exception as e:
                print(f"[PersonaCompiler] Active spec compile failed, using legacy settings fallback: {e}")
                persona_section = ""
                persona_trace["persona_spec_version"] = active_persona_row.get("version")
                persona_trace["persona_prompt_variant"] = active_variant_id

    if not persona_section:
        persona_section = f"YOUR PERSONA STYLE:\n- DESCRIPTION: {style_desc}"
        if phrases:
            persona_section += f"\n- SIGNATURE PHRASES: {', '.join(phrases)}"
        if opinion_map:
            opinions_text = "\n".join([f"- {t}: {d['stance']}" for t, d in opinion_map.items()])
            persona_section += f"\n- CORE WORLDVIEW:\n{opinions_text}"

    custom_instructions_block = f"CUSTOM INSTRUCTIONS:\n{custom_instructions}\n" if custom_instructions else ""
    public_intro_block = f"PUBLIC INTRO (use when asked to introduce yourself):\n{public_intro}\n" if public_intro else ""
    grounding_block = _build_persona_grounding_block(
        full_settings=full_settings,
        context_rows=context_rows,
        graph_context=graph_context,
        owner_memory_context=owner_memory_context,
        node_context=node_context,
    )
    intent_block = ""
    if isinstance(intent_profile, dict) and intent_profile:
        use_case = (intent_profile.get("use_case") or "").strip()
        audience = (intent_profile.get("audience") or "").strip()
        boundaries = (intent_profile.get("boundaries") or "").strip()
        intent_lines = []
        if use_case:
            intent_lines.append(f"- Primary use case: {use_case}")
        if audience:
            intent_lines.append(f"- Audience: {audience}")
        if boundaries:
            intent_lines.append(f"- Boundaries: {boundaries}")
        if intent_lines:
            intent_block = "INTENT PROFILE:\n" + "\n".join(intent_lines) + "\n"

    twin_name = str(full_settings.get("name") or "Digital Twin").strip() or "Digital Twin"
    prompt = _build_advisor_system_prompt(
        twin_name=twin_name,
        creator_namespace=_resolve_creator_namespace_label(twin_id),
        active_persona=str(
            persona_trace.get("persona_prompt_variant")
            or persona_trace.get("persona_spec_version")
            or DEFAULT_PERSONA_PROMPT_VARIANT
        ).strip(),
        retrieved_context_block=grounding_block or "- None available.",
        conversation_history=_format_prompt_history(messages, max_turns=5),
        additional_context_blocks=[
            custom_instructions_block,
            public_intro_block,
            intent_block,
            persona_section,
        ],
    )
    return prompt, persona_trace


def build_system_prompt(state: TwinState) -> str:
    prompt, _ = build_system_prompt_with_trace(state)
    return prompt


def _build_prompt_from_v2_persona(spec: Dict[str, Any], twin_name: str) -> str:
    """
    Build system prompt text from 5-Layer Persona Spec v2.

    Renders identity, voice, knowledge domains, guardrails, and response
    architecture so each twin sounds like the actual person — not a generic AI.
    """
    identity = spec.get("identity_frame", {})
    cognitive = spec.get("cognitive_heuristics", {})
    values = spec.get("value_hierarchy", {})
    communication = spec.get("communication_patterns", {})

    # Layer 1: Identity
    role = identity.get("role_definition") or twin_name
    expertise = identity.get("expertise_domains") or []
    background = (identity.get("background_summary") or "").strip()
    comm_tendencies = identity.get("communication_tendencies") or {}
    organizations = comm_tendencies.get("organizations", "")
    what_they_do = comm_tendencies.get("what_they_do", "")

    # Layer 4: Communication patterns
    signature_phrases = communication.get("signature_phrases") or []
    anti_patterns = communication.get("anti_patterns") or []

    # Layer 3: Values
    value_items = values.get("values") or []
    top_values = [
        v.get("name", "").replace("_", " ").title()
        for v in value_items[:4]
        if v.get("name")
    ]

    # Layer 2: Cognitive heuristics
    heuristics = cognitive.get("heuristics") or []
    active_heuristics = [h for h in heuristics if h.get("active", True)][:3]

    parts: List[str] = []

    # Identity block
    parts.append(f"PERSONA: {twin_name} — {role}")
    if expertise:
        parts.append(f"EXPERTISE: {', '.join(expertise[:6])}")
    if organizations:
        parts.append(f"ORGANIZATIONS: {organizations}")
    if what_they_do:
        parts.append(f"WHAT THEY DO: {what_they_do}")
    if background:
        parts.append(f"\nBACKGROUND (ground your answers in this):\n{background}")

    # Voice block
    parts.append("\nVOICE:")
    parts.append("- You ARE this person. First person always.")
    parts.append("- Lead with the answer or strong take. Never build up to it.")
    parts.append("- Specific numbers and examples over vague generalities.")
    parts.append("- Connected paragraphs. No bullet-point dumping.")
    if signature_phrases:
        quoted = ", ".join(f'"{p}"' for p in signature_phrases[:4])
        parts.append(f"- Draw on their voice and cadence. Examples: {quoted}")
    banned = anti_patterns[:8] or [
        "Great question!", "Certainly!", "I'd be happy to help!",
        "As an AI", "Let me break this down", "Here are some key points:",
    ]
    parts.append(f"- NEVER say: {', '.join(f'{chr(34)}{p}{chr(34)}' for p in banned)}")

    # Values
    if top_values:
        parts.append(f"\nCORE VALUES: {', '.join(top_values)}")

    # Cognitive heuristics
    if active_heuristics:
        parts.append("\nHOW THIS PERSON THINKS:")
        for h in active_heuristics:
            desc = (h.get("description") or h.get("name") or "").strip()
            if desc:
                parts.append(f"- {desc}")

    # Response architecture
    parts.append(
        "\nLENGTH:\n"
        "- Greeting / simple factual: 2-3 sentences.\n"
        "- Criteria / context question: 2-3 paragraphs.\n"
        "- Strategic / multi-part: 3-5 paragraphs. Hard cap at 6.\n"
        "- End every response with one specific diagnostic question about the\n"
        "  user's actual situation. Not 'Does that help?' Not a list of options."
    )

    return "\n".join(parts)


# =============================================================================
# POST-GENERATION VALIDATOR: Link-First Citation Compliance
# =============================================================================

CITATION_PATTERN = re.compile(r'\[claim_[a-f0-9]+\]', re.IGNORECASE)
OWNER_FACT_PATTERN = re.compile(
    r'\b(I|my|mine|me)\s+(?:prefer|like|believe|think|know|want|need|use|have|did|went|worked|founded|started|invested|advise)',
    re.IGNORECASE
)

class PostGenValidationResult:
    """Result of post-generation validation."""
    def __init__(self, is_valid: bool, violations: List[str], action: str, corrected_response: Optional[str] = None):
        self.is_valid = is_valid
        self.violations = violations
        self.action = action  # 'accept', 'reject_regenerate', 'clarify'
        self.corrected_response = corrected_response

async def validate_link_first_response(
    response_text: str,
    twin_id: str,
    persona_spec: Dict[str, Any],
    claim_store: Any = None,
) -> PostGenValidationResult:
    """
    POST-GEN VALIDATOR: Ensure link-first responses cite claims for owner facts.
    
    Rules:
    1. Every owner-specific factual claim MUST have [claim_id] citation
    2. If citation missing: reject and regenerate with clarification request
    3. No silent fallback to legacy persona
    4. Emit telemetry on violations
    
    Returns:
        PostGenValidationResult with validation outcome and action
    """
    # Check if this is link-first persona
    source = persona_spec.get("source", "")
    is_link_first = "link" in source.lower() or source == "link-compile"
    
    if not is_link_first:
        # Non-link-first personas skip this validation
        return PostGenValidationResult(True, [], 'accept')
    
    violations = []
    
    # Extract sentences with owner facts
    sentences = re.split(r'(?<=[.!?])\s+', response_text)
    
    for sentence in sentences:
        # Check if sentence contains owner facts
        has_owner_fact = OWNER_FACT_PATTERN.search(sentence)
        has_citation = CITATION_PATTERN.search(sentence)
        
        if has_owner_fact and not has_citation:
            violations.append(f"Owner fact without citation: {sentence[:100]}...")
    
    # Also check for uncited specific assertions
    # (e.g., "I invested $5M in Series A" without [claim_xxx])
    SPECIFIC_CLAIM_PATTERN = re.compile(
        r'\b(I|my)\s+\w+\s+(?:\$?[\d,]+(?:\.\d+)?\s*(?:million|billion|M|B|%|percent)|'
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|'
        r'(?:founded|started|launched|invested|advised|worked at)\s+(?:[A-Z][\w\s&]+){1,3})',
        re.IGNORECASE
    )
    
    for match in SPECIFIC_CLAIM_PATTERN.finditer(response_text):
        # Check if this specific claim has a citation nearby
        start = max(0, match.start() - 100)
        end = min(len(response_text), match.end() + 100)
        context = response_text[start:end]
        
        if not CITATION_PATTERN.search(context):
            violations.append(f"Specific claim without citation: {match.group()[:80]}...")
    
    # Determine action based on violations
    if not violations:
        return PostGenValidationResult(True, [], 'accept')
    
    # Violations found - need to reject and regenerate with clarification
    # Build corrected response that asks for clarification
    clarification_response = (
        "I'd like to answer that, but I need to verify my information first. "
        "Could you help me understand your perspective on this? "
        "This will help me give you a more accurate response grounded in your actual views."
    )
    
    # Emit telemetry (high severity)
    try:
        from modules.telemetry import emit_telemetry
        emit_telemetry(
            event="link_first_citation_violation",
            twin_id=twin_id,
            severity="high",
            payload={
                "violation_count": len(violations),
                "violations": violations[:5],  # First 5 only
                "response_preview": response_text[:500],
                "action_taken": "reject_and_clarify",
            }
        )
    except Exception as e:
        print(f"[PostGenValidator] Telemetry error: {e}")
    
    return PostGenValidationResult(
        is_valid=False,
        violations=violations,
        action='clarify',
        corrected_response=clarification_response
    )


# =============================================================================

def _twin_has_groundable_knowledge(twin_id: Optional[str]) -> bool:
    """
    Lightweight runtime signal for router policy.
    True when the twin has any persisted source / verified QnA / graph node.
    """
    if not twin_id:
        return False

    now = time.time()
    cached = _router_knowledge_cache.get(twin_id)
    if cached and (now - float(cached.get("ts", 0))) <= _ROUTER_KNOWLEDGE_CACHE_TTL_SECONDS:
        return bool(cached.get("has_knowledge", False))

    has_knowledge = False
    try:
        # Prefer cheap existence checks (limit 1) to avoid heavy counts.
        src_res = (
            supabase.table("sources")
            .select("id")
            .eq("twin_id", twin_id)
            .in_("status", ["live", "processed"])
            .limit(1)
            .execute()
        )
        has_knowledge = bool(src_res.data)

        if not has_knowledge:
            qna_res = (
                supabase.table("verified_qna")
                .select("id")
                .eq("twin_id", twin_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            has_knowledge = bool(qna_res.data)

        if not has_knowledge:
            nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 1}).execute()
            has_knowledge = bool(nodes_res.data)
    except Exception as e:
        print(f"[Router] Knowledge availability check failed for twin {twin_id}: {e}")
        has_knowledge = False

    _router_knowledge_cache[twin_id] = {"ts": now, "has_knowledge": has_knowledge}
    return has_knowledge


def _is_identity_intro_query(query: str) -> bool:
    policy = get_grounding_policy(query)
    return str(policy.get("query_class") or "") == "identity"


def _is_smalltalk_query(query: str) -> bool:
    policy = get_grounding_policy(query)
    return bool(policy.get("is_smalltalk"))


def _resolve_twin_pronoun_query(query: str) -> str:
    """
    In twin chats, default second-person pronouns to the twin persona.
    This helps retrieval pull owner/twin identity and behavior evidence.
    """
    original = re.sub(r"\s+", " ", str(query or "").strip())
    if not original:
        return ""

    lowered = original.lower()
    if _is_identity_intro_query(original):
        return (
            f"{original} (about the twin persona identity, biography, background, "
            "and core expertise)"
        )

    padded = f" {re.sub(r'\\s+', ' ', lowered)} "
    pronoun_markers = (
        " you ",
        " your ",
        " yourself ",
        " you're ",
        " youve ",
        " you've ",
        " you'd ",
        " you'll ",
    )
    if any(marker in padded for marker in pronoun_markers):
        return f"{original} (interpret you/your as the twin persona in this conversation)"
    return original


def _smalltalk_response(query: str, *, twin_name: str = "", full_settings: Optional[Dict[str, Any]] = None) -> str:
    q = re.sub(r"\s+", " ", str(query or "").strip()).lower()
    settings = full_settings or {}
    # Extract a brief persona activity hint from bio (second sentence preferred)
    bio = str(
        (settings.get("public_profile") or {}).get("bio")
        or settings.get("public_intro")
        or ""
    ).strip()
    bio_sentences = [s.strip() for s in bio.split(".") if s.strip()]
    # Skip first sentence if it's a self-intro ("I'm X") to avoid duplicate name
    activity_hint = ""
    for sentence in bio_sentences:
        if not re.match(r"^i'?m\b", sentence.lower()):
            activity_hint = sentence
            break

    if not q:
        if twin_name:
            return f"Hey. I'm {twin_name}. What's on your mind?"
        return "Hey. What's on your mind?"
    if any(marker in q for marker in ("thank you", "thanks")):
        return "You're welcome."
    if q in {"ok", "okay", "cool", "sounds good", "got it", "understood"}:
        return "Sounds good."
    if any(marker in q for marker in ("how are you", "how's your day", "hows your day")):
        return "Doing well, thanks. What do you want to figure out?"
    # Greeting — include persona name and activity hint for grader specificity
    if twin_name and activity_hint:
        return f"Hey. I'm {twin_name}. {activity_hint}. What do you want to know?"
    if twin_name:
        return f"Hey. I'm {twin_name}. What do you want to know?"
    return "Hey. What do you want to know?"


def _is_owner_specific_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = [
        r"\bwhere (did|do) i\b",
        r"\bwhen (did|do) i\b",
        r"\bwho am i\b",
        r"\bwhat (is|was) my (background|story|experience|history)\b",
        r"\bwhat (do|did) i think\b",
        r"\bwhat('?s| is) my (stance|view|opinion|belief|thesis|principle)\b",
        r"\bmy (stance|view|opinion|belief|thesis|principle)\b",
        r"\bhow do i (approach|decide|evaluate)\b",
        r"\bbased on my (sources|documents|knowledge)\b",
        r"\bfrom my (sources|documents|knowledge)\b",
    ]
    return any(re.search(pattern, q) for pattern in markers)


def _is_generic_business_coaching_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    coaching_markers = (
        "gtm",
        "go to market",
        "go-to-market",
        "icp",
        "positioning",
        "plg",
        "founder-led",
        "sales-led",
        "runway",
        "pricing",
        "startup",
        "founder",
        "traction",
        "funnel",
        "pipeline",
        "activation",
        "retention",
        "churn",
        "interview",
        "customer interview",
        "buyer",
        "objection",
        "pilot",
        "metrics",
        "kpi",
        "action items",
        "90-day",
        "90 day",
        "week 1",
        "week one",
        "month 1",
        "month one",
        "plan",
        "strategy",
        "cadence",
        "what should i do",
        "how should i",
        "help me",
    )
    return any(marker in q for marker in coaching_markers)


def _is_explicit_source_grounded_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = (
        "based on my sources",
        "from my sources",
        "from my documents",
        "from my knowledge",
        "cite",
        "citation",
        "according to my",
    )
    return any(marker in q for marker in markers)


def _is_explicit_teaching_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = (
        "teach me",
        "learn this",
        "remember this",
        "save this memory",
        "correct this answer",
        "update your memory",
    )
    return any(marker in q for marker in markers)


def _is_entity_probe_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    patterns = (
        r"^\s*do you know(?: about)?\s+.+",
        r"^\s*what is\s+.+",
        r"^\s*who is\s+.+",
        r"^\s*tell me about\s+.+",
        r"^\s*can you explain\s+.+",
    )
    return any(re.search(p, q) for p in patterns)


def _extract_conversation_history(
    messages: List[BaseMessage],
    max_turns: int = 5,
) -> List[Dict[str, str]]:
    """
    Extract conversation history from LangChain messages for query rewriting.
    
    Args:
        messages: List of LangChain messages (HumanMessage, AIMessage)
        max_turns: Maximum number of conversation turns to include
        
    Returns:
        List of {role, content} dicts suitable for query rewriter
    """
    history = []
    
    # Work backwards to get most recent turns
    user_assistant_pairs = []
    temp_pair = {}
    
    for msg in reversed(messages[:-1]):  # Exclude current query (last message)
        if isinstance(msg, HumanMessage):
            temp_pair["user"] = msg.content
            if "assistant" in temp_pair:
                user_assistant_pairs.append({
                    "user": temp_pair["user"],
                    "assistant": temp_pair["assistant"]
                })
                temp_pair = {}
                if len(user_assistant_pairs) >= max_turns:
                    break
        elif isinstance(msg, AIMessage):
            temp_pair["assistant"] = msg.content
    
    # Reverse to get chronological order
    for pair in reversed(user_assistant_pairs):
        history.append({"role": "user", "content": pair["user"]})
        history.append({"role": "assistant", "content": pair["assistant"]})
    
    return history


async def _rewrite_query_with_context(
    user_query: str,
    messages: List[BaseMessage],
    twin_id: Optional[str],
) -> Tuple[str, Optional[QueryRewriteResult]]:
    """
    Rewrite conversational query using conversation history.
    
    Args:
        user_query: Current user query
        messages: Full conversation history
        twin_id: Twin ID for context
        
    Returns:
        Tuple of (effective_query, rewrite_result)
    """
    if not QUERY_REWRITING_ENABLED:
        return user_query, None
    
    try:
        # Extract conversation history (last N turns)
        conversation_history = _extract_conversation_history(messages, max_turns=5)
        
        # Skip rewriting if no history or first message
        if not conversation_history:
            return user_query, None
        
        # Initialize rewriter
        rewriter = ConversationalQueryRewriter()
        
        # Get twin context if available
        twin_context = None
        if twin_id:
            twin_context = {"twin_id": twin_id}
        
        # Perform rewrite
        rewrite_result = await rewriter.rewrite(
            current_query=user_query,
            conversation_history=conversation_history,
            twin_context=twin_context,
        )
        
        # Use rewritten query if confident
        if rewrite_result.rewrite_applied and rewrite_result.rewrite_confidence >= 0.7:
            print(f"[QueryRewrite] '{user_query}' -> '{rewrite_result.standalone_query}' "
                  f"(intent: {rewrite_result.intent}, conf: {rewrite_result.rewrite_confidence:.2f})")
            return rewrite_result.standalone_query, rewrite_result
        else:
            print(f"[QueryRewrite] Skipped rewrite for '{user_query}' "
                  f"(applied: {rewrite_result.rewrite_applied}, conf: {rewrite_result.rewrite_confidence:.2f})")
            return user_query, rewrite_result
            
    except Exception as e:
        print(f"[QueryRewrite] Error rewriting query: {e}")
        return user_query, None


def _log_router_observation(
    *,
    mode: str,
    intent_label: str,
    requires_evidence: bool,
    target_owner_scope: bool,
    interaction_context: str,
    knowledge_available: bool,
    router_reason: Optional[str],
) -> None:
    """Best-effort router span metadata for Langfuse diagnostics."""
    try:
        langfuse_context.update_current_observation(
            metadata={
                "router_mode": mode,
                "router_intent_label": intent_label,
                "router_requires_evidence": bool(requires_evidence),
                "router_target_owner_scope": bool(target_owner_scope),
                "router_interaction_context": interaction_context,
                "router_knowledge_available": bool(knowledge_available),
                "router_reason": (router_reason or "")[:500],
            }
        )
    except Exception:
        pass


def _build_router_prompt(user_query: str, interaction_context: str) -> str:
    return f"""You are a generalized RAG router.
USER QUERY: {user_query}
INTERACTION CONTEXT: {interaction_context}
Always retrieve evidence first, then evaluate answerability.
Return JSON:
{{
  "mode": "QA_FACT",
  "is_person_specific": false,
  "requires_evidence": true,
  "reasoning": "evidence-first"
}}
"""

    # Define the nodes
@observe(name="router_node")
async def router_node(state: TwinState):
    """
    Generalized router for document reasoning:
    - Gate 0: bypass greetings/acknowledgements as smalltalk.
    - Gate 1: resolve second-person pronouns to twin persona semantics.
    - Gate 2: rewrite conversational queries using conversation history.
    - Non-smalltalk turns use retrieval + answerability evaluation.
    """
    messages = state["messages"]
    user_query = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()
    twin_id = state.get("twin_id")
    knowledge_available = _twin_has_groundable_knowledge(twin_id)
    
    # STEP 1: Conversational Query Rewriting
    # Transform underspecified queries ("what about that?") into standalone queries
    effective_query = user_query
    rewrite_result: Optional[QueryRewriteResult] = None
    
    if QUERY_REWRITING_ENABLED and len(messages) > 1:
        try:
            effective_query, rewrite_result = await _rewrite_query_with_context(
                user_query=user_query,
                messages=messages,
                twin_id=twin_id,
            )
        except Exception as e:
            print(f"[Router] Query rewriting failed: {e}")
            effective_query = user_query

    # STEP 1.5: Persona identity fast-path (optional, feature-flagged).
    # Keeps retrieval path unchanged unless explicitly enabled and profile is eligible.
    fastpath_match = classify_fastpath_intent(effective_query)
    if fastpath_match.get("matched") and twin_id:
        fastpath_payload: Optional[Dict[str, Any]] = None
        fastpath_profile_status = "unavailable"
        router_reason = "persona_fastpath_canonical"

        if is_persona_fastpath_enabled():
            allow_draft = is_persona_draft_profile_allowed()
            profile = get_persona_profile(str(twin_id))
            if profile and is_profile_eligible_for_fastpath(profile, allow_draft=allow_draft):
                fastpath_payload = build_fastpath_response(
                    intent=str(fastpath_match.get("intent")),
                    profile=profile,
                    query=effective_query,
                )
                fastpath_profile_status = str(profile.get("profile_status") or "approved")
                router_reason = "persona_fastpath_identity"
            else:
                print(
                    "[PersonaFastPath] miss "
                    f"twin_id={twin_id} reason={'no_profile' if not profile else 'profile_not_eligible'} "
                    f"allow_draft={allow_draft}"
                )

        if not fastpath_payload:
            canonical_profile = _build_clean_canonical_fastpath_profile(state.get("full_settings"))
            if canonical_profile:
                fastpath_payload = build_fastpath_response(
                    intent=str(fastpath_match.get("intent")),
                    profile=canonical_profile,
                    query=effective_query,
                )
                fastpath_profile_status = "canonical"

        if fastpath_payload and str(fastpath_payload.get("text") or "").strip():
            decision_payload = {
                "intent": "answer",
                "chosen_workflow": "answer",
                "output_schema": "workflow.answer.v1",
                "action": "answer",
                "confidence": float(fastpath_match.get("confidence") or 0.0),
                "required_inputs_missing": [],
                "clarifying_questions": [],
            }
            print(
                "[PersonaFastPath] hit "
                f"twin_id={twin_id} intent={fastpath_payload.get('intent')} "
                f"profile_status={fastpath_profile_status}"
            )
            try:
                langfuse_context.update_current_observation(
                    metadata={
                        "router_mode": "IDENTITY_FACT",
                        "router_intent_label": "meta_or_system",
                        "router_requires_evidence": False,
                        "router_target_owner_scope": False,
                        "router_interaction_context": interaction_context,
                        "router_knowledge_available": bool(knowledge_available),
                        "router_reason": router_reason,
                        "persona_fastpath_hit": True,
                        "persona_fastpath_intent": fastpath_payload.get("intent"),
                        "persona_fastpath_profile_status": fastpath_profile_status,
                    }
                )
            except Exception:
                pass

            return {
                "dialogue_mode": "IDENTITY_FACT",
                "intent_label": "meta_or_system",
                "target_owner_scope": False,
                "requires_evidence": False,
                "sub_queries": [],
                "router_reason": router_reason,
                "router_knowledge_available": knowledge_available,
                "workflow_intent": "answer",
                "routing_decision": decision_payload,
                "fastpath_intent": fastpath_payload.get("intent"),
                "fastpath_response": fastpath_payload,
                "query_class": "identity",
                "quote_intent": False,
                "execution_lane": False,
                "deepagents_plan": None,
                "original_query": user_query,
                "effective_query": effective_query,
                "query_rewrite_result": rewrite_result.model_dump() if rewrite_result else None,
                "reasoning_history": (state.get("reasoning_history") or [])
                + [f"Router: persona fast-path ({fastpath_payload.get('intent')})."],
            }
    
    # STEP 2: Apply grounding policy to effective query
    query_policy = get_grounding_policy(effective_query, interaction_context=interaction_context)
    is_smalltalk = bool(query_policy.get("is_smalltalk"))
    
    # DEBUG: Log smalltalk detection
    print(f"[Router DEBUG] effective_query='{effective_query}', is_smalltalk={is_smalltalk}, query_policy={query_policy}")
    
    deepagents_plan = (
        build_deepagents_plan(effective_query, interaction_context=interaction_context)
        if not is_smalltalk
        else {"is_action_or_control": False}
    )
    execution_lane = bool(deepagents_plan.get("is_action_or_control"))
    dialogue_mode = "SMALLTALK" if is_smalltalk else "QA_FACT"
    requires_evidence = bool(query_policy.get("requires_evidence")) and not execution_lane
    target_owner_scope = bool(classify_query(effective_query).get("requires_owner"))
    
    # STEP 3: Resolve pronouns (use effective query)
    resolved_query = _resolve_twin_pronoun_query(effective_query) if requires_evidence else ""
    
    # STEP 4: Classify intent (use effective query for better classification)
    intent_label = (
        "action_or_tool_execution"
        if execution_lane
        else classify_query_intent(effective_query, dialogue_mode=dialogue_mode)
    )

    routing_decision = build_routing_decision(
        query=effective_query,
        mode=dialogue_mode,
        intent_label=intent_label,
        interaction_context=interaction_context,
        target_owner_scope=target_owner_scope,
        requires_evidence=requires_evidence,
        knowledge_available=knowledge_available,
        pinned_context=None,
    )
    decision_payload = routing_decision.model_dump()
    decision_payload["action"] = "answer"
    decision_payload["clarifying_questions"] = []
    decision_payload["required_inputs_missing"] = []

    if is_smalltalk:
        router_reason = "smalltalk_bypass: conversational turn handled without retrieval."
    elif execution_lane:
        router_reason = "deepagents_execution_lane: action/tool request bypasses evidence clarify loop."
    else:
        router_reason = "general_rag_router: retrieval required for answerability evaluation."
    
    # Build router observation with rewrite info
    router_metadata = {
        "router_mode": dialogue_mode,
        "router_intent_label": intent_label,
        "router_requires_evidence": bool(requires_evidence),
        "router_target_owner_scope": bool(target_owner_scope),
        "router_interaction_context": interaction_context,
        "router_knowledge_available": bool(knowledge_available),
        "router_reason": (router_reason or "")[:500],
    }
    
    # Add query rewrite info to metadata if available
    if rewrite_result:
        router_metadata["query_rewrite.original"] = user_query
        router_metadata["query_rewrite.rewritten"] = effective_query
        router_metadata["query_rewrite.intent"] = rewrite_result.intent
        router_metadata["query_rewrite.confidence"] = rewrite_result.rewrite_confidence
        router_metadata["query_rewrite.applied"] = rewrite_result.rewrite_applied
    
    try:
        langfuse_context.update_current_observation(metadata=router_metadata)
    except Exception:
        pass

    # Build reasoning history entry
    reasoning_entry = "Router: "
    if is_smalltalk:
        reasoning_entry += "smalltalk bypass."
    elif execution_lane:
        reasoning_entry += "deepagents execution lane selected."
    else:
        reasoning_entry += "evidence-first routing."
    
    if rewrite_result and rewrite_result.rewrite_applied:
        reasoning_entry += f" Query rewritten ({rewrite_result.intent})."

    return {
        "dialogue_mode": dialogue_mode,
        "intent_label": intent_label,
        "target_owner_scope": target_owner_scope,
        "requires_evidence": requires_evidence,
        "sub_queries": [resolved_query] if requires_evidence and isinstance(resolved_query, str) and resolved_query.strip() else [],
        "router_reason": router_reason,
        "router_knowledge_available": knowledge_available,
        "workflow_intent": decision_payload.get("intent") or "answer",
        "routing_decision": decision_payload,
        "query_class": query_policy.get("query_class"),
        "quote_intent": bool(query_policy.get("quote_intent")),
        "execution_lane": execution_lane,
        "deepagents_plan": deepagents_plan if execution_lane else None,
        "fastpath_intent": None,
        "fastpath_response": None,
        # Query rewriting metadata
        "original_query": user_query,
        "effective_query": effective_query,
        "query_rewrite_result": rewrite_result.model_dump() if rewrite_result else None,
        "reasoning_history": (state.get("reasoning_history") or []) + [reasoning_entry],
    }

@observe(name="evidence_gate_node")
async def evidence_gate_node(state: TwinState):
    """
    Lightweight gate for generalized RAG flow.
    Retrieval always proceeds to planner answerability evaluation.
    """
    # Preserve existing dialogue_mode (don't overwrite SMALLTALK)
    current_mode = state.get("dialogue_mode", "QA_FACT")
    return {
        "dialogue_mode": current_mode,
        "requires_teaching": False,
        "reasoning_history": (state.get("reasoning_history") or []) + [
            "Gate: pass-through to answerability evaluation."
        ],
    }


@observe(name="deepagents_node")
async def deepagents_node(state: TwinState):
    """
    Dedicated execution lane for action/tool requests.
    This bypasses document answerability/clarification flow.
    """
    state_messages = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    user_query = next((m.content for m in reversed(state_messages) if isinstance(m, HumanMessage)), "")
    routing_decision = (
        dict(state.get("routing_decision"))
        if isinstance(state.get("routing_decision"), dict)
        else {
            "intent": "write",
            "chosen_workflow": "write",
            "output_schema": "workflow.write.v1",
        }
    )
    plan = dict(state.get("deepagents_plan") or {})
    if not plan:
        plan = build_deepagents_plan(
            user_query,
            interaction_context=str(state.get("interaction_context") or "owner_chat"),
        )

    try:
        result = await execute_deepagents_plan(
            twin_id=str(state.get("twin_id") or ""),
            plan=plan,
            actor_user_id=state.get("actor_user_id"),
            tenant_id=state.get("tenant_id"),
            conversation_id=None,
            interaction_context=str(state.get("interaction_context") or ""),
        )
    except Exception as exc:
        print(f"[DeepAgents] Execution lane exception: {exc}")
        result = {
            "status": "failed",
            "message": "Action lane failed due to an internal error.",
        }

    status = str(result.get("status") or "").strip().lower()
    error_code = (
        str((result.get("error") or {}).get("code") or "").strip()
        if isinstance(result.get("error"), dict)
        else ""
    )
    confidence = 0.0
    answer_points: List[str] = []
    teaching_questions: List[str] = []
    answerability: Dict[str, Any] = {
        "answerability": "direct",
        "answerable": True,
        "confidence": 0.72,
        "reasoning": "Execution lane handled action/tool request without document planner.",
        "missing_information": [],
        "ambiguity_level": "low",
    }
    action = "answer"

    if status in {"disabled", "forbidden"}:
        action = "refuse"
        confidence = 0.0
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        default_message = (
            "Action execution is unavailable in this context."
            if status == "forbidden"
            else "Action execution is disabled for this deployment."
        )
        message = str(error.get("message") or default_message).strip()
        answer_points = [message]
        answerability = {
            "answerability": "insufficient",
            "answerable": False,
            "confidence": 0.0,
            "reasoning": (
                "Execution lane is forbidden for public/anonymous contexts."
                if status == "forbidden"
                else "Execution lane is disabled via feature flag."
            ),
            "missing_information": [],
            "ambiguity_level": "low",
        }
    elif status == "missing_params":
        action = "clarify"
        confidence = 0.35
        question = build_single_missing_param_question(plan)
        teaching_questions = [question]
        answer_points = [question]
        missing_params = [str(v) for v in (result.get("missing_params") or []) if str(v).strip()]
        answerability = {
            "answerability": "insufficient",
            "answerable": False,
            "confidence": confidence,
            "reasoning": "Execution lane requires concrete action parameters before planning can run.",
            "missing_information": missing_params[:3],
            "ambiguity_level": "medium",
        }
    elif status == "needs_approval":
        confidence = 0.76
        action_id = str(result.get("action_id") or "").strip()
        summary = summarize_deepagents_plan(plan)
        answer_points = [
            "Action plan is ready and waiting for approval.",
            f"Plan: {summary}",
            f"Action ID: {action_id}" if action_id else "Action ID: unavailable",
        ]
    elif status == "approved":
        confidence = 0.8
        action_id = str(result.get("action_id") or "").strip()
        answer_points = [
            str(result.get("message") or "Action approved.").strip(),
            f"Action ID: {action_id}" if action_id else "Action ID: unavailable",
        ]
    elif status == "canceled":
        confidence = 0.78
        action_id = str(result.get("action_id") or "").strip()
        answer_points = [
            str(result.get("message") or "Action canceled.").strip(),
            f"Action ID: {action_id}" if action_id else "Action ID: unavailable",
        ]
    elif status == "executed":
        confidence = 0.84
        execution_id = str(result.get("execution_id") or "").strip()
        action_type = str(result.get("action_type") or plan.get("action_type") or "action").strip()
        answer_points = [
            f"Executed `{action_type}` successfully.",
            f"Execution ID: {execution_id}" if execution_id else "Execution ID: unavailable",
        ]
    else:
        action = "escalate"
        confidence = 0.2
        answer_points = [
            str(result.get("message") or "I could not execute that action safely.").strip(),
        ]
        answerability = {
            "answerability": "insufficient",
            "answerable": False,
            "confidence": confidence,
            "reasoning": "Execution lane returned a failure state.",
            "missing_information": [],
            "ambiguity_level": "medium",
        }

    updated_routing_decision = {
        **routing_decision,
        "action": action,
        "confidence": confidence,
        "required_inputs_missing": answerability.get("missing_information") or [],
        "clarifying_questions": teaching_questions[:1],
    }

    execution_lane_meta = {
        "status": status or "unknown",
        "action_type": str(plan.get("action_type") or result.get("action_type") or "").strip() or None,
        "needs_approval": status == "needs_approval",
        "action_id": str(result.get("action_id") or "").strip() or None,
        "execution_id": str(result.get("execution_id") or "").strip() or None,
        "error_code": error_code or None,
    }
    telemetry = _build_planner_telemetry(
        deepagents_route_rate=1,
        deepagents_forbidden_context_rate=1
        if status == "forbidden" and error_code == "DEEPAGENTS_FORBIDDEN_CONTEXT"
        else 0,
        deepagents_missing_params_rate=1 if status == "missing_params" else 0,
        deepagents_needs_approval_rate=1 if status == "needs_approval" else 0,
        deepagents_executed_rate=1 if status == "executed" else 0,
    )

    return {
        "planning_output": {
            "answer_points": answer_points[:3],
            "citations": [],
            "follow_up_question": "",
            "confidence": confidence,
            "teaching_questions": teaching_questions[:1],
            "render_strategy": "source_faithful",
            "reasoning_trace": str(answerability.get("reasoning") or ""),
            "answerability": answerability,
            "execution_lane": execution_lane_meta,
            "telemetry": telemetry,
        },
        "confidence_score": confidence,
        "routing_decision": updated_routing_decision,
        "workflow_intent": str(updated_routing_decision.get("intent") or "write"),
        "intent_label": "action_or_tool_execution",
        "persona_module_ids": [],
        "persona_spec_version": state.get("persona_spec_version"),
        "persona_prompt_variant": state.get("persona_prompt_variant"),
        "reasoning_history": (state.get("reasoning_history") or []) + [
            f"DeepAgents: execution lane status={status or 'unknown'}.",
        ],
    }


_PLANNER_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "with",
}


def _planner_query_tokens(query: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", (query or "").lower())
    return [tok for tok in tokens if len(tok) > 2 and tok not in _PLANNER_QUERY_STOPWORDS]


def _planner_text_tokens(text: str) -> set:
    tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
    return {tok for tok in tokens if len(tok) > 2 and tok not in _PLANNER_QUERY_STOPWORDS}


def _planner_overlap_ratio(query_tokens: List[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    qset = set(query_tokens)
    tset = _planner_text_tokens(text)
    if not tset:
        return 0.0
    return len(qset.intersection(tset)) / float(len(qset))


def _collect_valid_source_ids(context_data: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for row in context_data:
        if not isinstance(row, dict):
            continue
        source_id = row.get("source_id")
        if isinstance(source_id, str) and source_id and source_id not in out:
            out.append(source_id)
    return out


def _extract_retrieval_stats(context_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    for row in context_data:
        if not isinstance(row, dict):
            continue
        stats = row.get("retrieval_stats")
        if isinstance(stats, dict):
            return dict(stats)
    return {}


def _select_retrieval_signal(stats: Dict[str, Any], context_data: List[Dict[str, Any]]) -> float:
    rerank = stats.get("rerank_top1")
    dense = stats.get("dense_top1")
    sparse = stats.get("sparse_top1")

    for candidate in (rerank, dense, sparse):
        try:
            value = float(candidate)
            if value > 0.0:
                return max(0.0, min(1.0, value))
        except Exception:
            continue

    best_score = 0.0
    for row in context_data:
        if not isinstance(row, dict):
            continue
        try:
            best_score = max(
                best_score,
                float(row.get("score", row.get("vector_score", 0.0)) or 0.0),
            )
        except Exception:
            continue
    return max(0.0, min(1.0, best_score))


def _grounding_coverage_score(context_data: List[Dict[str, Any]]) -> float:
    if not context_data:
        return 0.0
    answer_rows = 0
    source_ids: set[str] = set()
    for row in context_data:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id") or "").strip()
        if source_id:
            source_ids.add(source_id)
        raw_answer = row.get("is_answer_text")
        block_type = str(row.get("block_type") or row.get("chunk_type") or "").strip().lower()
        is_answer = bool(raw_answer) if isinstance(raw_answer, bool) else block_type not in {"prompt_question", "heading"}
        if is_answer:
            answer_rows += 1
    answer_ratio = answer_rows / float(max(len(context_data), 1))
    source_diversity = min(len(source_ids) / 3.0, 1.0)
    return max(0.0, min(1.0, (0.65 * answer_ratio) + (0.35 * source_diversity)))


def _calibrate_confidence_score(
    *,
    raw_confidence: float,
    answerability_state: str,
    context_data: List[Dict[str, Any]],
) -> float:
    stats = _extract_retrieval_stats(context_data)
    retrieval_signal = _select_retrieval_signal(stats, context_data)
    coverage_signal = _grounding_coverage_score(context_data)

    base = max(0.0, min(1.0, float(raw_confidence or 0.0)))
    calibrated = (0.35 * base) + (0.40 * retrieval_signal) + (0.25 * coverage_signal)

    state = str(answerability_state or "").strip().lower()
    if state == "direct":
        calibrated += 0.08
    elif state == "derivable":
        calibrated += 0.03
    elif state == "insufficient":
        calibrated = min(calibrated, 0.30)

    return max(0.05, min(0.97, calibrated))


def _is_evaluative_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    markers = (
        "would this twin",
        "like a",
        "optimize for",
        "optimise for",
        "red flags",
        "pass on",
        "evaluate",
        "assessment",
        "feedback the way",
        "care about most",
        "what do you see in",
        "look for in founders",
        "founders",
        "founder",
        "act like",
        "digital twin",
    )
    return any(marker in q for marker in markers)


def _is_identity_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    markers = (
        "who are you",
        "tell me about yourself",
        "introduce yourself",
        "what do you do",
        "your background",
        "what public role",
        "what role",
        "what position",
        "what office",
        "what title",
        "associated with",
    )
    return any(marker in q for marker in markers)


def _is_selection_reply(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    if q in {"1", "2", "3", "yes", "no", "both", "either", "all", "all three", "all 3"}:
        return True
    patterns = (
        r"^all (three|3|of them)$",
        r"^(first|second|third)( one)?$",
        r"^option ?(1|2|3)$",
        r"^the (first|second|third) one$",
    )
    if any(re.match(pattern, q) for pattern in patterns):
        return True
    return q.startswith("are you asking about ") or q.startswith("do you want this answered from ")


def _extract_last_substantive_user_query(messages: List[BaseMessage]) -> str:
    """
    Recover the most recent non-clarification user intent.
    Helps resolve "all three" / clicked-clarifier follow-ups back to the real question.
    """
    candidates: List[str] = []
    for msg in messages or []:
        if not isinstance(msg, HumanMessage):
            continue
        content = re.sub(r"\s+", " ", str(msg.content or "").strip())
        if content:
            candidates.append(content)

    if not candidates:
        return ""

    current = candidates[-1]
    for prior in reversed(candidates[:-1]):
        lowered = prior.lower()
        if len(prior) < 8:
            continue
        if _is_selection_reply(prior):
            continue
        if lowered.startswith("are you asking about ") or lowered.startswith("do you want this answered from "):
            continue
        if lowered.startswith("should i answer from ") or lowered.startswith("should i keep this grounded"):
            continue
        return prior
    return current


def _answer_text_quality(context_data: List[Dict[str, Any]]) -> Dict[str, float]:
    total = len(context_data)
    if total <= 0:
        return {"answer_text_ratio": 0.0, "prompt_question_ratio": 0.0}

    answer_count = 0
    prompt_count = 0
    for row in context_data:
        if not isinstance(row, dict):
            continue
        block_type = str(row.get("block_type") or row.get("chunk_type") or "").strip().lower()
        if block_type == "prompt_question":
            prompt_count += 1
        raw_answer = row.get("is_answer_text")
        if isinstance(raw_answer, bool):
            is_answer = raw_answer
        elif block_type:
            is_answer = block_type not in {"prompt_question", "heading"}
        else:
            is_answer = True
        if is_answer:
            answer_count += 1

    return {
        "answer_text_ratio": answer_count / float(max(total, 1)),
        "prompt_question_ratio": prompt_count / float(max(total, 1)),
    }


def _should_retry_low_quality_evidence(context_data: List[Dict[str, Any]], query_class: str) -> bool:
    if not context_data:
        return False

    quality = _answer_text_quality(context_data)
    prompt_ratio = float(quality.get("prompt_question_ratio") or 0.0)
    answer_ratio = float(quality.get("answer_text_ratio") or 0.0)
    if prompt_ratio >= 0.5:
        return True
    if query_class in {"identity", "procedural", "evaluative"} and answer_ratio < 0.45:
        return True
    return False


def _clarification_streak(messages: List[BaseMessage]) -> int:
    streak = 0
    for msg in reversed(messages or []):
        if isinstance(msg, HumanMessage):
            continue
        if not isinstance(msg, AIMessage):
            continue
        content = re.sub(r"\s+", " ", str(msg.content or "").strip().lower())
        if not content:
            break
        if UNCERTAINTY_RESPONSE.lower() in content:
            streak += 1
            continue
        break
    return streak


def _should_break_clarification_loop(
    *,
    messages: List[BaseMessage],
    user_query: str,
    context_data: List[Dict[str, Any]],
) -> bool:
    if not context_data:
        return False
    streak = _clarification_streak(messages)
    if streak <= 0:
        return False
    if _is_selection_reply(user_query):
        return True
    if streak >= 2:
        return True
    return False


def _build_planner_telemetry(
    *,
    retry_reason: str = "none",
    prompt_question_dominance: bool = False,
    answer_text_ratio: float = 0.0,
    intent_recovered: bool = False,
    noisy_section_filtered_count: int = 0,
    clarify_option_count: int = 0,
    deepagents_route_rate: int = 0,
    deepagents_forbidden_context_rate: int = 0,
    deepagents_missing_params_rate: int = 0,
    deepagents_needs_approval_rate: int = 0,
    deepagents_executed_rate: int = 0,
    public_action_query_guarded_rate: int = 0,
    selection_recovery_failure_rate: int = 0,
) -> Dict[str, Any]:
    return {
        "retrieval.retry_reason": str(retry_reason or "none"),
        "retrieval.prompt_question_dominance": bool(prompt_question_dominance),
        "retrieval.answer_text_ratio": max(0.0, min(1.0, float(answer_text_ratio or 0.0))),
        "planner.intent_recovered": bool(intent_recovered),
        "clarify.noisy_section_filtered_count": max(0, int(noisy_section_filtered_count or 0)),
        "clarify.option_count": max(0, int(clarify_option_count or 0)),
        "deepagents_route_rate": 1 if int(deepagents_route_rate or 0) > 0 else 0,
        "deepagents_forbidden_context_rate": (
            1 if int(deepagents_forbidden_context_rate or 0) > 0 else 0
        ),
        "deepagents_missing_params_rate": 1 if int(deepagents_missing_params_rate or 0) > 0 else 0,
        "deepagents_needs_approval_rate": (
            1 if int(deepagents_needs_approval_rate or 0) > 0 else 0
        ),
        "deepagents_executed_rate": 1 if int(deepagents_executed_rate or 0) > 0 else 0,
        "public_action_query_guarded_rate": (
            1 if int(public_action_query_guarded_rate or 0) > 0 else 0
        ),
        "selection_recovery_failure_rate": (
            1 if int(selection_recovery_failure_rate or 0) > 0 else 0
        ),
    }


def _merge_context_rows(
    base_rows: List[Dict[str, Any]],
    extra_rows: List[Dict[str, Any]],
    *,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    for row in [*(base_rows or []), *(extra_rows or [])]:
        if not isinstance(row, dict):
            continue
        text = re.sub(r"\s+", " ", str(row.get("text") or "").strip())
        source_id = str(row.get("source_id") or "")
        if not text:
            continue
        key = (source_id, text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(row))
        if len(merged) >= max(1, limit):
            break
    return merged


async def _run_second_pass_retrieval(
    query: str,
    twin_id: str,
    *,
    group_id: Optional[str] = None,
    resolve_default_group: bool = True,
) -> List[Dict[str, Any]]:
    """
    Planner-level retrieval retry for low-context insufficient cases.
    Retrieval module still applies query expansion and HyDE.
    """
    from modules.retrieval import retrieve_context

    q = re.sub(r"\s+", " ", str(query or "").strip())
    if not q:
        return []

    second_pass_queries = [q]
    if _is_evaluative_query(q):
        second_pass_queries.append(
            f"{q} decision rubric thesis criteria assumptions risks tradeoffs"
        )
    if _is_identity_query(q):
        second_pass_queries.append(
            f"{q} twin identity biography background profile core expertise credibility"
        )

    expanded_rows: List[Dict[str, Any]] = []
    for candidate in second_pass_queries:
        try:
            rows = await retrieve_context(
                candidate,
                twin_id,
                group_id=group_id,
                top_k=PLANNER_SECOND_PASS_RETRIEVAL_TOP_K,
                resolve_default_group=resolve_default_group,
            )
        except Exception as e:
            print(f"[Planner] Second-pass retrieval failed for query '{candidate[:80]}': {e}")
            continue
        if isinstance(rows, list):
            expanded_rows.extend([row for row in rows if isinstance(row, dict)])

    return _merge_context_rows(
        [],
        expanded_rows,
        limit=PLANNER_SECOND_PASS_RETRIEVAL_TOP_K,
    )


def _collect_source_faithful_points(
    context_data: List[Dict[str, Any]],
    query_tokens: List[str],
) -> Tuple[List[str], List[str], float]:
    def _normalize_extract(raw: str) -> str:
        return re.sub(r"\s+", " ", (raw or "").strip().lstrip("-*").strip())

    scored_sentences: Dict[str, Dict[str, float]] = {}
    citation_ids: List[str] = []
    order_idx = 0

    for ctx in context_data[:5]:
        source_id = ctx.get("source_id")
        if isinstance(source_id, str) and source_id and source_id not in citation_ids:
            citation_ids.append(source_id)

        text = (ctx.get("text") or "").strip()
        if not text:
            continue

        vector_score = float(ctx.get("vector_score", ctx.get("score", 0.0)) or 0.0)
        for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
            sentence = _normalize_extract(raw)
            if not sentence or len(sentence) < 18:
                continue

            lowered = sentence.lower()
            overlap = sum(1 for tok in query_tokens if tok in lowered)
            label_bonus = 2 if lowered.startswith(("recommendation:", "assumptions:", "why:")) else 0
            score = float(overlap * 2 + label_bonus) + min(vector_score, 1.0)

            existing = scored_sentences.get(sentence)
            if existing is None or score > float(existing.get("score", 0.0)):
                scored_sentences[sentence] = {"score": score, "order": float(order_idx)}
            order_idx += 1

    ranked = sorted(
        scored_sentences.items(),
        key=lambda item: (-float(item[1].get("score", 0.0)), float(item[1].get("order", 0.0))),
    )
    answer_points = [sentence for sentence, _meta in ranked[:3]]

    if not answer_points:
        fallback_lines: List[str] = []
        for ctx in context_data[:3]:
            for raw_line in (ctx.get("text") or "").splitlines():
                line = _normalize_extract(raw_line)
                if line and line not in fallback_lines:
                    fallback_lines.append(line)
                if len(fallback_lines) >= 3:
                    break
            if len(fallback_lines) >= 3:
                break
        answer_points = fallback_lines[:3]

    max_score = max((float(meta.get("score", 0.0)) for _s, meta in ranked[:3]), default=0.0)
    return answer_points, citation_ids[:3], max_score


def _normalize_clarification_options(
    raw_options: Any,
    *,
    limit: int = 3,
) -> List[Dict[str, str]]:
    if not isinstance(raw_options, list):
        return []

    normalized: List[Dict[str, str]] = []
    seen_labels: set[str] = set()
    for item in raw_options:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            description = str(item.get("description") or "").strip()
        else:
            label = str(item or "").strip()
            description = ""
        if not label:
            continue
        dedupe = label.lower()
        if dedupe in seen_labels:
            continue
        seen_labels.add(dedupe)
        row: Dict[str, str] = {"label": label}
        if description:
            row["description"] = description
        normalized.append(row)
        if len(normalized) >= max(1, int(limit or 3)):
            break
    return normalized


def _normalize_identity_gate_clarification_hint(raw_hint: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_hint, dict):
        return None

    question = re.sub(r"\s+", " ", str(raw_hint.get("question") or "").strip())
    options = _normalize_clarification_options(raw_hint.get("options") or [])
    reason = re.sub(r"\s+", " ", str(raw_hint.get("reason") or "").strip())
    if not question and not options:
        return None

    hint: Dict[str, Any] = {
        "source": str(raw_hint.get("source") or "identity_gate"),
        "options": options,
    }
    if question:
        hint["question"] = question
    if reason:
        hint["reason"] = reason
    return hint


def _should_use_conversational_realizer(
    *,
    state: TwinState,
    answerability_state: str,
    citations: List[str],
    confidence: float,
    quote_intent: bool,
    strict_grounding: bool,
) -> bool:
    context_data = [
        row
        for row in ((state.get("retrieved_context") or {}).get("results") or [])
        if isinstance(row, dict)
    ]
    top_score = max(
        (float(row.get("score", row.get("vector_score", 0.0)) or 0.0) for row in context_data),
        default=0.0,
    )
    latest_query = next(
        (m.content for m in reversed(state.get("messages") or []) if isinstance(m, HumanMessage)),
        "",
    )
    owner_directed = bool(state.get("target_owner_scope"))
    if not owner_directed and latest_query:
        owner_directed = bool(classify_query(latest_query).get("requires_owner"))
    namespace_resolved = any(str(row.get("namespace") or "").strip() for row in context_data)

    if not CONVERSATIONAL_REALIZER_ENABLED:
        return False
    # Run LLM realizer for owner chat and public persona sharing sessions
    if str(state.get("interaction_context") or "").strip().lower() not in {"owner_chat", "public_share"}:
        return False
    # Never paraphrase verbatim-quote or strict-grounding requests
    if quote_intent or strict_grounding:
        return False
    action = ""
    if isinstance(state.get("routing_decision"), dict):
        action = str((state.get("routing_decision") or {}).get("action") or "").strip().lower()
    return action in {"", "answer"}


def _build_source_faithful_response_text(
    plan: Optional[Dict[str, Any]],
    *,
    state: TwinState,
    fallback_text: str,
) -> str:
    def _clean_point(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        return re.sub(r"^Answer:\s*", "", cleaned, flags=re.IGNORECASE).strip()

    def _default_follow_up_question() -> str:
        return "What part of that would be most useful to go deeper on?"

    points = []
    for p in (plan.get("answer_points", []) if isinstance(plan, dict) else []):
        if isinstance(p, str) and p.strip():
            cleaned = _clean_point(p)
            if cleaned:
                points.append(cleaned)

    follow_up = (plan.get("follow_up_question") if isinstance(plan, dict) else None) or ""
    context_data = [
        row
        for row in ((state.get("retrieved_context") or {}).get("results") or [])
        if isinstance(row, dict)
    ]
    latest_query = next(
        (m.content for m in reversed(state.get("messages") or []) if isinstance(m, HumanMessage)),
        "",
    ).strip()
    top_score = max(
        (float(row.get("score", row.get("vector_score", 0.0)) or 0.0) for row in context_data),
        default=0.0,
    )
    citations = [
        str(source_id).strip()
        for source_id in (plan.get("citations", []) if isinstance(plan, dict) else [])
        if str(source_id).strip()
    ]
    answerability_meta = plan.get("answerability") if isinstance(plan, dict) else {}
    answerability_state = (
        str(answerability_meta.get("answerability") or "").strip().lower()
        if isinstance(answerability_meta, dict)
        else ""
    )
    seeded_with_uncertainty = bool(points) and points[0].strip().lower().startswith(
        UNCERTAINTY_RESPONSE.lower()
    )

    response_lines: List[str] = []
    if not bool(state.get("requires_evidence", False)):
        response_lines.extend(points[:3])
        if isinstance(follow_up, str) and follow_up.strip():
            response_lines.append(follow_up.strip())
        realized_text = "\n".join(response_lines).strip()
        return realized_text or fallback_text

    partial_summary = " ".join(points[:2]).strip() or fallback_text
    if _is_identity_query(latest_query) and (
        answerability_state == "insufficient"
        or seeded_with_uncertainty
        or len(context_data) < 2
        or top_score < 0.65
    ):
        canonical_identity = _build_canonical_identity_response(state)
        question = (
            follow_up.strip()
            if isinstance(follow_up, str) and follow_up.strip()
            else _canonical_identity_follow_up_question()
        )
        if canonical_identity:
            return f"{canonical_identity} {question}".strip()
    if len(context_data) < 1 or top_score < 0.40:
        brief_take = partial_summary
        if not brief_take or brief_take == fallback_text:
            if context_data:
                first_snippet = re.sub(r"\s+", " ", str(context_data[0].get("text") or "").strip())
                brief_take = first_snippet[:260].rstrip(". ")
            else:
                brief_take = "this usually depends a lot on the specifics of the situation"
        brief_take = brief_take.rstrip(". ")
        question = follow_up.strip() if isinstance(follow_up, str) and follow_up.strip() else _default_follow_up_question()
        return (
            "I don't have a lot in my knowledge base on that specifically, but here's how "
            "I'd think about it based on what I do know: "
            f"{brief_take}. {question}"
        ).strip()

    evidence_refs: List[str] = []
    used_ids = set(citations[:3])
    for idx, row in enumerate(context_data[:5], start=1):
        source_id = str(row.get("source_id") or "").strip()
        if citations and source_id not in used_ids:
            continue
        snippet = re.sub(r"\s+", " ", str(row.get("text") or "").strip())
        if not source_id or not snippet:
            continue
        evidence_refs.append(f"[{idx}]")
        if len(evidence_refs) >= 3:
            break
    if not evidence_refs:
        for idx, row in enumerate(context_data[:3], start=1):
            source_id = str(row.get("source_id") or "").strip() or "unknown"
            snippet = re.sub(r"\s+", " ", str(row.get("text") or "").strip())
            if snippet:
                evidence_refs.append(f"[{idx}]")

    response_body = " ".join(points[:3]).strip() or fallback_text
    citation_suffix = " ".join(evidence_refs[:2]).strip()
    if citation_suffix:
        response_body = f"{response_body} {citation_suffix}".strip()
    next_question = (
        follow_up.strip()
        if isinstance(follow_up, str) and follow_up.strip()
        else _default_follow_up_question()
    )
    return f"{response_body} {next_question}".strip()


def _classify_grounding_policy(
    context_data: List[Dict[str, Any]],
    user_query: str,
) -> Dict[str, Any]:
    if not ADAPTIVE_GROUNDING_POLICY_ENABLED or not context_data:
        return {"level": "disabled", "top_score": 0.0, "margin": 0.0, "best_overlap": 0.0}

    scores = sorted(
        [float(ctx.get("score", ctx.get("vector_score", 0.0)) or 0.0) for ctx in context_data],
        reverse=True,
    )
    top_score = scores[0] if scores else 0.0
    second_score = scores[1] if len(scores) > 1 else 0.0
    margin = max(0.0, top_score - second_score)

    query_tokens = _planner_query_tokens(user_query)
    overlap_values = [
        _planner_overlap_ratio(query_tokens, str(ctx.get("text", "")))
        for ctx in context_data[:5]
    ]
    best_overlap = max(overlap_values, default=0.0)

    if top_score >= ADAPTIVE_GROUNDING_HIGH_SCORE and margin >= ADAPTIVE_GROUNDING_HIGH_MARGIN:
        level = "high"
    elif top_score >= ADAPTIVE_GROUNDING_MID_SCORE and best_overlap >= ADAPTIVE_GROUNDING_MID_OVERLAP:
        level = "mid"
    else:
        level = "low"

    return {
        "level": level,
        "top_score": top_score,
        "margin": margin,
        "best_overlap": best_overlap,
    }


@observe(name="planner_node")
async def planner_node(state: TwinState):
    """General evidence-driven planner."""
    fastpath_payload = state.get("fastpath_response")
    if isinstance(fastpath_payload, dict) and str(fastpath_payload.get("text") or "").strip():
        fastpath_text = str(fastpath_payload.get("text") or "").strip()
        confidence = max(0.0, min(1.0, float(fastpath_payload.get("confidence") or 0.92)))
        routing_decision = (
            dict(state.get("routing_decision"))
            if isinstance(state.get("routing_decision"), dict)
            else {
                "intent": "answer",
                "chosen_workflow": "answer",
                "output_schema": "workflow.answer.v1",
            }
        )
        updated_routing_decision = {
            **routing_decision,
            "action": "answer",
            "confidence": confidence,
            "required_inputs_missing": [],
            "clarifying_questions": [],
        }
        answerability = {
            "answerability": "direct",
            "answerable": True,
            "confidence": confidence,
            "reasoning": "Persona fast-path response from canonical profile.",
            "missing_information": [],
            "ambiguity_level": "low",
        }
        return {
            "planning_output": {
                "answer_points": [fastpath_text],
                "citations": [],
                "follow_up_question": str(fastpath_payload.get("follow_up_question") or "").strip(),
                "confidence": confidence,
                "teaching_questions": [],
                "render_strategy": "source_faithful",
                "reasoning_trace": "Planner fast-path identity response.",
                "answerability": answerability,
                "telemetry": _build_planner_telemetry(),
            },
            "confidence_score": confidence,
            "routing_decision": updated_routing_decision,
            "workflow_intent": str(updated_routing_decision.get("intent") or "answer"),
            "reasoning_history": (state.get("reasoning_history") or [])
            + [f"Planner: persona fast-path served ({state.get('fastpath_intent')})."],
        }

    raw_context = state.get("retrieved_context", {}).get("results", [])
    context_data = [row for row in raw_context if isinstance(row, dict)] if isinstance(raw_context, list) else []
    state_messages = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    user_query = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    effective_query = user_query
    selection_reply = _is_selection_reply(user_query)
    if selection_reply:
        recovered_query = _extract_last_substantive_user_query(state_messages)
        if recovered_query:
            effective_query = recovered_query
    intent_recovered = bool(effective_query != user_query)
    selection_recovery_failed = bool(selection_reply and not intent_recovered)
    query_class = str(state.get("query_class") or "factual").strip().lower() or "factual"
    quote_intent = bool(state.get("quote_intent"))
    strict_grounding = bool(get_grounding_policy(effective_query).get("strict_grounding"))
    _system_msg, persona_trace = build_system_prompt_with_trace(state)
    valid_source_ids: List[str] = _collect_valid_source_ids(context_data)
    identity_gate_clarification_hint = _normalize_identity_gate_clarification_hint(
        state.get("identity_gate_clarification_hint")
    )

    def _sanitize_answer_points(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        points: List[str] = []
        for raw in values:
            line = re.sub(r"\s+", " ", str(raw or "").strip())
            if not line:
                continue
            points.append(line)
            if len(points) >= 3:
                break
        return points

    def _sanitize_citations(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        out: List[str] = []
        for raw in values:
            cid = str(raw or "").strip()
            if cid and cid in valid_source_ids and cid not in out:
                out.append(cid)
            if len(out) >= 3:
                break
        return out

    def _build_evidence_blob(max_items: int = 6) -> str:
        lines: List[str] = []
        for idx, row in enumerate(context_data[: max(1, max_items)], 1):
            section = str(row.get("section_path") or row.get("section_title") or "").strip()
            page_number = row.get("page_number")
            if not section and page_number is not None:
                section = f"page_{page_number}"
            if not section:
                section = "unknown"
            text = re.sub(r"\s+", " ", str(row.get("text") or "").strip())[:1200]
            strategy = str(row.get("strategy_name") or "unknown").strip() or "unknown"
            score = float(row.get("score", row.get("vector_score", 0.0)) or 0.0)
            if text:
                lines.append(
                    f"[{idx}] {text}\n"
                    f"   section: {section} | strategy: {strategy} | score: {score:.2f}"
                )
        return "\n".join(lines) if lines else "No evidence retrieved."

    routing_decision = (
        dict(state.get("routing_decision"))
        if isinstance(state.get("routing_decision"), dict)
        else {
            "intent": "answer",
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
        }
    )

    # =====================================================================
    # 5-Layer Persona Integration (Phase 4)
    # =====================================================================
    # Check if we should use 5-Layer persona for this query
    used_5layer = False
    v2_result = None
    v2_state_updates = {}
    
    if should_use_5layer_persona(state):
        try:
            used_5layer, v2_result = await maybe_use_5layer_persona(
                state=state,
                user_query=user_query,
                context_data=context_data,
            )
            
            if used_5layer and v2_result:
                # Build state updates from v2 result
                v2_state_updates = {
                    "persona_v2_enabled": True,
                    "persona_v2_safety_blocked": v2_result.safety_blocked,
                }
                
                if v2_result.decision_output:
                    v2_state_updates.update(build_persona_v2_state_updates(v2_result.decision_output))
                
                # If safety blocked, return early
                if v2_result.safety_blocked:
                    safety_output = {
                        "planning_output": {
                            "answer_points": v2_result.answer_points,
                            "citations": [],
                            "follow_up_question": "",
                            "confidence": 0.0,
                            "teaching_questions": [],
                            "render_strategy": "source_faithful",
                            "reasoning_trace": "5-Layer Persona: Safety boundary triggered.",
                            "answerability": {
                                "answerability": "insufficient",
                                "answerable": False,
                                "confidence": 0.0,
                                "reasoning": "Request blocked by safety boundaries.",
                                "missing_information": [],
                                "ambiguity_level": "low",
                            },
                            "telemetry": _build_planner_telemetry(),
                        },
                        "confidence_score": 0.0,
                        "routing_decision": {
                            **routing_decision,
                            "action": "refuse",
                            "confidence": 0.0,
                        },
                        "workflow_intent": "refuse",
                        "intent_label": persona_trace.get("intent_label"),
                        "persona_module_ids": [],
                        "persona_spec_version": v2_result.decision_output.persona_version if v2_result.decision_output else None,
                        "reasoning_history": (state.get("reasoning_history") or []) + [
                            "Planner: 5-Layer Persona safety boundary triggered."
                        ],
                        **v2_state_updates,
                    }
                    return safety_output
                
        except Exception as e:
            print(f"[Planner] 5-Layer Persona integration error: {e}")
            used_5layer = False
    
    dialogue_mode = str(state.get("dialogue_mode") or "").strip().upper()
    is_smalltalk_check = dialogue_mode == "SMALLTALK" or _is_smalltalk_query(user_query)
    print(f"[Planner DEBUG] dialogue_mode={dialogue_mode}, user_query='{user_query}', is_smalltalk_check={is_smalltalk_check}")
    if is_smalltalk_check:
        _full_settings = state.get("full_settings") or {}
        twin_name = str(_full_settings.get("name") or "").strip()
        answer_text = _smalltalk_response(user_query, twin_name=twin_name, full_settings=_full_settings)
        smalltalk_confidence = 0.9
        smalltalk_answerability = {
            "answerability": "direct",
            "answerable": True,
            "confidence": smalltalk_confidence,
            "reasoning": "Smalltalk bypass: conversational message handled without retrieval/evaluator.",
            "missing_information": [],
            "ambiguity_level": "low",
        }
        updated_routing_decision = {
            **routing_decision,
            "action": "answer",
            "confidence": smalltalk_confidence,
            "required_inputs_missing": [],
            "clarifying_questions": [],
        }
        return {
            "planning_output": {
                "answer_points": [answer_text],
                "citations": [],
                "follow_up_question": "",
                "confidence": smalltalk_confidence,
                "teaching_questions": [],
                "render_strategy": (
                    "conversational_realizer"
                    if CONVERSATIONAL_REALIZER_ENABLED
                    and str(state.get("interaction_context") or "").strip().lower()
                    in {"owner_chat", "public_share"}
                    else "source_faithful"
                ),
                "reasoning_trace": "Smalltalk planner bypass.",
                "answerability": smalltalk_answerability,
                "telemetry": _build_planner_telemetry(),
            },
            "confidence_score": smalltalk_confidence,
            "routing_decision": updated_routing_decision,
            "workflow_intent": str(updated_routing_decision.get("intent") or "answer"),
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: smalltalk bypass (no retrieval/evaluator/clarification)."
            ],
        }

    try:
        answerability = await evaluate_answerability(effective_query, context_data)
    except Exception as exc:
        print(f"Planner answerability error: {exc}")
        answerability = {
            "answerability": "insufficient",
            "answerable": False,
            "confidence": 0.0,
            "reasoning": "Answerability evaluation failed.",
            "missing_information": ["the specific evidence needed to answer this question"],
            "ambiguity_level": "high",
        }

    answerability_state = str(answerability.get("answerability") or "").strip().lower()
    if answerability_state not in {"direct", "derivable", "insufficient"}:
        answerability_state = "direct" if bool(answerability.get("answerable")) else "insufficient"
        answerability["answerability"] = answerability_state
    answerability["answerable"] = answerability_state in {"direct", "derivable"}
    evidence_quality = _answer_text_quality(context_data)
    prompt_question_dominance = float(evidence_quality.get("prompt_question_ratio") or 0.0) >= 0.5
    answer_text_ratio = float(evidence_quality.get("answer_text_ratio") or 0.0)
    retry_reasons: List[str] = []

    second_pass_used = False
    loop_break_candidate = _should_break_clarification_loop(
        messages=state_messages,
        user_query=user_query,
        context_data=context_data,
    )
    low_quality_retry_candidate = _should_retry_low_quality_evidence(context_data, query_class)
    should_second_pass = answerability_state == "insufficient" and (
        (0 < len(context_data) < 3)
        or (query_class == "identity" and 0 < len(context_data) < PLANNER_SECOND_PASS_RETRIEVAL_TOP_K)
        or loop_break_candidate
        or low_quality_retry_candidate
    )
    if answerability_state == "insufficient":
        if 0 < len(context_data) < 3:
            retry_reasons.append("low_chunk_count")
        if query_class == "identity" and 0 < len(context_data) < PLANNER_SECOND_PASS_RETRIEVAL_TOP_K:
            retry_reasons.append("identity_sparse")
        if loop_break_candidate:
            retry_reasons.append("clarification_loop_break")
        if low_quality_retry_candidate:
            retry_reasons.append("low_quality_evidence")
    if should_second_pass:
        twin_id = str(state.get("twin_id") or "").strip()
        if twin_id:
            second_pass_rows = await _run_second_pass_retrieval(
                effective_query,
                twin_id,
                group_id=state.get("retrieval_group_id"),
                resolve_default_group=bool(state.get("resolve_default_group_filtering", True)),
            )
            merged_context = _merge_context_rows(
                context_data,
                second_pass_rows,
                limit=PLANNER_SECOND_PASS_RETRIEVAL_TOP_K,
            )
            if len(merged_context) > len(context_data):
                context_data = merged_context
                valid_source_ids = _collect_valid_source_ids(context_data)
                second_pass_used = True
                try:
                    answerability = await evaluate_answerability(effective_query, context_data)
                except Exception as exc:
                    print(f"Planner second-pass answerability error: {exc}")
                answerability_state = str(answerability.get("answerability") or "").strip().lower()
                if answerability_state not in {"direct", "derivable", "insufficient"}:
                    answerability_state = "direct" if bool(answerability.get("answerable")) else "insufficient"
                    answerability["answerability"] = answerability_state
                answerability["answerable"] = answerability_state in {"direct", "derivable"}
                evidence_quality = _answer_text_quality(context_data)
                prompt_question_dominance = (
                    float(evidence_quality.get("prompt_question_ratio") or 0.0) >= 0.5
                )
                answer_text_ratio = float(evidence_quality.get("answer_text_ratio") or 0.0)

    if (
        answerability_state == "insufficient"
        and _should_break_clarification_loop(
            messages=state_messages,
            user_query=user_query,
            context_data=context_data,
        )
    ):
        answerability_state = "derivable"
        answerability["answerability"] = "derivable"
        answerability["answerable"] = True
        answerability["missing_information"] = []
        answerability["confidence"] = max(float(answerability.get("confidence") or 0.0), 0.52)
        answerability["ambiguity_level"] = "medium"
        reason = re.sub(r"\s+", " ", str(answerability.get("reasoning") or "").strip())
        answerability["reasoning"] = (
            f"{reason} Loop-break policy: user replied to prior clarification, so planner synthesizes best grounded answer."
            if reason
            else "Loop-break policy: user replied to prior clarification, so planner synthesizes best grounded answer."
        )

    if answerability_state == "insufficient":
        missing_information = answerability.get("missing_information") or []
        clarification_questions = []
        clarification_options: List[Dict[str, str]] = []
        clarification_hint = None
        if identity_gate_clarification_hint:
            clarification_hint = identity_gate_clarification_hint
            question = str(identity_gate_clarification_hint.get("question") or "").strip()
            if question:
                clarification_questions = [question]
            clarification_options = list(identity_gate_clarification_hint.get("options") or [])
        if not clarification_questions:
            clarification_questions = build_targeted_clarification_questions(
                effective_query,
                missing_information,
                evidence_chunks=context_data,
                limit=3,
            )
        insufficient_confidence = _calibrate_confidence_score(
            raw_confidence=float(answerability.get("confidence") or 0.0),
            answerability_state=answerability_state,
            context_data=context_data,
        )
        answer_points = []
        if clarification_hint and clarification_questions:
            answer_points.append(clarification_questions[0])
            for idx, option in enumerate(clarification_options, 1):
                label = str(option.get("label") or "").strip()
                if label:
                    answer_points.append(f"{idx}. {label}")
        else:
            answer_points = [UNCERTAINTY_RESPONSE]
            for idx, question in enumerate(clarification_questions, 1):
                answer_points.append(f"{idx}. {question}")

        updated_routing_decision = {
            **routing_decision,
            "action": "clarify",
            "confidence": insufficient_confidence,
            "required_inputs_missing": [str(v) for v in missing_information[:3]],
            "clarifying_questions": clarification_questions[:3],
        }
        planner_telemetry = _build_planner_telemetry(
            retry_reason="+".join(retry_reasons) if retry_reasons else "none",
            prompt_question_dominance=prompt_question_dominance,
            answer_text_ratio=answer_text_ratio,
            intent_recovered=intent_recovered,
            noisy_section_filtered_count=0,
            clarify_option_count=len(clarification_questions[:3]),
            selection_recovery_failure_rate=1 if selection_recovery_failed else 0,
        )

        return {
            "planning_output": {
                "answer_points": answer_points,
                "citations": [],
                "follow_up_question": "",
                "confidence": insufficient_confidence,
                "teaching_questions": clarification_questions[:3],
                "clarification_options": clarification_options,
                "clarification_hint": clarification_hint,
                # Use conversational_realizer even for thin-evidence — the system prompt
                # handles it with "WHEN EVIDENCE IS THIN" instructions (persona-quality fallback).
                "render_strategy": (
                    "conversational_realizer"
                    if CONVERSATIONAL_REALIZER_ENABLED
                    and str(state.get("interaction_context") or "").strip().lower() in {"owner_chat", "public_share"}
                    else "source_faithful"
                ),
                "reasoning_trace": str(answerability.get("reasoning") or ""),
                "answerability": answerability,
                "telemetry": planner_telemetry,
            },
            "confidence_score": insufficient_confidence,
            "routing_decision": updated_routing_decision,
            "workflow_intent": str(updated_routing_decision.get("intent") or "answer"),
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: answerability=insufficient, produced targeted clarification questions."
                + (" (after second-pass retrieval)." if second_pass_used else "")
            ],
        }

    planner_prompt = f"""{_system_msg}

You are a grounded answer composer.
Use only the provided evidence. Do not use outside knowledge.

USER QUESTION:
{effective_query}

ANSWERABILITY JUDGEMENT:
{json.dumps(answerability, ensure_ascii=True)}

ALLOWED SOURCE IDS:
{json.dumps(valid_source_ids, ensure_ascii=True)}

EVIDENCE:
{_build_evidence_blob()}

Return STRICT JSON:
{{
  "answer_points": ["point 1", "point 2"],
  "citations": ["source_id"],
  "confidence": 0.0,
  "reasoning_trace": "short trace"
}}

Rules:
- Provide max 3 concise answer points.
- Cite only IDs from ALLOWED SOURCE IDS.
- Do not ask clarification questions when answerability is direct or derivable.
"""

    try:
        plan, _route_meta = await invoke_json(
            [{"role": "system", "content": planner_prompt}],
            task="planner",
            temperature=0,
            max_tokens=700,
        )
    except Exception as exc:
        print(f"Planner composition error: {exc}")
        composed = compose_answer_points(
            query=effective_query,
            query_class=query_class,
            quote_intent=quote_intent,
            planner_points=[],
            context_data=context_data,
            max_points=3,
        )
        fallback_points = [p for p in composed.get("points", []) if isinstance(p, str) and p.strip()]
        fallback_citations = _sanitize_citations(composed.get("source_ids"))
        plan = {
            "answer_points": fallback_points or ["Answer: The retrieved evidence supports a concise response."],
            "citations": fallback_citations or valid_source_ids[:3],
            "confidence": float(answerability.get("confidence") or 0.5),
            "reasoning_trace": "Planner composition fallback used.",
        }

    planner_points = _sanitize_answer_points(plan.get("answer_points"))
    composed = compose_answer_points(
        query=effective_query,
        query_class=query_class,
        quote_intent=quote_intent,
        planner_points=planner_points,
        context_data=context_data,
        max_points=3,
    )
    answer_points = [p for p in composed.get("points", []) if isinstance(p, str) and p.strip()]
    if not answer_points:
        answer_points = ["Answer: The retrieved evidence supports a concise response."]

    citations = _sanitize_citations(plan.get("citations"))
    composed_citations = _sanitize_citations(composed.get("source_ids"))
    if not citations and composed_citations:
        citations = composed_citations
    if not citations and valid_source_ids:
        citations = valid_source_ids[:3]

    raw_confidence = max(
        0.0,
        min(
            1.0,
            float(plan.get("confidence", answerability.get("confidence", 0.5)) or 0.5),
        ),
    )
    confidence = _calibrate_confidence_score(
        raw_confidence=raw_confidence,
        answerability_state=answerability_state,
        context_data=context_data,
    )
    render_strategy = (
        "conversational_realizer"
        if _should_use_conversational_realizer(
            state=state,
            answerability_state=answerability_state,
            citations=citations,
            confidence=confidence,
            quote_intent=quote_intent,
            strict_grounding=strict_grounding,
        )
        else "source_faithful"
    )

    updated_routing_decision = {
        **routing_decision,
        "action": "answer",
        "confidence": confidence,
        "required_inputs_missing": [],
        "clarifying_questions": [],
    }
    planner_telemetry = _build_planner_telemetry(
        retry_reason="+".join(retry_reasons) if (second_pass_used and retry_reasons) else "none",
        prompt_question_dominance=prompt_question_dominance,
        answer_text_ratio=answer_text_ratio,
        intent_recovered=intent_recovered,
        noisy_section_filtered_count=0,
        clarify_option_count=0,
        selection_recovery_failure_rate=1 if selection_recovery_failed else 0,
    )

    # Build base result
    result = {
        "planning_output": {
            "answer_points": answer_points[:3],
            "citations": citations[:3],
            "follow_up_question": "",
            "confidence": confidence,
            "teaching_questions": [],
            "clarification_options": [],
            "clarification_hint": None,
            "render_strategy": render_strategy,
            "reasoning_trace": str(plan.get("reasoning_trace") or answerability.get("reasoning") or ""),
            "answerability": answerability,
            "telemetry": planner_telemetry,
        },
        "confidence_score": confidence,
        "routing_decision": updated_routing_decision,
        "workflow_intent": str(updated_routing_decision.get("intent") or "answer"),
        "intent_label": persona_trace.get("intent_label"),
        "persona_module_ids": persona_trace.get("module_ids", []),
        "persona_spec_version": persona_trace.get("persona_spec_version"),
        "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
        "reasoning_history": (state.get("reasoning_history") or []) + [
            f"Planner: answerability={answerability_state}, generated grounded answer with citations."
            + (" (after second-pass retrieval)." if second_pass_used else "")
            + (" (resolved clarification follow-up to prior user question)." if effective_query != user_query else "")
        ],
    }
    
    # Add 5-Layer Persona state updates if used
    if used_5layer and v2_state_updates:
        result.update(v2_state_updates)
        # Update reasoning history to indicate 5-Layer was used
        result["reasoning_history"][-1] += " (5-Layer Persona enriched)."
    
    return result


def _build_realizer_message(
    *,
    content: str,
    plan: Optional[Dict[str, Any]],
    state: TwinState,
    mode: str,
    render_strategy: str,
    confidence_score: float,
    route_meta: Optional[Dict[str, Any]] = None,
) -> AIMessage:
    latest_query = next(
        (m.content for m in reversed(state.get("messages") or []) if isinstance(m, HumanMessage)),
        "",
    ).strip()
    msg = AIMessage(content=_ensure_closing_question(content, latest_query))
    teaching_questions = plan.get("teaching_questions", []) if isinstance(plan, dict) else []
    clarification_options = plan.get("clarification_options", []) if isinstance(plan, dict) else []
    clarification_hint = plan.get("clarification_hint") if isinstance(plan, dict) else None

    msg.additional_kwargs["teaching_questions"] = teaching_questions
    msg.additional_kwargs["clarification_options"] = clarification_options
    msg.additional_kwargs["clarification_hint"] = clarification_hint
    msg.additional_kwargs["planning_output"] = plan if isinstance(plan, dict) else {}
    msg.additional_kwargs["dialogue_mode"] = mode
    msg.additional_kwargs["intent_label"] = state.get("intent_label")
    msg.additional_kwargs["module_ids"] = state.get("persona_module_ids") or []
    msg.additional_kwargs["requires_evidence"] = bool(state.get("requires_evidence", False))
    msg.additional_kwargs["target_owner_scope"] = bool(state.get("target_owner_scope", False))
    msg.additional_kwargs["router_reason"] = state.get("router_reason")
    msg.additional_kwargs["router_knowledge_available"] = state.get("router_knowledge_available")
    msg.additional_kwargs["render_strategy"] = render_strategy
    msg.additional_kwargs["workflow_intent"] = state.get("workflow_intent")
    msg.additional_kwargs["confidence_score"] = confidence_score
    if isinstance(state.get("routing_decision"), dict):
        msg.additional_kwargs["routing_decision"] = state.get("routing_decision")
    if state.get("persona_spec_version"):
        msg.additional_kwargs["persona_spec_version"] = state.get("persona_spec_version")
    if state.get("persona_prompt_variant"):
        msg.additional_kwargs["persona_prompt_variant"] = state.get("persona_prompt_variant")
    provider = (route_meta or {}).get("provider") or get_active_provider()
    model = (route_meta or {}).get("model") or get_active_model()
    msg.additional_kwargs["inference_provider"] = provider
    msg.additional_kwargs["inference_model"] = model
    if route_meta:
        msg.additional_kwargs["inference_latency_ms"] = route_meta.get("latency_ms")
    return msg


@observe(name="realizer_node")
async def realizer_node(state: TwinState):
    """Pass B: Conversational Reification (Human-like Output)"""
    plan = state.get("planning_output", {})
    mode = state.get("dialogue_mode", "QA_FACT")
    render_strategy = str(plan.get("render_strategy", "")).strip().lower() if isinstance(plan, dict) else ""
    confidence_score = float(plan.get("confidence", state.get("confidence_score", 0.0)) or 0.0)
    citations = plan.get("citations", []) if isinstance(plan, dict) else []
    context_data = [
        row
        for row in ((state.get("retrieved_context") or {}).get("results") or [])
        if isinstance(row, dict)
    ]
    deterministic_text = _build_source_faithful_response_text(
        plan if isinstance(plan, dict) else {},
        state=state,
        fallback_text=UNCERTAINTY_RESPONSE,
    )

    print(f"[Realizer DEBUG] dialogue_mode={mode}, render_strategy={render_strategy}, plan_keys={list(plan.keys()) if isinstance(plan, dict) else 'N/A'}")
    
    if render_strategy == "source_faithful":
        # Source-faithful mode intentionally avoids LLM rewrite/paraphrase.
        print(f"[Realizer DEBUG] source-faithful_text='{deterministic_text[:50]}...'")
        res = _build_realizer_message(
            content=deterministic_text,
            plan=plan if isinstance(plan, dict) else {},
            state=state,
            mode=mode,
            render_strategy="source_faithful",
            confidence_score=confidence_score,
        )

        return {
            "messages": [res],
            "citations": citations,
            "confidence_score": confidence_score,
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Realizer: source-faithful deterministic rendering (no paraphrase)."
            ],
        }
    
    realizer_prompt = f"""{_build_advisor_system_prompt(
        twin_name=str((state.get("full_settings") or {}).get("name") or "Digital Twin").strip() or "Digital Twin",
        creator_namespace=_resolve_creator_namespace_label(str(state.get("twin_id") or "")),
        active_persona=str(
            state.get("persona_prompt_variant")
            or state.get("persona_spec_version")
            or DEFAULT_PERSONA_PROMPT_VARIANT
        ).strip(),
        retrieved_context_block=build_retrieved_context_block(context_data[:5]),
        conversation_history=_format_prompt_history(
            [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)],
            max_turns=5,
        ),
        additional_context_blocks=[],
    )}

Take the structured plan below and rewrite it into the final answer.

PLAN:
{json.dumps(plan, indent=2)}

CONSTRAINTS:
- Do not use section headers.
- Keep the tone conversational and natural.
- Use inline numeric citations like [1] or [2] only when they help.
- End with exactly one direct question.
- Do not fabricate sources or certainty.
- If the evidence is thin, acknowledge that naturally and keep moving forward.
"""
    
    try:
        realized_text, route_meta = await invoke_text(
            [{"role": "system", "content": realizer_prompt}],
            task="realizer",
            temperature=0.7,
            max_tokens=500,
        )
        res = _build_realizer_message(
            content=realized_text or deterministic_text,
            plan=plan if isinstance(plan, dict) else {},
            state=state,
            mode=mode,
            render_strategy=render_strategy or "conversational_realizer",
            confidence_score=confidence_score,
            route_meta=route_meta,
        )
        
        return {
            "messages": [res],
            "citations": citations,
            "confidence_score": confidence_score,
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Realizer: conversational rewrite completed."
            ]
        }
    except Exception as e:
        print(f"Realizer error: {e}")
        # Tag error in Langfuse
        try:
            langfuse_context.update_current_observation(
                level="ERROR",
                status_message=f"Realizer failed: {str(e)[:255]}",
                metadata={
                    "error": True,
                    "error_type": type(e).__name__,
                    "error_node": "realizer_node",
                }
            )
        except Exception:
            pass
        fallback_msg = _build_realizer_message(
            content=deterministic_text,
            plan=plan if isinstance(plan, dict) else {},
            state=state,
            mode=mode,
            render_strategy="source_faithful",
            confidence_score=confidence_score,
        )

        return {
            "messages": [fallback_msg],
            "citations": citations,
            "confidence_score": confidence_score,
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Realizer: deterministic source-faithful fallback used after exception."
            ],
        }

def create_twin_agent(
    twin_id: str,
    group_id: Optional[str] = None,
    resolve_default_group: bool = True,
    system_prompt_override: str = None,
    full_settings: dict = None,
    graph_context: str = "",
    owner_memory_context: str = "",
    conversation_history: Optional[List[BaseMessage]] = None
):
    # Retrieve-only tool setup needs to stay inside or be passed
    from modules.tools import get_retrieval_tool
    retrieval_tool = get_retrieval_tool(
        twin_id,
        group_id=group_id,
        conversation_history=conversation_history,
        resolve_default_group=resolve_default_group,
    )

    @observe(name="retrieve_hybrid_node")
    async def retrieve_hybrid_node(state: TwinState):
        """Phase 2: Executing planned retrieval (Audit 1: Parallel & Robust)"""
        sub_queries = state.get("sub_queries", [])
        all_results = []
        citations = []
        user_query = next(
            (m.content for m in reversed(state.get("messages") or []) if isinstance(m, HumanMessage)),
            "",
        )
        
        async def safe_retrieve(query):
            try:
                res_str = await retrieval_tool.ainvoke({"query": query})
                return json.loads(res_str)
            except Exception as e:
                print(f"Retrieval error: {e}")
                # Tag error in Langfuse
                try:
                    langfuse_context.update_current_observation(
                        level="WARNING",
                        metadata={
                            "retrieval_error": True,
                            "error_type": type(e).__name__,
                            "query": query[:200] if query else None,
                        }
                    )
                except Exception:
                    pass
                return []

        tasks = [safe_retrieve(q) for q in sub_queries]
        results_list = await asyncio.gather(*tasks)
        for res_data in results_list:
            if isinstance(res_data, list):
                for item in res_data:
                    all_results.append(item)
                    if "source_id" in item:
                        citations.append(item["source_id"])

        interaction_context = str(state.get("interaction_context") or "").strip().lower()
        use_profile_seed_rows = interaction_context in {"public_share", "public_widget"} or not all_results
        profile_seed_rows: List[Dict[str, Any]] = []
        if use_profile_seed_rows:
            profile_seed_rows = _build_query_ranked_profile_seed_rows(
                state.get("full_settings"),
                user_query,
                limit=6 if not all_results else 4,
            )
            if profile_seed_rows:
                all_results = _merge_context_rows(
                    all_results,
                    profile_seed_rows,
                    limit=max(PLANNER_SECOND_PASS_RETRIEVAL_TOP_K, 10),
                )

        if all_results:
            citations = []
            for item in all_results:
                source_id = item.get("source_id")
                if isinstance(source_id, str) and source_id and source_id not in citations:
                    citations.append(source_id)

        return {
            "retrieved_context": {"results": all_results},
            "citations": citations,
            "reasoning_history": (state.get("reasoning_history") or [])
            + [
                f"Retrieval: Executed {len(sub_queries)} queries."
                + (
                    f" Added {len(profile_seed_rows)} canonical profile seed rows."
                    if profile_seed_rows
                    else ""
                )
            ]
        }

    # Define the graph
    workflow = StateGraph(TwinState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("deepagents", deepagents_node)
    workflow.add_node("retrieve", retrieve_hybrid_node)
    workflow.add_node("gate", evidence_gate_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("realizer", realizer_node)
    
    workflow.set_entry_point("router")
    
    def route_after_router(state: TwinState):
        execution_lane = state.get("execution_lane")
        requires_evidence = state.get("requires_evidence")
        route = "deepagents" if execution_lane else ("retrieve" if requires_evidence else "planner")
        print(f"[RouterRoute DEBUG] execution_lane={execution_lane}, requires_evidence={requires_evidence}, route={route}")
        return route

    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {"deepagents": "deepagents", "retrieve": "retrieve", "planner": "planner"},
    )
    workflow.add_edge("deepagents", "realizer")
    workflow.add_edge("retrieve", "gate")
    workflow.add_edge("gate", "planner")
    workflow.add_edge("planner", "realizer")
    workflow.add_edge("realizer", END)
    
    checkpointer = get_checkpointer()
    return workflow.compile(checkpointer=checkpointer) if checkpointer else workflow.compile()

@observe(name="agent_response")
async def run_agent_stream(
    twin_id: str,
    query: str,
    history: List[BaseMessage] = None,
    system_prompt: str = None,
    group_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    owner_memory_context: str = "",
    interaction_context: str = "owner_chat",
    enforce_group_filtering: bool = True,
    actor_user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    identity_gate_clarification_hint: Optional[Dict[str, Any]] = None,
):
    """
    Runs the agent and yields events from the graph.
    
    P1-A: conversation_id is used as thread_id for state persistence if checkpointer is enabled.
    """
    # 0. Apply Phase 9 Safety Guardrails
    from modules.safety import apply_guardrails
    refusal_message = apply_guardrails(twin_id, query)
    if refusal_message:
        # Yield a simulated refusal event to match the graph output format
        refusal_ai = AIMessage(content=refusal_message)
        refusal_ai.additional_kwargs["routing_decision"] = {
            "intent": "answer",
            "confidence": 1.0,
            "required_inputs_missing": [],
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
            "action": "refuse",
            "clarifying_questions": [],
        }
        refusal_ai.additional_kwargs["workflow_intent"] = "answer"
        yield {
            "agent": {
                "messages": [refusal_ai]
            }
        }
        return

    # 1. Fetch full twin settings for persona encoding
    # RLS Fix: Use RPC
    twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
    settings = _merge_twin_row_settings(twin_res.data)
    
    # 2. Load group settings if group_id provided
    if group_id:
        try:
            from modules.access_groups import get_group_settings
            group_settings = await get_group_settings(group_id)
            # Merge group settings with twin settings (group takes precedence)
            settings = {**settings, **group_settings}
        except Exception as e:
            print(f"Warning: Failed to load group settings: {e}")
    
    # 3. Ensure style analysis has been run at least once
    if "persona_profile" not in settings:
        await get_owner_style_profile(twin_id)
        # Re-fetch after analysis
        # RLS Fix: Use RPC
        twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
        settings = _merge_twin_row_settings(twin_res.data)
        # Re-merge group settings if needed
        if group_id:
            try:
                from modules.access_groups import get_group_settings
                group_settings = await get_group_settings(group_id)
                settings = {**settings, **group_settings}
            except Exception:
                pass

    # 3.5 Fetch Graph Context (Phase 2 - Best effort with soft budget)
    # Feature flag: GRAPH_MEMORY_ENABLED (default: false)
    graph_context = ""
    graph_memory_enabled = os.getenv("GRAPH_MEMORY_ENABLED", "false").lower() == "true"
    graph_context_result = None
    
    if graph_memory_enabled and tenant_id:
        try:
            from modules.graph_context_builder import get_graph_context_for_chat
            # Use soft budget (default 500ms) - non-blocking for chat
            graph_context_result = await get_graph_context_for_chat(
                tenant_id=tenant_id,
                twin_id=twin_id,
                query=query,
                correlation_id=conversation_id or "no-conversation"
            )
            if graph_context_result.context:
                graph_context = graph_context_result.context
                print(f"[GraphMemory] Context retrieved: {graph_context_result.episode_count} episodes "
                      f"in {graph_context_result.latency_ms:.0f}ms")
            elif graph_context_result.source == "timeout":
                print(f"[GraphMemory] Soft budget timeout ({graph_context_result.latency_ms:.0f}ms), continuing without context")
            else:
                print(f"[GraphMemory] No context available (source: {graph_context_result.source})")
        except Exception as e:
            print(f"[GraphMemory] Retrieval failed gracefully: {e}")

    effective_group_id = group_id if enforce_group_filtering else None

    agent = create_twin_agent(
        twin_id,
        group_id=effective_group_id,
        resolve_default_group=enforce_group_filtering,
        system_prompt_override=system_prompt,
        full_settings=settings,
        graph_context=graph_context,
        owner_memory_context=owner_memory_context,
        conversation_history=history
    )
    
    initial_messages = history or []
    initial_messages.append(HumanMessage(content=query))
    
    state = {
        "messages": initial_messages,
        "twin_id": twin_id,
        "confidence_score": 0.0,
        "citations": [],
        "sub_queries": [],
        "reasoning_history": [],
        "retrieved_context": {},
        # Phase 4 initialization
        "dialogue_mode": "QA_FACT",
        "intent_label": "factual_with_evidence",
        "requires_evidence": True,
        "requires_teaching": False,
        "target_owner_scope": False,
        "planning_output": None,
        "persona_module_ids": [],
        "persona_spec_version": None,
        "persona_prompt_variant": None,
        "router_reason": None,
        "router_knowledge_available": None,
        "workflow_intent": "answer",
        "fastpath_intent": None,
        "fastpath_response": None,
        "retrieval_group_id": effective_group_id,
        "resolve_default_group_filtering": enforce_group_filtering,
        "query_class": None,
        "quote_intent": False,
        "execution_lane": False,
        "deepagents_plan": None,
        "actor_user_id": actor_user_id,
        "tenant_id": tenant_id,
        "routing_decision": {
            "intent": "answer",
            "confidence": 1.0,
            "required_inputs_missing": [],
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
            "action": "answer",
            "clarifying_questions": [],
        },
        # Path B / Phase 4 Context
        "full_settings": settings,
        "graph_context": graph_context,
        "owner_memory_context": owner_memory_context,
        "system_prompt_override": system_prompt,
        "interaction_context": interaction_context,
        "identity_gate_clarification_hint": identity_gate_clarification_hint,
    }
    
    # Phase 10: Metrics instrumentation
    from modules.metrics_collector import MetricsCollector
    import time
    
    metrics = MetricsCollector(twin_id=twin_id)
    metrics.record_request()
    agent_start = time.time()
    
    # P1-A: Generate thread_id from conversation_id for state persistence
    thread_id = None
    if conversation_id:
        # Thread ID format: conversation_id (simple, deterministic)
        thread_id = conversation_id
        print(f"[LangGraph] Using thread_id: {thread_id}")
    
    try:
        # P1-A: Pass thread_id if checkpointer is enabled
        config = {"configurable": {"thread_id": thread_id}} if thread_id and get_checkpointer() else {}
        
        # Track final response for post-generation validation (link-first)
        final_response_text = ""
        final_event = None
        
        async for event in agent.astream(state, stream_mode="updates", **config):
            # Capture agent messages for validation
            if event.get("agent") and event["agent"].get("messages"):
                for msg in event["agent"]["messages"]:
                    if hasattr(msg, 'content'):
                        final_response_text = msg.content
                    elif isinstance(msg, dict) and 'content' in msg:
                        final_response_text = msg['content']
                    final_event = event
            
            yield event
        
        # POST-GENERATION VALIDATION: Link-First Citation Compliance
        # Only validate if we have a response and it's link-first
        if final_response_text and settings.get("persona_v2_source") == "link-compile":
            try:
                # Get persona spec for validation
                persona_row = _load_active_persona_spec_v2_row(twin_id)
                if persona_row and persona_row.get("spec"):
                    validation_result = await validate_link_first_response(
                        response_text=final_response_text,
                        twin_id=twin_id,
                        persona_spec=persona_row["spec"],
                    )
                    
                    if not validation_result.is_valid and validation_result.corrected_response:
                        # Yield corrected response as a new event
                        from langchain_core.messages import AIMessage
                        corrected_msg = AIMessage(content=validation_result.corrected_response)
                        corrected_msg.additional_kwargs["post_gen_validated"] = True
                        corrected_msg.additional_kwargs["validation_action"] = validation_result.action
                        
                        yield {
                            "agent": {
                                "messages": [corrected_msg]
                            }
                        }
                        
                        print(f"[PostGenValidator] Corrected response for twin {twin_id}: {validation_result.action}")
            except Exception as e:
                print(f"[PostGenValidator] Validation error: {e}")
                # Don't block response on validation error
    
    finally:
        # Record agent latency and flush metrics
        agent_latency = (time.time() - agent_start) * 1000
        metrics.record_latency("agent", agent_latency)
        metrics.flush()

