"""
Name-Only Deep Research Router

Endpoints:
- POST /deep-research/runs
- GET /deep-research/runs/{id}
- GET /deep-research/runs/{id}/result.json
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.auth_guard import require_tenant
from modules.name_deep_research_service import (
    NameDeepResearchService,
    get_name_deep_research_service,
    is_name_only_deep_research_enabled,
)

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
                twin_result = (
                    service.db.table("twins")
                    .select("id")
                    .eq("tenant_id", user["tenant_id"])
                    .is_("settings->>deleted_at", "null")
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if twin_result.data:
                    response_twin_id = twin_result.data[0]["id"]
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
