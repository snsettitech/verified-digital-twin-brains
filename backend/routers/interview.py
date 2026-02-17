# backend/routers/interview.py
"""Interview Mode endpoints for real-time voice interviews.

Manages interview sessions with:
- Session creation with context bundle retrieval from Zep/Graphiti
- Ephemeral key endpoint for secure WebRTC connection
- Session finalization with memory extraction and graph upsert
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import os
import httpx

from modules.auth_guard import get_current_user
from modules.observability import supabase
from modules.owner_memory_store import (
    create_owner_memory,
    suggest_topic_from_value,
    list_owner_memories,
    format_owner_memory_context,
)

router = APIRouter(prefix="/api/interview", tags=["interview"])


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


AUTO_APPROVE_OWNER_MEMORY = os.getenv("AUTO_APPROVE_OWNER_MEMORY", "true").lower() == "true"
INTERVIEW_MEMORY_MIN_CONFIDENCE = _float_env("INTERVIEW_MEMORY_MIN_CONFIDENCE", 0.45)


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new interview session."""
    twin_id: Optional[str] = None  # Optional only when tenant has exactly one twin


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
    proposed_count: int = 0
    proposed_failed_count: int = 0
    notes: List[str] = Field(default_factory=list)
    status: str


class RealtimeSessionRequest(BaseModel):
    """Request for ephemeral Realtime session key."""
    model: str = "gpt-4o-realtime-preview-2024-12-17"
    voice: str = "alloy"
    system_prompt: Optional[str] = None
    twin_id: Optional[str] = None


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

def _build_system_prompt(context_bundle: str, intent_profile: Optional[Dict[str, Any]] = None, public_intro: Optional[str] = None) -> str:
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
- If an INTENT PROFILE is provided, validate it first:
  - Ask one clear question about the primary use case
  - Ask one clear question about the audience/outcomes
  - Ask one clear question about boundaries (what to avoid or never do)
  - Only after validating intent should you move to goals, constraints, and preferences

Keep responses concise - you're interviewing, not lecturing."""

    intent_block = ""
    if intent_profile:
        use_case = (intent_profile.get("use_case") or "").strip()
        audience = (intent_profile.get("audience") or "").strip()
        boundaries = (intent_profile.get("boundaries") or "").strip()
        intent_lines = []
        if use_case:
            intent_lines.append(f"- Primary use case: {use_case}")
        if audience:
            intent_lines.append(f"- Audience: {audience}")
        if boundaries:
            intent_lines.append(f"- Boundaries: {boundaries}")
        if intent_lines:
            intent_block = "INTENT PROFILE (tailor questions around this):\n" + "\n".join(intent_lines)

    public_intro = (public_intro or "").strip()
    public_block = f"PUBLIC INTRO (how the user wants to be known):\n{public_intro}" if public_intro else ""

    extra_blocks = "\n\n".join([b for b in [intent_block, public_block] if b])
    prompt = base_prompt
    if extra_blocks:
        prompt = f"{prompt}\n\n{extra_blocks}"
    if context_bundle:
        prompt = f"""{prompt}

=== WHAT YOU ALREADY KNOW ABOUT THIS USER ===
{context_bundle}

Use this context to personalize your questions and avoid re-asking things you already know. Reference this knowledge naturally when relevant."""
    return prompt


def _map_interview_memory_type(mem_type: str) -> str:
    """Map interview memory types to owner memory types."""
    mem_type = (mem_type or "").lower().strip()
    if mem_type == "preference":
        return "preference"
    if mem_type == "constraint":
        return "lens"
    if mem_type == "boundary":
        return "tone_rule"
    # intent, goal -> belief by default
    return "belief"


