# backend/routers/interview.py
"""Interview Mode endpoints for real-time voice interviews.

Manages interview sessions with:
- Session creation with context bundle retrieval from Zep/Graphiti
- Ephemeral key endpoint for secure WebRTC connection
- Session finalization with memory extraction and graph upsert
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import uuid
import os
import httpx

from modules.auth_guard import get_current_user
from modules.observability import supabase

router = APIRouter(prefix="/api/interview", tags=["interview"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new interview session."""
    twin_id: Optional[str] = None  # Optional, will use user's default twin if not provided


class CreateSessionResponse(BaseModel):
    """Response from session creation."""
    session_id: str
    context_bundle: str
    system_prompt: str
    metadata: Dict[str, Any] = {}


class TranscriptTurn(BaseModel):
    """A single turn in the transcript."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None


class FinalizeSessionRequest(BaseModel):
    """Request to finalize an interview session."""
    transcript: List[TranscriptTurn]
    duration_seconds: int
    metadata: Optional[Dict[str, Any]] = None


class ExtractedMemory(BaseModel):
    """A memory item extracted from the transcript."""
    type: str  # intent, goal, constraint, preference, boundary
    value: str
    evidence: str
    confidence: float
    timestamp: str
    session_id: str
    source: str = "interview_mode"


class FinalizeSessionResponse(BaseModel):
    """Response from session finalization."""
    session_id: str
    extracted_memories: List[ExtractedMemory]
    write_count: int
    status: str


class RealtimeSessionRequest(BaseModel):
    """Request for ephemeral Realtime session key."""
    model: str = "gpt-4o-realtime-preview-2024-12-17"
    voice: str = "alloy"
    system_prompt: Optional[str] = None


class RealtimeSessionResponse(BaseModel):
    """Response with ephemeral session credentials."""
    client_secret: str
    session_id: str
    expires_at: str


class ContextBundleRequest(BaseModel):
    """Request for user context bundle."""
    task: str = "interview"


class ContextBundleResponse(BaseModel):
    """Response with prioritized context bundle."""
    context_bundle: str
    memory_count: int
    priority_order: List[str]


# =============================================================================
# Helper Functions
# =============================================================================

def _build_system_prompt(context_bundle: str) -> str:
    """Build the system prompt for the Realtime interview session."""
    base_prompt = """You are conducting a conversational interview to learn about the user. Your goal is to understand their:

1. **Intent** - What they're trying to accomplish
2. **Goals** - Their short and long-term objectives  
3. **Constraints** - Limitations or restrictions they face
4. **Preferences** - How they like things done
5. **Boundaries** - What they won't do or topics they avoid

Guidelines:
- Be conversational, warm, and curious
- Ask follow-up questions to go deeper
- Acknowledge what they share before moving on
- Don't interrogate - this should feel natural
- If they seem uncomfortable with a topic, gracefully move on
- Summarize key points periodically to confirm understanding

Keep responses concise - you're interviewing, not lecturing."""

    if context_bundle:
        return f"""{base_prompt}

=== WHAT YOU ALREADY KNOW ABOUT THIS USER ===
{context_bundle}

Use this context to personalize your questions and avoid re-asking things you already know. Reference this knowledge naturally when relevant."""
    
    return base_prompt


async def _get_user_context(user_id: str, task: str = "interview") -> Tuple[str, int]:
    """
    Retrieve prioritized context bundle for the user from Zep/Graphiti.
    
    Priority order: boundaries > constraints > active goals > stable preferences > recent intent

    Returns:
        Tuple of (context_string, memory_count)
    """
    try:
        from modules.zep_memory import get_zep_client
        zep_client = get_zep_client()
        
        # This will query Graphiti for prioritized context facts
        context, count = await zep_client.get_user_context(
            user_id=user_id,
            task=task,
            max_tokens=2000
        )
        
        if context:
            print(f"[Interview] Retrieved {len(context)} chars of context ({count} memories) for user {user_id}")
        
        return context, count
        
    except Exception as e:
        print(f"Error fetching user context from Zep: {e}")
        return "", 0


