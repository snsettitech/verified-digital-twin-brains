"""
Training Jobs Module
Manages training job lifecycle and processing.
"""
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from modules.observability import supabase
from modules.job_queue import enqueue_job
from modules.twin_namespace import get_namespace_candidates_for_twin
# Note: process_and_index_text is imported inside process_training_job to avoid circular import


def _update_source_row(source_id: str, payload: Dict[str, Any]) -> None:
    """
    Update a source row while tolerating deployments that already dropped
    the legacy `staging_status` column.
    """
    try:
        supabase.table("sources").update(payload).eq("id", source_id).execute()
    except Exception as update_error:
        message = str(update_error).lower()
        if "staging_status" in message and "sources" in message:
            fallback = dict(payload)
            fallback.pop("staging_status", None)
            supabase.table("sources").update(fallback).eq("id", source_id).execute()
        else:
            raise


def _schedule_metrics_update(twin_id: str) -> None:
    """
    Schedule training metrics update as a background task.
    
    This fire-and-forget approach ensures metrics recomputation doesn't
    block the job processing pipeline.
    """
    async def _update():
        try:
            from modules.training_metrics import update_twin_training_metrics, is_training_metrics_enabled
            if is_training_metrics_enabled():
                await asyncio.to_thread(update_twin_training_metrics, twin_id)
        except Exception as e:
            print(f"[TrainingJobs] Background metrics update failed for twin {twin_id}: {e}")
    
    # Create and schedule the background task
    try:
        asyncio.create_task(_update())
    except Exception as e:
        print(f"[TrainingJobs] Failed to schedule metrics update: {e}")


def create_training_job(source_id: str, twin_id: str, job_type: str = 'ingestion',
                       priority: int = 0, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Creates job record and adds to Redis queue.
    
    Args:
        source_id: Source UUID
        twin_id: Twin UUID
        job_type: Type of job ('ingestion', 'reindex', 'health_check')
        priority: Priority level (higher = processed first, default 0)
        metadata: Optional job parameters
    
    Returns:
        Job ID (UUID)
    """
    job_id = str(uuid.uuid4())

    # Create job record in database
    supabase.table("training_jobs").insert({
        "id": job_id,
        "source_id": source_id,
        "twin_id": twin_id,
        "status": "queued",
        "job_type": job_type,
        "priority": priority,
        "metadata": metadata or {}
    }).execute()

    # Add to queue
    enqueue_job(job_id, job_type, priority, metadata)

    return job_id


def get_training_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Fetches job details."""
    try:
        response = supabase.table("training_jobs").select("*").eq("id", job_id).single().execute()
        return response.data if response.data else None
    except Exception as e:
        print(f"Error fetching training job: {e}")
        return None


def update_job_status(job_id: str, status: str, error_message: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None):
    """
    Updates job status.
    
    Args:
        job_id: Job UUID
        status: New status ('queued', 'processing', 'needs_attention', 'complete', 'failed')
        error_message: Optional error message
        metadata: Optional metadata updates
    """
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }

    # Get current job to check existing fields
    current_job = get_training_job(job_id)

    if status == "processing" and current_job and not current_job.get("started_at"):
        update_data["started_at"] = datetime.utcnow().isoformat()

    if status in ("complete", "failed", "needs_attention") and current_job and not current_job.get("completed_at"):
        update_data["completed_at"] = datetime.utcnow().isoformat()

    if error_message:
        update_data["error_message"] = error_message

    if metadata:
        # Merge with existing metadata
        existing_metadata = current_job.get("metadata", {}) if current_job else {}
        existing_metadata.update(metadata)
        update_data["metadata"] = existing_metadata

    supabase.table("training_jobs").update(update_data).eq("id", job_id).execute()


