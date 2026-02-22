"""
persona_link_compile.py

Phase 1-5 API Router: Link-First Persona Compiler endpoints.
"""

import os
import tempfile
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel, Field
from datetime import datetime

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.observability import supabase
from modules.governance import AuditLogger

# Link-First modules
from modules.robots_checker import check_url_fetchable
from modules.export_parsers import parse_export_file
from modules.ingestion import ingest_file, ingest_url, process_and_index_text
from modules.persona_claim_extractor import extract_and_store_claims, ClaimExtractor
from modules.persona_claim_inference import (
    PersonaFromClaimsCompiler,
    handle_clarification_answer,
)
from modules.persona_bio_generator import generate_and_store_bios


router = APIRouter(tags=["persona-link-compile"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ModeCUrlRequest(BaseModel):
    """Mode C: Public web fetch request."""
    twin_id: str
    urls: List[str] = Field(..., min_length=1, max_length=10)
    allowlisted_domains: Optional[List[str]] = Field(default=None)


class ModeBPasteRequest(BaseModel):
    """Mode B: Paste/import request."""
    twin_id: str
    content: str = Field(..., max_length=100000)  # 100KB limit
    title: Optional[str] = "Pasted Content"
    source_context: Optional[str] = None  # e.g., "Private Slack"


class ClarificationAnswerRequest(BaseModel):
    """Answer to a clarification question."""
    question_id: str
    question: dict  # The question metadata from clarification interview
    answer: str = Field(..., max_length=5000)


class LinkCompileJobResponse(BaseModel):
    """Response for link compile job creation."""
    job_id: str
    status: str
    mode: str
    message: str


class ClaimResponse(BaseModel):
    """Claim in API response."""
    id: str
    claim_text: str
    claim_type: str
    confidence: float
    authority: str
    verification_status: str
    source_id: str


class ActivateTwinRequest(BaseModel):
    final_name: Optional[str] = None


class ClaimVerifyRequest(BaseModel):
    verified: bool = True


def _require_authenticated_user(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(user, dict) or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _is_missing_column_error(error: Exception, column_name: str) -> bool:
    message = str(error).lower()
    col = (column_name or "").lower()
    return (
        bool(col)
        and col in message
        and (
            "pgrst204" in message
            or "could not find" in message
            or "column" in message
            or "does not exist" in message
        )
    )


def _set_twin_status(twin_id: str, status: str) -> Dict[str, Any]:
    """
    Update twin lifecycle status.
    Primary path uses `twins.status`; fallback stores lifecycle in settings for
    environments that have not applied the status-column migration yet.
    """
    now_iso = datetime.utcnow().isoformat()
    update_payload: Dict[str, Any] = {
        "status": status,
        "updated_at": now_iso,
    }

    # First attempt: native twins.status lifecycle column.
    while True:
        try:
            result = supabase.table("twins").update(update_payload).eq("id", twin_id).execute()
            if result.data:
                return result.data[0]
            raise HTTPException(404, "Twin not found")
        except Exception as update_error:
            removed_column = None
            for column in ("status", "updated_at"):
                if column in update_payload and _is_missing_column_error(update_error, column):
                    removed_column = column
                    break

            if removed_column:
                update_payload.pop(removed_column, None)
                # If status still exists, retry native path without the missing column.
                if "status" in update_payload:
                    continue
                # status itself is missing - switch to settings fallback path below.
                break

            raise

    # Fallback: encode lifecycle in settings.link_first_state when status column is absent.
    twin_result = supabase.table("twins").select("id, settings").eq("id", twin_id).single().execute()
    twin_row = twin_result.data or {}
    if not twin_row.get("id"):
        raise HTTPException(404, "Twin not found")

    settings = twin_row.get("settings") if isinstance(twin_row.get("settings"), dict) else {}
    merged_settings = dict(settings)
    merged_settings["link_first_state"] = status
    merged_settings["creation_mode"] = merged_settings.get("creation_mode") or "link_first"

    fallback_payload: Dict[str, Any] = {"settings": merged_settings, "updated_at": now_iso}
    while True:
        try:
            fallback_res = (
                supabase.table("twins")
                .update(fallback_payload)
                .eq("id", twin_id)
                .execute()
            )
            if not fallback_res.data:
                raise HTTPException(404, "Twin not found")

            twin = fallback_res.data[0]
            twin["status"] = status
            return twin
        except Exception as fallback_error:
            if "updated_at" in fallback_payload and _is_missing_column_error(fallback_error, "updated_at"):
                fallback_payload.pop("updated_at", None)
                continue
            raise


def _create_link_compile_source(
    *,
    twin_id: str,
    filename: str,
    content: str,
    citation_url: Optional[str] = None,
) -> str:
    """Create a source row and return a UUID source_id for chunk ingestion."""
    source_id = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "id": source_id,
        "twin_id": twin_id,
        "filename": (filename or "Link-Compile Source")[:240],
        "file_size": len(content or ""),
        "content_text": content or "",
        "status": "processing",
    }
    if citation_url:
        payload["citation_url"] = citation_url

    supabase.table("sources").upsert(payload).execute()
    return source_id


def _mark_source_live(source_id: str, chunk_count: Optional[int] = None) -> None:
    update_payload: Dict[str, Any] = {"status": "live"}
    if isinstance(chunk_count, int):
        update_payload["chunk_count"] = chunk_count

    while True:
        try:
            supabase.table("sources").update(update_payload).eq("id", source_id).execute()
            return
        except Exception as update_error:
            if "chunk_count" in update_payload and _is_missing_column_error(update_error, "chunk_count"):
                update_payload.pop("chunk_count", None)
                continue
            raise


# =============================================================================
# Phase 1: Ingestion Modes
# =============================================================================

@router.post("/persona/link-compile/jobs/mode-a")
async def create_mode_a_job(
    background_tasks: BackgroundTasks,
    twin_id: str = Form(...),
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    """
    Mode A: Export Upload (LinkedIn, Twitter/X archives, PDFs).
    
    Upload export files for processing. Max 50MB per file.
    """
    user = _require_authenticated_user(user)
    user_id = user.get("user_id")
    verify_twin_ownership(twin_id, user)
    
    # Validate files
    if not files:
        raise HTTPException(400, "No files provided")
    
    if len(files) > 10:
        raise HTTPException(400, "Max 10 files per upload")
    
    # Parse uploaded files into text snippets for downstream processing.
    source_files = []
    for uploaded_file in files:
        file_bytes = await uploaded_file.read()
        size_bytes = len(file_bytes)
        if size_bytes > 50 * 1024 * 1024:
            raise HTTPException(400, f"File too large: {uploaded_file.filename} (max 50MB)")

        extracted_text = ""
        temp_path = None
        try:
            suffix = os.path.splitext(uploaded_file.filename or "")[1] or ".txt"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            parsed_items = parse_export_file(temp_path)
            extracted_text = "\n\n".join(
                str(item.get("content") or "").strip()
                for item in parsed_items
                if str(item.get("content") or "").strip()
            )
            if not extracted_text:
                extracted_text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        source_files.append({
            "filename": uploaded_file.filename,
            "size": size_bytes,
            "type": uploaded_file.content_type,
            # Keep payload bounded so row size doesn't explode.
            "content": extracted_text[:20000],
        })

    # Create job record
    job_data = {
        "twin_id": twin_id,
        "created_by": user_id,
        "mode": "A",
        "status": "pending",
        "source_files": source_files,
        "total_sources": len(files),
    }
    
    result = supabase.table("link_compile_jobs").insert(job_data).execute()
    job_id = result.data[0]["id"]
    
    _set_twin_status(twin_id, "ingesting")
    background_tasks.add_task(_run_job_background, job_id)
    
    return LinkCompileJobResponse(
        job_id=job_id,
        status="pending",
        mode="A",
        message=f"Upload accepted. {len(files)} files queued for processing.",
    )


@router.post("/persona/link-compile/jobs/mode-b")
async def create_mode_b_job(
    background_tasks: BackgroundTasks,
    request: ModeBPasteRequest,
    user=Depends(get_current_user),
):
    """
    Mode B: Paste/Import (Private sources).
    
    Paste text or upload private documents.
    """
    user = _require_authenticated_user(user)
    user_id = user.get("user_id")
    twin_id = request.twin_id
    verify_twin_ownership(twin_id, user)
    
    # Create job record
    job_data = {
        "twin_id": twin_id,
        "created_by": user_id,
        "mode": "B",
        "status": "pending",
        "source_files": [{
            "type": "pasted",
            "title": request.title,
            "source_context": request.source_context,
            "content": request.content,
        }],
        "total_sources": 1,
    }
    
    result = supabase.table("link_compile_jobs").insert(job_data).execute()
    job_id = result.data[0]["id"]
    
    _set_twin_status(twin_id, "ingesting")
    background_tasks.add_task(_run_job_background, job_id)
    
    return LinkCompileJobResponse(
        job_id=job_id,
        status="processing",
        mode="B",
        message="Content accepted. Processing...",
    )


@router.post("/persona/link-compile/jobs/mode-c")
async def create_mode_c_job(
    background_tasks: BackgroundTasks,
    request: ModeCUrlRequest,
    user=Depends(get_current_user),
):
    """
    Mode C: Public Web Fetch (GitHub, Blogs).
    
    Fetch public URLs for ingestion.
    URL preflight accepts all http(s) domains; final fetchability is determined during ingestion.
    """
    user = _require_authenticated_user(user)
    user_id = user.get("user_id")
    twin_id = request.twin_id
    verify_twin_ownership(twin_id, user)
    
    # Validate URLs
    allowed_urls = []
    blocked_urls = []
    
    for url in request.urls:
        check_result = await check_url_fetchable(url)
        
        if check_result["allowed"]:
            allowed_urls.append(url)
        else:
            blocked_urls.append({
                "url": url,
                "reason": check_result["reason"],
                "error_code": check_result["error_code"],
            })
    
    if not allowed_urls:
        raise HTTPException(
            400,
            detail={
                "message": "No URLs allowed for fetching",
                "blocked": blocked_urls,
            }
        )
    
    # Create job record
    job_data = {
        "twin_id": twin_id,
        "created_by": user_id,
        "mode": "C",
        "status": "pending",
        "source_urls": allowed_urls,
        "total_sources": len(allowed_urls),
    }
    
    result = supabase.table("link_compile_jobs").insert(job_data).execute()
    job_id = result.data[0]["id"]
    _set_twin_status(twin_id, "ingesting")
    background_tasks.add_task(_run_job_background, job_id)
    
    return LinkCompileJobResponse(
        job_id=job_id,
        status="processing",
        mode="C",
        message=f"{len(allowed_urls)} URLs accepted. {len(blocked_urls)} blocked.",
    )


# =============================================================================
# Job Status & Processing
# =============================================================================

@router.get("/persona/link-compile/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user=Depends(get_current_user),
):
    """Get status of a link compile job."""
    user = _require_authenticated_user(user)
    result = supabase.table("link_compile_jobs").select("*").eq("id", job_id).single().execute()
    
    if not result.data:
        raise HTTPException(404, "Job not found")

    verify_twin_ownership(result.data["twin_id"], user)
    
    return result.data


async def _process_job_impl(job_id: str):
    """Internal job processor used by both API endpoint and background tasks."""
    # Fetch job
    job_result = supabase.table("link_compile_jobs").select("*").eq("id", job_id).single().execute()
    
    if not job_result.data:
        raise HTTPException(404, "Job not found")
    
    job = job_result.data
    twin_id = job["twin_id"]
    mode = job["mode"]
    
    # Update status
    supabase.table("link_compile_jobs").update({
        "status": "processing",
        "started_at": datetime.utcnow().isoformat(),
    }).eq("id", job_id).execute()
    _set_twin_status(twin_id, "ingesting")

    try:
        chunks = []

        if mode == "A":
            source_files = job.get("source_files", []) or []
            for idx, source in enumerate(source_files):
                content = str(source.get("content") or "").strip()
                if not content:
                    continue
                filename = str(source.get("filename") or f"Upload {idx + 1}").strip() or f"Upload {idx + 1}"
                source_id = _create_link_compile_source(
                    twin_id=twin_id,
                    filename=filename,
                    content=content,
                )

                metadata_override: Dict[str, Any] = {
                    "filename": filename[:240],
                    "type": "link_compile_upload",
                }
                source_type = str(source.get("type") or "").strip()
                if source_type:
                    metadata_override["source_type"] = source_type

                num_chunks = await process_and_index_text(
                    source_id=source_id,
                    twin_id=twin_id,
                    text=content,
                    metadata_override=metadata_override,
                )
                _mark_source_live(source_id, num_chunks)
                chunks.append({"text": content, "source_id": source_id})
        
        elif mode == "B":
            source_files = job.get("source_files", []) or []
            source_info = source_files[0] if source_files else {}
            content = str(source_info.get("content") or "").strip()
            if content:
                title = str(source_info.get("title") or "Pasted Content").strip() or "Pasted Content"
                source_context = str(source_info.get("source_context") or "").strip()
                source_id = _create_link_compile_source(
                    twin_id=twin_id,
                    filename=f"Pasted: {title}"[:240],
                    content=content,
                )

                metadata_override: Dict[str, Any] = {
                    "filename": f"Pasted: {title}"[:240],
                    "type": "link_compile_paste",
                }
                if source_context:
                    metadata_override["source_context"] = source_context

                num_chunks = await process_and_index_text(
                    source_id=source_id,
                    twin_id=twin_id,
                    text=content,
                    metadata_override=metadata_override,
                )
                _mark_source_live(source_id, num_chunks)
                chunks = [{"text": content, "source_id": source_id}]
        
        elif mode == "C":
            urls = job.get("source_urls", [])
            failed_urls = []
            for url in urls:
                try:
                    source_id = await ingest_url(twin_id, url)
                    chunks.append({"source_id": source_id, "text": f"Content from {url}"})
                except Exception as e:
                    error_str = str(e).lower()
                    # Classify error for better user feedback
                    if "auth" in error_str or "age-restrict" in error_str or "sign in" in error_str:
                        error_type = "auth_required"
                    elif "not available" in error_str or "unavailable" in error_str:
                        error_type = "unavailable"
                    elif "robot" in error_str or "blocked" in error_str:
                        error_type = "blocked"
                    else:
                        error_type = "fetch_failed"
                    
                    failed_urls.append({"url": url, "error": str(e), "type": error_type})
                    print(f"[ModeC] Failed to fetch {url}: {e}")
            
            # If all URLs failed, try to create fallback sources with metadata
            # This ensures the job doesn't fail completely
            if not chunks and failed_urls:
                # Create fallback chunks from metadata for failed URLs
                for fail_info in failed_urls:
                    url = fail_info["url"]
                    # Create a minimal source with metadata only
                    try:
                        source_id = _create_link_compile_source(
                            twin_id=twin_id,
                            filename=f"Web: {url}"[:240],
                            content=f"URL: {url}\nStatus: {fail_info['type']}\nNote: Content could not be extracted. This URL may require authentication, be blocked, or have no accessible content.",
                        )
                        num_chunks = await process_and_index_text(
                            source_id=source_id,
                            twin_id=twin_id,
                            text=f"URL: {url}\nThis source was submitted but content could not be fully extracted.",
                            metadata_override={
                                "filename": f"Web: {url}"[:240],
                                "type": "link_compile_url_fallback",
                                "url": url,
                                "fetch_status": fail_info['type'],
                                "fetch_error": fail_info['error'][:500],
                            },
                        )
                        _mark_source_live(source_id, num_chunks)
                        chunks.append({
                            "source_id": source_id, 
                            "text": f"Fallback metadata for {url}",
                            "fetch_failed": True,
                            "error_type": fail_info['type']
                        })
                    except Exception as fallback_error:
                        print(f"[ModeC] Fallback metadata creation failed for {url}: {fallback_error}")

        if not chunks:
            raise ValueError(
                "No processable content found in submitted sources. "
                "All URLs failed to fetch. This can happen if:\n"
                "- URLs require authentication (YouTube age-restricted videos, private pages)\n"
                "- Sites block automated access (robots.txt, anti-bot protection)\n"
                "- URLs are invalid or content is unavailable\n"
                "Try uploading files directly or pasting content instead."
            )
        
        # Update progress
        supabase.table("link_compile_jobs").update({
            "status": "extracting_claims",
            "processed_sources": len(chunks),
        }).eq("id", job_id).execute()
        
        # Phase 2: Extract claims
        extraction_result = await extract_and_store_claims(chunks, twin_id, supabase)
        
        supabase.table("link_compile_jobs").update({
            "status": "compiling_persona",
            "extracted_claims": extraction_result["stored_count"],
        }).eq("id", job_id).execute()
        
        # Phase 3: Compile persona
        compiler = PersonaFromClaimsCompiler(supabase)
        compile_result = await compiler.compile_persona(twin_id)
        
        persona_spec = compile_result["persona_spec"]
        
        # Phase 4: Generate bios
        from modules.persona_claim_extractor import ClaimStore
        claim_store = ClaimStore(supabase)
        all_claims = await claim_store.get_claims_for_twin(twin_id)
        
        bio_result = await generate_and_store_bios(twin_id, all_claims, supabase)
        
        # Update job with results
        supabase.table("link_compile_jobs").update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "result_persona_spec": persona_spec.model_dump(),
            "result_claim_ids": extraction_result["claim_ids"],
            "result_bio_variants": {k: v.bio_text for k, v in bio_result.get("variants", {}).items()},
        }).eq("id", job_id).execute()
        _set_twin_status(twin_id, "claims_ready")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "claims_extracted": extraction_result["stored_count"],
            "clarification_questions": compile_result["clarification_questions"],
            "bio_variants_valid": bio_result["valid_count"],
        }
        
    except Exception as e:
        # Update job with error
        supabase.table("link_compile_jobs").update({
            "status": "failed",
            "error_message": str(e),
        }).eq("id", job_id).execute()
        
        raise HTTPException(500, f"Processing failed: {e}")