async def _create_ephemeral_realtime_session(
    system_prompt: str,
    model: str = "gpt-4o-realtime-preview-2024-12-17",
    voice: str = "alloy"
) -> Dict[str, Any]:
    """
    Create an ephemeral Realtime session via OpenAI API.
    Returns client_secret for secure browser WebRTC connection.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "voice": voice,
                "instructions": system_prompt,
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            error_detail = response.text
            print(f"Realtime session error: {response.status_code} - {error_detail}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to create Realtime session: {error_detail}"
            )
        
        return response.json()


async def _extract_memories_from_transcript(
    transcript: List[TranscriptTurn],
    session_id: str
) -> List[ExtractedMemory]:
    """
    Extract structured memories from the transcript using LLM.
    
    Returns memories with types: intent, goal, constraint, preference, boundary
    """
    from modules.memory_extractor import extract_memories as _extract
    
    if not transcript:
        return []
    
    # Convert TranscriptTurn to dict format expected by extractor
    transcript_dicts = [{"role": t.role, "content": t.content} for t in transcript]
    
    # Run LLM extraction
    result = await _extract(transcript_dicts, session_id)
    
    # Convert to our response model format
    memories = []
    for mem in result.memories:
        memories.append(ExtractedMemory(
            type=mem.type,
            value=mem.value,
            evidence=mem.evidence,
            confidence=mem.confidence,
            timestamp=mem.timestamp,
            session_id=mem.session_id,
            source=mem.source
        ))
    
    return memories


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/sessions", response_model=CreateSessionResponse)
async def create_interview_session(
    request: CreateSessionRequest,
    user=Depends(get_current_user)
):
    """
    Create a new interview session.
    
    Returns session_id, context_bundle from prior sessions, and system_prompt
    for the Realtime connection.
    """
    user_id = user.get("user_id")
    tenant_id = user.get("tenant_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Get or determine twin_id
    twin_id = request.twin_id
    if not twin_id:
        # Get user's default twin
        twins_resp = supabase.table("twins").select("id").eq(
            "tenant_id", tenant_id
        ).limit(1).execute()
        
        if twins_resp.data:
            twin_id = twins_resp.data[0]["id"]
    
    # Get context from prior sessions
    context_bundle, memory_count = await _get_user_context(user_id, "interview")
    
    # Build system prompt
    system_prompt = _build_system_prompt(context_bundle)
    
    # Create session record
    session_id = str(uuid.uuid4())
    
    try:
        supabase.table("interview_sessions").insert({
            "id": session_id,
            "user_id": user_id,
            "twin_id": twin_id,
            "started_at": datetime.utcnow().isoformat(),
            "status": "active",
            "metadata": {
                "context_provided": bool(context_bundle),
                "memory_count_at_start": memory_count
            }
        }).execute()
    except Exception as e:
        print(f"Error creating interview session: {e}")
        # Table might not exist yet - continue anyway
        pass
    
    return CreateSessionResponse(
        session_id=session_id,
        context_bundle=context_bundle,
        system_prompt=system_prompt,
        metadata={
            "twin_id": twin_id,
            "has_prior_context": bool(context_bundle),
            "memory_count": memory_count
        }
    )


@router.post("/sessions/{session_id}/finalize", response_model=FinalizeSessionResponse)
async def finalize_interview_session(
    session_id: str,
    request: FinalizeSessionRequest,
    user=Depends(get_current_user)
):
    """
    Finalize an interview session.
    
    Processes the transcript, extracts memories, and upserts to Zep/Graphiti.
    """
    user_id = user.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Extract memories from transcript
    extracted_memories = await _extract_memories_from_transcript(
        request.transcript,
        session_id
    )
    
    # Upsert memories to Zep/Graphiti
    write_count = 0
    try:
        from modules.zep_memory import get_zep_client
        zep_client = get_zep_client()
        
        for memory in extracted_memories:
            result = await zep_client.upsert_memory(
                user_id,
                memory.model_dump()
            )
            if result.get("status") in ["created", "fallback"]:
                write_count += 1
    except Exception as e:
        print(f"Error upserting memories to Zep: {e}")
        # Continue anyway - transcript storage is more important
    
    # Update session record
    try:
        supabase.table("interview_sessions").update({
            "ended_at": datetime.utcnow().isoformat(),
            "duration_seconds": request.duration_seconds,
            "transcript": [t.model_dump() for t in request.transcript],
            "memories_extracted": len(extracted_memories),
            "status": "completed",
            "metadata": request.metadata or {}
        }).eq("id", session_id).execute()
    except Exception as e:
        print(f"Error updating interview session: {e}")
        # Continue anyway - extraction is more important
    
    return FinalizeSessionResponse(
        session_id=session_id,
        extracted_memories=extracted_memories,
        write_count=write_count,
        status="completed"
    )


@router.post("/realtime/sessions", response_model=RealtimeSessionResponse)
async def create_realtime_session(
    request: RealtimeSessionRequest,
    user=Depends(get_current_user)
):
    """
    Create an ephemeral OpenAI Realtime session.
    
    SECURITY CRITICAL: This endpoint creates a short-lived client_secret
    that the browser uses to establish WebRTC connection. The browser
    NEVER sees the actual OpenAI API key.
    """
    user_id = user.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Get user context if no system prompt provided
    system_prompt = request.system_prompt
    if not system_prompt:
        context_bundle, _ = await _get_user_context(user_id, "interview")
        system_prompt = _build_system_prompt(context_bundle)
    
    # Create ephemeral session via OpenAI
    session_data = await _create_ephemeral_realtime_session(
        system_prompt=system_prompt,
        model=request.model,
        voice=request.voice
    )
    
    # Extract client_secret from response
    client_secret = session_data.get("client_secret", {}).get("value", "")
    session_id = session_data.get("id", str(uuid.uuid4()))
    # OpenAI returns expires_at as Unix timestamp integer - convert to string
    expires_at_raw = session_data.get("client_secret", {}).get("expires_at", "")
    expires_at = str(expires_at_raw) if expires_at_raw else ""
    
    if not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Failed to obtain ephemeral client secret from OpenAI"
        )
    
    return RealtimeSessionResponse(
        client_secret=client_secret,
        session_id=session_id,
        expires_at=expires_at
    )


@router.get("/context", response_model=ContextBundleResponse)
async def get_user_context(
    task: str = "interview",
    user=Depends(get_current_user)
):
    """
    Get prioritized context bundle for the user.
    
    Priority order: boundaries > constraints > active goals > stable preferences > recent intent
    """
    user_id = user.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    context_bundle, memory_count = await _get_user_context(user_id, task)
    
    return ContextBundleResponse(
        context_bundle=context_bundle,
        memory_count=memory_count,
        priority_order=["boundary", "constraint", "goal", "preference", "intent"]
    )
