"""ADK-first research and compiler routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from adk_core.app import get_persona_repository, get_research_repository
from adk_core.runtime import run_compiler_pipeline
from adk_core.schemas.api import CompilePersonaRequest, ResearchRunCreateRequest
from modules.auth_guard import require_tenant, verify_twin_ownership
from modules.name_deep_research_service import get_name_deep_research_service

router = APIRouter(tags=["deep-research-v2"])


@router.post("/v2/research/runs")
async def create_research_run(
    request: ResearchRunCreateRequest,
    user: dict = Depends(require_tenant),
) -> Dict[str, Any]:
    if request.twin_id:
        verify_twin_ownership(request.twin_id, user)
    service = get_name_deep_research_service()
    row = await service.create_run(
        tenant_id=user["tenant_id"],
        user_id=user["user_id"],
        name=request.subject_name,
        hints=request.hints,
        idempotency_key=request.idempotency_key,
        twin_id=request.twin_id,
    )
    return {
        "run_id": row["id"],
        "twin_id": row.get("twin_id"),
        "subject_name": row.get("subject_name"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@router.get("/v2/research/runs/{run_id}")
async def get_research_run(
    run_id: str,
    user: dict = Depends(require_tenant),
) -> Dict[str, Any]:
    row = get_research_repository().get_run(run_id=run_id, tenant_id=user["tenant_id"])
    if not row:
        raise HTTPException(status_code=404, detail="Research run not found.")
    return row


@router.get("/v2/research/runs/{run_id}/artifact")
async def get_research_artifact(
    run_id: str,
    user: dict = Depends(require_tenant),
) -> Dict[str, Any]:
    artifact = get_research_repository().get_artifact(run_id=run_id, tenant_id=user["tenant_id"])
    if not artifact:
        raise HTTPException(status_code=404, detail="Research artifact not found.")
    return artifact["artifact_json"]


@router.post("/v2/research/runs/{run_id}/compile")
async def compile_research_run(
    run_id: str,
    request: CompilePersonaRequest,
    user: dict = Depends(require_tenant),
) -> Dict[str, Any]:
    verify_twin_ownership(request.twin_id, user)
    artifact_row = get_research_repository().get_artifact(run_id=run_id, tenant_id=user["tenant_id"])
    if not artifact_row:
        raise HTTPException(status_code=404, detail="Research artifact not found.")
    service = get_name_deep_research_service()
    research_artifact = service.parse_artifact(artifact_row["artifact_json"])
    compile_result = await run_compiler_pipeline(
        run_id=run_id,
        tenant_id=user["tenant_id"],
        twin_id=request.twin_id,
        user_id=user["user_id"],
        research_artifact=research_artifact,
        publish=request.publish,
    )
    persona_row = get_persona_repository().get_active_artifact(
        twin_id=request.twin_id,
        tenant_id=user["tenant_id"],
    )
    return {
        **compile_result,
        "persona": (persona_row or {}).get("artifact_json"),
    }
