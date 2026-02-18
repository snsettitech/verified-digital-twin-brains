from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from modules.auth_guard import verify_owner, verify_twin_ownership, ensure_twin_active
from modules.learning_inputs_store import (
    apply_learning_input_to_new_spec,
    create_learning_input,
    list_learning_inputs,
    reject_learning_input,
)
from modules.persona_spec_store import get_active_persona_spec
from modules.runtime_audit_store import list_owner_review_queue, resolve_owner_review_queue_item
from modules.twin_spec_contract import build_twin_spec_from_persona_spec_row


router = APIRouter(tags=["twin-runtime"])


class LearningInputRequest(BaseModel):
    input_type: str = Field(
        pattern="^(add_faq_answer|add_adjust_rubric_rule|add_workflow_step_template|add_guardrail_refusal_rule|add_style_preference)$"
    )
    payload: Dict[str, Any] = Field(default_factory=dict)
    base_persona_spec_version: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None


class LearningInputApplyRequest(BaseModel):
    notes: Optional[str] = None


class ReviewQueueResolveRequest(BaseModel):
    status: str = Field(pattern="^(resolved|dismissed)$")
    review_note: Optional[str] = None


@router.get("/twins/{twin_id}/twin-spec/active")
async def get_active_twin_spec_endpoint(
    twin_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    active = get_active_persona_spec(twin_id=twin_id)
    if not active:
        raise HTTPException(status_code=404, detail="No active persona spec found")
    twin_spec = build_twin_spec_from_persona_spec_row(active)
    return {
        "active": True,
        "source_persona_spec_version": active.get("version"),
        "twin_spec": twin_spec.model_dump(),
    }


@router.get("/twins/{twin_id}/owner-review-queue")
async def list_owner_review_queue_endpoint(
    twin_id: str,
    status: Optional[str] = Query("pending"),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    rows = list_owner_review_queue(twin_id=twin_id, status=status, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.post("/twins/{twin_id}/owner-review-queue/{item_id}/resolve")
async def resolve_owner_review_queue_endpoint(
    twin_id: str,
    item_id: str,
    request: ReviewQueueResolveRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    row = resolve_owner_review_queue_item(
        item_id=item_id,
        status=request.status,
        resolved_by=user.get("user_id"),
        review_note=request.review_note,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Review queue item not found")
    return {"status": row.get("status"), "item": row}


@router.get("/twins/{twin_id}/learning-inputs")
async def list_learning_inputs_endpoint(
    twin_id: str,
    status: Optional[str] = Query("all"),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    rows = list_learning_inputs(twin_id=twin_id, status=status, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.post("/twins/{twin_id}/learning-inputs")
async def create_learning_input_endpoint(
    twin_id: str,
    request: LearningInputRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    row = create_learning_input(
        twin_id=twin_id,
        tenant_id=user.get("tenant_id"),
        created_by=user.get("user_id"),
        input_type=request.input_type,
        payload=request.payload,
        base_persona_spec_version=request.base_persona_spec_version,
        source_conversation_id=request.source_conversation_id,
        source_message_id=request.source_message_id,
    )
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create learning input")
    return {"status": "pending", "learning_input": row}


@router.post("/twins/{twin_id}/learning-inputs/{learning_input_id}/apply")
async def apply_learning_input_endpoint(
    twin_id: str,
    learning_input_id: str,
    request: LearningInputApplyRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    try:
        result = apply_learning_input_to_new_spec(
            twin_id=twin_id,
            tenant_id=user.get("tenant_id"),
            created_by=user.get("user_id"),
            learning_input_id=learning_input_id,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "status": "applied",
        "new_persona_spec_version": result.get("new_version"),
        "persona_spec": result.get("persona_spec"),
    }


@router.post("/twins/{twin_id}/learning-inputs/{learning_input_id}/reject")
async def reject_learning_input_endpoint(
    twin_id: str,
    learning_input_id: str,
    request: LearningInputApplyRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    row = reject_learning_input(
        learning_input_id=learning_input_id,
        review_note=request.notes,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Learning input not found")
    return {"status": "rejected", "learning_input": row}

