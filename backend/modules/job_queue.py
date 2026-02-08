"""
Job Queue Module
Manages background job queue with Redis (preferred) with a DB-backed fallback.

Why DB fallback?
- This repo persists job records in Supabase (`training_jobs`, `jobs`) before enqueueing.
- In multi-process deployments (Render web + Render worker), an in-memory queue is not shared and becomes a no-op.
- In-memory enqueueing in the web process also leaks memory (nothing dequeues it).

So when Redis isn't configured/available, we dequeue from the database instead.
"""
import os
import json
import heapq
from typing import Optional, Dict, Any
from datetime import datetime

# Try to import Redis, fallback to in-memory if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Warning: Redis not available, using in-memory queue")

# In-memory queue is disabled by default because it breaks in multi-process deployments.
# It is kept only as an explicit opt-in for single-process local experimentation.
_in_memory_queue = []
_in_memory_lock = False  # Simple lock simulation

def _in_memory_enabled() -> bool:
    return os.getenv("ENABLE_IN_MEMORY_QUEUE", "false").lower() == "true"


def init_redis_client():
    """Initialize Redis connection, return None if unavailable."""
    if not REDIS_AVAILABLE:
        return None
    
    # Do not assume localhost Redis in production; require explicit configuration.
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        client.ping()
        return client
    except Exception as e:
        print(f"Redis connection failed: {e}. Using in-memory queue.")
        return None


# Global Redis client (lazy initialization)
_redis_client = None


