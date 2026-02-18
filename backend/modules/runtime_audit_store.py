"""
Persistence helpers for routing decisions, response audits, and owner review queue.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.observability import supabase


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def persist_routing_decision(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    message_id: Optional[str],
    interaction_context: Optional[str],
    router_mode: Optional[str],
    decision: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "interaction_context": interaction_context,
        "router_mode": router_mode,
        "intent": str(decision.get("intent") or "answer"),
        "confidence": float(decision.get("confidence") or 0.0),
        "required_inputs_missing": decision.get("required_inputs_missing") or [],
        "chosen_workflow": str(decision.get("chosen_workflow") or "answer"),
        "output_schema": str(decision.get("output_schema") or "workflow.answer.v1"),
        "action": str(decision.get("action") or "answer"),
        "clarifying_questions": decision.get("clarifying_questions") or [],
        "metadata": metadata or {},
    }
    try:
        res = supabase.table("conversation_routing_decisions").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[RuntimeAudit] persist_routing_decision failed: {e}")
        return None


def persist_response_audit(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    assistant_message_id: Optional[str],
    routing_decision_id: Optional[str],
    spec_version: Optional[str],
    prompt_variant: Optional[str],
    intent_label: Optional[str],
    workflow_intent: Optional[str],
    response_action: str,
    confidence_score: Optional[float],
    citations: Optional[List[str]],
    sources_used: Optional[List[Dict[str, Any]]],
    refusal_reason: Optional[str],
    escalation_reason: Optional[str],
    retrieval_summary: Optional[Dict[str, Any]],
    artifacts_used: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "assistant_message_id": assistant_message_id,
        "routing_decision_id": routing_decision_id,
        "spec_version": spec_version,
        "prompt_variant": prompt_variant,
        "intent_label": intent_label,
        "workflow_intent": workflow_intent,
        "response_action": response_action,
        "confidence_score": confidence_score,
        "citations": citations or [],
        "sources_used": sources_used or [],
        "refusal_reason": refusal_reason,
        "escalation_reason": escalation_reason,
        "retrieval_summary": retrieval_summary or {},
        "artifacts_used": artifacts_used or {},
    }
    try:
        res = supabase.table("conversation_response_audits").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[RuntimeAudit] persist_response_audit failed: {e}")
        return None


def enqueue_owner_review_item(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    message_id: Optional[str],
    routing_decision_id: Optional[str],
    reason: str,
    priority: str = "medium",
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    row = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "routing_decision_id": routing_decision_id,
        "reason": reason,
        "priority": priority,
        "status": "pending",
        "payload": payload or {},
        "updated_at": _now_iso(),
    }
    try:
        res = supabase.table("owner_review_queue").insert(row).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[RuntimeAudit] enqueue_owner_review_item failed: {e}")
        return None


def list_owner_review_queue(
    *,
    twin_id: str,
    status: Optional[str] = "pending",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    try:
        query = supabase.table("owner_review_queue").select("*").eq("twin_id", twin_id)
        if status and status != "all":
            query = query.eq("status", status)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        print(f"[RuntimeAudit] list_owner_review_queue failed: {e}")
        return []


def resolve_owner_review_queue_item(
    *,
    item_id: str,
    status: str,
    resolved_by: Optional[str],
    review_note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    update_payload: Dict[str, Any] = {
        "status": status,
        "updated_at": _now_iso(),
        "resolved_by": resolved_by,
    }
    if status in {"resolved", "dismissed"}:
        update_payload["resolved_at"] = _now_iso()
    if review_note:
        update_payload["payload"] = {"review_note": review_note}
    try:
        res = supabase.table("owner_review_queue").update(update_payload).eq("id", item_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[RuntimeAudit] resolve_owner_review_queue_item failed: {e}")
        return None

