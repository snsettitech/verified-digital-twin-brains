"""
Name-only deep research synthesis helpers.

This module intentionally separates tolerant draft parsing + payload
normalization from the strict public response model.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


_CLAIM_TYPES = {
    "credential",
    "experience",
    "role",
    "preference",
    "opinion",
    "project",
    "contact",
    "other",
}
_CLAIM_STATUSES = {"verified", "partially_verified", "unverified", "disputed", "unknown"}


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "value", "content", "summary", "title", "name"):
            if key in value and value.get(key) is not None:
                return str(value.get(key)).strip()
        return ""
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    return ""


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        txt = value.strip().lower()
        if not txt:
            return default
        try:
            return max(0.0, min(1.0, float(txt)))
        except Exception:
            pass
        label_map = {
            "very_high": 0.9,
            "high": 0.8,
            "medium": 0.6,
            "moderate": 0.6,
            "low": 0.35,
            "very_low": 0.2,
            "evidence_based_with_minor_gaps": 0.62,
        }
        if txt in label_map:
            return label_map[txt]
        for token, mapped in label_map.items():
            if token in txt:
                return mapped
    return default


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return default
        try:
            return max(0, int(float(txt)))
        except Exception:
            return default
    return default


def _coerce_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            txt = _extract_text(item)
            if txt:
                out.append(txt)
        return out
    txt = _extract_text(value)
    if not txt:
        return []
    # Split common compressed list patterns while preserving simple strings.
    chunks = [chunk.strip() for chunk in re.split(r"[;\n]|,\s(?=[A-Z0-9])", txt) if chunk.strip()]
    return chunks or [txt]


def _coerce_citations(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                txt = item.strip()
                if txt:
                    out.append(txt)
            elif isinstance(item, dict):
                for key in ("source_id", "citation", "id"):
                    raw = item.get(key)
                    if raw:
                        out.append(str(raw).strip())
                        break
            else:
                out.append(str(item).strip())
        return [x for x in out if x]
    if isinstance(value, str):
        txt = value.strip()
        return [txt] if txt else []
    if isinstance(value, dict):
        for key in ("source_id", "citation", "id"):
            raw = value.get(key)
            if raw:
                return [str(raw).strip()]
    return []


def _coerce_expertise_topics(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []

    items: List[Any]
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        txt = _extract_text(value)
        items = [chunk.strip() for chunk in txt.split(",")] if txt else []
    elif isinstance(value, str):
        items = [chunk.strip() for chunk in value.split(",")] if value.strip() else []
    else:
        return []

    normalized: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            topic = _extract_text(item.get("topic") or item.get("name") or item.get("text"))
            if not topic:
                continue
            normalized.append(
                {
                    "topic": topic,
                    "confidence": _coerce_float(item.get("confidence"), default=0.5),
                    "evidence_count": _coerce_int(item.get("evidence_count"), default=1),
                }
            )
            continue

        topic = _extract_text(item)
        if not topic:
            continue
        normalized.append(
            {
                "topic": topic,
                "confidence": 0.5,
                "evidence_count": 1,
            }
        )
    return normalized


def _normalize_possible_duplicates(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []

    if not isinstance(value, list):
        txt = _extract_text(value)
        value = [txt] if txt else []

    out: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            name = _extract_text(item.get("name") or item.get("person") or item.get("title"))
            reason = _extract_text(item.get("reason") or item.get("note")) or "Possible duplicate identity."
            confidence = _coerce_float(item.get("confidence"), default=0.3)
            if not name:
                continue
            out.append({"name": name, "reason": reason, "confidence": confidence})
            continue
        txt = _extract_text(item)
        if not txt:
            continue
        out.append(
            {
                "name": txt[:200],
                "reason": "Possible duplicate identity from model output.",
                "confidence": 0.3,
            }
        )
    return out


class DraftBioModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    short: Optional[Union[str, Dict[str, Any]]] = None
    medium: Optional[Union[str, Dict[str, Any]]] = None
    long: Optional[Union[str, Dict[str, Any]]] = None


class DraftClaimedIdentityModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    canonical_name: Optional[Any] = None
    is_match_confidence: Optional[Any] = None
    disambiguation_notes: Optional[Any] = None
    possible_duplicates: Optional[Any] = None


class DraftProfileSummaryModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    what_they_do: Optional[Any] = None
    expertise_topics: Optional[Any] = None
    organizations: Optional[Any] = None
    locations: Optional[Any] = None
    public_roles: Optional[Any] = None


class DraftTimelineItemModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    date_or_range: Optional[Any] = Field(default=None, validation_alias=AliasChoices("date_or_range", "date"))
    event: Optional[Any] = Field(default=None, validation_alias=AliasChoices("event", "text"))
    confidence: Optional[Any] = None
    citations: Optional[Any] = Field(default=None, validation_alias=AliasChoices("citations", "source_id"))


class DraftClaimItemModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    claim_id: Optional[Any] = None
    text: Optional[Any] = Field(default=None, validation_alias=AliasChoices("text", "claim"))
    claim_type: Optional[Any] = None
    status: Optional[Any] = None
    confidence: Optional[Any] = None
    citations: Optional[Any] = Field(default=None, validation_alias=AliasChoices("citations", "source_id"))
    notes: Optional[Any] = None


class DraftKnownUnknownModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    question: Optional[Any] = None
    why_missing: Optional[Any] = None


class DraftQualityModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    overall_confidence: Optional[Any] = None
    freshness_score: Optional[Any] = None
    coverage_score: Optional[Any] = None
    hallucination_risk: Optional[Any] = None
    warnings: Optional[Any] = None


class NameDeepResearchDraftModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    claimed_identity: Optional[DraftClaimedIdentityModel] = None
    bio: Optional[DraftBioModel] = None
    profile_summary: Optional[DraftProfileSummaryModel] = None
    timeline: Optional[Union[List[DraftTimelineItemModel], List[Dict[str, Any]], Dict[str, Any], str]] = None
    claims: Optional[Union[List[DraftClaimItemModel], List[Dict[str, Any]], Dict[str, Any], str]] = None
    known_unknowns: Optional[Union[List[DraftKnownUnknownModel], List[Dict[str, Any]], Dict[str, Any], str]] = None
    suggested_followup_questions: Optional[Any] = None
    quality: Optional[DraftQualityModel] = None
    crawl_stats: Optional[Dict[str, Any]] = None


def normalize_name_deep_research_synthesis_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize shape-drifted LLM output into a strict-schema-ready dictionary.
    """
    if not isinstance(raw, dict):
        raw = {}

    draft = NameDeepResearchDraftModel.model_validate(raw)
    source = draft.model_dump(exclude_none=True)

    claimed_identity_raw = source.get("claimed_identity") or {}
    profile_raw = source.get("profile_summary") or {}
    bio_raw = source.get("bio") or {}
    quality_raw = source.get("quality") or {}

    normalized: Dict[str, Any] = {
        "claimed_identity": {
            "canonical_name": _extract_text(claimed_identity_raw.get("canonical_name")),
            "is_match_confidence": _coerce_float(claimed_identity_raw.get("is_match_confidence"), default=0.0),
            "disambiguation_notes": _coerce_string_list(claimed_identity_raw.get("disambiguation_notes")),
            "possible_duplicates": _normalize_possible_duplicates(claimed_identity_raw.get("possible_duplicates")),
        },
        "bio": {
            "short": _extract_text(bio_raw.get("short")),
            "medium": _extract_text(bio_raw.get("medium")),
            "long": _extract_text(bio_raw.get("long")),
        },
        "profile_summary": {
            "what_they_do": _coerce_string_list(profile_raw.get("what_they_do")),
            "expertise_topics": _coerce_expertise_topics(profile_raw.get("expertise_topics")),
            "organizations": _coerce_string_list(profile_raw.get("organizations")),
            "locations": _coerce_string_list(profile_raw.get("locations")),
            "public_roles": _coerce_string_list(profile_raw.get("public_roles")),
        },
        "timeline": [],
        "claims": [],
        "known_unknowns": [],
        "suggested_followup_questions": _coerce_string_list(source.get("suggested_followup_questions")),
        "quality": {
            "overall_confidence": _coerce_float(quality_raw.get("overall_confidence"), default=0.0),
            "freshness_score": _coerce_float(quality_raw.get("freshness_score"), default=0.0),
            "coverage_score": _coerce_float(quality_raw.get("coverage_score"), default=0.0),
            "hallucination_risk": (
                str(quality_raw.get("hallucination_risk") or "high").strip().lower()
                if str(quality_raw.get("hallucination_risk") or "").strip().lower() in {"low", "medium", "high"}
                else "high"
            ),
            "warnings": _coerce_string_list(quality_raw.get("warnings")),
        },
    }

    timeline_raw = source.get("timeline")
    timeline_items: List[Any]
    if isinstance(timeline_raw, list):
        timeline_items = timeline_raw
    elif timeline_raw is None:
        timeline_items = []
    else:
        timeline_items = [timeline_raw]

    for item in timeline_items:
        if not isinstance(item, dict):
            continue
        date_or_range = _extract_text(item.get("date_or_range") or item.get("date"))
        event = _extract_text(item.get("event") or item.get("text"))
        citations = _coerce_citations(item.get("citations") if "citations" in item else item.get("source_id"))
        if not date_or_range or not event or not citations:
            continue
        normalized["timeline"].append(
            {
                "date_or_range": date_or_range,
                "event": event,
                "confidence": _coerce_float(item.get("confidence"), default=0.5),
                "citations": citations,
            }
        )

    claims_raw = source.get("claims")
    claim_items: List[Any]
    if isinstance(claims_raw, list):
        claim_items = claims_raw
    elif claims_raw is None:
        claim_items = []
    else:
        claim_items = [claims_raw]

    for idx, item in enumerate(claim_items, start=1):
        if not isinstance(item, dict):
            continue
        citations = _coerce_citations(item.get("citations") if "citations" in item else item.get("source_id"))
        text = _extract_text(item.get("text") or item.get("claim"))
        if not text or not citations:
            continue
        claim_type = str(item.get("claim_type") or "other").strip().lower()
        if claim_type not in _CLAIM_TYPES:
            claim_type = "other"
        status = str(item.get("status") or "unknown").strip().lower()
        if status not in _CLAIM_STATUSES:
            status = "unknown"
        normalized["claims"].append(
            {
                "claim_id": _extract_text(item.get("claim_id")) or f"claim_{idx}",
                "text": text,
                "claim_type": claim_type,
                "status": status,
                "confidence": _coerce_float(item.get("confidence"), default=0.5),
                "citations": citations,
                "notes": _extract_text(item.get("notes")),
            }
        )

    unknowns_raw = source.get("known_unknowns")
    unknown_items: List[Any]
    if isinstance(unknowns_raw, list):
        unknown_items = unknowns_raw
    elif unknowns_raw is None:
        unknown_items = []
    else:
        unknown_items = [unknowns_raw]

    for item in unknown_items:
        if isinstance(item, dict):
            q = _extract_text(item.get("question"))
            w = _extract_text(item.get("why_missing"))
            if q and w:
                normalized["known_unknowns"].append({"question": q, "why_missing": w})
                continue
        txt = _extract_text(item)
        if txt:
            normalized["known_unknowns"].append({"question": txt, "why_missing": "Missing grounding details."})

    return normalized

