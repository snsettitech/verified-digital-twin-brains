"""Persona artifact read routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from adk_core.app import get_persona_repository
from modules.auth_guard import require_tenant, verify_twin_ownership

router = APIRouter(tags=["personas-v2"])


@router.get("/v2/personas/{twin_id}")
async def get_persona(
    twin_id: str,
    user: dict = Depends(require_tenant),
) -> Dict[str, Any]:
    verify_twin_ownership(twin_id, user)
    artifact = get_persona_repository().get_active_artifact(twin_id=twin_id, tenant_id=user["tenant_id"])
    if not artifact:
        raise HTTPException(status_code=404, detail="Persona artifact not found.")
    return artifact["artifact_json"]