def list_training_jobs(twin_id: str, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Lists jobs with filtering.
    
    Args:
        twin_id: Twin UUID
        status: Optional status filter
        limit: Maximum number of jobs to return
    
    Returns:
        List of job records
    """
    query = supabase.table("training_jobs").select("*").eq("twin_id", twin_id)

    if status:
        query = query.eq("status", status)

    query = query.order("created_at", desc=True).limit(limit)

    response = query.execute()
    return response.data if response.data else []


async def process_training_job(job_id: str) -> bool:
    """
    Main processing logic (called by worker).
    
    Args:
        job_id: Job UUID
    
    Returns:
        True if successful, False otherwise
    """
    job = get_training_job(job_id)
    if not job:
        print(f"Job {job_id} not found")
        return False

    source_id = job["source_id"]
    twin_id = job["twin_id"]
    job_type = job["job_type"]
    job_metadata = job.get("metadata") or {}
    correlation_id = job_metadata.get("correlation_id")

    source_data = {}
    citation_url = None
    provider = job_metadata.get("provider")

    try:
        # Update status to processing
        update_job_status(job_id, "processing")

        # Get source data
        source_response = supabase.table("sources").select("*").eq("id", source_id).single().execute()
        if not source_response.data:
            raise ValueError(f"Source {source_id} not found")

        source_data = source_response.data or {}
        extracted_text = source_data.get("content_text")
        filename = source_data.get("filename", "Unknown")
        citation_url = source_data.get("citation_url") or job_metadata.get("url")

        # If this is a URL-based ingestion job, run the URL pipeline end-to-end.
        if job_type == "ingestion" and citation_url:
            from modules.ingestion import ingest_url_to_source, detect_url_provider
            provider = provider or detect_url_provider(citation_url)

            num_chunks = await ingest_url_to_source(
                source_id=source_id,
                twin_id=twin_id,
                url=citation_url,
                provider=provider,
                correlation_id=correlation_id
            )

            # Mark job complete. Source status is updated by the ingestion pipeline.
            update_job_status(job_id, "complete", metadata={
                "provider": provider,
                "url": citation_url,
                "chunks_created": num_chunks,
            })
            return True

        # Validate content_text exists
        if not extracted_text or len(extracted_text.strip()) == 0:
            # Fallback: If no content_text, try to reconstruct from Pinecone
            print(f"[Process Job] Source {source_id} ({filename}) has no content_text, attempting to reconstruct from Pinecone...")
            from modules.clients import get_pinecone_index
            index = get_pinecone_index()

            # Query Pinecone for all chunks from this source
            try:
                # Use a dummy query to get all vectors for this source.
                # During migration we probe creator + legacy namespaces.
                matches = []
                for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
                    try:
                        query_res = index.query(
                            vector=[0.1] * 3072,  # Dummy vector
                            top_k=1000,
                            include_metadata=True,
                            filter={"source_id": {"$eq": source_id}},
                            namespace=namespace
                        )
                        if query_res.get("matches"):
                            matches.extend(query_res["matches"])
                    except Exception as ns_error:
                        print(f"[Process Job] Namespace query failed ({namespace}): {ns_error}")

                if matches:
                    # Reconstruct text from chunks (sorted by some order if available)
                    chunks = [match["metadata"].get("text", "") for match in matches]
                    extracted_text = " ".join(chunks)

                    if extracted_text:
                        # Save the reconstructed text back to the source
                        supabase.table("sources").update({
                            "content_text": extracted_text,
                            "extracted_text_length": len(extracted_text)
                        }).eq("id", source_id).execute()
                        print(f"Reconstructed {len(extracted_text)} characters from Pinecone chunks")
                    else:
                        raise ValueError(
                            f"Source '{filename}' has no extracted text content and no chunks found in Pinecone. "
                            f"This usually means text extraction failed during ingestion. "
                            f"Please delete this source and re-upload it."
                        )
                else:
                    raise ValueError(
                        f"Source '{filename}' has no extracted text content and no chunks found in Pinecone. "
                        f"This usually means text extraction failed during ingestion. "
                        f"Please delete this source and re-upload it."
                    )
            except ValueError:
                # Re-raise ValueError as-is (it already has a good message)
                raise
            except Exception as pinecone_error:
                print(f"Error reconstructing from Pinecone: {pinecone_error}")
                raise ValueError(
                    f"Source '{filename}' has no extracted text content. "
                    f"Could not reconstruct from Pinecone: {str(pinecone_error)}. "
                    f"Please delete this source and re-upload it."
                )

        # Process based on job type
        if job_type == "ingestion":
            # Index existing content_text (file uploads or pre-extracted sources)
            from modules.ingestion import process_and_index_text
            from modules.ingestion_diagnostics import start_step, finish_step

            provider = provider or "file"
            num_chunks = await process_and_index_text(
                source_id,
                twin_id,
                extracted_text,
                metadata_override={
                    "filename": filename,
                    "type": "file",
                },
                provider=provider,
                correlation_id=correlation_id,
            )

            # Update source with chunk count and extracted text length
            _update_source_row(source_id, {
                "chunk_count": num_chunks,
                "extracted_text_length": len(extracted_text),
                "staging_status": "live",
                "status": "live"
            })

            # Emit terminal "live" step event for UI.
            live_event_id = start_step(
                source_id=source_id,
                twin_id=twin_id,
                provider=provider,
                step="live",
                correlation_id=correlation_id,
                message="Source is live",
            )
            finish_step(
                event_id=live_event_id,
                source_id=source_id,
                twin_id=twin_id,
                provider=provider,
                step="live",
                status="completed",
                correlation_id=correlation_id,
                metadata={"chunks": num_chunks},
            )

            # Update job metadata
            update_job_status(job_id, "complete", metadata={"chunks_created": num_chunks})
            
            # Trigger training metrics recompute in background (fire-and-forget)
            _schedule_metrics_update(twin_id)

        elif job_type == "reindex":
            # Reindex existing content (delete old vectors and re-index)
            # This would require deleting old vectors from Pinecone first
            # For now, just re-index
            from modules.ingestion import process_and_index_text
            num_chunks = await process_and_index_text(source_id, twin_id, extracted_text)

            _update_source_row(source_id, {
                "chunk_count": num_chunks,
                "staging_status": "live",
                "status": "live"
            })

            update_job_status(job_id, "complete", metadata={"chunks_created": num_chunks})
            
            # Trigger training metrics recompute in background (fire-and-forget)
            _schedule_metrics_update(twin_id)

        elif job_type == "health_check":
            # Run health checks (already done during ingestion, but can be re-run)
            from modules.health_checks import run_all_health_checks
            health_result = run_all_health_checks(
                source_id,
                twin_id,
                extracted_text,
                chunk_count=source_data.get("chunk_count"),
                source_data=source_data
            )

            # Update source health status
            supabase.table("sources").update({
                "health_status": health_result["overall_status"]
            }).eq("id", source_id).execute()

            update_job_status(job_id, "complete", metadata=health_result)
        else:
            raise ValueError(f"Unknown job type: {job_type}")

        return True

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        print(f"Error processing job {job_id}: {error_msg}")
        print(f"Traceback: {error_traceback}")
        update_job_status(job_id, "failed", error_message=f"{error_msg}\n\nTraceback:\n{error_traceback}")

        # Update source status (only if source_id is available)
        if source_id:
            try:
                from modules.ingestion_diagnostics import finish_step, build_error, diagnostics_schema_status
                from modules.ingestion import detect_url_provider

                provider = provider or (detect_url_provider(citation_url) if citation_url else "file")

                # Do not overwrite a provider-specific `last_error` if it was already captured.
                emit_generic_error = True
                diag_ok, _diag_err = diagnostics_schema_status()
                if diag_ok:
                    try:
                        current = (
                            supabase.table("sources")
                            .select("status,last_error,last_step")
                            .eq("id", source_id)
                            .eq("twin_id", twin_id)
                            .single()
                            .execute()
                        )
                        cur = current.data or {}
                        existing = cur.get("last_error")
                        if cur.get("status") == "error" and isinstance(existing, dict) and existing.get("code"):
                            emit_generic_error = False
                    except Exception:
                        # If schema drifts, fall back to emitting a generic error (it will be minimal anyway).
                        emit_generic_error = True

                if emit_generic_error:
                    step = (source_data.get("last_step") or "processing") if isinstance(source_data, dict) else "processing"
                    err = build_error(
                        code="INGESTION_JOB_FAILED",
                        message=error_msg,
                        provider=provider,
                        step=step,
                        correlation_id=correlation_id,
                        raw={"job_id": job_id, "url": citation_url},
                        exc=e,
                    )
                    finish_step(
                        event_id="",
                        source_id=source_id,
                        twin_id=twin_id,
                        provider=provider,
                        step=step,
                        status="error",
                        correlation_id=correlation_id,
                        error=err,
                    )
            except Exception as source_error:
                print(f"Error updating source status: {source_error}")

        return False


async def process_training_queue(twin_ids: list) -> Dict[str, Any]:
    """
    Process all queued training jobs for the given twin IDs.
    This is an async function that properly awaits job processing.

    Args:
        twin_ids: List of twin UUIDs to process jobs for

    Returns:
        Dict with processed, failed, remaining counts and errors
    """
    from modules.observability import supabase

    # Get all queued jobs for these twins
    try:
        query = supabase.table("training_jobs").select("id, twin_id, source_id") \
            .in_("twin_id", twin_ids).eq("status", "queued") \
            .order("priority", desc=True).limit(50)
        response = query.execute()
        queued_jobs = response.data or []
    except Exception as e:
        print(f"Error fetching queued jobs: {e}")
        return {
            "processed": 0,
            "failed": 0,
            "remaining": 0,
            "errors": [str(e)]
        }

    if not queued_jobs:
        return {
            "processed": 0,
            "failed": 0,
            "remaining": 0,
            "errors": []
        }

    processed = 0
    failed = 0
    errors = []

    # Process each job - properly await the async function
    for job in queued_jobs:
        job_id = job["id"]
        try:
            success = await process_training_job(job_id)
            if success:
                processed += 1
            else:
                failed += 1
                errors.append(f"Job {job_id}: Processing returned False")
        except Exception as e:
            failed += 1
            errors.append(f"Job {job_id}: {str(e)}")

    # Count remaining
    try:
        remaining_query = supabase.table("training_jobs") \
            .select("id", count="exact") \
            .in_("twin_id", twin_ids).eq("status", "queued")
        remaining_response = remaining_query.execute()
        remaining = remaining_response.count or 0
    except Exception:
        remaining = 0

    return {
        "processed": processed,
        "failed": failed,
        "remaining": remaining,
        "errors": errors
    }


# =============================================================================
# Dead Letter Queue & Retry Logic
# =============================================================================

MAX_RETRY_ATTEMPTS = 3  # Maximum number of retry attempts before DLQ
RETRY_DELAY_BASE_SECONDS = 30  # Base delay for exponential backoff


def should_retry_job(job: Dict[str, Any], error_message: str) -> bool:
    """
    Determine if a failed job should be retried based on error type and attempt count.
    
    Args:
        job: The failed job record
        error_message: The error message from the failure
        
    Returns:
        True if job should be retried, False to send to DLQ
    """
    retry_count = job.get("retry_count", 0)
    
    # Don't retry if max attempts reached
    if retry_count >= MAX_RETRY_ATTEMPTS:
        print(f"[Retry] Job {job['id']} exceeded max retries ({MAX_RETRY_ATTEMPTS}), sending to DLQ")
        return False
    
    # Non-retryable error patterns
    non_retryable_patterns = [
        "YOUTUBE_TRANSCRIPT_UNAVAILABLE",
        "X_BLOCKED_OR_UNSUPPORTED", 
        "LINKEDIN_BLOCKED_OR_REQUIRES_AUTH",
        "FILE_EXTRACTION_EMPTY",
        "FILE_EXTRACTION_FAILED",
        "Invalid YouTube URL",
        "No text extracted",
        "not available in your region",
        "requires authentication",
        "deleted, private, or not found",
    ]
    
    error_lower = error_message.lower()
    for pattern in non_retryable_patterns:
        if pattern.lower() in error_lower:
            print(f"[Retry] Job {job['id']} has non-retryable error pattern '{pattern}', sending to DLQ")
            return False
    
    return True


def calculate_retry_delay(retry_count: int) -> int:
    """
    Calculate delay for retry using exponential backoff with jitter.
    
    Args:
        retry_count: Current retry attempt (0-indexed)
        
    Returns:
        Delay in seconds
    """
    import random
    
    # Exponential backoff: 30s, 60s, 120s
    base_delay = RETRY_DELAY_BASE_SECONDS * (2 ** retry_count)
    
    # Add jitter (±25%) to prevent thundering herd
    jitter = random.uniform(0.75, 1.25)
    delay = int(base_delay * jitter)
    
    # Cap at 5 minutes
    return min(delay, 300)


def retry_training_job_with_backoff(job_id: str) -> bool:
    """
    Retry a failed training job with exponential backoff.
    
    Args:
        job_id: Job UUID to retry
        
    Returns:
        True if job was successfully re-queued, False otherwise
    """
    try:
        job = get_training_job(job_id)
        if not job:
            print(f"[Retry] Job {job_id} not found")
            return False
        
        # Check if job is in a retryable state
        if job.get("status") not in ["failed", "needs_attention"]:
            print(f"[Retry] Job {job_id} is not in failed state (status: {job.get('status')})")
            return False
        
        # Check retry eligibility
        error_message = job.get("error_message", "")
        if not should_retry_job(job, error_message):
            # Move to DLQ state (permanent failure)
            update_job_status(job_id, "dead_letter", 
                error_message=f"PERMANENT FAILURE: {error_message}")
            return False
        
        # Increment retry count
        current_retry = job.get("retry_count", 0)
        new_retry_count = current_retry + 1
        delay_seconds = calculate_retry_delay(current_retry)
        
        # Calculate next attempt time
        from datetime import datetime, timedelta
        next_attempt_at = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()
        
        # Update job for retry
        update_data = {
            "status": "queued",
            "retry_count": new_retry_count,
            "error_message": None,  # Clear error message
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Update metadata with retry info
        metadata = job.get("metadata", {})
        metadata["retry_history"] = metadata.get("retry_history", []) + [{
            "attempt": new_retry_count,
            "previous_error": error_message[:500],  # Truncate long errors
            "retried_at": datetime.utcnow().isoformat(),
            "next_attempt_delay_seconds": delay_seconds,
        }]
        metadata["next_attempt_after"] = next_attempt_at
        update_data["metadata"] = metadata
        
        # Clear completed_at since we're retrying
        update_data["completed_at"] = None
        
        supabase.table("training_jobs").update(update_data).eq("id", job_id).execute()
        
        # Re-queue with delay (if Redis supports delayed queues) or immediate
        # For now, we rely on the next_attempt_after metadata for filtering
        enqueue_job(job_id, job.get("job_type", "ingestion"), job.get("priority", 0), metadata)
        
        print(f"[Retry] Job {job_id} re-queued for attempt {new_retry_count}/{MAX_RETRY_ATTEMPTS} "
              f"(delay: {delay_seconds}s)")
        return True
        
    except Exception as e:
        print(f"[Retry] Error retrying job {job_id}: {e}")
        return False


def get_jobs_pending_retry() -> List[Dict[str, Any]]:
    """
    Get jobs that are queued but waiting for their retry delay to pass.
    
    Returns:
        List of jobs ready to be processed
    """
    try:
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        
        # Get queued jobs where next_attempt_after has passed or is null
        response = supabase.table("training_jobs") \
            .select("*") \
            .eq("status", "queued") \
            .or_(f"metadata->>next_attempt_after.is.null,metadata->>next_attempt_after.lte.{now}") \
            .order("priority", desc=True) \
            .order("created_at", desc=False) \
            .limit(50) \
            .execute()
        
        return response.data or []
    except Exception as e:
        print(f"[Retry] Error fetching jobs pending retry: {e}")
        return []


def get_dead_letter_jobs(twin_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get jobs that have exceeded max retries and are in dead letter state.
    
    Args:
        twin_id: Optional twin filter
        limit: Maximum results
        
    Returns:
        List of dead letter jobs
    """
    try:
        query = supabase.table("training_jobs") \
            .select("*") \
            .eq("status", "dead_letter")
        
        if twin_id:
            query = query.eq("twin_id", twin_id)
        
        response = query.order("updated_at", desc=True).limit(limit).execute()
        return response.data or []
    except Exception as e:
        print(f"[DLQ] Error fetching dead letter jobs: {e}")
        return []


def replay_dead_letter_job(job_id: str) -> bool:
    """
    Manually replay a job from the dead letter queue.
    Resets retry count and re-queues for processing.
    
    Args:
        job_id: Job UUID in dead letter state
        
    Returns:
        True if successfully replayed
    """
    try:
        job = get_training_job(job_id)
        if not job or job.get("status") != "dead_letter":
            print(f"[DLQ] Job {job_id} not found or not in dead_letter state")
            return False
        
        # Reset for retry
        from datetime import datetime
        update_data = {
            "status": "queued",
            "retry_count": 0,  # Reset retry count
            "error_message": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        metadata = job.get("metadata", {})
        metadata["replayed_from_dlq_at"] = datetime.utcnow().isoformat()
        metadata["dlq_error"] = job.get("error_message")  # Preserve original error
        update_data["metadata"] = metadata
        
        supabase.table("training_jobs").update(update_data).eq("id", job_id).execute()
        
        enqueue_job(job_id, job.get("job_type", "ingestion"), job.get("priority", 0), metadata)
        
        print(f"[DLQ] Job {job_id} replayed from dead letter queue")
        return True
        
    except Exception as e:
        print(f"[DLQ] Error replaying job {job_id}: {e}")
        return False


# Modify process_training_job to use retry logic
def process_training_job_with_retry(job_id: str) -> bool:
    """
    Wrapper around process_training_job that handles automatic retries.
    
    Args:
        job_id: Job UUID
        
    Returns:
        True if job succeeded or was successfully queued for retry
    """
    from modules.training_jobs import process_training_job
    
    success = process_training_job(job_id)
    
    if not success:
        # Try to retry with backoff
        retry_queued = retry_training_job_with_backoff(job_id)
        if retry_queued:
            # Return True because we successfully queued for retry
            # The job will be processed again later
            return True
        # If retry not queued, it went to DLQ - return False
    
    return success
