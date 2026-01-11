"""
Training Jobs Module
Manages training job lifecycle and processing.
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from modules.observability import supabase
from modules.job_queue import enqueue_job
# Note: process_and_index_text is imported inside process_training_job to avoid circular import


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

    try:
        # Update status to processing
        update_job_status(job_id, "processing")

        # Get source data
        source_response = supabase.table("sources").select("*").eq("id", source_id).single().execute()
        if not source_response.data:
            raise ValueError(f"Source {source_id} not found")

        source_data = source_response.data
        extracted_text = source_data.get("content_text")
        filename = source_data.get("filename", "Unknown")

        # Validate content_text exists
        if not extracted_text or len(extracted_text.strip()) == 0:
            # Fallback: If no content_text, try to reconstruct from Pinecone
            print(f"[Process Job] Source {source_id} ({filename}) has no content_text, attempting to reconstruct from Pinecone...")
            from modules.clients import get_pinecone_index
            index = get_pinecone_index()

            # Query Pinecone for all chunks from this source
            try:
                # Use a dummy query to get all vectors for this source
                query_res = index.query(
                    vector=[0.1] * 3072,  # Dummy vector
                    top_k=1000,
                    include_metadata=True,
                    filter={"source_id": {"$eq": source_id}},
                    namespace=twin_id
                )

                if query_res.get("matches"):
                    # Reconstruct text from chunks (sorted by some order if available)
                    chunks = [match["metadata"].get("text", "") for match in query_res["matches"]]
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
            # Process and index text (lazy import to avoid circular dependency)
            from modules.ingestion import process_and_index_text
            num_chunks = await process_and_index_text(source_id, twin_id, extracted_text)

            # Update source with chunk count and extracted text length
            supabase.table("sources").update({
                "chunk_count": num_chunks,
                "extracted_text_length": len(extracted_text),
                "staging_status": "live",
                "status": "live"
            }).eq("id", source_id).execute()

            # Update job metadata
            update_job_status(job_id, "complete", metadata={"chunks_created": num_chunks})

        elif job_type == "reindex":
            # Reindex existing content (delete old vectors and re-index)
            # This would require deleting old vectors from Pinecone first
            # For now, just re-index
            from modules.ingestion import process_and_index_text
            num_chunks = await process_and_index_text(source_id, twin_id, extracted_text)

            supabase.table("sources").update({
                "chunk_count": num_chunks,
                "staging_status": "live",
                "status": "live"
            }).eq("id", source_id).execute()

            update_job_status(job_id, "complete", metadata={"chunks_created": num_chunks})

        elif job_type == "health_check":
            # Run health checks (already done during staging, but can be re-run)
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
                supabase.table("sources").update({
                    "status": "error",
                    "health_status": "failed"
                }).eq("id", source_id).execute()
            except Exception as source_error:
                print(f"Error updating source status: {source_error}")

        return False


def process_training_queue(twin_ids: list) -> Dict[str, Any]:
    """
    Process all queued training jobs for the given twin IDs.
    This is a synchronous wrapper that handles async job processing.

    Args:
        twin_ids: List of twin UUIDs to process jobs for

    Returns:
        Dict with processed, failed, remaining counts and errors
    """
    import asyncio
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

    # Process each job
    for job in queued_jobs:
        job_id = job["id"]
        try:
            # Run the async function in a new event loop context
            # This handles the sync-to-async bridge
            success = asyncio.get_event_loop().run_until_complete(process_training_job(job_id))
            if success:
                processed += 1
            else:
                failed += 1
                errors.append(f"Job {job_id}: Processing returned False")
        except RuntimeError:
            # If there's no event loop or it's already running, create a new one
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(process_training_job(job_id))
                    if success:
                        processed += 1
                    else:
                        failed += 1
                        errors.append(f"Job {job_id}: Processing returned False")
                finally:
                    loop.close()
            except Exception as e:
                failed += 1
                errors.append(f"Job {job_id}: {str(e)}")
        except Exception as e:
            failed += 1
            errors.append(f"Job {job_id}: {str(e)}")

    # Count remaining
    try:
        remaining_query = supabase.table("training_jobs").select("id", count="exact").in_("twin_id", twin_ids).eq("status", "queued")
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
