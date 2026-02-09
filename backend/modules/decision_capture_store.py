"""
Decision Capture Store

Stores SJT, pairwise, and introspection training signals and derives draft procedural modules.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha1
from typing import Any, Dict, Optional
import re

from modules.observability import supabase


def _stable_clause_id(prefix: str, basis: str) -> str:
    digest = sha1((basis or "").encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}_{digest}"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", (value or "").strip().lower())
    return cleaned.strip("_") or "generic"


def _insert_module_candidate(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    owner_id: str,
    training_session_id: str,
    source_event_type: str,
    source_event_id: str,
    module_id: str,
    intent_label: Optional[str],
    module_data: Dict[str, Any],
    confidence: float = 0.7,
) -> Optional[Dict[str, Any]]:
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "training_session_id": training_session_id,
        "source_event_type": source_event_type,
        "source_event_id": source_event_id,
        "module_id": module_id,
        "intent_label": intent_label,
        "module_data": module_data,
        "status": "draft",
        "confidence": confidence,
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        res = supabase.table("persona_modules").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[DecisionCapture] module insert failed: {e}")
        return None


def record_sjt_capture(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    owner_id: str,
    training_session_id: str,
    scenario_id: Optional[str],
    intent_label: Optional[str],
    prompt: str,
    options: list[Dict[str, Any]],
    selected_option: str,
    rationale: Optional[str],
    thresholds: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    clause_id = _stable_clause_id(
        "POL_DECISION",
        f"{scenario_id}|{intent_label}|{selected_option}|{rationale}",
    )
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "training_session_id": training_session_id,
        "scenario_id": scenario_id,
        "intent_label": intent_label,
        "prompt": prompt,
        "options": options or [],
        "selected_option": selected_option,
        "rationale": rationale,
        "thresholds": thresholds or {},
        "clause_ids": [clause_id],
        "metadata": metadata or {},
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        res = supabase.table("persona_decision_traces").insert(payload).execute()
        event = res.data[0] if res.data else None
        if not event:
            return None
    except Exception as e:
        print(f"[DecisionCapture] sjt insert failed: {e}")
        return None

    module_id = f"procedural.decision.{_slug(intent_label or scenario_id or selected_option)}"
    module_data = {
        "when": {"intent_label": intent_label, "scenario_id": scenario_id, **(thresholds or {})},
        "do": [f"prefer_option:{selected_option}"],
        "say_style": {"rationale_required": True},
        "ban": [],
        "clause_ids": [clause_id],
    }
    module = _insert_module_candidate(
        twin_id=twin_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        training_session_id=training_session_id,
        source_event_type="sjt",
        source_event_id=event["id"],
        module_id=module_id,
        intent_label=intent_label,
        module_data=module_data,
        confidence=0.75,
    )
    return {"event": event, "module": module, "clause_ids": [clause_id]}


def record_pairwise_capture(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    owner_id: str,
    training_session_id: str,
    intent_label: Optional[str],
    prompt: str,
    candidate_a: Dict[str, Any],
    candidate_b: Dict[str, Any],
    preferred: str,
    rationale: Optional[str],
    metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    clause_id = _stable_clause_id(
        "POL_STYLE",
        f"{intent_label}|{preferred}|{candidate_a}|{candidate_b}|{rationale}",
    )
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "training_session_id": training_session_id,
        "intent_label": intent_label,
        "prompt": prompt,
        "candidate_a": candidate_a,
        "candidate_b": candidate_b,
        "preferred": preferred,
        "rationale": rationale,
        "clause_ids": [clause_id],
        "metadata": metadata or {},
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        res = supabase.table("persona_preferences").insert(payload).execute()
        event = res.data[0] if res.data else None
        if not event:
            return None
    except Exception as e:
        print(f"[DecisionCapture] pairwise insert failed: {e}")
        return None

    preferred_key = "a" if preferred == "a" else "b"
    preferred_text = (candidate_a if preferred_key == "a" else candidate_b).get("text", "")
    module_id = f"procedural.style.{_slug(intent_label or 'generic')}"
    module_data = {
        "when": {"intent_label": intent_label},
        "do": [f"prefer_response_variant:{preferred_key}"],
        "say_style": {"preferred_signal": preferred_text[:400]},
        "ban": [],
        "clause_ids": [clause_id],
    }
    module = _insert_module_candidate(
        twin_id=twin_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        training_session_id=training_session_id,
        source_event_type="pairwise",
        source_event_id=event["id"],
        module_id=module_id,
        intent_label=intent_label,
        module_data=module_data,
        confidence=0.7,
    )
    return {"event": event, "module": module, "clause_ids": [clause_id]}


def record_introspection_capture(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    owner_id: str,
    training_session_id: str,
    intent_label: Optional[str],
    question: str,
    answer: str,
    thresholds: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    clause_id = _stable_clause_id(
        "POL_PROCESS",
        f"{intent_label}|{question}|{answer}|{thresholds}",
    )
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "training_session_id": training_session_id,
        "intent_label": intent_label,
        "question": question,
        "answer": answer,
        "thresholds": thresholds or {},
        "clause_ids": [clause_id],
        "metadata": metadata or {},
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        res = supabase.table("persona_introspection").insert(payload).execute()
        event = res.data[0] if res.data else None
        if not event:
            return None
    except Exception as e:
        print(f"[DecisionCapture] introspection insert failed: {e}")
        return None

    module_id = f"procedural.process.{_slug(intent_label or 'generic')}"
    module_data = {
        "when": {"intent_label": intent_label, **(thresholds or {})},
        "do": [f"follow_process:{answer[:300]}"],
        "say_style": {"process_first": True},
        "ban": [],
        "clause_ids": [clause_id],
    }
    module = _insert_module_candidate(
        twin_id=twin_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        training_session_id=training_session_id,
        source_event_type="introspection",
        source_event_id=event["id"],
        module_id=module_id,
        intent_label=intent_label,
        module_data=module_data,
        confidence=0.68,
    )
    return {"event": event, "module": module, "clause_ids": [clause_id]}
