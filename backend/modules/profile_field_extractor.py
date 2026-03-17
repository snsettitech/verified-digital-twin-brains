"""
Profile Field Extractor

Extracts structured profile pack fields from unstructured source text
(resume PDFs, personal websites, pasted bios) using a lightweight LLM call.

Used after Mode A/B/C ingestion to also update the profile pack — not just Pinecone.

Public API:
    extract_profile_fields(text, source_type, existing_profile) -> dict
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

SourceType = Literal["resume", "website", "paste"]

# Confidence score assigned per source type (used in merge decisions)
_CONFIDENCE_BY_SOURCE: Dict[str, float] = {
    "resume":  0.60,
    "website": 0.55,
    "paste":   0.50,
}

_EXTRACTION_PROMPT = """\
You are extracting structured profile information from the text below.
Return ONLY a valid JSON object. Extract only what is clearly present in the text.
Do NOT invent, guess, or infer values that aren't stated. Use null for missing fields.

Source type: {source_type}

Text to extract from (first 4000 chars):
---
{text}
---

Return this exact JSON shape:
{{
  "display_name": "Full name of the person or null",
  "headline": "One-line title/role e.g. 'Senior Engineer at Acme' or null",
  "bio": "A 2-4 sentence biography paragraph or null",
  "short_description": "One sentence summary or null",
  "role": "Current job title/role or null",
  "organization": "Current employer/company or null",
  "birth_year": 1980,
  "nationality": "Country of nationality or null",
  "areas_of_expertise": ["topic1", "topic2"],
  "work_experience": [
    {{
      "company": "Company name",
      "role": "Job title",
      "description": "What they did (1 sentence) or null",
      "start_year": 2018,
      "end_year": null
    }}
  ],
  "education": [
    {{
      "institution": "University name",
      "degree": "Degree type e.g. BSc, MBA",
      "field": "Field of study",
      "end_year": 2010
    }}
  ]
}}

Rules:
- Return ONLY the JSON object, no markdown, no commentary
- areas_of_expertise: max 6 items, short phrases only
- work_experience: max 5 most recent jobs
- education: max 3 entries
- If a field is truly not present in the text, use null (not empty string)
- birth_year and end_year/start_year must be integers or null
"""


def _clean_extraction_output(raw: str) -> Optional[Dict[str, Any]]:
    """Strip markdown fences and parse JSON."""
    text = raw.strip()
    # Remove ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find first { ... } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _validate_field(value: Any, expected_type: type) -> bool:
    if value is None:
        return True
    return isinstance(value, expected_type)


def _safe_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_string_list(value: Any, limit: int = 6) -> List[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        s = _safe_string(item)
        if s and len(result) < limit:
            result.append(s)
    return result


def _safe_work_list(value: Any, limit: int = 5) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        entry = {
            "company":     _safe_string(item.get("company")),
            "role":        _safe_string(item.get("role")),
            "description": _safe_string(item.get("description")),
            "start_year":  _safe_int(item.get("start_year")),
            "end_year":    _safe_int(item.get("end_year")),
        }
        # Skip entirely empty entries
        if not entry["company"] and not entry["role"]:
            continue
        result.append(entry)
        if len(result) >= limit:
            break
    return result


def _safe_edu_list(value: Any, limit: int = 3) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        entry = {
            "institution": _safe_string(item.get("institution")),
            "degree":      _safe_string(item.get("degree")),
            "field":       _safe_string(item.get("field")),
            "end_year":    _safe_int(item.get("end_year")),
        }
        if not entry["institution"] and not entry["degree"]:
            continue
        result.append(entry)
        if len(result) >= limit:
            break
    return result


async def extract_profile_fields(
    text: str,
    source_type: SourceType,
    existing_profile: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to extract structured profile fields from unstructured text.

    Returns a dict of extracted fields (only non-null values), or None if
    extraction fails or yields nothing useful.

    Args:
        text:             Raw text content (resume, website, paste).
        source_type:      One of 'resume', 'website', 'paste'.
        existing_profile: Current public_profile — used to skip already-filled fields.

    Returns:
        Dict with some/all of: display_name, headline, bio, short_description,
        role, organization, birth_year, nationality, areas_of_expertise,
        work_experience, education — plus a 'confidence' float.
    """
    from modules.inference_router import invoke_json

    existing = existing_profile or {}

    # If profile is already well-populated, skip extraction
    filled_fields = sum(1 for f in [
        "display_name", "bio", "role", "organization", "work_experience"
    ] if existing.get(f))
    if filled_fields >= 4:
        logger.debug(
            "profile_field_extractor: skipping extraction — profile already populated (%d/5 fields)",
            filled_fields,
        )
        return None

    prompt = _EXTRACTION_PROMPT.format(
        source_type=source_type,
        text=text[:4000],
    )

    try:
        raw, _meta = await invoke_json(
            [{"role": "user", "content": prompt}],
            task="extraction",
            temperature=0.0,
            max_tokens=1200,
        )
        data = raw if isinstance(raw, dict) else _clean_extraction_output(str(raw))
    except Exception as exc:
        logger.warning("profile_field_extractor: LLM call failed: %s", exc)
        return None

    if not data:
        logger.warning("profile_field_extractor: could not parse LLM output")
        return None

    confidence = _CONFIDENCE_BY_SOURCE.get(source_type, 0.50)

    # Build cleaned result — only include non-null values
    result: Dict[str, Any] = {"confidence": confidence}

    for field in ("display_name", "headline", "bio", "short_description", "role", "organization", "nationality"):
        val = _safe_string(data.get(field))
        if val:
            result[field] = val

    birth_year = _safe_int(data.get("birth_year"))
    if birth_year and 1900 < birth_year < 2010:
        result["birth_year"] = birth_year

    expertise = _safe_string_list(data.get("areas_of_expertise"), limit=6)
    if expertise:
        result["areas_of_expertise"] = expertise

    work_exp = _safe_work_list(data.get("work_experience"), limit=5)
    if work_exp:
        result["work_experience"] = work_exp

    education = _safe_edu_list(data.get("education"), limit=3)
    if education:
        result["education"] = education

    # Return None if nothing useful was extracted
    meaningful_fields = [k for k in result if k != "confidence"]
    if not meaningful_fields:
        logger.debug("profile_field_extractor: extraction yielded no useful fields")
        return None

    logger.info(
        "profile_field_extractor: extracted %d fields from %s (confidence=%.2f)",
        len(meaningful_fields), source_type, confidence,
    )
    return result
