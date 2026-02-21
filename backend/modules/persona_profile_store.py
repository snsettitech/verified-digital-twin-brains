"""
Persona profile persistence helpers.

Storage strategy:
- Canonical profile + extraction candidates are stored in twins.settings
- This keeps rollout migration-free and backward compatible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.observability import supabase


PERSONA_PROFILE_SETTINGS_KEY = "persona_identity_pack"
PERSONA_EXTRACTION_CANDIDATES_KEY = "persona_extraction_candidates"


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _get_twin_row(twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        row = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
        if row and isinstance(row.data, dict):
            return row.data
    except Exception:
        pass

    try:
        row = supabase.table("twins").select("id,tenant_id,settings").eq("id", twin_id).single().execute()
        if row and isinstance(row.data, dict):
            return row.data
    except Exception:
        return None
    return None


def _get_settings_for_twin(twin_id: str) -> Dict[str, Any]:
    row = _get_twin_row(twin_id)
    return _safe_dict((row or {}).get("settings"))


def _update_twin_settings(twin_id: str, settings: Dict[str, Any]) -> bool:
    try:
        supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
        return True
    except Exception as e:
        print(f"[PersonaProfileStore] Failed to update twins.settings for {twin_id}: {e}")
        return False


def get_persona_profile(twin_id: str) -> Optional[Dict[str, Any]]:
    settings = _get_settings_for_twin(twin_id)
    profile = settings.get(PERSONA_PROFILE_SETTINGS_KEY)
    if not isinstance(profile, dict):
        return None
    return profile


def is_profile_eligible_for_fastpath(profile: Dict[str, Any], allow_draft: bool = False) -> bool:
    if not isinstance(profile, dict):
        return False
    status = str(profile.get("profile_status") or "draft").strip().lower()
    if status == "approved":
        return True
    if allow_draft and status == "draft":
        return True
    return False


def upsert_persona_profile(
    twin_id: str,
    patch: Dict[str, Any],
    *,
    merge: bool = True,
) -> Optional[Dict[str, Any]]:
    if not isinstance(patch, dict):
        return None

    settings = _get_settings_for_twin(twin_id)
    existing = _safe_dict(settings.get(PERSONA_PROFILE_SETTINGS_KEY))
    base = dict(existing) if merge else {}
    base.update({k: v for k, v in patch.items() if v is not None})

    base.setdefault("twin_id", twin_id)
    base.setdefault("profile_status", "draft")
    base.setdefault("social_links", {})
    base.setdefault("expertise_areas", [])
    base.setdefault("tone_tags", [])
    base["updated_at"] = _utc_now_iso()

    settings[PERSONA_PROFILE_SETTINGS_KEY] = base
    if not _update_twin_settings(twin_id, settings):
        return None
    return base


def store_extraction_candidates(
    twin_id: str,
    source_id: str,
    extraction_payload: Dict[str, Any],
) -> bool:
    if not isinstance(extraction_payload, dict):
        return False

    settings = _get_settings_for_twin(twin_id)
    blob = _safe_dict(settings.get(PERSONA_EXTRACTION_CANDIDATES_KEY))
    by_source = _safe_dict(blob.get("by_source"))

    by_source[str(source_id)] = extraction_payload
    blob["by_source"] = by_source
    blob["updated_at"] = _utc_now_iso()

    settings[PERSONA_EXTRACTION_CANDIDATES_KEY] = blob
    return _update_twin_settings(twin_id, settings)


def _best_candidate(facts: Dict[str, Any], field_name: str) -> Optional[Dict[str, Any]]:
    candidates = _safe_list(facts.get(field_name))
    if not candidates:
        return None
    best = None
    best_score = -1.0
    for item in candidates:
        if not isinstance(item, dict):
            continue
        score = float(item.get("confidence") or 0.0)
        if score > best_score:
            best = item
            best_score = score
    return best


def build_profile_patch_from_extraction(
    extraction_payload: Dict[str, Any],
    *,
    min_autopromote_confidence: float = 0.78,
) -> Dict[str, Any]:
    """
    Promote only high-confidence candidates into canonical draft profile.
    Low-confidence candidates remain in candidate storage / owner review queue.
    """
    facts = _safe_dict(extraction_payload.get("facts"))
    patch: Dict[str, Any] = {}

    def _take_str(field_name: str, target_key: str):
        item = _best_candidate(facts, field_name)
        if not item:
            return
        value = str(item.get("value") or "").strip()
        conf = float(item.get("confidence") or 0.0)
        if value and conf >= min_autopromote_confidence:
            patch[target_key] = value

    _take_str("full_name", "display_name")
    _take_str("one_line_intro", "one_line_intro")
    _take_str("short_intro", "short_intro")
    _take_str("disclosure_line", "disclosure_line")
    _take_str("contact_handoff_line", "contact_handoff_line")
    _take_str("preferred_contact_channel", "preferred_contact_channel")

    expertise_best = _best_candidate(facts, "expertise_areas")
    if expertise_best and float(expertise_best.get("confidence") or 0.0) >= min_autopromote_confidence:
        value = expertise_best.get("value")
        if isinstance(value, list):
            patch["expertise_areas"] = [str(v).strip() for v in value if str(v).strip()]

    tone_best = _best_candidate(facts, "tone_tags")
    if tone_best and float(tone_best.get("confidence") or 0.0) >= min_autopromote_confidence:
        value = tone_best.get("value")
        if isinstance(value, list):
            patch["tone_tags"] = [str(v).strip() for v in value if str(v).strip()]

    links_best = _best_candidate(facts, "public_contact_links")
    if links_best and float(links_best.get("confidence") or 0.0) >= min_autopromote_confidence:
        value = links_best.get("value")
        if isinstance(value, dict):
            patch["social_links"] = {
                str(k): str(v).strip()
                for k, v in value.items()
                if str(v).strip()
            }

    return patch


def collect_low_confidence_facts(
    extraction_payload: Dict[str, Any],
    *,
    threshold: float = 0.65,
) -> List[Dict[str, Any]]:
    facts = _safe_dict(extraction_payload.get("facts"))
    out: List[Dict[str, Any]] = []
    for field_name, values in facts.items():
        for item in _safe_list(values):
            if not isinstance(item, dict):
                continue
            score = float(item.get("confidence") or 0.0)
            if score < threshold:
                out.append(
                    {
                        "field": field_name,
                        "value": item.get("value"),
                        "confidence": score,
                        "evidence": item.get("evidence") or [],
                    }
                )
    return out
