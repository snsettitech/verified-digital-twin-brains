from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any

from modules.auth_guard import verify_owner, verify_twin_ownership
from modules.schemas import ClarificationResolveRequest
from modules.owner_memory_store import (
    list_owner_memories,
    list_owner_memory_history,
    list_clarification_threads,
    get_clarification_thread,
    resolve_clarification_thread,
    create_owner_memory,
    find_owner_memory_candidates,
    retract_owner_memory,
    get_owner_memory,
    approve_owner_memory,
)
from modules.memory_events import create_memory_event
from modules.verified_qna import create_verified_qna
from pydantic import BaseModel, Field


class OwnerMemoryCreateRequest(BaseModel):
    topic_normalized: str = Field(..., description="Normalized topic label")
    memory_type: str = Field(..., description="belief | preference | stance | lens | tone_rule")
    value: str = Field(..., description="Owner-approved memory value")
    stance: Optional[str] = None
    intensity: Optional[int] = None


class OwnerMemoryUpdateRequest(BaseModel):
    topic_normalized: Optional[str] = None
    memory_type: Optional[str] = None
    value: Optional[str] = None
    stance: Optional[str] = None
    intensity: Optional[int] = None


class OwnerCorrectionRequest(BaseModel):
    question: str = Field(..., description="Original user/public question")
    corrected_answer: str = Field(..., description="Owner-approved corrected answer")
    topic_normalized: Optional[str] = Field(None, description="Optional memory topic; inferred from answer when omitted")
    memory_type: str = Field("belief", description="belief | preference | stance | lens | tone_rule")
    create_verified_qna_entry: bool = Field(True, description="Also write corrected answer to verified_qna")


router = APIRouter(tags=["owner-memory"])


