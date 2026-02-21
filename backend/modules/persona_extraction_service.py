"""
Feature-flagged persona extraction service.

Extracts persona candidates from normalized source text and stores:
- raw candidates with confidence/evidence/provenance
- high-confidence draft profile fields (canonical identity pack)
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from modules.observability import supabase
from modules.persona_profile_store import (
    build_profile_patch_from_extraction,
    collect_low_confidence_facts,
    store_extraction_candidates,
    upsert_persona_profile,
)
from modules.runtime_audit_store import enqueue_owner_review_item


def is_persona_extraction_enabled() -> bool:
    return os.getenv("PERSONA_EXTRACTION_ENABLED", "false").strip().lower() == "true"


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _first_sentences(text: str, max_sentences: int = 2) -> str:
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    picked = [p.strip() for p in parts if p.strip()][:max_sentences]
    return " ".join(picked).strip()


def _split_paragraphs(text: str) -> List[str]:
    if not text:
        return []
    chunks = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    return chunks[:80]


def _clean_name(value: str) -> str:
    value = _safe_str(value)
    value = re.sub(r"\s+", " ", value).strip(" ,.;:-")
    return value


def _candidate(
    *,
    value: Any,
    confidence: float,
    source_id: str,
    pointer: str,
    source_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "value": value,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "evidence": [{"source_id": source_id, "pointer": pointer}],
        "source_provenance": source_provenance,
    }


def _dedupe_keep_best(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_value: Dict[str, Dict[str, Any]] = {}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        key = str(value).strip().lower()
        if not key:
            continue
        current = best_by_value.get(key)
        if not current or float(item.get("confidence") or 0.0) > float(current.get("confidence") or 0.0):
            best_by_value[key] = item
    return list(best_by_value.values())


def _extract_links(text: str) -> Dict[str, str]:
    links: Dict[str, str] = {}
    for raw in re.findall(r"(https?://[^\s)]+)", text, flags=re.IGNORECASE):
        link = raw.rstrip(".,;:)")
        lowered = link.lower()
        if "linkedin.com" in lowered:
            links.setdefault("linkedin", link)
        elif "instagram.com" in lowered:
            links.setdefault("instagram", link)
        elif "youtube.com" in lowered or "youtu.be" in lowered:
            links.setdefault("youtube", link)
        else:
            links.setdefault("website", link)

    email_match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, flags=re.IGNORECASE)
    if email_match:
        links["email"] = email_match.group(0)
    return links


def _extract_expertise_terms(text: str) -> List[str]:
    labels = [
        "ai systems",
        "machine learning",
        "product strategy",
        "startup fundraising",
        "go-to-market",
        "cloud architecture",
        "reliability engineering",
        "developer productivity",
        "leadership",
        "growth",
        "sales",
        "marketing",
        "design",
        "operations",
    ]
    lower = text.lower()
    found = [label for label in labels if label in lower]
    return found[:8]


def _extract_tone_tags(text: str) -> List[str]:
    lower = text.lower()
    tags: List[str] = []
    if any(k in lower for k in ("let's", "lets", "feel free", "happy to", "glad to")):
        tags.append("warm")
    if any(k in lower for k in ("direct", "straight to", "bottom line", "no fluff")):
        tags.append("direct")
    if any(k in lower for k in ("approachable", "ask me anything", "open to")):
        tags.append("approachable")
    if not tags:
        tags = ["professional"]
    return tags


def _infer_preferred_channel(text: str, links: Dict[str, str]) -> Optional[Tuple[str, float]]:
    lower = text.lower()
    if "email me" in lower or "reach me at" in lower:
        if links.get("email"):
            return ("email", 0.85)
    if "connect on linkedin" in lower and links.get("linkedin"):
        return ("linkedin", 0.82)
    if "dm" in lower and links.get("instagram"):
        return ("instagram", 0.8)
    if links.get("email"):
        return ("email", 0.62)
    if links.get("linkedin"):
        return ("linkedin", 0.58)
    return None


def extract_persona_facts(
    *,
    source_id: str,
    text: str,
    source_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source_metadata = source_metadata or {}
    source_provenance = {
        "source_id": source_id,
        "provider": _safe_str(source_metadata.get("provider")),
        "filename": _safe_str(source_metadata.get("filename")),
        "citation_url": _safe_str(source_metadata.get("citation_url")),
    }
    scan_text = (text or "")[:25000]
    paragraphs = _split_paragraphs(scan_text)
    p1 = paragraphs[0] if paragraphs else _first_sentences(scan_text, max_sentences=1)

    facts: Dict[str, List[Dict[str, Any]]] = {
        "full_name": [],
        "brand_name": [],
        "roles_titles": [],
        "credentials": [],
        "company_organization": [],
        "expertise_areas": [],
        "one_line_intro": [],
        "short_intro": [],
        "public_contact_links": [],
        "preferred_contact_channel": [],
        "tone_tags": [],
        "disclosure_line": [],
        "contact_handoff_line": [],
    }

    # full_name candidates
    for m in re.finditer(
        r"\b(?:my name is|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
        scan_text,
        flags=re.IGNORECASE,
    ):
        name = _clean_name(m.group(1))
        if name:
            facts["full_name"].append(
                _candidate(
                    value=name,
                    confidence=0.84,
                    source_id=source_id,
                    pointer=f"char:{m.start()}",
                    source_provenance=source_provenance,
                )
            )

    # roles + organization + credentials
    role_pattern = re.compile(
        r"\b(?:i am|i'm|serving as|work as)\s+(?:a|an|the)?\s*([^.\n]{3,80})",
        flags=re.IGNORECASE,
    )
    for m in role_pattern.finditer(scan_text):
        phrase = _safe_str(m.group(1))
        if phrase:
            facts["roles_titles"].append(
                _candidate(
                    value=phrase,
                    confidence=0.66,
                    source_id=source_id,
                    pointer=f"char:{m.start()}",
                    source_provenance=source_provenance,
                )
            )

    for m in re.finditer(r"\b(?:founder|ceo|cto|coo|engineer|investor|advisor|coach|researcher)\b", scan_text, flags=re.IGNORECASE):
        facts["roles_titles"].append(
            _candidate(
                value=m.group(0).lower(),
                confidence=0.58,
                source_id=source_id,
                pointer=f"char:{m.start()}",
                source_provenance=source_provenance,
            )
        )

    for m in re.finditer(r"\b(phd|mba|ms|m\.s\.|b\.s\.|cfa|cpa)\b", scan_text, flags=re.IGNORECASE):
        facts["credentials"].append(
            _candidate(
                value=m.group(0).upper().replace(".", ""),
                confidence=0.78,
                source_id=source_id,
                pointer=f"char:{m.start()}",
                source_provenance=source_provenance,
            )
        )

    company_patterns = [
        r"\b(?:founder|co-founder)\s+of\s+([A-Z][\w&\-\s]{2,60})",
        r"\b(?:at|with)\s+([A-Z][\w&\-\s]{2,60})",
    ]
    for pattern in company_patterns:
        for m in re.finditer(pattern, scan_text):
            org = _clean_name(m.group(1))
            if org:
                facts["company_organization"].append(
                    _candidate(
                        value=org,
                        confidence=0.62,
                        source_id=source_id,
                        pointer=f"char:{m.start()}",
                        source_provenance=source_provenance,
                    )
                )

    links = _extract_links(scan_text)
    if links:
        facts["public_contact_links"].append(
            _candidate(
                value=links,
                confidence=0.9,
                source_id=source_id,
                pointer="regex:url_email",
                source_provenance=source_provenance,
            )
        )

    preferred = _infer_preferred_channel(scan_text, links)
    if preferred:
        channel, conf = preferred
        facts["preferred_contact_channel"].append(
            _candidate(
                value=channel,
                confidence=conf,
                source_id=source_id,
                pointer="heuristic:contact_channel",
                source_provenance=source_provenance,
            )
        )

    expertise = _extract_expertise_terms(scan_text)
    if expertise:
        facts["expertise_areas"].append(
            _candidate(
                value=expertise,
                confidence=0.72,
                source_id=source_id,
                pointer="heuristic:expertise_terms",
                source_provenance=source_provenance,
            )
        )

    tone_tags = _extract_tone_tags(scan_text)
    facts["tone_tags"].append(
        _candidate(
            value=tone_tags,
            confidence=0.64,
            source_id=source_id,
            pointer="heuristic:tone_tags",
            source_provenance=source_provenance,
        )
    )

    one_line_intro = _first_sentences(p1 or scan_text, max_sentences=1)
    if one_line_intro:
        facts["one_line_intro"].append(
            _candidate(
                value=one_line_intro[:240],
                confidence=0.61,
                source_id=source_id,
                pointer="paragraph:1",
                source_provenance=source_provenance,
            )
        )

    short_intro = _first_sentences(scan_text, max_sentences=2)
    if short_intro:
        facts["short_intro"].append(
            _candidate(
                value=short_intro[:500],
                confidence=0.58,
                source_id=source_id,
                pointer="paragraph:1-2",
                source_provenance=source_provenance,
            )
        )

    display_name = ""
    if facts["full_name"]:
        display_name = _safe_str(facts["full_name"][0].get("value"))
    elif source_provenance.get("filename"):
        display_name = _safe_str(source_provenance.get("filename")).split(".")[0][:80]
    else:
        display_name = "this twin"

    disclosure_line = (
        f"I’m a digital AI representation of {display_name}, based on provided sources, "
        "and not the real person directly."
    )
    facts["disclosure_line"].append(
        _candidate(
            value=disclosure_line,
            confidence=0.93,
            source_id=source_id,
            pointer="template:disclosure",
            source_provenance=source_provenance,
        )
    )

    handoff_line = "For direct contact, please use the official public channels listed in this profile."
    if preferred:
        handoff_line = f"For direct contact, please use the public {preferred[0]} channel listed in this profile."
    facts["contact_handoff_line"].append(
        _candidate(
            value=handoff_line,
            confidence=0.9,
            source_id=source_id,
            pointer="template:handoff",
            source_provenance=source_provenance,
        )
    )

    # brand_name candidate from org if present
    if facts["company_organization"]:
        best_org = facts["company_organization"][0]
        facts["brand_name"].append(
            _candidate(
                value=_safe_str(best_org.get("value")),
                confidence=0.57,
                source_id=source_id,
                pointer="heuristic:company_as_brand",
                source_provenance=source_provenance,
            )
        )

    # Dedupe all fields by value while keeping highest confidence.
    for key in list(facts.keys()):
        facts[key] = _dedupe_keep_best(facts[key])

    return {
        "schema_version": "persona_extraction.v1",
        "source_id": source_id,
        "extracted_at": _utc_now_iso(),
        "facts": facts,
    }


def _get_twin_tenant_id(twin_id: str) -> Optional[str]:
    try:
        res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
        if res and isinstance(res.data, dict):
            tenant_id = res.data.get("tenant_id")
            return str(tenant_id) if tenant_id else None
    except Exception:
        return None
    return None


def _get_source_metadata(source_id: str) -> Dict[str, Any]:
    try:
        res = (
            supabase.table("sources")
            .select("id,filename,citation_url")
            .eq("id", source_id)
            .single()
            .execute()
        )
        if res and isinstance(res.data, dict):
            return res.data
    except Exception:
        return {}
    return {}


def run_persona_extraction_for_source(
    *,
    twin_id: str,
    source_id: str,
    text: str,
    provider: str = "",
) -> Dict[str, Any]:
    """
    Non-fatal extraction entrypoint called from ingestion.
    Returns summary for logging/debugging.
    """
    if not is_persona_extraction_enabled():
        return {"enabled": False, "reason": "flag_off"}

    try:
        source_metadata = _get_source_metadata(source_id)
        source_metadata["provider"] = provider
        extraction_payload = extract_persona_facts(
            source_id=source_id,
            text=text,
            source_metadata=source_metadata,
        )

        stored = store_extraction_candidates(
            twin_id=twin_id,
            source_id=source_id,
            extraction_payload=extraction_payload,
        )

        profile_patch = build_profile_patch_from_extraction(extraction_payload)
        if profile_patch:
            profile_patch.setdefault("twin_id", twin_id)
            profile_patch.setdefault("profile_status", "draft")
            upsert_persona_profile(twin_id, profile_patch, merge=True)

        low_confidence_items = collect_low_confidence_facts(extraction_payload, threshold=0.65)
        if low_confidence_items:
            enqueue_owner_review_item(
                twin_id=twin_id,
                tenant_id=_get_twin_tenant_id(twin_id),
                conversation_id=None,
                message_id=None,
                routing_decision_id=None,
                reason="persona_extraction_low_confidence",
                priority="medium",
                payload={
                    "source_id": source_id,
                    "low_confidence_facts": low_confidence_items[:20],
                },
            )

        print(
            "[PersonaExtraction] completed "
            f"twin_id={twin_id} source_id={source_id} stored={stored} "
            f"profile_patch_keys={sorted(profile_patch.keys()) if profile_patch else []} "
            f"low_confidence_count={len(low_confidence_items)}"
        )
        return {
            "enabled": True,
            "stored_candidates": stored,
            "profile_patch_keys": sorted(profile_patch.keys()) if profile_patch else [],
            "low_confidence_count": len(low_confidence_items),
        }
    except Exception as e:
        print(f"[PersonaExtraction] failed twin_id={twin_id} source_id={source_id}: {e}")
        return {"enabled": True, "error": str(e)}
