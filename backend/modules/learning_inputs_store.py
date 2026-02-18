"""
Learning Inputs store and application logic.

Learning inputs are typed owner corrections that update Twin behavior through
versioned persona specs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from copy import deepcopy

from modules.observability import supabase
from modules.persona_spec import PersonaSpec
from modules.persona_spec_store import (
    create_persona_spec,
    get_active_persona_spec,
    get_next_spec_version,
    get_persona_spec,
)


INPUT_TYPES = {
    "add_faq_answer",
    "add_adjust_rubric_rule",
    "add_workflow_step_template",
    "add_guardrail_refusal_rule",
    "add_style_preference",
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def list_learning_inputs(
    *,
    twin_id: str,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    try:
        query = supabase.table("learning_inputs").select("*").eq("twin_id", twin_id)
        if status and status != "all":
            query = query.eq("status", status)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        print(f"[LearningInputs] list failed: {e}")
        return []


def create_learning_input(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    created_by: Optional[str],
    input_type: str,
    payload: Dict[str, Any],
    base_persona_spec_version: Optional[str] = None,
    source_conversation_id: Optional[str] = None,
    source_message_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    input_type = (input_type or "").strip()
    if input_type not in INPUT_TYPES:
        raise ValueError(f"Unsupported learning input type: {input_type}")

    row = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "created_by": created_by,
        "base_persona_spec_version": base_persona_spec_version,
        "input_type": input_type,
        "payload": payload or {},
        "status": "pending",
        "source_conversation_id": source_conversation_id,
        "source_message_id": source_message_id,
        "updated_at": _now_iso(),
    }
    try:
        res = supabase.table("learning_inputs").insert(row).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[LearningInputs] create failed: {e}")
        return None


def _resolve_base_spec_payload(
    *,
    twin_id: str,
    base_persona_spec_version: Optional[str],
) -> Dict[str, Any]:
    if base_persona_spec_version:
        row = get_persona_spec(twin_id=twin_id, version=base_persona_spec_version)
    else:
        row = get_active_persona_spec(twin_id=twin_id)
    if not row:
        raise ValueError("No base persona spec available for this twin")
    spec_payload = row.get("spec")
    if not isinstance(spec_payload, dict):
        raise ValueError("Base persona spec payload is invalid")
    return deepcopy(spec_payload)


def _apply_style_preference(spec_payload: Dict[str, Any], payload: Dict[str, Any]) -> None:
    if payload.get("identity_voice") and not payload.get("allow_persona_fundamental_change"):
        raise ValueError(
            "Style preference cannot modify identity_voice without explicit allow_persona_fundamental_change=true"
        )

    interaction_style = spec_payload.setdefault("interaction_style", {})
    if not isinstance(interaction_style, dict):
        interaction_style = {}
        spec_payload["interaction_style"] = interaction_style

    allowed_keys = {
        "tone_sliders",
        "phrasing_preferences",
        "do_not_say",
        "summarization_pattern",
        "pushback_style",
        "brevity_default",
        "structure_default",
        "disagreement_style",
    }
    for key, value in payload.items():
        if key in {"allow_persona_fundamental_change", "identity_voice"}:
            continue
        if key in allowed_keys:
            interaction_style[key] = value

    if payload.get("allow_persona_fundamental_change") and isinstance(payload.get("identity_voice"), dict):
        identity_voice = spec_payload.setdefault("identity_voice", {})
        if isinstance(identity_voice, dict):
            identity_voice.update(payload["identity_voice"])


def _apply_learning_input_to_spec_payload(
    *,
    spec_payload: Dict[str, Any],
    input_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    out = deepcopy(spec_payload)

    if input_type == "add_faq_answer":
        rows = out.setdefault("faq_library", [])
        if not isinstance(rows, list):
            rows = []
            out["faq_library"] = rows
        rows.append(
            {
                "question": str(payload.get("question") or "").strip(),
                "answer": str(payload.get("answer") or "").strip(),
                "template": payload.get("template"),
            }
        )
        return out

    if input_type == "add_adjust_rubric_rule":
        decision_policy = out.setdefault("decision_policy", {})
        if not isinstance(decision_policy, dict):
            decision_policy = {}
            out["decision_policy"] = decision_policy
        rules = decision_policy.setdefault("rubric_rules", [])
        if not isinstance(rules, list):
            rules = []
            decision_policy["rubric_rules"] = rules
        rules.append(payload)
        return out

    if input_type == "add_workflow_step_template":
        workflow_library = out.setdefault("workflow_library", {})
        if not isinstance(workflow_library, dict):
            workflow_library = {}
            out["workflow_library"] = workflow_library
        workflow_name = str(payload.get("workflow") or "answer").strip() or "answer"
        wf = workflow_library.setdefault(workflow_name, {})
        if not isinstance(wf, dict):
            wf = {}
            workflow_library[workflow_name] = wf
        steps = wf.setdefault("steps", [])
        if not isinstance(steps, list):
            steps = []
            wf["steps"] = steps
        step = str(payload.get("step") or "").strip()
        if step:
            steps.append(step)
        template = str(payload.get("template") or "").strip()
        if template:
            wf["template"] = template
        required_inputs = payload.get("required_inputs")
        if isinstance(required_inputs, list):
            wf["required_inputs"] = [str(v).strip() for v in required_inputs if str(v).strip()]
        output_schema = str(payload.get("output_schema") or "").strip()
        if output_schema:
            wf["output_schema"] = output_schema
        return out

    if input_type == "add_guardrail_refusal_rule":
        guardrails = out.setdefault("guardrails", {})
        if not isinstance(guardrails, dict):
            guardrails = {}
            out["guardrails"] = guardrails
        for field in (
            "forbidden_topics",
            "refusal_templates",
            "confidentiality_rules",
            "conflict_rules",
        ):
            values = payload.get(field)
            if isinstance(values, list):
                existing = guardrails.setdefault(field, [])
                if not isinstance(existing, list):
                    existing = []
                    guardrails[field] = existing
                existing.extend([str(v).strip() for v in values if str(v).strip()])
        for scalar in ("uncertainty_rule", "escalation_rule"):
            value = str(payload.get(scalar) or "").strip()
            if value:
                guardrails[scalar] = value
        return out

    if input_type == "add_style_preference":
        _apply_style_preference(out, payload)
        return out

    raise ValueError(f"Unsupported learning input type: {input_type}")


def _update_learning_input_status(
    *,
    learning_input_id: str,
    status: str,
    applied_persona_spec_version: Optional[str] = None,
    review_note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "status": status,
        "updated_at": _now_iso(),
    }
    if applied_persona_spec_version:
        payload["applied_persona_spec_version"] = applied_persona_spec_version
        payload["applied_at"] = _now_iso()
    if review_note:
        payload["review_note"] = review_note
    try:
        res = supabase.table("learning_inputs").update(payload).eq("id", learning_input_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[LearningInputs] status update failed: {e}")
        return None


def apply_learning_input_to_new_spec(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    created_by: Optional[str],
    learning_input_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    res = supabase.table("learning_inputs").select("*").eq("id", learning_input_id).single().execute()
    learning_input = res.data if res.data else None
    if not learning_input:
        raise ValueError("Learning input not found")
    if learning_input.get("twin_id") != twin_id:
        raise ValueError("Learning input does not belong to twin")
    if learning_input.get("status") != "pending":
        raise ValueError("Learning input is not pending")

    base_version = learning_input.get("base_persona_spec_version")
    spec_payload = _resolve_base_spec_payload(
        twin_id=twin_id,
        base_persona_spec_version=base_version,
    )
    updated_spec_payload = _apply_learning_input_to_spec_payload(
        spec_payload=spec_payload,
        input_type=str(learning_input.get("input_type")),
        payload=learning_input.get("payload") if isinstance(learning_input.get("payload"), dict) else {},
    )
    updated_spec_payload["version"] = get_next_spec_version(twin_id=twin_id)

    validated = PersonaSpec.model_validate(updated_spec_payload)
    row = create_persona_spec(
        twin_id=twin_id,
        tenant_id=tenant_id,
        created_by=created_by or learning_input.get("created_by"),
        spec=validated,
        status="draft",
        source="learning_input",
        notes=notes or f"Applied learning input {learning_input_id}",
    )
    if not row:
        raise ValueError("Failed to create draft persona spec from learning input")

    _update_learning_input_status(
        learning_input_id=learning_input_id,
        status="applied",
        applied_persona_spec_version=validated.version,
        review_note=notes,
    )
    return {
        "learning_input": learning_input,
        "persona_spec": row,
        "new_version": validated.version,
    }


def reject_learning_input(
    *,
    learning_input_id: str,
    review_note: Optional[str],
) -> Optional[Dict[str, Any]]:
    return _update_learning_input_status(
        learning_input_id=learning_input_id,
        status="rejected",
        review_note=review_note,
    )

