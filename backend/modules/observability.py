from supabase import create_client, Client
import os
import time
from typing import Optional, Any, Callable
from functools import wraps
from dotenv import load_dotenv
from modules.clients import get_pinecone_index

load_dotenv()

# =============================================================================
# CONNECTION POOL CONFIGURATION (CRITICAL BUG FIX: H1)
# =============================================================================

# Connection pool settings from environment
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))  # Max connections per worker
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))  # Additional connections under load
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))  # Seconds to wait for connection
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # Recycle connections after N seconds

# Retry configuration
DB_RETRY_ATTEMPTS = int(os.getenv("DB_RETRY_ATTEMPTS", "3"))
DB_RETRY_DELAY = float(os.getenv("DB_RETRY_DELAY", "1.0"))  # Initial delay in seconds
DB_RETRY_BACKOFF = float(os.getenv("DB_RETRY_BACKOFF", "2.0"))  # Exponential backoff multiplier

# Track connection health
_connection_health = {"healthy": True, "last_error": None, "last_check": time.time()}


class ConnectionPoolManager:
    """
    Manages database connection pool with health checks and retry logic.
    """
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._initialized = False
        self._connection_count = 0
    
    def _create_client(self) -> Client:
        """Create Supabase client with connection pooling."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        # Fallback to anon key if service key is placeholder or missing
        if not supabase_key or "your_supabase_service_role_key" in supabase_key:
            supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url:
            raise ValueError("SUPABASE_URL environment variable is not set.")
        if not supabase_key:
            raise ValueError("SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable is not set.")
        
        try:
            # Create client - options parameter format varies by supabase-py version
            # Try without options first for compatibility
            client = create_client(supabase_url, supabase_key)
            return client
        except Exception as e:
            raise ValueError(f"Failed to initialize Supabase client: {e}")
    
    def get_client(self) -> Client:
        """Get or create Supabase client."""
        if self._client is None:
            self._client = self._create_client()
            self._initialized = True
        return self._client
    
    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            # Simple health check query
            result = self._client.table("twins").select("count").limit(1).execute()
            _connection_health["healthy"] = True
            _connection_health["last_check"] = time.time()
            return True
        except Exception as e:
            _connection_health["healthy"] = False
            _connection_health["last_error"] = str(e)
            _connection_health["last_check"] = time.time()
            return False
    
    def reset_connection(self):
        """Reset connection pool (call after errors)."""
        self._client = None
        self._initialized = False


# Global pool manager
_pool_manager = ConnectionPoolManager()

# Initialize on import
try:
    supabase: Client = _pool_manager.get_client()
except Exception as e:
    print(f"[Observability] Failed to initialize Supabase: {e}")
    supabase = None  # Will be re-initialized on first use


def with_db_retry(max_attempts: int = None, initial_delay: float = None):
    """
    Decorator to add retry logic to database operations.
    
    Args:
        max_attempts: Max retry attempts (default: DB_RETRY_ATTEMPTS)
        initial_delay: Initial delay in seconds (default: DB_RETRY_DELAY)
    """
    max_attempts = max_attempts or DB_RETRY_ATTEMPTS
    initial_delay = initial_delay or DB_RETRY_DELAY
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Don't retry on certain errors
                    non_retryable = [
                        "not found", "does not exist", "permission denied",
                        "invalid", "syntax error", "constraint violation"
                    ]
                    if any(nr in error_msg for nr in non_retryable):
                        raise
                    
                    # Check if it's a connection/pool exhaustion error
                    if any(err in error_msg for err in ["pool", "connection", "timeout", "refused"]):
                        print(f"[DB Retry] Connection issue on attempt {attempt + 1}/{max_attempts}: {e}")
                        # Reset connection pool
                        _pool_manager.reset_connection()
                        # Re-initialize global supabase
                        global supabase
                        supabase = _pool_manager.get_client()
                    
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        delay *= DB_RETRY_BACKOFF
                    else:
                        raise last_error
            
            return None
        
        return wrapper
    return decorator


def get_supabase_client() -> Client:
    """Get Supabase client with automatic initialization."""
    global supabase
    if supabase is None:
        supabase = _pool_manager.get_client()
    return supabase

def create_conversation(
    twin_id: str,
    user_id: str = None,
    group_id: str = None,
    interaction_context: str = None,
    origin_endpoint: str = None,
    share_link_id: str = None,
    training_session_id: str = None,
):
    data = {"twin_id": twin_id}
    if user_id:
        data["user_id"] = user_id
    if group_id:
        data["group_id"] = group_id
    if interaction_context:
        data["interaction_context"] = interaction_context
    if origin_endpoint:
        data["origin_endpoint"] = origin_endpoint
    if share_link_id:
        data["share_link_id"] = share_link_id
    if training_session_id:
        data["training_session_id"] = training_session_id

    try:
        response = supabase.table("conversations").insert(data).execute()
    except Exception:
        # Compatibility fallback for environments where context columns are not migrated yet.
        fallback = {"twin_id": twin_id}
        if user_id:
            fallback["user_id"] = user_id
        if group_id:
            fallback["group_id"] = group_id
        response = supabase.table("conversations").insert(fallback).execute()
    return response.data[0] if response.data else None

def log_interaction(
    conversation_id: str,
    role: str,
    content: str,
    citations: list = None,
    answerability_state: str = None,
    source_tier: str = None,
    review_required: bool = None,
    review_reason: str = None,
    interaction_context: str = None,
):
    data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content
    }
    if citations:
        data["citations"] = citations
    if answerability_state:
        data["answerability_state"] = answerability_state
    if source_tier:
        data["source_tier"] = source_tier
    if review_required is not None:
        data["review_required"] = review_required
    if review_reason:
        data["review_reason"] = review_reason
    if interaction_context:
        data["interaction_context"] = interaction_context

    try:
        response = supabase.table("messages").insert(data).execute()
    except Exception:
        # Compatibility fallback for environments where message context column is not migrated yet.
        fallback = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
        }
        if citations:
            fallback["citations"] = citations
        response = supabase.table("messages").insert(fallback).execute()
    return response.data[0] if response.data else None

def get_conversations(twin_id: str):
    response = supabase.table("conversations").select("*").eq("twin_id", twin_id).order("created_at", desc=True).execute()
    return response.data

def get_messages(conversation_id: str):
    """Get messages for a conversation with error handling."""
    if not conversation_id:
        return []
    
    try:
        # BUG #10 FIX: add secondary sort by id so messages with the same
        # created_at timestamp return in a deterministic, stable order
        response = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .order("id", desc=False)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching messages for conversation {conversation_id}: {e}")
        # Return empty list on error to prevent chat from failing completely
        return []

def get_sources(twin_id: str):
    response = supabase.table("sources").select("*").eq("twin_id", twin_id).order("created_at", desc=True).execute()
    return response.data

async def get_knowledge_profile(twin_id: str):
    """
    Analyzes the twin's knowledge base to generate stats on facts vs opinions and tone.
    """
    import traceback
    
    total_chunks = 0
    fact_count = 0
    opinion_count = 0
    tone_distribution = {}
    
    # Query Pinecone for a sample of vectors to analyze metadata
    # We use a dummy non-zero vector for a broad search within the namespace
    # Dimensions for text-embedding-3-large is 3072
    try:
        index = get_pinecone_index()
        if index:
            try:
                from modules.twin_namespace import get_namespace_candidates_for_twin

                matches = []
                namespaces = get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True)
                
                for namespace in namespaces:
                    try:
                        query_res = index.query(
                            vector=[0.1] * 3072,
                            top_k=1000, # Analyze up to 1000 chunks
                            include_metadata=True,
                            namespace=namespace
                        )
                        if query_res and hasattr(query_res, 'get'):
                            matches.extend(query_res.get("matches", []))
                    except Exception as e:
                        print(f"[Knowledge Profile] Error querying namespace {namespace}: {e}")
                        continue
                
                total_chunks = len(matches)
                
                for match in matches:
                    try:
                        metadata = match.get("metadata", {}) if match else {}
                        
                        # Category: FACT or OPINION
                        category = metadata.get("category", "FACT")
                        if category == "OPINION":
                            opinion_count += 1
                        else:
                            fact_count += 1
                            
                        # Tone Distribution
                        tone = metadata.get("tone", "Neutral")
                        tone_distribution[tone] = tone_distribution.get(tone, 0) + 1
                    except Exception as match_e:
                        print(f"[Knowledge Profile] Error processing match: {match_e}")
                        continue
            except Exception as e:
                print(f"[Knowledge Profile] Error querying Pinecone: {e}")
                print(f"[Knowledge Profile] Traceback: {traceback.format_exc()}")
    except Exception as e:
        print(f"[Knowledge Profile] Failed to get Pinecone index: {e}")
    
    # Get top tone
    top_tone = "Neutral"
    if tone_distribution:
        try:
            top_tone = max(tone_distribution, key=tone_distribution.get)
        except Exception:
            top_tone = "Neutral"
        
    # Get total sources from Supabase
    total_sources = 0
    try:
        sources_res = supabase.table("sources").select("id", count="exact").eq("twin_id", twin_id).execute()
        total_sources = sources_res.count if hasattr(sources_res, 'count') else len(sources_res.data or [])
    except Exception as e:
        print(f"[Knowledge Profile] Error fetching sources count: {e}")
    
    return {
        "total_chunks": total_chunks,
        "total_sources": total_sources,
        "fact_count": fact_count,
        "opinion_count": opinion_count,
        "tone_distribution": tone_distribution,
        "top_tone": top_tone
    }

# Phase 6: Ingestion Logging Functions

def log_ingestion_event(source_id: str, twin_id: str, level: str, message: str, metadata: dict = None):
    """
    Logs ingestion event to ingestion_logs table.
    
    Args:
        source_id: Source UUID
        twin_id: Twin UUID
        level: Log level ('info', 'warning', 'error')
        message: Log message
        metadata: Optional context/metadata
    """
    try:
        supabase.table("ingestion_logs").insert({
            "source_id": source_id,
            "twin_id": twin_id,
            "log_level": level,
            "message": message,
            "metadata": metadata or {}
        }).execute()
    except Exception as e:
        print(f"Error logging ingestion event: {e}")

def get_ingestion_logs(source_id: str, limit: int = 100):
    """
    Retrieves logs for a source.
    
    Args:
        source_id: Source UUID
        limit: Maximum number of logs to return
    
    Returns:
        List of log entries
    """
    try:
        response = supabase.table("ingestion_logs").select("*").eq(
            "source_id", source_id
        ).order("created_at", desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching ingestion logs: {e}")
        return []

def get_dead_letter_queue(twin_id: str):
    """
    Lists sources in error state that need attention.
    
    Args:
        twin_id: Twin UUID
    
    Returns:
        List of sources needing attention
    """
    try:
        response = supabase.table("sources").select("*").eq(
            "twin_id", twin_id
        ).in_("status", ["error", "needs_attention"]).order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching dead letter queue: {e}")
        return []

def retry_failed_ingestion(source_id: str, twin_id: str):
    """
    Resets status and recreates training job for failed ingestion.
    
    Args:
        source_id: Source UUID
        twin_id: Twin UUID
    
    Returns:
        New training job ID
    """
    from modules.training_jobs import create_training_job
    
    # Reset source status
    supabase.table("sources").update({
        "status": "processing",
        "staging_status": "staged",
        "health_status": "healthy"
    }).eq("id", source_id).execute()
    
    # Create new training job
    job_id = create_training_job(source_id, twin_id, job_type="ingestion", priority=0)
    
    log_ingestion_event(source_id, twin_id, "info", f"Retry initiated, training job {job_id} created")
    
    return job_id