def get_redis_client():
    """Get or initialize Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = init_redis_client()
    return _redis_client


def enqueue_job(job_id: str, job_type: str, priority: int = 0, metadata: Optional[Dict[str, Any]] = None):
    """
    Add job to queue (priority-based: higher priority numbers processed first).
    
    Args:
        job_id: Training job UUID
        job_type: Type of job ('ingestion', 'reindex', 'health_check')
        priority: Priority level (higher = processed first, default 0)
        metadata: Optional job metadata
    """
    client = get_redis_client()
    
    if client:
        # Use Redis sorted set for priority queue
        # Score = -priority (negative so higher priority comes first)
        # Member = job_id
        score = -priority  # Negative for descending order
        client.zadd("training_jobs_queue", {job_id: score})
        
        # Store job metadata in hash
        if metadata:
            client.hset(f"job_metadata:{job_id}", mapping={
                "job_type": job_type,
                "metadata": json.dumps(metadata),
                "enqueued_at": datetime.utcnow().isoformat()
            })
        else:
            client.hset(f"job_metadata:{job_id}", mapping={
                "job_type": job_type,
                "enqueued_at": datetime.utcnow().isoformat()
            })
    else:
        # DB-backed fallback: job records are already persisted in Supabase (`training_jobs` or `jobs` tables).
        # Do NOT enqueue in-memory by default (web/worker are separate processes in production).
        if _in_memory_enabled():
            heapq.heappush(_in_memory_queue, (-priority, job_id, job_type, metadata or {}))


def _try_claim_training_job(row: Dict[str, Any]) -> bool:
    """Best-effort claim of a queued training_job by transitioning it to processing."""
    try:
        from modules.observability import supabase

        job_id = row.get("id")
        if not job_id:
            return False

        now = datetime.utcnow().isoformat()
        res = (
            supabase.table("training_jobs")
            .update({"status": "processing", "updated_at": now})
            .eq("id", job_id)
            .eq("status", "queued")
            .execute()
        )
        if res.data:
            return True

        # Some PostgREST configurations return minimal bodies; verify via re-fetch.
        check = supabase.table("training_jobs").select("status").eq("id", job_id).single().execute()
        return bool(check.data and check.data.get("status") == "processing")
    except Exception:
        return False


def _try_claim_job(row: Dict[str, Any]) -> bool:
    """Best-effort claim of a queued job by transitioning it to processing."""
    try:
        from modules.observability import supabase

        job_id = row.get("id")
        if not job_id:
            return False

        now = datetime.utcnow().isoformat()
        res = (
            supabase.table("jobs")
            .update({"status": "processing", "updated_at": now})
            .eq("id", job_id)
            .eq("status", "queued")
            .execute()
        )
        if res.data:
            return True

        check = supabase.table("jobs").select("status").eq("id", job_id).single().execute()
        return bool(check.data and check.data.get("status") == "processing")
    except Exception:
        return False


def _dequeue_from_db() -> Optional[Dict[str, Any]]:
    """
    DB-backed dequeue when Redis isn't configured/available.

    Priority:
    1) `training_jobs` (ingestion/reindex/health_check) because it directly affects the UI.
    2) `jobs` (graph/content extraction) for background enrichment.

    Returns:
        job dict compatible with worker dispatch: {job_id, job_type, priority, metadata}
    """
    try:
        from modules.observability import supabase

        # 1) training_jobs
        tj_res = (
            supabase.table("training_jobs")
            .select("id, job_type, priority, metadata")
            .eq("status", "queued")
            .order("priority", desc=True)
            .order("created_at", desc=False)
            .limit(5)
            .execute()
        )
        for row in tj_res.data or []:
            if not _try_claim_training_job(row):
                continue
            return {
                "job_id": row.get("id"),
                "job_type": row.get("job_type", "ingestion"),
                "priority": row.get("priority", 0),
                "metadata": row.get("metadata") or {},
            }

        # 2) jobs table
        j_res = (
            supabase.table("jobs")
            .select("id, job_type, priority, metadata")
            .eq("status", "queued")
            .order("priority", desc=True)
            .order("created_at", desc=False)
            .limit(5)
            .execute()
        )
        for row in j_res.data or []:
            if not _try_claim_job(row):
                continue
            return {
                "job_id": row.get("id"),
                "job_type": row.get("job_type", "other"),
                "priority": row.get("priority", 0),
                "metadata": row.get("metadata") or {},
            }

        return None
    except Exception as e:
        print(f"[JobQueue] DB dequeue failed: {e}")
        return None


def dequeue_job() -> Optional[Dict[str, Any]]:
    """
    Get next job from queue (highest priority first).
    
    Returns:
        Dict with job_id, job_type, and metadata, or None if queue is empty
    """
    client = get_redis_client()
    
    if client:
        # Get highest priority job (lowest score = highest priority)
        result = client.zrange("training_jobs_queue", 0, 0, withscores=True)
        if not result:
            return None
        
        job_id = result[0][0]
        score = result[0][1]
        priority = -int(score)  # Convert back from negative
        
        # Remove from queue
        client.zrem("training_jobs_queue", job_id)
        
        # Get metadata
        metadata = client.hgetall(f"job_metadata:{job_id}")
        job_type = metadata.get("job_type", "ingestion")
        
        # Parse metadata JSON if present
        metadata_json = metadata.get("metadata")
        job_metadata = json.loads(metadata_json) if metadata_json else {}
        
        # Clean up metadata hash
        client.delete(f"job_metadata:{job_id}")
        
        return {
            "job_id": job_id,
            "job_type": job_type,
            "priority": priority,
            "metadata": job_metadata
        }
    else:
        if _in_memory_enabled() and _in_memory_queue:
            priority, job_id, job_type, metadata = heapq.heappop(_in_memory_queue)
            return {
                "job_id": job_id,
                "job_type": job_type,
                "priority": -priority,  # Convert back from negative
                "metadata": metadata,
            }
        return _dequeue_from_db()


def get_queue_length() -> int:
    """Get current queue size."""
    client = get_redis_client()
    
    if client:
        return client.zcard("training_jobs_queue")
    else:
        if _in_memory_enabled():
            return len(_in_memory_queue)
        try:
            from modules.observability import supabase

            tj = supabase.table("training_jobs").select("id", count="exact").eq("status", "queued").execute()
            j = supabase.table("jobs").select("id", count="exact").eq("status", "queued").execute()
            return int((tj.count or 0) + (j.count or 0))
        except Exception:
            return 0


def remove_job(job_id: str):
    """Remove a specific job from the queue."""
    client = get_redis_client()
    
    if client:
        client.zrem("training_jobs_queue", job_id)
        client.delete(f"job_metadata:{job_id}")
    else:
        if _in_memory_enabled():
            # In-memory: rebuild queue without the job
            global _in_memory_queue
            _in_memory_queue = [
                item for item in _in_memory_queue
                if item[1] != job_id  # item[1] is job_id
            ]
            heapq.heapify(_in_memory_queue)

