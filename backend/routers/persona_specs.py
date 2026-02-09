from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from modules.auth_guard import verify_owner, verify_twin_ownership, ensure_twin_active
from modules.persona_spec import PersonaSpec
from modules.persona_spec_store import (
    bootstrap_persona_spec_from_user_data,
    create_persona_spec,
    get_active_persona_spec,
    get_next_spec_version,
    list_persona_specs,
    publish_persona_spec,
)
from modules.persona_compiler import compile_prompt_plan
from modules.persona_prompt_variant_store import (
    activate_persona_prompt_variant,
    get_active_persona_prompt_variant,
    list_persona_prompt_variants,
)
from modules.persona_feedback_learning import (
    list_feedback_learning_runs,
    run_feedback_learning_cycle,
)
from eval.persona_prompt_optimizer import optimize_persona_prompts


router = APIRouter(tags=["persona-specs"])


class PersonaSpecCreateRequest(BaseModel):
    spec: Dict[str, Any]
    version: Optional[str] = None
    notes: Optional[str] = None
    source: str = Field(default="manual", max_length=50)


class PersonaSpecGenerateRequest(BaseModel):
    notes: Optional[str] = None
    auto_publish: bool = False


class PersonaPromptOptimizationRequest(BaseModel):
    mode: str = Field(default="auto", pattern="^(auto|heuristic|openai)$")
    model: str = Field(default="gpt-4o-mini", max_length=80)
    apply_best: bool = Field(default=True)
    dataset_path: Optional[str] = None


class PersonaFeedbackLearningRequest(BaseModel):
    min_events: int = Field(default=10, ge=1, le=5000)
    event_limit: int = Field(default=500, ge=10, le=5000)
    judge_limit: int = Field(default=500, ge=10, le=5000)
    max_confidence_delta: float = Field(default=0.08, ge=0.01, le=0.30)
    activation_threshold: float = Field(default=0.75, ge=0.50, le=0.99)
    archive_threshold: float = Field(default=0.45, ge=0.01, le=0.90)
    auto_publish: bool = Field(default=False)
    run_regression_gate: bool = Field(default=True)
    regression_dataset_path: Optional[str] = None


@router.get("/twins/{twin_id}/persona-specs")
async def list_persona_specs_endpoint(
    twin_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    return list_persona_specs(twin_id=twin_id)


@router.get("/twins/{twin_id}/persona-specs/active")
async def get_active_persona_spec_endpoint(
    twin_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    active = get_active_persona_spec(twin_id=twin_id)
    return {"active": bool(active), "spec": active}


@router.post("/twins/{twin_id}/persona-specs")
async def create_persona_spec_endpoint(
    twin_id: str,
    request: PersonaSpecCreateRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    tenant_id = user.get("tenant_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = dict(request.spec or {})
    if request.version:
        payload["version"] = request.version
    elif "version" not in payload:
        payload["version"] = get_next_spec_version(twin_id=twin_id)

    try:
        spec = PersonaSpec.model_validate(payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid persona spec: {e}") from e

    row = create_persona_spec(
        twin_id=twin_id,
        tenant_id=tenant_id,
        created_by=owner_id,
        spec=spec,
        status="draft",
        source=request.source,
        notes=request.notes,
    )
    if not row:
        raise HTTPException(status_code=500, detail="Failed to persist persona spec")

    prompt_plan = compile_prompt_plan(spec=spec)
    return {
        "status": "draft",
        "persona_spec": row,
        "prompt_plan_preview": prompt_plan.model_dump(),
    }


@router.post("/twins/{twin_id}/persona-specs/generate")
async def generate_persona_spec_endpoint(
    twin_id: str,
    request: PersonaSpecGenerateRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    owner_id = user.get("user_id")
    tenant_id = user.get("tenant_id")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    spec = bootstrap_persona_spec_from_user_data(twin_id=twin_id)
    row = create_persona_spec(
        twin_id=twin_id,
        tenant_id=tenant_id,
        created_by=owner_id,
        spec=spec,
        status="draft",
        source="auto_generate",
        notes=request.notes,
    )
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create generated persona spec")

    published = None
    if request.auto_publish:
        published = publish_persona_spec(twin_id=twin_id, version=spec.version)

    prompt_plan = compile_prompt_plan(spec=spec)
    return {
        "status": "active" if published else "draft",
        "persona_spec": published or row,
        "prompt_plan_preview": prompt_plan.model_dump(),
        "generated_from": "twins.settings+owner_memory",
    }


@router.post("/twins/{twin_id}/persona-specs/{version}/publish")
async def publish_persona_spec_endpoint(
    twin_id: str,
    version: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    row = publish_persona_spec(twin_id=twin_id, version=version)
    if not row:
        raise HTTPException(status_code=404, detail="Persona spec version not found")
    return {"status": "active", "persona_spec": row}


@router.get("/twins/{twin_id}/persona-prompt-variants")
async def list_persona_prompt_variants_endpoint(
    twin_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    rows = list_persona_prompt_variants(twin_id=twin_id)
    active = get_active_persona_prompt_variant(twin_id=twin_id)
    return {"variants": rows, "active_variant": active}


@router.post("/twins/{twin_id}/persona-prompt-variants/{variant_id}/activate")
async def activate_persona_prompt_variant_endpoint(
    twin_id: str,
    variant_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    row = activate_persona_prompt_variant(twin_id=twin_id, variant_id=variant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Prompt variant not found")
    return {"status": "active", "variant": row}


@router.post("/twins/{twin_id}/persona-prompt-optimization/runs")
async def run_persona_prompt_optimization_endpoint(
    twin_id: str,
    request: PersonaPromptOptimizationRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    summary = await optimize_persona_prompts(
        twin_id=twin_id,
        tenant_id=user.get("tenant_id"),
        created_by=user.get("user_id"),
        dataset_path=request.dataset_path,
        spec_path=None,
        candidates=None,
        generator_mode=request.mode,
        model=request.model,
        apply_best=request.apply_best,
        persist=True,
    )
    if summary.get("status") != "completed":
        raise HTTPException(status_code=500, detail=summary)
    return summary


@router.get("/twins/{twin_id}/persona-feedback-learning/runs")
async def list_persona_feedback_learning_runs_endpoint(
    twin_id: str,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    runs = list_feedback_learning_runs(twin_id=twin_id, limit=30)
    return {"runs": runs}


@router.post("/twins/{twin_id}/persona-feedback-learning/runs")
async def run_persona_feedback_learning_endpoint(
    twin_id: str,
    request: PersonaFeedbackLearningRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    summary = run_feedback_learning_cycle(
        twin_id=twin_id,
        tenant_id=user.get("tenant_id"),
        created_by=user.get("user_id"),
        min_events=request.min_events,
        event_limit=request.event_limit,
        judge_limit=request.judge_limit,
        max_confidence_delta=request.max_confidence_delta,
        activation_threshold=request.activation_threshold,
        archive_threshold=request.archive_threshold,
        auto_publish=request.auto_publish,
        run_regression_gate=request.run_regression_gate,
        regression_dataset_path=request.regression_dataset_path,
    )
    if summary.get("status") != "completed":
        raise HTTPException(status_code=500, detail=summary)
    return summary
