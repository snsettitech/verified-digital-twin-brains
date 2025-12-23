from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from modules.auth_guard import verify_owner, get_current_user
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
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_youtube_transcript(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/podcast/{twin_id}")
async def ingest_podcast(twin_id: str, request: PodcastIngestRequest, user=Depends(verify_owner)):
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_podcast_rss(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/x/{twin_id}")
async def ingest_x(twin_id: str, request: XThreadIngestRequest, user=Depends(verify_owner)):
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_x_thread(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/{twin_id}")
async def ingest(twin_id: str, file: UploadFile = File(...), user=Depends(verify_owner)):
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
    try:
        await delete_source(source_id, twin_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources/{twin_id}")
async def list_sources(twin_id: str, user=Depends(get_current_user)):
    return get_sources(twin_id)

@router.post("/sources/{source_id}/approve")
async def approve_source_endpoint(source_id: str, user=Depends(verify_owner)):
    """Approve staged source → creates training job"""
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
    try:
        results = await bulk_approve_sources(request.source_ids)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/bulk-update")
async def bulk_update_sources_endpoint(request: BulkUpdateRequest, user=Depends(verify_owner)):
    """Bulk update metadata (access group, publish_date, author, citation_url, visibility)"""
    try:
        await bulk_update_source_metadata(request.source_ids, request.metadata)
        return {"status": "success", "message": f"Updated {len(request.source_ids)} source(s)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources/{source_id}/health")
async def get_source_health(source_id: str, user=Depends(get_current_user)):
    """Get health check results for a source"""
    try:
        health_status = get_source_health_status(source_id)
        return health_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources/{source_id}/logs")
async def get_source_logs(source_id: str, limit: int = 100, user=Depends(get_current_user)):
    """Get ingestion logs for a source"""
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
    from modules.training_jobs import process_training_job
    
    processed = 0
    failed = 0
    max_jobs = 10  # Process up to 10 jobs per request to avoid timeout
    
    # First, try to process from queue
    for _ in range(max_jobs):
        job = dequeue_job()
        if not job:
            break
        
        job_id = job["job_id"]
        try:
            print(f"Processing job {job_id} from queue")
            success = await process_training_job(job_id)
            if success:
                processed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
            failed += 1
    
    # Fallback: If queue is empty but there are queued jobs in DB, process them directly
    if processed == 0 and twin_id:
        try:
            queued_jobs = list_training_jobs(twin_id, status="queued", limit=max_jobs)
            for job in queued_jobs:
                job_id = job["id"]
                try:
                    print(f"Processing job {job_id} from database (queue was empty)")
                    success = await process_training_job(job_id)
                    if success:
                        processed += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"Error processing job {job_id}: {e}")
                    failed += 1
        except Exception as e:
            print(f"Error fetching queued jobs from database: {e}")
    
    remaining = get_queue_length()
    
    return {
        "status": "success",
        "processed": processed,
        "failed": failed,
        "remaining": remaining,
        "message": f"Processed {processed} job(s), {failed} failed, {remaining} remaining in queue"
    }

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
    try:
        sources = get_dead_letter_queue(twin_id)
        return sources
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/{source_id}/retry")
async def retry_source_ingestion(source_id: str, user=Depends(verify_owner)):
    """Retry failed ingestion"""
    try:
        # Get twin_id from source
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
