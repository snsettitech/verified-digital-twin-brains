"""
Name-Only Deep Research Router

Endpoints:
- POST /deep-research/runs
- GET /deep-research/runs/{id}
- GET /deep-research/runs/{id}/result.json
- POST /deep-research/runs/{id}/compile-to-twin
- POST /deep-research/runs/{id}/reindex
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.auth_guard import require_tenant, verify_twin_ownership
from modules.deep_research_compiler import compile_run_to_twin
from modules.name_deep_research_service import (
    NameDeepResearchService,
    get_name_deep_research_service,
    is_name_only_deep_research_enabled,
)
from modules.observability import supabase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deep-research"])


def _check_feature_enabled() -> None:
    if not is_name_only_deep_research_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Feature disabled",
                "code": "NAME_ONLY_DEEP_RESEARCH_DISABLED",
                "message": "Set NAME_ONLY_DEEP_RESEARCH_ENABLED=true to enable this flow.",
            },
        )


class NameOnlyHintsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None


class CreateDeepResearchRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=200)
    hints: NameOnlyHintsRequest = Field(default_factory=NameOnlyHintsRequest)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = " ".join((value or "").split())
        if not cleaned:
            raise ValueError("name is required")
        return cleaned


class CreateDeepResearchRunResponse(BaseModel):
    run_id: str
    twin_id: Optional[str] = None
    status: str
    created_at: str
    run_started_at: Optional[str] = None


class DeepResearchRunStatusResponse(BaseModel):
    run_id: str
    twin_id: Optional[str] = None
    status: str
    input: Dict[str, Any]
    crawl_stats: Dict[str, Any]
    selected_model: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    run_started_at: Optional[str] = None
    run_completed_at: Optional[str] = None


@router.post(
    "/deep-research/runs",
    response_model=CreateDeepResearchRunResponse,
    responses={
        503: {"description": "Feature disabled"},
        422: {"description": "Validation error"},
    },
)
async def create_deep_research_run(
    request: CreateDeepResearchRunRequest,
    user: dict = Depends(require_tenant),
    service: NameDeepResearchService = Depends(get_name_deep_research_service),
):
    """
    Create a name-only deep research run.

    Idempotency:
    - If idempotency_key is provided and already exists for tenant, returns existing run.
    """
    _check_feature_enabled()
    try:
        row = await service.create_run(
            tenant_id=user["tenant_id"],
            user_id=user["user_id"],
            name=request.name,
            hints=request.hints.model_dump(),
            idempotency_key=request.idempotency_key,
        )
        response_twin_id = row.get("twin_id")
        if not response_twin_id:
            try:
                fallback_twin = service._find_existing_profile_twin(
                    tenant_id=user["tenant_id"],
                    user_id=user["user_id"],
                )
                if fallback_twin:
                    response_twin_id = fallback_twin["id"]
            except Exception:
                response_twin_id = None
        return CreateDeepResearchRunResponse(
            run_id=row["id"],
            twin_id=response_twin_id,
            status=row.get("status", "created"),
            created_at=row.get("created_at"),
            run_started_at=row.get("run_started_at"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Invalid input",
                "code": "INVALID_INPUT",
                "message": str(exc),
            },
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create name-only deep research run: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Run creation failed",
                "code": "NAME_RESEARCH_CREATE_FAILED",
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/deep-research/runs/{run_id}",
    response_model=DeepResearchRunStatusResponse,
    responses={
        404: {"description": "Run not found"},
        503: {"description": "Feature disabled"},
    },
)
async def get_deep_research_run(
    run_id: str,
    user: dict = Depends(require_tenant),
    service: NameDeepResearchService = Depends(get_name_deep_research_service),
):
    """Get run status and crawl stats for polling UI."""
    _check_feature_enabled()
    row = await service.get_run(run_id=run_id, tenant_id=user["tenant_id"])
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Run not found",
                "code": "NAME_RESEARCH_NOT_FOUND",
                "message": f"No run found for id={run_id}",
            },
        )

    crawl_stats = {
        "queries_used": row.get("queries_used", []),
        "urls_considered": row.get("urls_considered", 0),
        "urls_crawled": row.get("urls_crawled", 0),
        "urls_blocked": row.get("urls_blocked", 0),
        "sources_used_in_final": row.get("sources_used_in_final", 0),
        "words_extracted": row.get("words_extracted", 0),
        "run_started_at": row.get("run_started_at"),
        "run_completed_at": row.get("run_completed_at"),
    }
    return DeepResearchRunStatusResponse(
        run_id=row["id"],
        twin_id=row.get("twin_id"),
        status=row["status"],
        input={
            "name": row.get("input_name"),
            "hints": {
                "location": row.get("input_location"),
                "company": row.get("input_company"),
                "website": row.get("input_website"),
            },
        },
        crawl_stats=crawl_stats,
        selected_model=row.get("selected_model"),
        error_message=row.get("error_message"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        run_started_at=row.get("run_started_at"),
        run_completed_at=row.get("run_completed_at"),
    )


@router.get(
    "/deep-research/runs/{run_id}/result.json",
    responses={
        404: {"description": "Run or result not found"},
        409: {"description": "Result not ready"},
        503: {"description": "Feature disabled"},
    },
)
async def get_deep_research_result_json(
    run_id: str,
    user: dict = Depends(require_tenant),
    service: NameDeepResearchService = Depends(get_name_deep_research_service),
):
    """Download final deep research result JSON."""
    _check_feature_enabled()
    run = await service.get_run(run_id=run_id, tenant_id=user["tenant_id"])
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Run not found",
                "code": "NAME_RESEARCH_NOT_FOUND",
                "message": f"No run found for id={run_id}",
            },
        )

    result = await service.get_result(run_id=run_id, tenant_id=user["tenant_id"])
    if not result:
        current_status = run.get("status")
        if current_status in {"created", "searching", "crawling", "extracting", "synthesizing"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Result not ready",
                    "code": "NAME_RESEARCH_RESULT_PENDING",
                    "message": f"Run is still in progress (status={current_status})",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Result not found",
                "code": "NAME_RESEARCH_RESULT_MISSING",
                "message": "No JSON artifact found for this run.",
            },
        )

    return JSONResponse(
        content=result,
        headers={
            "Content-Disposition": f'attachment; filename=\"deep-research-{run_id}.json\"'
        },
    )


# -----------------------------------------------------------------------------
# Deep Research → Twin Compilation
# -----------------------------------------------------------------------------


class CompileToTwinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    twin_id: str = Field(..., min_length=1)


@router.post("/deep-research/runs/{run_id}/compile-to-twin")
async def compile_deep_research_to_twin(
    run_id: str,
    request: CompileToTwinRequest,
    user: dict = Depends(require_tenant),
    service: NameDeepResearchService = Depends(get_name_deep_research_service),
) -> Dict[str, Any]:
    """
    Ingest a completed deep research run into the twin's knowledge base.

    1. Builds a text document from the result and indexes it to Pinecone.
    2. Maps structured claims directly to persona_claims (no LLM re-extraction).
    3. Compiles persona from those claims.
    4. Writes the bio from the deep research result to the twin's public profile.
    5. Advances twin status to persona_built, which unlocks chat.
    """
    _check_feature_enabled()
    twin_id = request.twin_id
    tenant_id = user["tenant_id"]

    run = await service.get_run(run_id=run_id, tenant_id=tenant_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No run found for id={run_id}"},
        )
    if run.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": f"Run not yet completed (status={run.get('status')})"},
        )

    verify_twin_ownership(twin_id, user)

    result = await service.get_result(run_id=run_id, tenant_id=tenant_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "No result artifact found for this run"},
        )

    try:
        result_data = await compile_run_to_twin(
            run_id=run_id,
            twin_id=twin_id,
            tenant_id=tenant_id,
            result=result,
            db=supabase,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("compile-to-twin failed: run=%s twin=%s: %s", run_id, twin_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Compilation failed: {exc}"},
        ) from exc
    return result_data


# -----------------------------------------------------------------------------
# Reindex — re-run granular vector indexing on an already-compiled run
# -----------------------------------------------------------------------------


class ReindexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    twin_id: str = Field(..., min_length=1)


@router.post(
    "/deep-research/runs/{run_id}/reindex",
    responses={
        404: {"description": "Run or result not found"},
        409: {"description": "Run not completed"},
        503: {"description": "Feature disabled"},
    },
)
async def reindex_deep_research(
    run_id: str,
    request: ReindexRequest,
    user: dict = Depends(require_tenant),
    service: NameDeepResearchService = Depends(get_name_deep_research_service),
) -> Dict[str, Any]:
    """
    Re-index an already-compiled deep research run with granular per-item
    Pinecone vectors.

    Use this to fix twins compiled before the granular indexing fix was deployed.
    The endpoint:
    1. Deletes all existing "Deep Research:" sources for the twin (Pinecone + Supabase).
    2. Re-indexes the result with chunk_entries_override so each Q&A pair,
       claim, and timeline event gets its own embedding vector.
    3. Does NOT re-run persona compilation or overwrite the bio — those are
       already correct from the original compile-to-twin call.
    """
    _check_feature_enabled()
    twin_id = request.twin_id
    tenant_id = user["tenant_id"]

    run = await service.get_run(run_id=run_id, tenant_id=tenant_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No run found for id={run_id}"},
        )
    if run.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": f"Run not yet completed (status={run.get('status')})"},
        )

    verify_twin_ownership(twin_id, user)

    result = await service.get_result(run_id=run_id, tenant_id=tenant_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "No result artifact found for this run"},
        )

    try:
        result_data = await compile_run_to_twin(
            run_id=run_id,
            twin_id=twin_id,
            tenant_id=tenant_id,
            result=result,
            db=supabase,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("reindex failed: run=%s twin=%s: %s", run_id, twin_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Reindex failed: {exc}"},
        ) from exc

    logger.info(
        "Reindex complete: twin=%s run=%s chunks_indexed=%d",
        twin_id, run_id, result_data.get("chunks_indexed", 0),
    )

    return {
        **result_data,
        "run_id": run_id,
    }