@router.get("/twins/{twin_id}/owner-memory")
async def list_owner_memory_endpoint(twin_id: str, status: Optional[str] = Query("active"), user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return list_owner_memories(twin_id, status=status or "active", limit=200)


@router.post("/twins/{twin_id}/owner-memory/{memory_id}/approve")
async def approve_owner_memory_endpoint(
    twin_id: str,
    memory_id: str,
    user=Depends(verify_owner),
):
    """
    Promote a proposed owner memory to verified so retrieval can use it.
    """
    verify_twin_ownership(twin_id, user)

    existing = get_owner_memory(memory_id)
    if not existing or existing.get("twin_id") != twin_id:
        raise HTTPException(status_code=404, detail="Owner memory not found")

    current_status = str(existing.get("status") or "").lower()
    if current_status in {"verified", "active"}:
        return {
            "status": "already_approved",
            "owner_memory_id": memory_id,
            "memory_status": current_status,
        }
    if current_status != "proposed":
        raise HTTPException(
            status_code=409,
            detail=f"Only proposed memories can be approved (current status: {current_status or 'unknown'})",
        )

    approved = approve_owner_memory(
        mem_id=memory_id,
        approver_id=user.get("user_id"),
        expected_status="proposed",
    )
    if not approved:
        raise HTTPException(status_code=500, detail="Failed to approve owner memory")

    try:
        await create_memory_event(
            twin_id=twin_id,
            tenant_id=user.get("tenant_id"),
            event_type="owner_memory_write",
            payload={
                "owner_memory_id": approved.get("id"),
                "topic": approved.get("topic_normalized"),
                "memory_type": approved.get("memory_type"),
                "approval": "proposed_to_verified",
            },
            status="applied",
            source_type="manual",
            source_id=None,
        )
    except Exception as e:
        print(f"[OwnerMemory] approval audit log failed: {e}")

    return {
        "status": "approved",
        "owner_memory_id": approved.get("id"),
        "from_status": current_status,
        "to_status": approved.get("status", "verified"),
    }


@router.post("/twins/{twin_id}/owner-memory/approve-proposed")
async def approve_proposed_owner_memories_endpoint(
    twin_id: str,
    limit: int = Query(200, ge=1, le=1000),
    user=Depends(verify_owner),
):
    """
    Bulk-approve proposed memories for faster bootstrap after interview ingestion.
    """
    verify_twin_ownership(twin_id, user)

    proposed_memories = list_owner_memories(twin_id, status="proposed", limit=limit)
    approved_ids: List[str] = []
    failed_ids: List[str] = []

    for mem in proposed_memories:
        mem_id = mem.get("id")
        if not mem_id:
            continue
        updated = approve_owner_memory(
            mem_id=mem_id,
            approver_id=user.get("user_id"),
            expected_status="proposed",
        )
        if updated:
            approved_ids.append(mem_id)
        else:
            failed_ids.append(mem_id)

    if approved_ids:
        try:
            await create_memory_event(
                twin_id=twin_id,
                tenant_id=user.get("tenant_id"),
                event_type="owner_memory_write",
                payload={
                    "approval": "bulk_proposed_to_verified",
                    "approved_count": len(approved_ids),
                    "failed_count": len(failed_ids),
                },
                status="applied",
                source_type="manual",
                source_id=None,
            )
        except Exception as e:
            print(f"[OwnerMemory] bulk approval audit log failed: {e}")

    return {
        "status": "completed",
        "proposed_found": len(proposed_memories),
        "approved_count": len(approved_ids),
        "failed_count": len(failed_ids),
        "approved_ids": approved_ids,
        "failed_ids": failed_ids,
    }


@router.delete("/twins/{twin_id}/owner-memory/{memory_id}")
async def delete_owner_memory_endpoint(
    twin_id: str,
    memory_id: str,
    user=Depends(verify_owner)
):
    """Retract (soft-delete) an owner memory. Idempotent."""
    verify_twin_ownership(twin_id, user)
    
    success = retract_owner_memory(memory_id, reason="owner_request")
    if not success:
        raise HTTPException(status_code=500, detail="Failed to retract memory")
    
    # Audit trail
    try:
        await create_memory_event(
            twin_id=twin_id,
            tenant_id=user.get("tenant_id"),
            event_type="owner_memory_retract",
            payload={
                "owner_memory_id": memory_id,
                "retracted_by": user.get("user_id")
            },
            status="applied",
            source_type="manual",
            source_id=None
        )
    except Exception as e:
        print(f"[OwnerMemory] audit log failed: {e}")
    
    return {"status": "retracted", "memory_id": memory_id}


@router.get("/twins/{twin_id}/owner-memory/{memory_id}/history")
async def get_owner_memory_history_endpoint(
    twin_id: str,
    memory_id: str,
    user=Depends(verify_owner)
):
    verify_twin_ownership(twin_id, user)

    existing = get_owner_memory(memory_id)
    if not existing or existing.get("twin_id") != twin_id:
        raise HTTPException(status_code=404, detail="Owner memory not found")

    history = list_owner_memory_history(
        twin_id=twin_id,
        topic_normalized=existing.get("topic_normalized", ""),
        memory_type=existing.get("memory_type")
    )
    return history


@router.post("/twins/{twin_id}/owner-memory")
async def create_owner_memory_endpoint(
    twin_id: str,
    request: OwnerMemoryCreateRequest,
    user=Depends(verify_owner)
):
    verify_twin_ownership(twin_id, user)

    if not request.value.strip():
        raise HTTPException(status_code=422, detail="Value is required")
    if not request.topic_normalized.strip():
        raise HTTPException(status_code=422, detail="Topic is required")
    allowed_types = {"belief", "preference", "stance", "lens", "tone_rule"}
    if request.memory_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Invalid memory_type")

    new_memory = create_owner_memory(
        twin_id=twin_id,
        tenant_id=user.get("tenant_id"),
        topic_normalized=request.topic_normalized.strip(),
        memory_type=request.memory_type,
        value=request.value.strip(),
        stance=request.stance,
        intensity=request.intensity,
        confidence=1.0,
        provenance={
            "source_type": "manual",
            "owner_id": user.get("user_id")
        },
        supersede_id=None
    )

    if not new_memory:
        raise HTTPException(status_code=500, detail="Failed to create owner memory")

    try:
        await create_memory_event(
            twin_id=twin_id,
            tenant_id=user.get("tenant_id"),
            event_type="owner_memory_write",
            payload={
                "owner_memory_id": new_memory.get("id"),
                "topic": new_memory.get("topic_normalized"),
                "memory_type": new_memory.get("memory_type"),
                "value": new_memory.get("value")
            },
            status="applied",
            source_type="manual",
            source_id=None
        )
    except Exception as e:
        print(f"[OwnerMemory] audit log failed: {e}")

    return {"status": "created", "owner_memory_id": new_memory.get("id")}


@router.post("/twins/{twin_id}/owner-corrections")
async def create_owner_correction_endpoint(
    twin_id: str,
    request: OwnerCorrectionRequest,
    user=Depends(verify_owner)
):
    """
    Owner-authored correction flow for rapid teaching from conversation.
    Writes structured memory and optionally promotes answer to verified_qna.
    """
    verify_twin_ownership(twin_id, user)

    question = (request.question or "").strip()
    corrected_answer = (request.corrected_answer or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")
    if not corrected_answer:
        raise HTTPException(status_code=422, detail="corrected_answer is required")

    allowed_types = {"belief", "preference", "stance", "lens", "tone_rule"}
    if request.memory_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Invalid memory_type")

    topic = (request.topic_normalized or "").strip() or question[:120]
    stance = _infer_stance_from_text(corrected_answer) if request.memory_type == "stance" else None

    new_memory = create_owner_memory(
        twin_id=twin_id,
        tenant_id=user.get("tenant_id"),
        topic_normalized=topic,
        memory_type=request.memory_type,
        value=corrected_answer,
        stance=stance,
        intensity=None,
        confidence=1.0,
        provenance={
            "source_type": "owner_correction",
            "owner_id": user.get("user_id"),
            "question": question,
        },
        supersede_id=None,
        status="verified",
    )
    if not new_memory:
        raise HTTPException(status_code=500, detail="Failed to persist owner correction")

    verified_qna_id = None
    if request.create_verified_qna_entry:
        try:
            verified_qna_id = await create_verified_qna(
                question=question,
                answer=corrected_answer,
                owner_id=user.get("user_id"),
                twin_id=twin_id,
            )
        except Exception as e:
            print(f"[OwnerMemory] create_verified_qna from correction failed: {e}")

    try:
        await create_memory_event(
            twin_id=twin_id,
            tenant_id=user.get("tenant_id"),
            event_type="owner_memory_write",
            payload={
                "owner_memory_id": new_memory.get("id"),
                "topic": topic,
                "memory_type": request.memory_type,
                "question": question,
                "verified_qna_id": verified_qna_id,
            },
            status="applied",
            source_type="chat_turn",
            source_id=None,
        )
    except Exception as e:
        print(f"[OwnerMemory] correction audit log failed: {e}")

    return {
        "status": "applied",
        "owner_memory_id": new_memory.get("id"),
        "verified_qna_id": verified_qna_id,
        "topic": topic,
        "memory_type": request.memory_type,
    }


@router.patch("/twins/{twin_id}/owner-memory/{memory_id}")
async def update_owner_memory_endpoint(
    twin_id: str,
    memory_id: str,
    request: OwnerMemoryUpdateRequest,
    user=Depends(verify_owner)
):
    verify_twin_ownership(twin_id, user)

    existing = get_owner_memory(memory_id)
    if not existing or existing.get("twin_id") != twin_id:
        raise HTTPException(status_code=404, detail="Owner memory not found")

    updated_topic = (request.topic_normalized or existing.get("topic_normalized") or "").strip()
    updated_value = (request.value or existing.get("value") or "").strip()
    updated_type = request.memory_type or existing.get("memory_type")

    if not updated_topic or not updated_value or not updated_type:
        raise HTTPException(status_code=422, detail="Topic, type, and value are required")
    allowed_types = {"belief", "preference", "stance", "lens", "tone_rule"}
    if updated_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Invalid memory_type")

    new_memory = create_owner_memory(
        twin_id=twin_id,
        tenant_id=user.get("tenant_id"),
        topic_normalized=updated_topic,
        memory_type=updated_type,
        value=updated_value,
        stance=request.stance if request.stance is not None else existing.get("stance"),
        intensity=request.intensity if request.intensity is not None else existing.get("intensity"),
        confidence=1.0,
        provenance={
            "source_type": "manual_edit",
            "owner_id": user.get("user_id"),
            "source_id": memory_id
        },
        supersede_id=memory_id
    )

    if not new_memory:
        raise HTTPException(status_code=500, detail="Failed to update owner memory")

    try:
        await create_memory_event(
            twin_id=twin_id,
            tenant_id=user.get("tenant_id"),
            event_type="owner_memory_supersede",
            payload={
                "owner_memory_id": new_memory.get("id"),
                "superseded_id": memory_id,
                "topic": updated_topic,
                "memory_type": updated_type
            },
            status="applied",
            source_type="manual",
            source_id=None
        )
    except Exception as e:
        print(f"[OwnerMemory] audit log failed: {e}")

    return {
        "status": "updated",
        "owner_memory_id": new_memory.get("id"),
        "superseded_id": memory_id
    }


@router.get("/twins/{twin_id}/clarifications")
async def list_clarifications_endpoint(twin_id: str, status: Optional[str] = Query("pending_owner"), user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return list_clarification_threads(twin_id, status=status, limit=100)


def _infer_stance_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    lower = text.lower()
    if any(w in lower for w in ["support", "favor", "favour", "pro", "yes", "agree", "for it"]):
        return "positive"
    if any(w in lower for w in ["oppose", "against", "anti", "no", "disagree"]):
        return "negative"
    if any(w in lower for w in ["neutral", "depends", "mixed", "not sure", "uncertain"]):
        return "neutral"
    return None


@router.post("/twins/{twin_id}/clarifications/{clarification_id}/resolve")
async def resolve_clarification_endpoint(
    twin_id: str,
    clarification_id: str,
    request: ClarificationResolveRequest,
    user=Depends(verify_owner)
):
    verify_twin_ownership(twin_id, user)

    thread = get_clarification_thread(clarification_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Clarification not found")
    if thread.get("twin_id") != twin_id:
        raise HTTPException(status_code=404, detail="Clarification not found for this twin")
    if thread.get("status") != "pending_owner":
        raise HTTPException(status_code=400, detail="Clarification already resolved")

    proposal = thread.get("memory_write_proposal") or {}
    topic = proposal.get("topic") or "general"
    memory_type = proposal.get("memory_type") or "stance"

    answer_text = request.answer.strip()
    if not answer_text:
        raise HTTPException(status_code=422, detail="Answer is required")

    # If selected option provided, prefer its value
    selected_value = None
    selected_stance = None
    selected_intensity = None
    if request.selected_option and thread.get("options"):
        for opt in thread.get("options", []):
            if opt.get("label") == request.selected_option:
                selected_value = opt.get("value")
                selected_stance = opt.get("stance")
                selected_intensity = opt.get("intensity")
                break

    value = selected_value or answer_text
    stance = selected_stance or _infer_stance_from_text(answer_text) if memory_type == "stance" else None
    intensity = selected_intensity

    # Check for existing memory to supersede
    candidates = find_owner_memory_candidates(query=topic, twin_id=twin_id, topic_normalized=topic, memory_type=memory_type)
    supersede_id = candidates[0]["id"] if candidates and candidates[0].get("_score", 0) > 0.8 else None

    new_memory = create_owner_memory(
        twin_id=twin_id,
        tenant_id=user.get("tenant_id"),
        topic_normalized=topic,
        memory_type=memory_type,
        value=value,
        stance=stance,
        intensity=intensity,
        confidence=1.0,
        provenance={
            "clarification_id": clarification_id,
            "owner_id": user.get("user_id"),
            "source": "owner_clarification"
        },
        supersede_id=supersede_id
    )

    if not new_memory:
        raise HTTPException(status_code=500, detail="Failed to write owner memory")

    resolve_clarification_thread(
        clarification_id=clarification_id,
        answer_text=answer_text,
        owner_memory_id=new_memory.get("id"),
        answered_by=user.get("user_id")
    )

    # Audit trail
    try:
        await create_memory_event(
            twin_id=twin_id,
            tenant_id=user.get("tenant_id"),
            event_type="owner_memory_write",
            payload={
                "owner_memory_id": new_memory.get("id"),
                "topic": topic,
                "memory_type": memory_type,
                "value": value,
                "superseded": bool(supersede_id)
            },
            status="applied",
            source_type="chat_turn",
            source_id=thread.get("conversation_id")
        )
    except Exception as e:
        print(f"[OwnerMemory] audit log failed: {e}")

    return {
        "status": "applied",
        "owner_memory_id": new_memory.get("id"),
        "topic": topic,
        "memory_type": memory_type,
        "value": value
    }
