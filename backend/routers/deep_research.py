"""
Name-Only Deep Research Router

Endpoints:
- POST /deep-research/runs
- GET /deep-research/runs/{id}
- GET /deep-research/runs/{id}/result.json
"""

from __future__ import annotations

import hashlib
import logging
import uuid as _uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.auth_guard import require_tenant, verify_twin_ownership
from modules.ingestion import process_and_index_text
from modules.name_deep_research_service import (
    NameDeepResearchService,
    get_name_deep_research_service,
    is_name_only_deep_research_enabled,
)
from modules.observability import supabase
from modules.persona_claim_extractor import ClaimCitation, ClaimStore, PersonaClaim
from modules.persona_claim_inference import PersonaFromClaimsCompiler

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

_DR_CLAIM_TYPE_MAP: Dict[str, str] = {
    "credential": "belief",
    "experience": "experience",
    "role": "belief",
    "preference": "preference",
    "opinion": "belief",
    "project": "experience",
    "contact": "uncertain",
    "other": "uncertain",
}


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

    # ------------------------------------------------------------------
    # 1. Build text document + granular chunk list for Pinecone indexing
    #
    # Each Q&A pair, claim, and timeline event is a separate vector so
    # retrieval can surface the most relevant fact for each query rather
    # than always returning the same monolithic bio blob.
    # ------------------------------------------------------------------
    lines: list[str] = []
    chunk_entries: list[dict] = []  # per-item chunks for chunk_entries_override

    bio = result.get("bio") or {}
    if bio.get("medium"):
        lines.append(bio["medium"])
        chunk_entries.append({"text": bio["medium"], "block_type": "answer_text", "is_answer_text": True})

    profile_summary = result.get("profile_summary") or {}
    summary_parts: list[str] = []
    if profile_summary.get("what_they_do"):
        summary_parts.append("What they do: " + "; ".join(profile_summary["what_they_do"]))
    if profile_summary.get("public_roles"):
        summary_parts.append("Public roles: " + ", ".join(profile_summary["public_roles"]))
    if profile_summary.get("organizations"):
        summary_parts.append("Organizations: " + ", ".join(profile_summary["organizations"]))
    if summary_parts:
        summary_text = "\n".join(summary_parts)
        lines.append(summary_text)
        chunk_entries.append({"text": summary_text, "block_type": "answer_text", "is_answer_text": True})

    for item in result.get("timeline") or []:
        if item.get("event"):
            event_text = f"{item.get('date_or_range', '')}: {item['event']}"
            lines.append(event_text)
            chunk_entries.append({"text": event_text, "block_type": "answer_text", "is_answer_text": True})

    for claim in result.get("claims") or []:
        if claim.get("text"):
            lines.append(claim["text"])
            chunk_entries.append({"text": claim["text"], "block_type": "answer_text", "is_answer_text": True})

    for qa in result.get("prepared_question_answers") or []:
        if qa.get("question") and qa.get("answer"):
            qa_text = f"Q: {qa['question']}\nA: {qa['answer']}"
            lines.append(qa_text)
            # Index Q&A pairs as separate vectors — critical for per-question retrieval
            chunk_entries.append({"text": qa_text, "block_type": "answer_text", "is_answer_text": True})

    text_doc = "\n\n".join(lines).strip()
    if not text_doc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Deep research result contains no indexable content"},
        )

    # ------------------------------------------------------------------
    # 2. Register source and index to Pinecone
    # ------------------------------------------------------------------
    input_name = (result.get("input") or {}).get("name", "Profile")
    source_id = str(_uuid.uuid4())
    supabase.table("sources").upsert({
        "id": source_id,
        "twin_id": twin_id,
        "filename": f"Deep Research: {input_name}"[:240],
        "file_size": len(text_doc),
        "content_text": text_doc,
        "status": "processing",
    }).execute()

    # Use per-item chunks so each Q&A pair / claim gets its own vector.
    # Falls back to automatic chunking if the override list is empty.
    await process_and_index_text(
        source_id=source_id,
        twin_id=twin_id,
        text=text_doc,
        provider="deep_research",
        chunk_entries_override=chunk_entries if chunk_entries else None,
    )

    supabase.table("sources").update({"status": "live"}).eq("id", source_id).execute()

    # ------------------------------------------------------------------
    # 3. Map deep research claims → PersonaClaim and store
    # ------------------------------------------------------------------
    claims_to_store: list[PersonaClaim] = []
    for item in result.get("claims") or []:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        claims_to_store.append(PersonaClaim(
            twin_id=twin_id,
            claim_text=text,
            claim_type=_DR_CLAIM_TYPE_MAP.get(item.get("claim_type", "other"), "uncertain"),
            confidence=float(item.get("confidence", 0.7)),
            authority="extracted",
            citation=ClaimCitation(
                source_id=source_id,
                chunk_id=f"dr_{item.get('claim_id', '')}",
                span_start=0,
                span_end=len(text),
                quote=text[:120],
                content_hash=content_hash,
            ),
            extraction_version="dr-1.0",
        ))

    claim_store = ClaimStore(supabase)
    await claim_store.save_claims(claims_to_store)

    # ------------------------------------------------------------------
    # 4. Compile persona from stored claims
    # ------------------------------------------------------------------
    compiler = PersonaFromClaimsCompiler(supabase)
    await compiler.compile_persona(twin_id)

    # ------------------------------------------------------------------
    # 5. Publish bio from deep research result to twin's public profile
    # ------------------------------------------------------------------
    bio_text = bio.get("short") or bio.get("medium") or ""
    if bio_text:
        twin_row = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        current_settings = (twin_row.data or {}).get("settings") or {}
        current_public_profile = current_settings.get("public_profile") or {}
        supabase.table("twins").update({
            "settings": {
                **current_settings,
                "public_profile": {**current_public_profile, "bio": bio_text},
            }
        }).eq("id", twin_id).execute()

    # ------------------------------------------------------------------
    # 6. Advance status to persona_built (unlocks chat gate)
    # ------------------------------------------------------------------
    supabase.table("twins").update({"status": "persona_built"}).eq("id", twin_id).execute()

    return {
        "status": "completed",
        "twin_id": twin_id,
        "claims_ingested": len(claims_to_store),
        "bio_written": bool(bio_text),
    }