async def _run_job_background(job_id: str) -> None:
    try:
        await _process_job_impl(job_id)
    except Exception as exc:
        print(f"[LinkCompile] Background processing failed for {job_id}: {exc}")


@router.post("/persona/link-compile/jobs/{job_id}/process")
async def process_job(
    job_id: str,
    user=Depends(get_current_user),
):
    """
    Process a pending job (extract claims, compile persona).
    
    In production, this is triggered by background workers.
    """
    user = _require_authenticated_user(user)
    job_result = supabase.table("link_compile_jobs").select("twin_id").eq("id", job_id).single().execute()
    if not job_result.data:
        raise HTTPException(404, "Job not found")
    verify_twin_ownership(job_result.data["twin_id"], user)

    return await _process_job_impl(job_id)


# =============================================================================
# Phase 3: Clarification Interview
# =============================================================================

@router.get("/persona/link-compile/twins/{twin_id}/clarification-questions")
async def get_clarification_questions(
    twin_id: str,
    user=Depends(get_current_user),
):
    """
    Get clarification questions for low-confidence Layer 2/3 items.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    compiler = PersonaFromClaimsCompiler(supabase)
    result = await compiler.compile_persona(twin_id)
    
    return {
        "twin_id": twin_id,
        "questions": result["clarification_questions"],
        "low_confidence_count": len(result["clarification_questions"]),
    }


@router.post("/persona/link-compile/twins/{twin_id}/clarification-answers")
async def submit_clarification_answer(
    twin_id: str,
    request: ClarificationAnswerRequest,
    user=Depends(get_current_user),
):
    """
    Submit answer to a clarification question.
    Creates owner_direct claim and updates persona.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    result = await handle_clarification_answer(
        twin_id=twin_id,
        question=request.question,
        answer=request.answer,
        supabase_client=supabase,
    )
    
    return result


