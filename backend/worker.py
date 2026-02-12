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
        ("SUPABASE_SERVICE_KEY", "Database authentication"),
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
from modules.realtime_ingestion import process_realtime_job
from modules.realtime_stream_queue import (
    ack_realtime_stream_message,
    dequeue_realtime_stream_job,
    get_realtime_stream_metrics,
    streams_available,
)
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
    if streams_available():
        stream_metrics = get_realtime_stream_metrics()
        print(
            "[Worker] Realtime stream enabled "
            f"(stream={stream_metrics.get('stream')}, group={stream_metrics.get('group')}, "
            f"pending={stream_metrics.get('pending')})"
        )
    else:
        print("[Worker] Realtime stream disabled/unavailable; using legacy queue for realtime jobs")

    consecutive_empty_polls = 0
    jobs_processed = 0

    while not shutdown_event.is_set():
        try:
            # Poll realtime stream first, then fallback to regular queue.
            stream_job = dequeue_realtime_stream_job(worker_id) if streams_available() else None
            job = stream_job or dequeue_job()
            
            if job:
                consecutive_empty_polls = 0
                jobs_processed += 1
                
                job_id = job.get("job_id")
                job_type = job.get("job_type")
                metadata = job.get("metadata", {})
                stream_message_id = job.get("stream_message_id")

                if not job_id:
                    print("[Worker] Skipping malformed job payload (missing job_id)")
                    if stream_message_id:
                        ack_realtime_stream_message(stream_message_id)
                    continue
                
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
                    elif job_type == "realtime_ingestion":
                        success = await process_realtime_job(job_id)
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
                status_symbol = "OK" if success else "FAIL"
                print(f"[Worker] [{status_symbol}] Job {job_id} finished in {duration:.2f}s")
                if stream_message_id and success:
                    acked = ack_realtime_stream_message(stream_message_id)
                    if not acked:
                        print(f"[Worker] WARN: failed to ACK stream message {stream_message_id}")
                elif stream_message_id and not success and job_type == "realtime_ingestion":
                    # Poison-message protection:
                    # if job reached terminal status, ACK to avoid infinite redelivery loop.
                    try:
                        from modules.observability import supabase

                        job_row = (
                            supabase.table("jobs")
                            .select("status")
                            .eq("id", job_id)
                            .limit(1)
                            .execute()
                        )
                        status = None
                        if job_row.data:
                            status = str(job_row.data[0].get("status") or "").lower()
                        if status in {"failed", "complete", "needs_attention"}:
                            acked = ack_realtime_stream_message(stream_message_id)
                            if acked:
                                print(
                                    "[Worker] ACKed terminal failed realtime stream message "
                                    f"{stream_message_id} (status={status})"
                                )
                    except Exception as ack_err:
                        print(f"[Worker] WARN: terminal ACK check failed for stream message {stream_message_id}: {ack_err}")
                
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
