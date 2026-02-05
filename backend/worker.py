import asyncio
import os
import signal
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from modules.job_queue import dequeue_job, get_redis_client, get_queue_length
from modules._core.scribe_engine import process_graph_extraction_job, process_content_extraction_job
from modules.training_jobs import process_training_job

# Graceful shutdown
shutdown_event = asyncio.Event()

# Ensure logs are flushed immediately
if sys.platform != 'win32':
    # Windows doesn't support line_buffering param in reconfigure easily in all versions, 
    # but strictly this is for Render (Linux)
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

def handle_shutdown(sig, frame):
    print("\n[Worker] Shutdown signal received. Finishing current job and stopping...")
    shutdown_event.set()

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

async def worker_loop():
    """
    Main worker loop that polls for jobs and executes them.
    """
    worker_id = os.getenv("RENDER_INSTANCE_ID", "local-worker")
    print(f"[Worker] Starting background worker ({worker_id})...")
    
    # Check Redis connection
    redis_client = get_redis_client()
    if redis_client:
        print("[Worker] Connected to Redis queue")
    else:
        print("[Worker] WARNING: No Redis connection - using in-memory queue (ONLY WORKS LOCALLY OR SINGLE INSTANCE)")
        print("[Worker] For Render, ensure REDIS_URL is set in environment variables")

    consecutive_empty_polls = 0
    jobs_processed = 0

    while not shutdown_event.is_set():
        try:
            # Poll for job
            job = dequeue_job()
            
            if job:
                consecutive_empty_polls = 0
                jobs_processed += 1
                
                job_id = job.get("job_id")
                job_type = job.get("job_type")
                metadata = job.get("metadata", {})
                
                print(f"[Worker] Processing job {job_id} ({job_type})")
                
                start_time = asyncio.get_event_loop().time()
                success = False
                
                try:
                    # Dispatch based on job type
                    if job_type == "content_extraction":
                        success = await process_content_extraction_job(job_id)
                    elif job_type == "graph_extraction":
                        success = await process_graph_extraction_job(job_id)
                    elif job_type in ["ingestion", "reindex", "health_check"]:
                        # Training jobs (legacy/ingestion module)
                        success = await process_training_job(job_id)
                    else:
                        print(f"[Worker] Unknown job type: {job_type}")
                        success = False
                        
                except Exception as e:
                    print(f"[Worker] Job {job_id} crashed: {e}")
                    import traceback
                    traceback.print_exc()
                    success = False
                
                duration = asyncio.get_event_loop().time() - start_time
                status_symbol = "✅" if success else "❌"
                print(f"[Worker] {status_symbol} Job {job_id} finished in {duration:.2f}s")
                
            else:
                consecutive_empty_polls += 1
                # Adaptive sleep: sleep longer if queue is empty for a while, up to 5s
                sleep_time = min(5, 0.5 + (consecutive_empty_polls * 0.1))
                await asyncio.sleep(sleep_time)
                
                # Log heartbeat every ~60s of inactivity
                if consecutive_empty_polls % 60 == 0 and consecutive_empty_polls > 0:
                     print(f"[Worker] Heartbeat: Waiting for jobs... (Queue empty)")

        except Exception as e:
            print(f"[Worker] Critical error in loop: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)  # Backoff on critical error

    print(f"[Worker] Shutdown complete. Processed {jobs_processed} jobs.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(worker_loop())
