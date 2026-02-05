"""
Training Worker
Processes training jobs from the queue.
Can be run as a separate process or triggered via API.
"""
import os
import asyncio
import time
from dotenv import load_dotenv
from modules.job_queue import dequeue_job, get_queue_length
from modules.training_jobs import process_training_job

load_dotenv()

WORKER_ENABLED = os.getenv("WORKER_ENABLED", "true").lower() == "true"
WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))


async def process_queue():
    """Main worker loop that processes jobs from the queue."""
    if not WORKER_ENABLED:
        print("Worker is disabled (WORKER_ENABLED=false)")
        return
    
    print(f"Training worker started (poll interval: {WORKER_POLL_INTERVAL}s)")
    
    while True:
        try:
            # Get next job from queue
            job = dequeue_job()
            
            if job:
                job_id = job["job_id"]
                job_type = job["job_type"]
                print(f"Processing job {job_id} (type: {job_type}, priority: {job['priority']})")
                
                # Route to appropriate processor based on job type
                if job_type == "graph_extraction":
                    from modules._core.scribe_engine import process_graph_extraction_job
                    success = await process_graph_extraction_job(job_id)
                elif job_type == "content_extraction":
                    from modules._core.scribe_engine import process_content_extraction_job
                    success = await process_content_extraction_job(job_id)
                else:
                    # Default to training job processor (ingestion, reindex, health_check)
                    success = await process_training_job(job_id)
                
                if success:
                    print(f"Job {job_id} completed successfully")
                else:
                    print(f"Job {job_id} failed")
            else:
                # No jobs in queue, wait before checking again
                queue_length = get_queue_length()
                if queue_length > 0:
                    print(f"Queue has {queue_length} jobs, but dequeue returned None (possible race condition)")
                await asyncio.sleep(WORKER_POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print("\nWorker stopped by user")
            break
        except Exception as e:
            print(f"Error in worker loop: {e}")
            await asyncio.sleep(WORKER_POLL_INTERVAL)


async def process_single_job(job_id: str):
    """
    Process a single job by ID (for on-demand processing via API).
    Routes to appropriate processor based on job type.
    
    Args:
        job_id: Job UUID to process
    """
    from modules.observability import supabase
    try:
        # Get job details to determine type
        job_result = supabase.table("jobs").select("job_type").eq("id", job_id).single().execute()
        if not job_result.data:
            print(f"Job {job_id} not found")
            return False
        
        job_type = job_result.data.get("job_type")
        
        # Route to appropriate processor
        if job_type == "graph_extraction":
            from modules._core.scribe_engine import process_graph_extraction_job
            success = await process_graph_extraction_job(job_id)
        elif job_type == "content_extraction":
            from modules._core.scribe_engine import process_content_extraction_job
            success = await process_content_extraction_job(job_id)
        else:
            # Default to training job processor
            success = await process_training_job(job_id)
        
        return success
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        return False


if __name__ == "__main__":
    # Run worker loop
    asyncio.run(process_queue())

