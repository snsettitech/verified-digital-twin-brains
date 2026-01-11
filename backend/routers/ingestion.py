from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership, verify_source_ownership
from modules.schemas import (
    YouTubeIngestRequest, PodcastIngestRequest, XThreadIngestRequest,
    SourceRejectRequest, BulkApproveRequest, BulkUpdateRequest
)
from modules.ingestion import (
    ingest_youtube_transcript, ingest_podcast_rss, ingest_x_thread, ingest_source,
    delete_source, approve_source, reject_source, bulk_approve_sources, bulk_update_source_metadata
)
from modules.observability import get_sources, get_ingestion_logs, get_dead_letter_queue, supabase
from modules.health_checks import get_source_health_status
from modules.training_jobs import list_training_jobs, get_training_job, update_job_status
from worker import process_single_job
import uuid
import os
import shutil
from typing import Optional

router = APIRouter(tags=["ingestion"])

@router.post("/ingest/youtube/{twin_id}")
async def ingest_youtube(twin_id: str, request: YouTubeIngestRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_youtube_transcript(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/podcast/{twin_id}")
async def ingest_podcast(twin_id: str, request: PodcastIngestRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_podcast_rss(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/x/{twin_id}")
async def ingest_x(twin_id: str, request: XThreadIngestRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_x_thread(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/{twin_id}")
async def ingest(twin_id: str, file: UploadFile = File(...), user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    # Save file temporarily
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    source_id = str(uuid.uuid4())
    
    try:
        num_chunks = await ingest_source(source_id, twin_id, file_path, file.filename)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@router.delete("/sources/{twin_id}/{source_id}")
async def remove_source(twin_id: str, source_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    try:
        await delete_source(source_id, twin_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources/{twin_id}")
async def list_sources(twin_id: str, user=Depends(get_current_user)):
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    return get_sources(twin_id)

@router.post("/sources/{source_id}/approve")
async def approve_source_endpoint(source_id: str, user=Depends(verify_owner)):
    """Approve staged source → creates training job"""
    verify_source_ownership(source_id, user)
    try:
        job_id = await approve_source(source_id)
        return {"status": "success", "job_id": job_id, "message": "Source approved, training job created"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/{source_id}/reject")
async def reject_source_endpoint(source_id: str, request: SourceRejectRequest, user=Depends(verify_owner)):
    """Reject source with reason"""
    verify_source_ownership(source_id, user)
    try:
        await reject_source(source_id, request.reason)
        return {"status": "success", "message": "Source rejected"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/bulk-approve")
async def bulk_approve_sources_endpoint(request: BulkApproveRequest, user=Depends(verify_owner)):
    """Bulk approve multiple sources"""
    # Verify ownership of all sources
    for source_id in request.source_ids:
        verify_source_ownership(source_id, user)
    try:
        results = await bulk_approve_sources(request.source_ids)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/bulk-update")
async def bulk_update_sources_endpoint(request: BulkUpdateRequest, user=Depends(verify_owner)):
    """Bulk update metadata (access group, publish_date, author, citation_url, visibility)"""
    # Verify ownership of all sources
    for source_id in request.source_ids:
        verify_source_ownership(source_id, user)
    try:
        await bulk_update_source_metadata(request.source_ids, request.metadata)
        return {"status": "success", "message": f"Updated {len(request.source_ids)} source(s)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources/{source_id}/health")
async def get_source_health(source_id: str, user=Depends(get_current_user)):
    """Get health check results for a source"""
    verify_source_ownership(source_id, user)
    try:
        health_status = get_source_health_status(source_id)
        return health_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources/{source_id}/logs")
async def get_source_logs(source_id: str, limit: int = 100, user=Depends(get_current_user)):
    """Get ingestion logs for a source"""
    verify_source_ownership(source_id, user)
    try:
        logs = get_ingestion_logs(source_id, limit=limit)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/training-jobs")
async def list_training_jobs_endpoint(twin_id: Optional[str] = None, status: Optional[str] = None, user=Depends(get_current_user)):
    """List training jobs (with filters: status, twin_id)"""
    try:
        if not twin_id:
            # Get twin_id from user context if available
            # For now, require twin_id as query param
            raise HTTPException(status_code=400, detail="twin_id query parameter is required")
        jobs = list_training_jobs(twin_id, status=status)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/training-jobs/process-queue")
async def process_queue_endpoint(twin_id: Optional[str] = None, user=Depends(verify_owner)):
    """Process all queued jobs (on-demand, runs in API process)"""
    from modules.job_queue import dequeue_job, get_queue_length
    from modules.training_jobs import process_training_job, list_training_jobs
    import traceback
    
    # Validate twin_id is provided
    if not twin_id:
        raise HTTPException(
            status_code=400, 
            detail="twin_id query parameter is required"
        )
    
    # Verify user owns this twin
    verify_twin_ownership(twin_id, user)
    
    processed = 0
    failed = 0
    errors = []  # Track error messages
    max_jobs = 10  # Process up to 10 jobs per request to avoid timeout
    
    # First, try to process from queue
    for _ in range(max_jobs):
        job = dequeue_job()
        if not job:
            break
        
        job_id = job["job_id"]
        try:
            print(f"[Process Queue] Processing job {job_id} from queue")
            success = await process_training_job(job_id)
            if success:
                processed += 1
                print(f"[Process Queue] Job {job_id} completed successfully")
            else:
                failed += 1
                errors.append(f"Job {job_id}: Processing returned False")
        except Exception as e:
            error_msg = f"Job {job_id}: {str(e)}"
            print(f"[Process Queue] Error processing job {job_id}: {e}")
            print(traceback.format_exc())
            errors.append(error_msg)
            failed += 1
    
    # Fallback: If queue is empty but there are queued jobs in DB, process them directly
    if processed == 0 and twin_id:
        try:
            print(f"[Process Queue] Queue empty, checking database for queued jobs (twin_id: {twin_id})")
            queued_jobs = list_training_jobs(twin_id, status="queued", limit=max_jobs)
            print(f"[Process Queue] Found {len(queued_jobs)} queued jobs in database")
            
            for job in queued_jobs:
                job_id = job["id"]
                try:
                    print(f"[Process Queue] Processing job {job_id} from database (queue was empty)")
                    success = await process_training_job(job_id)
                    if success:
                        processed += 1
                        print(f"[Process Queue] Job {job_id} completed successfully")
                    else:
                        failed += 1
                        errors.append(f"Job {job_id}: Processing returned False")
                except Exception as e:
                    error_msg = f"Job {job_id}: {str(e)}"
                    print(f"[Process Queue] Error processing job {job_id}: {e}")
                    print(traceback.format_exc())
                    errors.append(error_msg)
                    failed += 1
        except Exception as e:
            error_msg = f"Error fetching queued jobs from database: {str(e)}"
            print(f"[Process Queue] {error_msg}")
            print(traceback.format_exc())
            errors.append(error_msg)
    
    remaining = get_queue_length()
    
    # Determine status based on results
    if failed > 0 and processed == 0:
        status = "error"
    elif failed > 0:
        status = "partial"
    else:
        status = "success"
    
    response_data = {
        "status": status,
        "processed": processed,
        "failed": failed,
        "remaining": remaining,
        "message": f"Processed {processed} job(s), {failed} failed, {remaining} remaining in queue"
    }
    
    # Include error details if any
    if errors:
        response_data["errors"] = errors[:5]  # Limit to first 5 errors to avoid huge response
        # If all failed, include first error in message
        if processed == 0 and failed > 0:
            response_data["message"] = f"Failed to process {failed} job(s). First error: {errors[0]}"
    
    # Return appropriate HTTP status codes
    if status == "error":
        # All jobs failed - return 500 Internal Server Error
        # Use JSONResponse to return error status code with full error details in body
        return JSONResponse(
            status_code=500,
            content=response_data
        )
    elif status == "partial":
        # Some succeeded, some failed - return 200 OK with status in body
        # Frontend can check response_data.status === "partial" to handle appropriately
        return response_data
    else:
        # All succeeded - return 200 OK
        return response_data

@router.get("/training-jobs/{job_id}")
async def get_training_job_endpoint(job_id: str, user=Depends(get_current_user)):
    """Get job details"""
    try:
        job = get_training_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Training job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/{source_id}/re-extract")
async def re_extract_source_text(source_id: str, user=Depends(verify_owner)):
    """
    Re-extracts text content for a source that lost its content_text.
    Useful for fixing sources that were approved but have no content.
    Currently only supports X Thread sources.
    """
    import re
    import httpx
    
    # Get source info
    source_response = supabase.table("sources").select("*").eq("id", source_id).single().execute()
    if not source_response.data:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source_data = source_response.data
    twin_id = source_data["twin_id"]
    filename = source_data.get("filename", "")
    
    # Verify ownership
    verify_twin_ownership(twin_id, user)
    
    # Check if it's an X Thread source
    if filename.startswith("X Thread:"):
        # Extract tweet ID from filename
        tweet_id_match = re.search(r'X Thread: (\d+)', filename)
        if tweet_id_match:
            tweet_id = tweet_id_match.group(1)
            # Re-fetch from X API
            try:
                syndication_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
                async with httpx.AsyncClient() as client:
                    response = await client.get(syndication_url)
                    if response.status_code == 200:
                        data = response.json()
                        text = data.get("text", "")
                        
                        if text:
                            # Update source with extracted text
                            supabase.table("sources").update({
                                "content_text": text,
                                "extracted_text_length": len(text),
                                "staging_status": "staged"  # Reset to staged so it can be re-approved
                            }).eq("id", source_id).execute()
                            
                            return {
                                "status": "success",
                                "message": f"Re-extracted {len(text)} characters from X Thread",
                                "extracted_text_length": len(text)
                            }
                        else:
                            raise HTTPException(
                                status_code=400,
                                detail="X Thread API returned empty text. The tweet may have been deleted or is unavailable."
                            )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to fetch X Thread: HTTP {response.status_code}"
                        )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error re-extracting X Thread: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Could not extract tweet ID from source filename"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Re-extraction is only supported for X Thread sources. For other sources, please delete and re-upload."
        )

@router.post("/training-jobs/{job_id}/retry")
async def retry_training_job(job_id: str, user=Depends(verify_owner)):
    """Retry failed job"""
    try:
        job = get_training_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Training job not found")
        
        # Get the error message from the job to provide context
        previous_error = job.get("error_message", "Unknown error")
        
        # Reset job status and clear error
        update_job_status(job_id, "queued", error_message=None)
        
        # Process the job
        success = await process_single_job(job_id)
        
        if success:
            return {"status": "success", "message": "Job retried successfully"}
        else:
            # Get the updated job to see the new error message
            updated_job = get_training_job(job_id)
            new_error = updated_job.get("error_message", "Job processing failed") if updated_job else "Job processing failed"
            raise HTTPException(status_code=500, detail=f"Job processing failed: {new_error}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("/dead-letter-queue")
async def get_dead_letter_queue_endpoint(twin_id: str, user=Depends(verify_owner)):
    """List sources needing attention"""
    verify_twin_ownership(twin_id, user)
    try:
        sources = get_dead_letter_queue(twin_id)
        return sources
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/{source_id}/retry")
async def retry_source_ingestion(source_id: str, user=Depends(verify_owner)):
    """Retry failed ingestion"""
    verify_source_ownership(source_id, user)
    try:
        # Get twin_id from source (already verified by verify_source_ownership, but need it for the function call)
        source_response = supabase.table("sources").select("twin_id").eq("id", source_id).single().execute()
        if not source_response.data:
            raise HTTPException(status_code=404, detail="Source not found")
        
        twin_id = source_response.data["twin_id"]
        # Assuming retry_failed_ingestion is not imported or needed logic for now
        # Logic from main.py seemed to use a function not imported or local check
        # Checking main.py for retry_failed_ingestion import...
        from modules.ingestion import retry_failed_ingestion
        job_id = retry_failed_ingestion(source_id, twin_id)
        return {"status": "success", "job_id": job_id, "message": "Retry initiated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
