import asyncio
import os
import signal
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def validate_worker_environment():
    """
    Validate critical environment variables at startup.
    Fail fast if required variables are missing.
    """
    required_vars = [
        ("SUPABASE_URL", "Database connection"),
        ("PINECONE_API_KEY", "Pinecone vector search"),
        ("PINECONE_INDEX_NAME", "Pinecone index name"),
    ]
    
    optional_vars = [
        ("REDIS_URL", "Redis queue (falls back to DB polling if missing)"),
        ("DATABASE_URL", "LangGraph checkpointer (optional)"),
    ]
    
    missing = []
    for var, description in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(f"  - {var}: {description}")

    # Accept either Supabase key variable for compatibility with API service config.
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not supabase_key:
        missing.append("  - SUPABASE_SERVICE_KEY or SUPABASE_KEY: Database authentication")

    # Provider-aware key requirements (Phase 4 hybrid inference support).
    openai_key = os.getenv("OPENAI_API_KEY")
    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    inference_provider = os.getenv("INFERENCE_PROVIDER", "openai").lower()
    asr_provider = os.getenv("YOUTUBE_ASR_PROVIDER", "openai").lower()

    # Require at least one model provider key for LLM operations.
    if not any([openai_key, cerebras_key, anthropic_key]):
        missing.append("  - One of OPENAI_API_KEY/CEREBRAS_API_KEY/ANTHROPIC_API_KEY is required")

    # Require OPENAI key when active providers explicitly depend on it.
    if embedding_provider == "openai" and not openai_key:
        missing.append("  - OPENAI_API_KEY required when EMBEDDING_PROVIDER=openai")
    if inference_provider == "openai" and not openai_key:
        missing.append("  - OPENAI_API_KEY required when INFERENCE_PROVIDER=openai")
    if asr_provider == "openai" and not openai_key:
        missing.append("  - OPENAI_API_KEY required when YOUTUBE_ASR_PROVIDER=openai")
    
    if missing:
        print("=" * 70)
        print("FATAL: Worker missing required environment variables:")
        for m in missing:
            print(m)
        print("=" * 70)
        print("\nPlease set these variables in your worker environment.")
        print("For Render: Check your Background Worker service environment variables.")
        print("For local: Create a .env file with these variables.")
        sys.exit(1)
    
    # Warn about optional variables
    for var, description in optional_vars:
        if not os.getenv(var):
            print(f"[WARN] {var} not set: {description}")
    
    # Validate Supabase connection format
    supabase_url = os.getenv("SUPABASE_URL", "")
    if not supabase_url.startswith("https://"):
        print(f"[WARN] SUPABASE_URL should start with https://, got: {supabase_url[:30]}...")
    
    # Validate OpenAI key format when present
    if openai_key and not openai_key.startswith("sk-"):
        print(f"[WARN] OPENAI_API_KEY should start with 'sk-', check your key format")
    
    print("[OK] Worker environment validation passed")
    return True

# Run validation before importing modules that depend on env vars
validate_worker_environment()

from modules.job_queue import dequeue_job, get_redis_client, get_queue_length
from modules._core.scribe_engine import process_graph_extraction_job, process_content_extraction_job
from modules.persona_feedback_learning_jobs import process_feedback_learning_job
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
        # Job queue falls back to DB-backed dequeue when REDIS_URL is not configured.
        print("[Worker] INFO: REDIS_URL not configured/available - using DB-backed queue polling")
        print("[Worker] TIP: Configure REDIS_URL for lower latency and horizontal scaling")

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
                    elif job_type == "feedback_learning":
                        success = await process_feedback_learning_job(job_id)
                    elif job_type in ["ingestion", "reindex", "health_check"]:
                        # Training jobs with automatic retry logic
                        from modules.training_jobs import process_training_job_with_retry
                        success = await process_training_job_with_retry(job_id)
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
