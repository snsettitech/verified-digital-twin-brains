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

import hashlib
import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.auth_guard import require_tenant, verify_twin_ownership
from modules.ingestion import delete_source, process_and_index_text
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

def _build_deep_research_chunks(result: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Convert a deep research result artifact into a flat text document and a
    list of granular chunk entries for per-item Pinecone vector indexing.

    Returns:
        (text_doc, chunk_entries) — text_doc is the full concatenated text for
        the sources table; chunk_entries is passed as chunk_entries_override to
        process_and_index_text so each Q&A pair, claim, and timeline event gets
        its own embedding vector.
    """
    lines: List[str] = []
    chunk_entries: List[Dict[str, Any]] = []

    def _add(text: str) -> None:
        lines.append(text)
        chunk_entries.append({"text": text, "block_type": "answer_text", "is_answer_text": True})

    bio = result.get("bio") or {}
    if bio.get("medium"):
        _add(bio["medium"])

    profile_summary = result.get("profile_summary") or {}
    summary_parts: List[str] = []
    if profile_summary.get("what_they_do"):
        summary_parts.append("What they do: " + "; ".join(profile_summary["what_they_do"]))
    if profile_summary.get("public_roles"):
        summary_parts.append("Public roles: " + ", ".join(profile_summary["public_roles"]))
    if profile_summary.get("organizations"):
        summary_parts.append("Organizations: " + ", ".join(profile_summary["organizations"]))
    if summary_parts:
        _add("\n".join(summary_parts))

    for item in result.get("timeline") or []:
        if item.get("event"):
            _add(f"{item.get('date_or_range', '')}: {item['event']}")

    for claim in result.get("claims") or []:
        if claim.get("text"):
            _add(claim["text"])

    for qa in result.get("prepared_question_answers") or []:
        if qa.get("question") and qa.get("answer"):
            _add(f"Q: {qa['question']}\nA: {qa['answer']}")

    return "\n\n".join(lines).strip(), chunk_entries


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
    # ------------------------------------------------------------------
    text_doc, chunk_entries = _build_deep_research_chunks(result)
    if not text_doc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Deep research result contains no indexable content"},
        )

    # ------------------------------------------------------------------
    # 2. Delete any prior deep-research sources for this twin to prevent
    #    duplicate vectors from a double compile-to-twin call.
    # ------------------------------------------------------------------
    prior_sources = (
        supabase.table("sources")
        .select("id")
        .eq("twin_id", twin_id)
        .like("filename", "Deep Research:%")
        .execute()
    )
    for prior in prior_sources.data or []:
        try:
            await delete_source(source_id=prior["id"], twin_id=twin_id)
        except Exception as exc:
            logger.warning("Could not delete prior deep-research source %s: %s", prior["id"], exc)

    # ------------------------------------------------------------------
    # 3. Register new source and index to Pinecone with granular chunks
    # ------------------------------------------------------------------
    input_name = (result.get("input") or {}).get("name", "Profile")
    source_id = str(_uuid.uuid4())
    supabase.table("sources").insert({
        "id": source_id,
        "twin_id": twin_id,
        "filename": f"Deep Research: {input_name}"[:240],
        "file_size": len(text_doc),
        "content_text": text_doc,
        "status": "processing",
    }).execute()

    await process_and_index_text(
        source_id=source_id,
        twin_id=twin_id,
        text=text_doc,
        provider="deep_research",
        chunk_entries_override=chunk_entries if chunk_entries else None,
    )

    supabase.table("sources").update({"status": "live"}).eq("id", source_id).execute()

    # ------------------------------------------------------------------
    # 4. Map deep research claims → PersonaClaim and store
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
    # 5. Compile persona from stored claims
    # ------------------------------------------------------------------
    compiler = PersonaFromClaimsCompiler(supabase)
    await compiler.compile_persona(twin_id)

    # ------------------------------------------------------------------
    # 6. Publish bio from deep research result to twin's public profile
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
    # 7. Advance status to persona_built (unlocks chat gate)
    # ------------------------------------------------------------------
    supabase.table("twins").update({"status": "persona_built"}).eq("id", twin_id).execute()

    return {
        "status": "completed",
        "twin_id": twin_id,
        "claims_ingested": len(claims_to_store),
        "bio_written": bool(bio_text),
        "chunks_indexed": len(chunk_entries),
    }


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

    text_doc, chunk_entries = _build_deep_research_chunks(result)
    if not text_doc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Deep research result contains no indexable content"},
        )

    # Delete all existing deep-research sources for this twin so stale
    # single-chunk vectors are removed from Pinecone before re-indexing.
    prior_sources = (
        supabase.table("sources")
        .select("id")
        .eq("twin_id", twin_id)
        .like("filename", "Deep Research:%")
        .execute()
    )
    deleted_count = 0
    for prior in prior_sources.data or []:
        try:
            await delete_source(source_id=prior["id"], twin_id=twin_id)
            deleted_count += 1
        except Exception as exc:
            logger.warning("Could not delete prior source %s during reindex: %s", prior["id"], exc)

    # Create fresh source record and re-index with granular chunks.
    input_name = (result.get("input") or {}).get("name", "Profile")
    source_id = str(_uuid.uuid4())
    supabase.table("sources").insert({
        "id": source_id,
        "twin_id": twin_id,
        "filename": f"Deep Research: {input_name}"[:240],
        "file_size": len(text_doc),
        "content_text": text_doc,
        "status": "processing",
    }).execute()

    try:
        await process_and_index_text(
            source_id=source_id,
            twin_id=twin_id,
            text=text_doc,
            provider="deep_research",
            chunk_entries_override=chunk_entries if chunk_entries else None,
        )
    except Exception as exc:
        # Mark source as failed so it's visible in the dashboard rather than
        # silently stuck in "processing".
        supabase.table("sources").update({"status": "failed"}).eq("id", source_id).execute()
        logger.exception("Reindex failed for twin %s run %s: %s", twin_id, run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Reindex failed: {exc}"},
        ) from exc

    supabase.table("sources").update({"status": "live"}).eq("id", source_id).execute()

    logger.info(
        "Reindex complete: twin=%s run=%s sources_deleted=%d chunks_indexed=%d",
        twin_id, run_id, deleted_count, len(chunk_entries),
    )

    return {
        "status": "completed",
        "twin_id": twin_id,
        "run_id": run_id,
        "source_id": source_id,
        "sources_deleted": deleted_count,
        "chunks_indexed": len(chunk_entries),
    }
