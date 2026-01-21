from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership, verify_source_ownership
from modules.ingestion import ingest_youtube_transcript_wrapper, ingest_podcast_transcript, ingest_x_thread_wrapper, ingest_file, ingest_url
from modules.observability import supabase
from modules.training_jobs import get_training_job, process_training_queue
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

@router.post("/ingest/youtube/{twin_id}")
async def ingest_youtube(twin_id: str, request: YouTubeIngestRequest, user=Depends(verify_owner)):
    try:
        source_id = await ingest_youtube_transcript_wrapper(twin_id, request.url)
        return {"source_id": source_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/podcast/{twin_id}")
async def ingest_podcast(twin_id: str, request: PodcastIngestRequest, user=Depends(verify_owner)):
    try:
        source_id = await ingest_podcast_transcript(twin_id, request.url)
        return {"source_id": source_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/x/{twin_id}")
async def ingest_x(twin_id: str, request: XThreadIngestRequest, user=Depends(verify_owner)):
    try:
        source_id = await ingest_x_thread_wrapper(twin_id, request.url)
        return {"source_id": source_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/file/{twin_id}")
async def ingest_file_endpoint(
    twin_id: str,
    file: UploadFile = File(...),
    user=Depends(verify_owner)
):
    try:
        source_id = await ingest_file(twin_id, file)
        return {"source_id": source_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/url/{twin_id}")
async def ingest_url_endpoint(twin_id: str, request: URLIngestRequest, user=Depends(verify_owner)):
    try:
        source_id = await ingest_url(twin_id, request.url)
        return {"source_id": source_id, "status": "processing"}
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

    # Get user's twins
    twins_result = supabase.table("twins").select("id").eq("tenant_id", user_id).execute()
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
    
    # Get source and verify ownership
    source_result = supabase.table("sources").select(
        "id, twin_id, content_text, filename, status"
    ).eq("id", source_id).single().execute()
    
    if not source_result.data:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source = source_result.data
    twin_id = source["twin_id"]
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
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
        
        # Update source to mark extraction complete
        supabase.table("sources").update({
            "health_status": "extracted"
        }).eq("id", source_id).execute()
        
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
