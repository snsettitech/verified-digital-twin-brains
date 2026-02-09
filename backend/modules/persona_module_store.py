"""
Persona Module Store

Runtime retrieval of intent-scoped procedural modules derived from owner
training events (Phase 3).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.observability import supabase
from modules.persona_intents import normalize_intent_label
from modules.persona_spec import ProceduralModule


def _normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _normalize_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _row_to_module(row: Dict[str, Any]) -> Optional[ProceduralModule]:
    module_id = str(row.get("module_id") or "").strip()
    if not module_id:
        return None

    module_data = _normalize_mapping(row.get("module_data"))
    row_intent = row.get("intent_label")
    when = _normalize_mapping(module_data.get("when"))
    do = _normalize_string_list(module_data.get("do"))
    say_style = _normalize_mapping(module_data.get("say_style"))
    ban = _normalize_string_list(module_data.get("ban"))
    few_shot_ids = _normalize_string_list(module_data.get("few_shot_ids"))

    intent_labels = _normalize_string_list(module_data.get("intent_labels"))
    if row_intent:
        intent_labels.append(str(row_intent))
    if when.get("intent_label"):
        intent_labels.append(str(when["intent_label"]))
    intent_labels = list(dict.fromkeys([normalize_intent_label(v) for v in intent_labels if v]))

    raw_priority = module_data.get("priority", 90)
    try:
        priority = int(raw_priority)
    except Exception:
        priority = 90

    try:
        return ProceduralModule(
            id=module_id,
            intent_labels=intent_labels,
            when=when,
            do=do,
            say_style=say_style,
            ban=ban,
            few_shot_ids=few_shot_ids,
            priority=priority,
            active=True,
        )
    except Exception as e:
        print(f"[PersonaModuleStore] invalid runtime module {module_id}: {e}")
        return None


def _intent_matches(module: ProceduralModule, intent_label: str) -> bool:
    if not module.intent_labels:
        return True
    return intent_label in module.intent_labels


def list_runtime_modules_for_intent(
    *,
    twin_id: str,
    intent_label: str,
    limit: int = 8,
    include_draft: bool = True,
    min_confidence: float = 0.65,
) -> List[ProceduralModule]:
    """
    Returns runtime procedural modules for the selected intent.
    """
    normalized_intent = normalize_intent_label(intent_label)
    statuses = ["active"]
    if include_draft:
        statuses.append("draft")

    try:
        query = (
            supabase.table("persona_modules")
            .select("module_id,intent_label,module_data,status,confidence,created_at")
            .eq("twin_id", twin_id)
            .in_("status", statuses)
            .or_(f"intent_label.eq.{normalized_intent},intent_label.is.null")
            .order("confidence", desc=True)
            .order("created_at", desc=True)
            .limit(max(limit * 3, 20))
        )
        if min_confidence is not None:
            query = query.gte("confidence", min_confidence)
        res = query.execute()
        rows = res.data or []
    except Exception as e:
        print(f"[PersonaModuleStore] fetch failed: {e}")
        return []

    merged: Dict[str, ProceduralModule] = {}
    for row in rows:
        module = _row_to_module(row)
        if not module:
            continue
        if not _intent_matches(module, normalized_intent):
            continue
        if module.id not in merged:
            merged[module.id] = module

    modules = sorted(merged.values(), key=lambda m: (m.priority, m.id))
    return modules[:limit]

