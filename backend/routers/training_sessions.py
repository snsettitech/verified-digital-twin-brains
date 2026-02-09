from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from modules.auth_guard import verify_owner, verify_twin_ownership, ensure_twin_active
from modules.training_sessions import (
    get_active_training_session,
    start_training_session,
    stop_training_session,
)


router = APIRouter(tags=["training-sessions"])


class TrainingSessionStartRequest(BaseModel):
    metadata: Optional[Dict[str, Any]] = None


@router.post("/twins/{twin_id}/training-sessions/start")
async def start_training_session_endpoint(
    twin_id: str,
    request: TrainingSessionStartRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    tenant_id = user.get("tenant_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = start_training_session(
        twin_id=twin_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        metadata=request.metadata or {},
    )
    if not session:
        raise HTTPException(status_code=500, detail="Failed to start training session")
    return {
        "status": "active",
        "session": session,
    }


@router.post("/twins/{twin_id}/training-sessions/{session_id}/stop")
async def stop_training_session_endpoint(
    twin_id: str,
    session_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = stop_training_session(
        session_id=session_id,
        twin_id=twin_id,
        owner_id=owner_id,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Active training session not found")
    return {
        "status": "stopped",
        "session": session,
    }


@router.get("/twins/{twin_id}/training-sessions/active")
async def get_active_training_session_endpoint(
    twin_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = get_active_training_session(twin_id=twin_id, owner_id=owner_id)
    return {
        "active": bool(session),
        "session": session,
    }

