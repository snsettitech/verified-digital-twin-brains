"""
persona_link_compile.py

Phase 1-5 API Router: Link-First Persona Compiler endpoints.
"""

import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from datetime import datetime

from modules.auth_guard import get_current_user
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
    urls: List[str] = Field(..., min_items=1, max_items=10)
    allowlisted_domains: Optional[List[str]] = Field(default=None)


class ModeBPasteRequest(BaseModel):
    """Mode B: Paste/import request."""
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


# =============================================================================
# Phase 1: Ingestion Modes
# =============================================================================

@router.post("/persona/link-compile/jobs/mode-a")
async def create_mode_a_job(
    twin_id: str,
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    """
    Mode A: Export Upload (LinkedIn, Twitter/X archives, PDFs).
    
    Upload export files for processing. Max 50MB per file.
    """
    user_id = user.get("user_id")
    
    # Validate files
    if not files:
        raise HTTPException(400, "No files provided")
    
    if len(files) > 10:
        raise HTTPException(400, "Max 10 files per upload")
    
    # Create job record
    job_data = {
        "twin_id": twin_id,
        "created_by": user_id,
        "mode": "A",
        "status": "pending",
        "source_files": [
            {"filename": f.filename, "size": f.size if hasattr(f, 'size') else 0, "type": f.content_type}
            for f in files
        ],
        "total_sources": len(files),
    }
    
    result = supabase.table("link_compile_jobs").insert(job_data).execute()
    job_id = result.data[0]["id"]
    
    # Process files asynchronously (in production, use background tasks)
    # For now, return job ID for polling
    
    return LinkCompileJobResponse(
        job_id=job_id,
        status="pending",
        mode="A",
        message=f"Upload accepted. {len(files)} files queued for processing.",
    )


@router.post("/persona/link-compile/jobs/mode-b")
async def create_mode_b_job(
    twin_id: str,
    request: ModeBPasteRequest,
    user=Depends(get_current_user),
):
    """
    Mode B: Paste/Import (Private sources).
    
    Paste text or upload private documents.
    """
    user_id = user.get("user_id")
    
    # Create job record
    job_data = {
        "twin_id": twin_id,
        "created_by": user_id,
        "mode": "B",
        "status": "processing",
        "source_files": [{"type": "pasted", "title": request.title}],
        "total_sources": 1,
    }
    
    result = supabase.table("link_compile_jobs").insert(job_data).execute()
    job_id = result.data[0]["id"]
    
    # Process immediately (text is small)
    # In production, this should be async
    
    return LinkCompileJobResponse(
        job_id=job_id,
        status="processing",
        mode="B",
        message="Content accepted. Processing...",
    )


@router.post("/persona/link-compile/jobs/mode-c")
async def create_mode_c_job(
    twin_id: str,
    request: ModeCUrlRequest,
    user=Depends(get_current_user),
):
    """
    Mode C: Public Web Fetch (GitHub, Blogs).
    
    Fetch publicly crawlable URLs. Enforces robots.txt and domain allowlist.
    LinkedIn and X/Twitter are BLOCKED - use Mode A instead.
    """
    user_id = user.get("user_id")
    
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
    
    return LinkCompileJobResponse(
        job_id=job_id,
        status="pending",
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
    result = supabase.table("link_compile_jobs").select("*").eq("id", job_id).single().execute()
    
    if not result.data:
        raise HTTPException(404, "Job not found")
    
    return result.data


@router.post("/persona/link-compile/jobs/{job_id}/process")
async def process_job(
    job_id: str,
    user=Depends(get_current_user),
):
    """
    Process a pending job (extract claims, compile persona).
    
    In production, this is triggered by background workers.
    """
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
    
    try:
        # Phase 1: Ingest sources
        chunks = []
        
        if mode == "A":
            # Mode A: Process uploaded files
            # In production, files are retrieved from storage
            pass
        
        elif mode == "B":
            # Mode B: Process pasted content
            source_id = f"paste_{job_id}"
            # Create source, chunk it
            await process_and_index_text(
                source_id=source_id,
                twin_id=twin_id,
                text=job.get("source_files", [{}])[0].get("content", ""),
            )
            chunks = [{"text": job.get("source_files", [{}])[0].get("content", ""), "source_id": source_id}]
        
        elif mode == "C":
            # Mode C: Fetch URLs
            urls = job.get("source_urls", [])
            for url in urls:
                try:
                    source_id = await ingest_url(twin_id, url)
                    chunks.append({"source_id": source_id, "text": f"Content from {url}"})
                except Exception as e:
                    print(f"[ModeC] Failed to fetch {url}: {e}")
        
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
    result = await check_url_fetchable(url)
    
    return {
        "url": url,
        "allowed": result["allowed"],
        "reason": result["reason"],
        "error_code": result["error_code"],
        "crawl_delay": result["crawl_delay"],
    }
