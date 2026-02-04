from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any

from modules.auth_guard import verify_owner, verify_twin_ownership
from modules.schemas import ClarificationResolveRequest
from modules.owner_memory_store import (
    list_owner_memories,
    list_clarification_threads,
    get_clarification_thread,
    resolve_clarification_thread,
    create_owner_memory,
    find_owner_memory_candidates,
    retract_owner_memory
)
from modules.memory_events import create_memory_event


router = APIRouter(tags=["owner-memory"])


@router.get("/twins/{twin_id}/owner-memory")
async def list_owner_memory_endpoint(twin_id: str, status: Optional[str] = Query("active"), user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return list_owner_memories(twin_id, status=status or "active", limit=200)


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
        confidence=0.85,
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
