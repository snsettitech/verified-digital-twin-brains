from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from modules.auth_guard import verify_owner, verify_twin_ownership, ensure_twin_active
from modules.decision_capture_store import (
    record_introspection_capture,
    record_pairwise_capture,
    record_sjt_capture,
)
from modules.interaction_context import require_owner_training_context, trace_fields


router = APIRouter(tags=["decision-capture"])


class DecisionCaptureBaseRequest(BaseModel):
    training_session_id: str = Field(min_length=1)
    intent_label: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SJTOption(BaseModel):
    label: str = Field(min_length=1)
    value: Optional[str] = None
    description: Optional[str] = None


class SJTDecisionCaptureRequest(DecisionCaptureBaseRequest):
    scenario_id: Optional[str] = None
    prompt: str = Field(min_length=1, max_length=4000)
    options: List[SJTOption] = Field(default_factory=list)
    selected_option: str = Field(min_length=1, max_length=200)
    rationale: Optional[str] = None
    thresholds: Dict[str, Any] = Field(default_factory=dict)


class PairwiseCandidate(BaseModel):
    id: Optional[str] = None
    text: str = Field(min_length=1, max_length=8000)


class PairwiseDecisionCaptureRequest(DecisionCaptureBaseRequest):
    prompt: str = Field(min_length=1, max_length=4000)
    candidate_a: PairwiseCandidate
    candidate_b: PairwiseCandidate
    preferred: str = Field(pattern="^(a|b|tie)$")
    rationale: Optional[str] = None


class IntrospectionDecisionCaptureRequest(DecisionCaptureBaseRequest):
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=8000)
    thresholds: Dict[str, Any] = Field(default_factory=dict)


@router.post("/twins/{twin_id}/decision-capture/sjt")
async def decision_capture_sjt(
    twin_id: str,
    request: SJTDecisionCaptureRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    tenant_id = user.get("tenant_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    resolved = require_owner_training_context(
        request_payload=request,
        user=user,
        twin_id=twin_id,
        action="SJT decision capture",
    )
    saved = record_sjt_capture(
        twin_id=twin_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        training_session_id=request.training_session_id,
        scenario_id=request.scenario_id,
        intent_label=request.intent_label,
        prompt=request.prompt,
        options=[opt.model_dump() for opt in request.options],
        selected_option=request.selected_option,
        rationale=request.rationale,
        thresholds=request.thresholds,
        metadata=request.metadata,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to record SJT decision capture")

    return {
        "status": "recorded",
        "capture_type": "sjt",
        "record": saved.get("event"),
        "module_candidate": saved.get("module"),
        "clause_ids": saved.get("clause_ids", []),
        **trace_fields(resolved),
    }


@router.post("/twins/{twin_id}/decision-capture/pairwise")
async def decision_capture_pairwise(
    twin_id: str,
    request: PairwiseDecisionCaptureRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    tenant_id = user.get("tenant_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    resolved = require_owner_training_context(
        request_payload=request,
        user=user,
        twin_id=twin_id,
        action="Pairwise decision capture",
    )
    saved = record_pairwise_capture(
        twin_id=twin_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        training_session_id=request.training_session_id,
        intent_label=request.intent_label,
        prompt=request.prompt,
        candidate_a=request.candidate_a.model_dump(),
        candidate_b=request.candidate_b.model_dump(),
        preferred=request.preferred,
        rationale=request.rationale,
        metadata=request.metadata,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to record pairwise decision capture")

    return {
        "status": "recorded",
        "capture_type": "pairwise",
        "record": saved.get("event"),
        "module_candidate": saved.get("module"),
        "clause_ids": saved.get("clause_ids", []),
        **trace_fields(resolved),
    }


@router.post("/twins/{twin_id}/decision-capture/introspection")
async def decision_capture_introspection(
    twin_id: str,
    request: IntrospectionDecisionCaptureRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    tenant_id = user.get("tenant_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    resolved = require_owner_training_context(
        request_payload=request,
        user=user,
        twin_id=twin_id,
        action="Introspection decision capture",
    )
    saved = record_introspection_capture(
        twin_id=twin_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        training_session_id=request.training_session_id,
        intent_label=request.intent_label,
        question=request.question,
        answer=request.answer,
        thresholds=request.thresholds,
        metadata=request.metadata,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to record introspection decision capture")

    return {
        "status": "recorded",
        "capture_type": "introspection",
        "record": saved.get("event"),
        "module_candidate": saved.get("module"),
        "clause_ids": saved.get("clause_ids", []),
        **trace_fields(resolved),
    }
