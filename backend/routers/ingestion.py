from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership, verify_source_ownership
from modules.ingestion import ingest_youtube_transcript_wrapper, ingest_podcast_transcript, ingest_x_thread_wrapper, ingest_file, ingest_url
from modules.observability import supabase
from modules.training_jobs import get_training_job, process_training_queue, list_training_jobs
from modules.job_queue import enqueue_job
from pydantic import BaseModel
from typing import Optional, List
import os

router = APIRouter(tags=["ingestion"])

class YouTubeIngestRequest(BaseModel):
    url: str

class PodcastIngestRequest(BaseModel):
    url: str

class XThreadIngestRequest(BaseModel):
    url: str

class URLIngestRequest(BaseModel):
    url: str

class URLIngestWithTwinRequest(BaseModel):
    url: str
    twin_id: str

@router.post("/ingest/youtube/{twin_id}")
async def ingest_youtube(twin_id: str, request: YouTubeIngestRequest, user=Depends(verify_owner)):
    # SECURITY: Verify user owns this twin before ingesting content
    verify_twin_ownership(twin_id, user)
    try:
        source_id = await ingest_youtube_transcript_wrapper(twin_id, request.url)
        return {"source_id": source_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/podcast/{twin_id}")
async def ingest_podcast(twin_id: str, request: PodcastIngestRequest, user=Depends(verify_owner)):
    # SECURITY: Verify user owns this twin before ingesting content
    verify_twin_ownership(twin_id, user)
    try:
        source_id = await ingest_podcast_transcript(twin_id, request.url)
        return {"source_id": source_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/x/{twin_id}")
async def ingest_x(twin_id: str, request: XThreadIngestRequest, user=Depends(verify_owner)):
    # SECURITY: Verify user owns this twin before ingesting content
    verify_twin_ownership(twin_id, user)
    try:
        source_id = await ingest_x_thread_wrapper(twin_id, request.url)
        return {"source_id": source_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/file/{twin_id}")
async def ingest_file_endpoint(
    twin_id: str,
    file: UploadFile = File(...),
    auto_index: bool = True,
    user=Depends(verify_owner)
):
    """
    Ingest a file for the specified twin.
    
    Args:
        twin_id: Owner twin ID
        file: The file to upload
        auto_index: If True (default), bypasses staging and indexes directly to Pinecone
    """
    # SECURITY: Verify user owns this twin before ingesting content
    verify_twin_ownership(twin_id, user)
    try:
        source_id = await ingest_file(twin_id, file, auto_index=auto_index)
        status = "live" if auto_index else "staged"
        return {"source_id": source_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/url/{twin_id}")
async def ingest_url_endpoint(twin_id: str, request: URLIngestRequest, user=Depends(verify_owner)):
    """Ingest content from URL - auto-detects type (YouTube, X, Podcast, or generic page)."""
    # SECURITY: Verify user owns this twin before ingesting content
    verify_twin_ownership(twin_id, user)
    try:
        source_id = await ingest_url(twin_id, request.url, auto_index=True)
        # All URL types now auto-index directly, so status will be live
        return {"source_id": source_id, "status": "live"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------------------------
# Compatibility shims (Phase 2)
# ---------------------------------------------------------------------------

@router.post("/ingest/document")
async def ingest_document_compat(
    file: UploadFile = File(...),
    twin_id: str = Form(...),
    auto_index: bool = True,
    user=Depends(verify_owner)
):
    """
    Compatibility shim for onboarding:
    Accepts form-data with file + twin_id and forwards to canonical /ingest/file/{twin_id}.
    """
    print("[DEPRECATED] /ingest/document called. Use /ingest/file/{twin_id}.")
    verify_twin_ownership(twin_id, user)
    try:
        source_id = await ingest_file(twin_id, file, auto_index=auto_index)
        status = "live" if auto_index else "staged"
        return {"source_id": source_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/url")
async def ingest_url_compat(request: URLIngestWithTwinRequest, user=Depends(verify_owner)):
    """
    Compatibility shim for onboarding:
    Accepts JSON { url, twin_id } and forwards to canonical /ingest/url/{twin_id}.
    """
    print("[DEPRECATED] /ingest/url called without twin_id in path. Use /ingest/url/{twin_id}.")
    verify_twin_ownership(request.twin_id, user)
    try:
        source_id = await ingest_url(request.twin_id, request.url, auto_index=True)
        return {"source_id": source_id, "status": "live"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/training-jobs/process-queue")
async def process_queue_endpoint(twin_id: Optional[str] = None, user=Depends(verify_owner)):
    """
    Process queued training jobs for the authenticated user's twins.
    Returns status: "success", "partial", or "error" with details.
    """
    # Get user's twin IDs
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Get user's twins - use tenant_id NOT user_id!
    # CRITICAL FIX: user_id is auth UUID, tenant_id is the actual tenant association
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return {
            "status": "error",
            "processed": 0,
            "failed": 0,
            "remaining": 0,
            "message": "User has no tenant association"
        }
    twins_result = supabase.table("twins").select("id").eq("tenant_id", tenant_id).execute()
    user_twin_ids = [t["id"] for t in (twins_result.data or [])]

    if not user_twin_ids:
        return {
            "status": "success",
            "processed": 0,
            "failed": 0,
            "remaining": 0,
            "message": "No twins found for this user"
        }

    # Filter by twin_id if provided
    if twin_id:
        if twin_id not in user_twin_ids:
            raise HTTPException(status_code=403, detail="Not authorized to process jobs for this twin")
        twin_ids_to_process = [twin_id]
    else:
        twin_ids_to_process = user_twin_ids

    # Process queue (async function - must await)
    results = await process_training_queue(twin_ids_to_process)

    processed = results.get("processed", 0)
    failed = results.get("failed", 0)
    remaining = results.get("remaining", 0)
    errors = results.get("errors", [])

    # Determine overall status
    if failed == 0:
        status = "success"
    elif processed > 0:
        status = "partial"
    else:
        status = "error"

    response_data = {
        "status": status,
        "processed": processed,
        "failed": failed,
        "remaining": remaining,
        "errors": errors[:5]  # Limit to first 5 errors
    }

    # If all failed, include first error in message
    if processed == 0 and failed > 0:
        response_data["message"] = f"Failed to process {failed} job(s). First error: {errors[0]}"

    # Return appropriate HTTP status codes
    # Note: Always return 200 OK to maintain backward compatibility
    # Frontend can check response_data.status === "error" to handle errors appropriately
    # This prevents breaking changes for clients expecting HTTP 200 OK
    return response_data

@router.get("/training-jobs/{job_id}")
async def get_training_job_endpoint(job_id: str, user=Depends(get_current_user)):
    """Get job details"""
    try:
        job = get_training_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Verify user has access to this job's twin
        if job.get("twin_id"):
            verify_twin_ownership(job["twin_id"], user)

        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-jobs")
async def list_training_jobs_endpoint(
    twin_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    user=Depends(get_current_user)
):
    """List training jobs for a twin."""
    verify_twin_ownership(twin_id, user)
    try:
        return list_training_jobs(twin_id=twin_id, status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training-jobs/{job_id}/retry")
async def retry_training_job_endpoint(job_id: str, user=Depends(verify_owner)):
    """Retry a failed training job by re-queueing it."""
    job = get_training_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify user has access to this job's twin
    if job.get("twin_id"):
        verify_twin_ownership(job["twin_id"], user)

    try:
        # Reset status and error before re-queue
        supabase.table("training_jobs").update({
            "status": "queued",
            "error_message": None
        }).eq("id", job_id).execute()

        enqueue_job(
            job_id=job_id,
            job_type=job.get("job_type", "ingestion"),
            priority=job.get("priority", 0),
            metadata=job.get("metadata", {})
        )

        return {"status": "queued", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExtractNodesRequest(BaseModel):
    """Request to extract graph nodes from an ingested source."""
    max_chunks: Optional[int] = 10  # Limit chunks to control cost


@router.post("/ingest/extract-nodes/{source_id}")
async def extract_nodes_from_source(
    source_id: str,
    request: ExtractNodesRequest = None,
    user=Depends(get_current_user)
):
    """
    Extract graph nodes/edges from an ingested source's content.
    
    Takes the content_text from a staged/approved source and runs it through
    the Scribe Engine to create graph_nodes and graph_edges.
    
    This bridges content ingestion with the cognitive graph.
    """
    from modules._core.scribe_engine import extract_from_content
    
    # HARDENED: Verify source ownership and tenant/twin association
    # This ensures the source belongs to a twin owned by the user's tenant.
    twin_id = verify_source_ownership(source_id, user)
    
    # Fetch source content (now that ownership is verified)
    source_result = supabase.table("sources").select(
        "id, content_text, filename, status"
    ).eq("id", source_id).single().execute()
    
    if not source_result.data:
        raise HTTPException(status_code=404, detail="Source not found or access denied")
    
    source = source_result.data

    
    content_text = source.get("content_text")
    if not content_text:
        raise HTTPException(status_code=400, detail="Source has no content_text to extract from")
    
    # Determine source type from filename
    filename = source.get("filename", "")
    source_type = "ingested_content"
    if "YouTube" in filename:
        source_type = "youtube"
    elif "Podcast" in filename:
        source_type = "podcast"
    elif filename.endswith(".pdf"):
        source_type = "pdf"
    elif "X Thread" in filename:
        source_type = "twitter"
    
    # Run extraction
    try:
        max_chunks = request.max_chunks if request else 10
        
        result = await extract_from_content(
            twin_id=twin_id,
            content_text=content_text,
            source_id=source_id,
            source_type=source_type,
            max_chunks=max_chunks,
            tenant_id=user.get("user_id")
        )
        
        return {
            "status": "success",
            "source_id": source_id,
            "nodes_created": len(result.get("all_nodes", [])),
            "edges_created": len(result.get("all_edges", [])),
            "chunks_processed": result.get("chunks_processed", 0),
            "confidence": result.get("total_confidence", 0.0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
