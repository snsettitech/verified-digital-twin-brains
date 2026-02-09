from supabase import create_client, Client
import os
from dotenv import load_dotenv
from modules.clients import get_pinecone_index

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
# Fallback to anon key if service key is placeholder or missing
if not supabase_key or "your_supabase_service_role_key" in supabase_key:
    supabase_key = os.getenv("SUPABASE_KEY")

# Validate environment variables before creating client
if not supabase_url:
    raise ValueError("SUPABASE_URL environment variable is not set. Please check your .env file.")
if not supabase_key:
    raise ValueError("SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable is not set. Please check your .env file.")

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    raise ValueError(f"Failed to initialize Supabase client: {e}. Please check your SUPABASE_URL and SUPABASE_KEY environment variables.")

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
    confidence_score: float = None,
    interaction_context: str = None,
):
    data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content
    }
    if citations:
        data["citations"] = citations
    if confidence_score is not None:
        data["confidence_score"] = confidence_score
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
        if confidence_score is not None:
            fallback["confidence_score"] = confidence_score
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
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
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
    index = get_pinecone_index()
    
    # Query Pinecone for a sample of vectors to analyze metadata
    # We use a dummy non-zero vector for a broad search within the namespace
    # Dimensions for text-embedding-3-large is 3072
    query_res = index.query(
        vector=[0.1] * 3072,
        top_k=1000, # Analyze up to 1000 chunks
        include_metadata=True,
        namespace=twin_id
    )
    
    matches = query_res.get("matches", [])
    total_chunks = len(matches)
    
    fact_count = 0
    opinion_count = 0
    tone_distribution = {}
    
    for match in matches:
        metadata = match.get("metadata", {})
        
        # Category: FACT or OPINION
        category = metadata.get("category", "FACT")
        if category == "OPINION":
            opinion_count += 1
        else:
            fact_count += 1
            
        # Tone Distribution
        tone = metadata.get("tone", "Neutral")
        tone_distribution[tone] = tone_distribution.get(tone, 0) + 1
    
    # Get top tone
    top_tone = "Neutral"
    if tone_distribution:
        top_tone = max(tone_distribution, key=tone_distribution.get)
        
    # Get total sources from Supabase
    sources_res = supabase.table("sources").select("id", count="exact").eq("twin_id", twin_id).execute()
    total_sources = sources_res.count if hasattr(sources_res, 'count') else len(sources_res.data)
    
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