async def _get_user_context(user_id: str, task: str = "interview", twin_id: Optional[str] = None) -> str:
    """
    Retrieve prioritized context bundle for the user from Zep/Graphiti.
    
    Priority order: boundaries > constraints > active goals > stable preferences > recent intent
    """
    try:
        from modules.zep_memory import get_zep_client
        zep_client = get_zep_client()
        
        # This will query Graphiti for prioritized context facts
        context = await zep_client.get_user_context(
            user_id=user_id,
            task=task,
            max_tokens=2000
        )
        
        if context:
            print(f"[Interview] Retrieved {len(context)} chars of context for user {user_id}")
        
        if context:
            return context
        
    except Exception as e:
        print(f"Error fetching user context from Zep: {e}")

    # Fallback when graph memory is unavailable: use owner memory rows for this twin.
    if twin_id:
        try:
            active_memories = list_owner_memories(twin_id, status="active", limit=20)
            proposed_memories: List[Dict[str, Any]] = []
            if not AUTO_APPROVE_OWNER_MEMORY:
                proposed_memories = list_owner_memories(twin_id, status="proposed", limit=20)

            sections: List[str] = []
            if active_memories:
                sections.append("**Approved owner memories:**")
                sections.append(format_owner_memory_context(active_memories, max_items=8))
            if proposed_memories:
                sections.append("**Pending owner memory proposals:**")
                sections.append(format_owner_memory_context(proposed_memories, max_items=6))

            fallback_context = "\n".join([s for s in sections if s]).strip()
            if fallback_context:
                summary = f"{len(active_memories)} approved"
                if proposed_memories:
                    summary += f", {len(proposed_memories)} proposed"
                print(
                    f"[Interview] Using owner memory fallback context "
                    f"({summary}) for twin {twin_id}"
                )
                return fallback_context
        except Exception as e:
            print(f"Error building owner-memory fallback context: {e}")

    return ""


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
    if twin_id:
        # Verify provided twin belongs to this tenant.
        twin_res = (
            supabase.table("twins")
            .select("id")
            .eq("id", twin_id)
            .eq("tenant_id", tenant_id)
            .single()
            .execute()
        )
        if not twin_res.data:
            raise HTTPException(status_code=404, detail="Twin not found")
    else:
        # Safe fallback only if tenant has exactly one twin.
        twins_resp = (
            supabase.table("twins")
            .select("id")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(2)
            .execute()
        )
        twin_rows = twins_resp.data or []
        if len(twin_rows) == 1:
            twin_id = twin_rows[0]["id"]
        elif len(twin_rows) == 0:
            raise HTTPException(status_code=404, detail="No twin found for this account")
        else:
            raise HTTPException(
                status_code=422,
                detail="Multiple twins found. Select a twin explicitly before starting interview mode."
            )
    
    # Get context from prior sessions
    context_bundle = await _get_user_context(user_id, "interview", twin_id=twin_id)

    # Load intent profile + public intro from twin settings if available
    intent_profile = {}
    public_intro = ""
    if twin_id:
        try:
            twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
            settings = twin_res.data.get("settings", {}) if twin_res.data else {}
            intent_profile = settings.get("intent_profile") or {}
            public_intro = settings.get("public_intro") or ""
        except Exception as e:
            print(f"Warning: failed to load intent profile: {e}")
    
    # Build system prompt
    system_prompt = _build_system_prompt(context_bundle, intent_profile=intent_profile, public_intro=public_intro)
    
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
                "context_provided": bool(context_bundle)
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
            "has_prior_context": bool(context_bundle)
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
    
    # Load and validate session ownership first.
    session_row = None
    try:
        session_res = (
            supabase.table("interview_sessions")
            .select("id, twin_id, user_id, status")
            .eq("id", session_id)
            .single()
            .execute()
        )
        session_row = session_res.data
    except Exception as e:
        print(f"Error loading interview session {session_id}: {e}")

    if not session_row:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session_row.get("user_id") and session_row.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this interview session")
    if session_row.get("status") == "completed":
        raise HTTPException(status_code=409, detail="Interview session already finalized")

    # Extract memories from transcript
    extracted_memories = await _extract_memories_from_transcript(
        request.transcript,
        session_id
    )

    # Store extracted memories as owner memories.
    # In auto-approve mode we persist directly as verified.
    twin_id = session_row.get("twin_id")
    proposed_count = 0
    proposed_failed_count = 0
    low_confidence_skipped = 0
    notes: List[str] = []
    memory_status = "verified" if AUTO_APPROVE_OWNER_MEMORY else "proposed"

    if twin_id and extracted_memories:
        for memory in extracted_memories:
            try:
                if memory.confidence < INTERVIEW_MEMORY_MIN_CONFIDENCE:
                    low_confidence_skipped += 1
                    continue
                mapped_type = _map_interview_memory_type(memory.type)
                topic_normalized = suggest_topic_from_value(memory.value)
                created = create_owner_memory(
                    twin_id=twin_id,
                    tenant_id=user.get("tenant_id"),
                    topic_normalized=topic_normalized,
                    memory_type=mapped_type,
                    value=memory.value,
                    confidence=float(memory.confidence),
                    provenance={
                        "source_type": "interview",
                        "source_id": session_id,
                        "owner_id": user_id,
                        "original_type": memory.type
                    },
                    status=memory_status
                )
                if created:
                    proposed_count += 1
                else:
                    proposed_failed_count += 1
            except Exception as e:
                print(f"[Interview] Failed to propose owner memory: {e}")
                proposed_failed_count += 1

        if low_confidence_skipped > 0:
            notes.append(
                f"{low_confidence_skipped} low-confidence memories were skipped "
                f"(<{INTERVIEW_MEMORY_MIN_CONFIDENCE})."
            )
        if proposed_failed_count > 0:
            target_state = "verified memories" if AUTO_APPROVE_OWNER_MEMORY else "memory proposals"
            notes.append(
                f"{proposed_failed_count} memories could not be saved as {target_state}. "
                "Check owner_beliefs migration/status constraints."
            )
        if proposed_count == 0 and extracted_memories:
            notes.append("No interview memories were persisted. Review extraction quality and owner memory schema.")
        elif AUTO_APPROVE_OWNER_MEMORY and proposed_count > 0:
            notes.append(f"{proposed_count} interview memories were auto-approved and saved as verified.")
    elif not twin_id:
        notes.append("Interview session has no twin_id; owner memories could not be created.")
    elif not extracted_memories:
        notes.append("No memories were extracted from transcript.")
    
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
    
    session_metadata = dict(request.metadata or {})
    session_metadata.update({
        "extracted_count": len(extracted_memories),
        "proposed_count": proposed_count,
        "proposed_failed_count": proposed_failed_count,
        "low_confidence_skipped": low_confidence_skipped,
        "memory_status_target": memory_status,
        "auto_approve_owner_memory": AUTO_APPROVE_OWNER_MEMORY,
    })

    # Update session record
    try:
        supabase.table("interview_sessions").update({
            "ended_at": datetime.utcnow().isoformat(),
            "duration_seconds": request.duration_seconds,
            "transcript": [t.model_dump() for t in request.transcript],
            "memories_extracted": len(extracted_memories),
            "status": "completed",
            "metadata": session_metadata
        }).eq("id", session_id).execute()
    except Exception as e:
        print(f"Error updating interview session: {e}")
        # Continue anyway - extraction is more important
    
    return FinalizeSessionResponse(
        session_id=session_id,
        extracted_memories=extracted_memories,
        write_count=write_count,
        proposed_count=proposed_count,
        proposed_failed_count=proposed_failed_count,
        notes=notes,
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
    tenant_id = user.get("tenant_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Validate optional twin scope for context binding.
    if request.twin_id:
        twin_res = (
            supabase.table("twins")
            .select("id")
            .eq("id", request.twin_id)
            .eq("tenant_id", tenant_id)
            .single()
            .execute()
        )
        if not twin_res.data:
            raise HTTPException(status_code=404, detail="Twin not found")

    # Get user context if no system prompt provided
    system_prompt = request.system_prompt
    if not system_prompt:
        context_bundle = await _get_user_context(user_id, "interview", twin_id=request.twin_id)
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
    
    context_bundle = await _get_user_context(user_id, task)
    
    return ContextBundleResponse(
        context_bundle=context_bundle,
        memory_count=0,  # TODO: Return actual count from Zep
        priority_order=["boundary", "constraint", "goal", "preference", "intent"]
    )