# =============================================================================
# Phase 4: Bio Variants
# =============================================================================

@router.get("/persona/link-compile/twins/{twin_id}/bios")
async def get_bio_variants(
    twin_id: str,
    user=Depends(get_current_user),
):
    """Get all generated bio variants for a twin."""
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    result = supabase.table("persona_bio_variants").select("*").eq("twin_id", twin_id).execute()
    
    return {
        "twin_id": twin_id,
        "variants": result.data or [],
    }


@router.get("/persona/link-compile/twins/{twin_id}/claims")
async def get_claims(
    twin_id: str,
    claim_type: Optional[str] = None,
    min_confidence: float = 0.0,
    user=Depends(get_current_user),
):
    """Get persona claims for a twin."""
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    query = (
        supabase.table("persona_claims")
        .select("*")
        .eq("twin_id", twin_id)
        .eq("is_active", True)
        .gte("confidence", min_confidence)
    )
    
    if claim_type:
        query = query.eq("claim_type", claim_type)
    
    result = query.execute()
    
    return {
        "twin_id": twin_id,
        "claims": result.data or [],
        "count": len(result.data or []),
    }


@router.post("/persona/link-compile/twins/{twin_id}/claims/{claim_id}/verify")
async def verify_claim(
    twin_id: str,
    claim_id: str,
    request: Optional[ClaimVerifyRequest] = None,
    user=Depends(get_current_user),
):
    """
    Compatibility endpoint for claim-level owner verification in claim-review UIs.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    is_verified = True if request is None else bool(request.verified)
    verification_status = "confirmed" if is_verified else "rejected"
    authority = "owner_direct" if is_verified else "extracted"

    result = (
        supabase.table("persona_claims")
        .update(
            {
                "verification_status": verification_status,
                "authority": authority,
                "verified_at": datetime.utcnow().isoformat(),
            }
        )
        .eq("id", claim_id)
        .eq("twin_id", twin_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(404, "Claim not found")

    return {
        "twin_id": twin_id,
        "claim_id": claim_id,
        "verification_status": verification_status,
        "authority": authority,
    }


# =============================================================================
# Twin Job Status (for polling)
# =============================================================================

@router.get("/persona/link-compile/twins/{twin_id}/job")
async def get_twin_link_compile_job(
    twin_id: str,
    user=Depends(get_current_user),
):
    """
    Get the latest link-compile job for a twin.
    Used by frontend for polling during ingestion.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    result = (
        supabase.table("link_compile_jobs")
        .select("*")
        .eq("twin_id", twin_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    
    if not result.data:
        raise HTTPException(404, "No job found for this twin")
    
    job = result.data[0]
    
    # Also get claim count
    claims_result = (
        supabase.table("persona_claims")
        .select("id", count="exact")
        .eq("twin_id", twin_id)
        .execute()
    )
    
    return {
        "job_id": job["id"],
        "status": job["status"],
        "mode": job["mode"],
        "source_urls": job.get("source_urls", []),
        "source_files": job.get("source_files", []),
        "total_sources": job.get("total_sources", 0),
        "processed_sources": job.get("processed_sources", 0),
        "extracted_claims": job.get("extracted_claims") or len(claims_result.data or []),
        "error_message": job.get("error_message"),
        "created_at": job["created_at"],
        "updated_at": job.get("updated_at"),
    }


# =============================================================================
# State Transition Endpoints
# =============================================================================

@router.post("/twins/{twin_id}/transition/clarification-pending")
async def transition_to_clarification_pending(
    twin_id: str,
    user=Depends(get_current_user),
):
    """
    Transition twin from 'claims_ready' to 'clarification_pending'.
    Called after user reviews and approves claims.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)
    tenant_id = user.get("tenant_id")
    
    _set_twin_status(twin_id, "clarification_pending")
    
    # Log transition
    AuditLogger.log(
        tenant_id=tenant_id,
        event_type="twin_status_transition",
        action="transition_to_clarification_pending",
        twin_id=twin_id,
        actor_id=user.get("user_id"),
        metadata={"from_status": "claims_ready", "to_status": "clarification_pending"},
    )
    
    return {"twin_id": twin_id, "status": "clarification_pending"}


@router.post("/twins/{twin_id}/transition/persona-built")
async def transition_to_persona_built(
    twin_id: str,
    user=Depends(get_current_user),
):
    """
    Transition twin from 'clarification_pending' to 'persona_built'.
    Called after user completes clarification questions.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)
    tenant_id = user.get("tenant_id")
    
    _set_twin_status(twin_id, "persona_built")
    
    # Log transition
    AuditLogger.log(
        tenant_id=tenant_id,
        event_type="twin_status_transition",
        action="transition_to_persona_built",
        twin_id=twin_id,
        actor_id=user.get("user_id"),
        metadata={"from_status": "clarification_pending", "to_status": "persona_built"},
    )
    
    return {"twin_id": twin_id, "status": "persona_built"}


@router.post("/twins/{twin_id}/transition/{target_state}")
async def transition_twin_state(
    twin_id: str,
    target_state: str,
    user=Depends(get_current_user),
):
    """
    Compatibility endpoint for generic transition calls from older clients.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)
    tenant_id = user.get("tenant_id")

    state_map = {
        "clarification-pending": "clarification_pending",
        "clarification_pending": "clarification_pending",
        "persona-built": "persona_built",
        "persona_built": "persona_built",
    }
    normalized = (target_state or "").strip().lower()
    status = state_map.get(normalized)
    if not status:
        raise HTTPException(400, f"Unsupported target_state: {target_state}")

    _set_twin_status(twin_id, status)

    AuditLogger.log(
        tenant_id=tenant_id,
        event_type="twin_status_transition",
        action="transition_twin_state",
        twin_id=twin_id,
        actor_id=user.get("user_id"),
        metadata={"to_status": status, "target_state": target_state},
    )

    return {"twin_id": twin_id, "status": status}


@router.post("/twins/{twin_id}/activate")
async def activate_twin(
    twin_id: str,
    request: Optional[ActivateTwinRequest] = None,
    final_name: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    Activate a link-first twin by setting status to 'active'.
    Creates the active persona spec from compiled data.
    """
    from modules.persona_spec_store_v2 import create_persona_spec_v2
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)
    tenant_id = user.get("tenant_id")
    resolved_final_name = request.final_name if request and request.final_name is not None else final_name
    
    # Get twin data
    twin_result = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
    if not twin_result.data:
        raise HTTPException(404, "Twin not found")
    
    twin = twin_result.data
    
    # Get the latest job with persona spec
    job_result = (
        supabase.table("link_compile_jobs")
        .select("*")
        .eq("twin_id", twin_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    
    if not job_result.data:
        raise HTTPException(400, "No link-compile job found for this twin")
    
    job = job_result.data[0]
    persona_spec = job.get("result_persona_spec")
    
    if not persona_spec:
        raise HTTPException(400, "Persona spec not yet compiled. Wait for job to complete.")
    
    # Update twin name if provided (separate from status for legacy-schema fallback).
    if resolved_final_name:
        rename_payload: Dict[str, Any] = {
            "name": resolved_final_name,
            "updated_at": datetime.utcnow().isoformat(),
        }
        while True:
            try:
                rename_result = (
                    supabase.table("twins")
                    .update(rename_payload)
                    .eq("id", twin_id)
                    .execute()
                )
                if not rename_result.data:
                    raise HTTPException(404, "Twin not found")
                break
            except Exception as rename_error:
                if "updated_at" in rename_payload and _is_missing_column_error(rename_error, "updated_at"):
                    rename_payload.pop("updated_at", None)
                    continue
                raise

    _set_twin_status(twin_id, "active")
    
    # Create active persona spec
    try:
        persona_record = create_persona_spec_v2(
            twin_id=twin_id,
            tenant_id=twin.get("tenant_id"),
            created_by=user.get("user_id"),
            spec=persona_spec,
            status="active",
            source="link-compile",
            metadata={
                "compiled_from_job": job["id"],
                "activation_time": datetime.utcnow().isoformat(),
            }
        )
    except Exception as e:
        print(f"[Activate] Warning: Failed to create persona spec: {e}")
        persona_record = None
    
    # Log activation
    AuditLogger.log(
        tenant_id=tenant_id,
        event_type="twin_activated",
        action="activate_twin",
        twin_id=twin_id,
        actor_id=user.get("user_id"),
        metadata={"mode": "link_first", "final_name": resolved_final_name},
    )
    
    return {
        "twin_id": twin_id,
        "status": "active",
        "name": resolved_final_name or twin.get("name"),
        "persona_spec_id": persona_record.get("id") if persona_record else None,
    }


# =============================================================================
# Link Suggestion (Deep Search)
# =============================================================================

class LinkSuggestionResponse(BaseModel):
    """Response for link suggestion endpoint."""
    candidates: list
    search_query: str
    total_found: int


@router.get("/persona/link-compile/suggest")
async def suggest_links(
    name: str,
    location: Optional[str] = None,
    role: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    Search for public links matching a person's identity.
    
    Returns ranked candidates with confidence scores and match signals.
    User must explicitly confirm which links are actually them.
    """
    _require_authenticated_user(user)
    from modules.robots_checker import check_url_fetchable
    
    # Build search query
    search_terms = [name]
    if location:
        search_terms.append(location)
    if role:
        search_terms.append(role)
    
    search_query = " ".join(search_terms)
    
    # TODO: Integrate with actual search API (Serper, Google Custom Search, etc.)
    # For now, return mock candidates that demonstrate the UX
    mock_candidates = [
        {
            "id": "cand_1",
            "url": f"https://linkedin.com/in/{name.lower().replace(' ', '-')}",
            "title": f"{name} - Professional Profile",
            "snippet": f"View {name}'s professional profile on LinkedIn. {role or ''}",
            "favicon": "https://linkedin.com/favicon.ico",
            "confidence": "high",
            "match_signals": ["Exact name match", "Professional profile"],
        },
        {
            "id": "cand_2", 
            "url": f"https://twitter.com/{name.lower().replace(' ', '')}",
            "title": f"{name} (@{name.lower().replace(' ', '')}) / X",
            "snippet": f"Follow {name} on X. {location or ''}",
            "favicon": "https://x.com/favicon.ico",
            "confidence": "medium",
            "match_signals": ["Name match", "Location match"],
        },
        {
            "id": "cand_3",
            "url": f"https://github.com/{name.lower().replace(' ', '-')}",
            "title": f"{name} · GitHub",
            "snippet": f"{name} has 42 repositories available. Follow their code on GitHub.",
            "favicon": "https://github.com/favicon.ico",
            "confidence": "medium",
            "match_signals": ["Name match"],
        },
    ]
    
    # Validate which URLs can actually be fetched
    valid_candidates = []
    for cand in mock_candidates:
        validation = await check_url_fetchable(cand["url"])
        if validation["allowed"]:
            valid_candidates.append(cand)
    
    normalized_candidates = []
    for cand in valid_candidates:
        normalized = dict(cand)
        if "matchSignals" not in normalized:
            normalized["matchSignals"] = normalized.get("match_signals", [])
        normalized_candidates.append(normalized)

    return LinkSuggestionResponse(
        candidates=normalized_candidates,
        search_query=search_query,
        total_found=len(normalized_candidates),
    )


# =============================================================================
# Validation Endpoints
# =============================================================================

@router.post("/persona/link-compile/validate-url")
async def validate_url(
    url: str,
    user=Depends(get_current_user),
):
    """
    Validate if a URL can be fetched (Mode C).
    Returns detailed reason if blocked.
    """
    _require_authenticated_user(user)
    result = await check_url_fetchable(url)
    
    return {
        "url": url,
        "allowed": result["allowed"],
        "reason": result["reason"],
        "error_code": result["error_code"],
        "crawl_delay": result["crawl_delay"],
    }
