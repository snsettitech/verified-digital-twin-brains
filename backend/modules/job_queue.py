"""
Job Queue Module
Manages training job queue with Redis (or in-memory fallback).
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

# In-memory queue fallback
_in_memory_queue = []
_in_memory_lock = False  # Simple lock simulation


def init_redis_client():
    """Initialize Redis connection, return None if unavailable."""
    if not REDIS_AVAILABLE:
        return None
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
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
        # In-memory fallback using heapq (min-heap, so we negate priority)
        heapq.heappush(_in_memory_queue, (-priority, job_id, job_type, metadata or {}))


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
        # In-memory fallback
        if not _in_memory_queue:
            return None
        
        priority, job_id, job_type, metadata = heapq.heappop(_in_memory_queue)
        return {
            "job_id": job_id,
            "job_type": job_type,
            "priority": -priority,  # Convert back from negative
            "metadata": metadata
        }


def get_queue_length() -> int:
    """Get current queue size."""
    client = get_redis_client()
    
    if client:
        return client.zcard("training_jobs_queue")
    else:
        return len(_in_memory_queue)


def remove_job(job_id: str):
    """Remove a specific job from the queue."""
    client = get_redis_client()
    
    if client:
        client.zrem("training_jobs_queue", job_id)
        client.delete(f"job_metadata:{job_id}")
    else:
        # In-memory: rebuild queue without the job
        global _in_memory_queue
        _in_memory_queue = [
            item for item in _in_memory_queue 
            if item[1] != job_id  # item[1] is job_id
        ]
        heapq.heapify(_in_memory_queue)

