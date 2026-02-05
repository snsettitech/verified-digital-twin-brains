from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional
from modules.schemas import (
    ChatRequest, ChatMetadata, ChatWidgetRequest, PublicChatRequest, 
    MessageSchema, ConversationSchema
)
from modules.auth_guard import get_current_user, verify_twin_ownership, verify_conversation_ownership, ensure_twin_active
from modules.access_groups import get_user_group, get_default_group
from modules.observability import (
    supabase, get_conversations, get_messages, 
    log_interaction, create_conversation
)
from modules.agent import run_agent_stream
from modules.identity_gate import run_identity_gate
from modules.owner_memory_store import create_clarification_thread
from modules.memory_events import create_memory_event
from langchain_core.messages import HumanMessage, AIMessage
from datetime import datetime
import re
import json
import asyncio

# Langfuse v3 tracing
try:
    from langfuse import observe, get_client
    _langfuse_available = True
    _langfuse_client = get_client()
except ImportError:
    _langfuse_available = False
    _langfuse_client = None
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

def _normalize_json(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, list):
        return [_normalize_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_json(v) for k, v in value.items()}
    return str(value)

@router.post("/chat/{twin_id}")
@observe(name="chat_request")
async def chat(twin_id: str, request: ChatRequest, user=Depends(get_current_user)):
    # P0: Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    
    # Compatibility: accept legacy {message} payloads
    query = request.query or request.message or ""
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    conversation_id = request.conversation_id
    group_id = request.group_id
    
    # Update Langfuse trace with session and user info (v3 pattern)
    if _langfuse_available and _langfuse_client:
        try:
            import os
            release = os.getenv("LANGFUSE_RELEASE", "dev")
            # Get current observation and call update_trace on it
            current_obs = _langfuse_client.get_current_observation()
            if current_obs and hasattr(current_obs, 'update_trace'):
                current_obs.update_trace(
                    session_id=conversation_id,
                    user_id=twin_id,
                    metadata={
                        "group_id": group_id,
                        "query_length": len(query) if query else 0,
                        "release": release,
                    }
                )
        except Exception as e:
            logger.warning(f"Langfuse trace update failed: {e}")
    
    # Determine user's group
    try:
        if not group_id:
            # Check if conversation has a group_id set
            if conversation_id:
                try:
                    conv_response = supabase.table("conversations").select("group_id").eq("id", conversation_id).single().execute()
                    if conv_response.data and conv_response.data.get("group_id"):
                        group_id = conv_response.data["group_id"]
                except Exception as e:
                    logger.warning(f"Warning: Could not fetch conversation group_id: {e}")
            
            # If still no group_id, get user's default group
            if not group_id:
                user_id = user.get("user_id") if user else None
                if user_id:
                    user_group = await get_user_group(user_id, twin_id)
                    if user_group:
                        group_id = user_group["id"]
            
            # If still no group_id (anonymous or no group assigned), try public default
            if not group_id:
                default_group = await get_default_group(twin_id)
                if default_group:
                    group_id = default_group["id"]
    except Exception as e:
        logger.error(f"Chat Setup Error: {e}", exc_info=True)
        # Don't raise, let stream generator handle it or default to None
        logger.error(f"Chat Setup Failed: {e}")

    mode = request.mode or ("public" if user and user.get("role") == "visitor" else "owner")

    async def stream_generator():
        nonlocal conversation_id
        try:
            # 1. Prepare History
            raw_history = []
            langchain_history = []
            if conversation_id:
                raw_history = get_messages(conversation_id)
                for msg in raw_history:
                    if msg.get("role") == "user":
                        langchain_history.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        langchain_history.append(AIMessage(content=msg.get("content", "")))

            # 2. Run Agent Stream - collect final response
            full_response = ""
            citations = []
            confidence_score = 1.0
            decision_trace = None
            
            # Fetch graph stats for this twin
            from modules.graph_context import get_graph_stats
            graph_stats = get_graph_stats(twin_id)
            
            # Identity Confidence Gate (deterministic)
            history_for_gate = []
            if raw_history:
                for msg in raw_history[-6:]:
                    history_for_gate.append({
                        "role": msg.get("role"),
                        "content": msg.get("content", "")
                    })

            gate = await run_identity_gate(
                query=query,
                history=history_for_gate,
                twin_id=twin_id,
                tenant_id=user.get("tenant_id") if user else None,
                group_id=group_id,
                mode=mode
            )

            # If clarification required, emit single clarify event and stop
            if gate.get("decision") == "CLARIFY":
                # Ensure conversation exists for audit trail
                if not conversation_id:
                    user_id = user.get("user_id") if user else None
                    conv = create_conversation(twin_id, user_id, group_id=group_id)
                    conversation_id = conv["id"]

                # Create clarification thread
                clarif = create_clarification_thread(
                    twin_id=twin_id,
                    tenant_id=user.get("tenant_id") if user else None,
                    question=gate.get("question", ""),
                    options=gate.get("options", []),
                    memory_write_proposal=gate.get("memory_write_proposal", {}),
                    original_query=query,
                    conversation_id=conversation_id,
                    mode=mode,
                    requested_by="owner" if mode == "owner" else "public",
                    created_by=user.get("user_id") if user else None
                )

                # Audit event for pending clarification
                try:
                    if user and user.get("tenant_id"):
                        await create_memory_event(
                            twin_id=twin_id,
                            tenant_id=user.get("tenant_id"),
                            event_type="owner_memory_pending",
                            payload={
                                "clarification_id": clarif.get("id") if clarif else None,
                                "question": gate.get("question"),
                                "topic": gate.get("topic"),
                                "memory_type": gate.get("memory_type")
                            },
                            status="pending_review",
                            source_type="chat_turn",
                            source_id=conversation_id
                        )
                except Exception as e:
                    logger.warning(f"Memory event pending log failed: {e}")

                # Log interaction
                log_interaction(conversation_id, "user", query)
                log_interaction(conversation_id, "assistant", gate.get("question", ""))

                clarify_event = {
                    "type": "clarify",
                    "clarification_id": clarif.get("id") if clarif else None,
                    "question": gate.get("question"),
                    "options": gate.get("options", []),
                    "memory_write_proposal": gate.get("memory_write_proposal", {}),
                    "status": "pending_owner",
                    "conversation_id": conversation_id
                }
                yield json.dumps(clarify_event) + "\n"
                return

            owner_memory_context = gate.get("owner_memory_context", "")
            owner_memory_refs = gate.get("owner_memory_refs", [])
            owner_memory_candidates = gate.get("owner_memory") or []
            owner_memory_summaries = []
            for mem in owner_memory_candidates:
                topic = mem.get("topic_normalized") or mem.get("topic")
                if mem.get("id") or topic:
                    owner_memory_summaries.append({
                        "id": mem.get("id"),
                        "topic": topic
                    })
            owner_memory_topics = [s.get("topic") for s in owner_memory_summaries if s.get("topic")]

            # DETECT REASONING INTENT (Simple Heuristic for now)
            # In production, use a classifier model
            is_reasoning_query = any(phrase in query.lower() for phrase in [
                "would i ", "do i think", "what is my stance", "how do i feel"
            ])
            # If owner memory is available, skip reasoning engine for stance queries
            if owner_memory_refs:
                is_reasoning_query = False
            
            if is_reasoning_query:
                try:
                    from modules.reasoning_engine import ReasoningEngine
                    engine = ReasoningEngine(twin_id)
                    trace = await engine.predict_stance(query, context_context=owner_memory_context)
                    
                    full_response = trace.to_readable_trace()
                    confidence_score = trace.confidence_score
                    decision_trace = trace.model_dump()
                    
                    # Log as assistant message
                    langchain_history.append(AIMessage(content=full_response))
                    
                except Exception as e:
                    print(f"Reasoning Engine Failed: {e}")
                    # Fallback to standard agent
                    is_reasoning_query = False
            
            print(f"[Chat] Stream started for twin_id={twin_id}, query='{query}'")
            # Log full query for debugging
            print(f"[Chat DEBUG] Full Query: {query}")
            
            if not is_reasoning_query:
                agent_iter = run_agent_stream(
                    twin_id=twin_id,
                    query=query,
                    history=langchain_history,
                    group_id=group_id,
                    conversation_id=conversation_id,
                    owner_memory_context=owner_memory_context
                ).__aiter__()

                pending_task = None
                while True:
                    if pending_task is None:
                        pending_task = asyncio.create_task(agent_iter.__anext__())

                    done, _ = await asyncio.wait({pending_task}, timeout=10)
                    if not done:
                        # Keep the SSE stream alive while the agent is still thinking.
                        # Keep SSE stream alive using canonical event type
                        yield json.dumps({"type": "metadata", "ping": True}) + "\n"
                        continue

                    try:
                        chunk = pending_task.result()
                    except StopAsyncIteration:
                        break
                    finally:
                        pending_task = None

                    # Capture metadata from tools
                    if "tools" in chunk:
                        data = chunk["tools"]
                        citations = data.get("citations", citations)
                        confidence_score = data.get("confidence_score", confidence_score)
                        print(f"[Chat] Tools event: confidence={confidence_score}, citations={len(citations)}")
    
                    # Capture final response from agent (only if has content, not just tool calls)
                    if "agent" in chunk:
                        msgs = chunk["agent"]["messages"]
                        if msgs and isinstance(msgs[-1], AIMessage):
                            msg = msgs[-1]
                            # Only update if there's actual content (not just tool calls)
                            if msg.content and not getattr(msg, 'tool_calls', None):
                                full_response = msg.content

            # If model fell back despite having citations, try a deterministic extract
            fallback_message = "I don't have this specific information in my knowledge base."
            if full_response.strip() == fallback_message and citations:
                needs_exact = re.search(r"(exact|verbatim|only the exact).*(phrase|quote|line)", query.lower())
                if needs_exact:
                    try:
                        from modules.retrieval import retrieve_context
                        contexts = await retrieve_context(query, twin_id, group_id=group_id, top_k=1)
                        if contexts:
                            context_text = contexts[0].get("text", "")
                            first_line = next((line.strip() for line in context_text.splitlines() if line.strip()), "")
                            if first_line:
                                full_response = first_line
                                print("[Chat] Fallback override: extracted exact line from context")
                    except Exception as e:
                        print(f"[Chat] Fallback override failed: {e}")
            
            # Determine if graph was likely used (no external citations and has graph)
            graph_used = graph_stats["has_graph"] and len(citations) == 0
            
            # 3. Send metadata first (so frontend knows context is found)
            metadata = _normalize_json({
                "type": "metadata",
                "citations": citations,
                "confidence_score": confidence_score,
                "conversation_id": conversation_id,
                "owner_memory_refs": owner_memory_refs,
                "owner_memory_topics": owner_memory_topics,
                "owner_memory_summaries": owner_memory_summaries,
                "graph_context": {
                    "has_graph": graph_stats["has_graph"],
                    "node_count": graph_stats["node_count"],
                    "graph_used": graph_used
                },
                "decision_trace": decision_trace
            })
            yield json.dumps(metadata) + "\n"
            
            # 4. Send final content
            if full_response:
                print(f"[Chat] Yielding content: {len(full_response)} chars")
                yield json.dumps({"type": "content", "token": full_response, "content": full_response}) + "\n"
            else:
                fallback = "I don't have this specific information in my knowledge base."
                print(f"[Chat] Fallback emitted: {fallback}")
                yield json.dumps({"type": "content", "token": fallback, "content": fallback}) + "\n"

            # 5. Done event
            yield json.dumps({"type": "done"}) + "\n"
            
            print(f"[Chat] Stream ended for twin_id={twin_id}")

            # 5. Log conversation
            if full_response or True: # Always log if we reached here
                # Create conversation if needed
                if not conversation_id:
                    user_id = user.get("user_id") if user else None
                    conv = create_conversation(twin_id, user_id, group_id=group_id)
                    conversation_id = conv["id"]
                
                log_interaction(conversation_id, "user", query)
                log_interaction(conversation_id, "assistant", full_response or fallback, citations, confidence_score)
            
            # 6. Trigger Scribe (Job Queue for reliability)
            try:
                from modules._core.scribe_engine import enqueue_graph_extraction_job
                job_id = None
                if full_response:
                    # Get tenant_id from user for MemoryEvent audit trail
                    tenant_id = user.get("tenant_id") if user else None
                    # Enqueue graph extraction job (replaces fire-and-forget)
                    job_id = enqueue_graph_extraction_job(
                        twin_id=twin_id,
                        user_message=query,
                        assistant_message=full_response,
                        history=raw_history,
                        tenant_id=tenant_id,
                        conversation_id=conversation_id
                    )
                    if job_id:
                        print(f"[Chat] Enqueued graph extraction job {job_id} for conversation {conversation_id}")
            except Exception as se:
                print(f"[Chat] Scribe enqueue failed (non-blocking): {se}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"Error: {str(e)}"
            print(f"[Chat] ERROR yielded in stream: {error_msg}")
            yield json.dumps({"type": "error", "error": error_msg}) + "\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@router.get("/conversations/{twin_id}")
async def list_conversations_endpoint(twin_id: str, user=Depends(get_current_user)):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    return get_conversations(twin_id)

@router.get("/conversations/{conversation_id}/messages")
async def list_messages_endpoint(conversation_id: str, user=Depends(get_current_user)):
    verify_conversation_ownership(conversation_id, user)
    return get_messages(conversation_id)

# Chat Widget Interface
@router.post("/chat-widget/{twin_id}")
async def chat_widget(twin_id: str, request: ChatWidgetRequest, req_raw: Request = None):
    """
    Public chat interface for widgets.
    Uses API keys and sessions instead of user auth.
    """
    from modules.api_keys import validate_api_key, validate_domain
    from modules.sessions import create_session, get_session, update_session_activity
    from modules.rate_limiting import check_rate_limit, record_request
    
    # 1. Validate API Key
    key_info = validate_api_key(request.api_key)
    if not key_info or key_info["twin_id"] != twin_id:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # 2. Validate Domain (CORS/Origin check)
    origin = ""
    if req_raw:
        origin = req_raw.headers.get("origin", "")
    
    if key_info["allowed_domains"] and not validate_domain(origin, key_info["allowed_domains"]):
        raise HTTPException(status_code=403, detail="Domain not allowed")
    
    # 3. Handle Session
    ensure_twin_active(twin_id)
    session_id = request.session_id
    if session_id:
        session = get_session(session_id)
        if not session or session["twin_id"] != twin_id:
            session_id = None # Force new session if invalid
        else:
            update_session_activity(session_id)
    
    if not session_id:
        session_id = create_session(
            twin_id=twin_id,
            group_id=key_info.get("group_id"),
            session_type="anonymous",
            ip_address=req_raw.client.host if req_raw else None,
            user_agent=req_raw.headers.get("user-agent") if req_raw else None
        )
    
    # 4. Rate Limiting Check
    # Check sessions per hour
    allowed, status = check_rate_limit(session_id, "session", "requests_per_hour", 30)
    if not allowed:
        raise HTTPException(status_code=429, detail="Session rate limit exceeded")
    
    # 5. Process Chat
    # Compatibility: accept legacy {message} payloads
    query = request.query or request.message or ""
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    group_id = key_info.get("group_id")
    
    # Get conversation for session
    # (Simplified for now: 1 conversation per session)
    conv_response = supabase.table("conversations").select("id").eq("session_id", session_id).limit(1).execute()
    if conv_response.data and len(conv_response.data) > 0:
        conversation_id = conv_response.data[0]["id"]
    else:
        conv_obj = create_conversation(twin_id, None, group_id=group_id)
        conversation_id = conv_obj["id"]
        # Link conversation to session
        supabase.table("conversations").update({"session_id": session_id}).eq("id", conversation_id).execute()
    
    # Get system prompt and history
    twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
    system_prompt = ""
    if twin_res.data:
        system_prompt = twin_res.data.get("settings", {}).get("system_prompt", "")
    
    # Inject Style Guidelines
    from modules.graph_context import get_style_guidelines
    style_guide = get_style_guidelines(twin_id)
    if style_guide:
        system_prompt += f"\n\n{style_guide}"
    
    history = get_messages(conversation_id)

    # Identity gate for public/widget
    gate = await run_identity_gate(
        query=query,
        history=[{"role": m.get("role"), "content": m.get("content", "")} for m in (history or [])[-6:]],
        twin_id=twin_id,
        tenant_id=None,
        group_id=group_id,
        mode="public"
    )

    if gate.get("decision") == "CLARIFY":
        # Create clarification thread for owner to resolve
        clarif = create_clarification_thread(
            twin_id=twin_id,
            tenant_id=None,
            question=gate.get("question", ""),
            options=gate.get("options", []),
            memory_write_proposal=gate.get("memory_write_proposal", {}),
            original_query=query,
            conversation_id=conversation_id,
            mode="public",
            requested_by="public",
            created_by=None
        )

        async def widget_clarify_stream():
            yield json.dumps({
                "type": "clarify",
                "clarification_id": clarif.get("id") if clarif else None,
                "question": gate.get("question"),
                "options": gate.get("options", []),
                "memory_write_proposal": gate.get("memory_write_proposal", {}),
                "status": "pending_owner",
                "conversation_id": conversation_id,
                "session_id": session_id
            }) + "\n"
        return StreamingResponse(widget_clarify_stream(), media_type="text/event-stream")

    owner_memory_context = gate.get("owner_memory_context", "")
    owner_memory_refs = gate.get("owner_memory_refs", [])
    owner_memory_candidates = gate.get("owner_memory") or []
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]
    owner_memory_candidates = gate.get("owner_memory") or []
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]
    owner_memory_candidates = gate.get("owner_memory") or []
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]
    owner_memory_candidates = gate.get("owner_memory") or []
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]
    owner_memory_candidates = gate.get("owner_memory") or []
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]
    
    async def widget_stream_generator():
        final_content = ""
        citations = []
        confidence_score = 0.0
        sent_metadata = False

        async for event in run_agent_stream(
            twin_id,
            query,
            history,
            system_prompt,
            group_id=group_id,
            conversation_id=conversation_id,
            owner_memory_context=owner_memory_context
        ):
            if "tools" in event:
                citations = event["tools"].get("citations", citations)
                confidence_score = event["tools"].get("confidence_score", confidence_score)
                
                if not sent_metadata:
                    output = {
                        "type": "metadata",
                        "confidence_score": confidence_score,
                        "citations": citations,
                        "conversation_id": conversation_id,
                        "owner_memory_refs": owner_memory_refs,
                        "owner_memory_topics": owner_memory_topics,
                        "session_id": session_id
                    }
                    yield json.dumps(output) + "\n"
                    sent_metadata = True

            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                if isinstance(msg, AIMessage):
                    final_content += msg.content
                    yield json.dumps({"type": "content", "token": msg.content, "content": msg.content}) + "\n"

        # Record usage
        record_request(session_id, "session", "requests_per_hour")
        
        # Log interaction
        log_interaction(conversation_id, "assistant", final_content, citations, confidence_score)
        
        yield json.dumps({"type": "done", "escalated": confidence_score < 0.7}) + "\n"

    return StreamingResponse(widget_stream_generator(), media_type="text/event-stream")

@router.post("/public/chat/{twin_id}/{token}")
async def public_chat_endpoint(twin_id: str, token: str, request: PublicChatRequest, req_raw: Request = None):
    """Handle public chat via share link"""
    from modules.share_links import validate_share_token, get_public_group_for_twin
    from modules.actions_engine import EventEmitter, TriggerMatcher, ActionDraftManager
    from modules.rate_limiting import check_rate_limit
    
    # Validate share token
    if not validate_share_token(token, twin_id):
        raise HTTPException(status_code=403, detail="Invalid or expired share link")
    
    ensure_twin_active(twin_id)
    
    # Rate limit by IP address for public endpoints
    client_ip = req_raw.client.host if req_raw and req_raw.client else "unknown"
    rate_key = f"public_chat:{twin_id}:{client_ip}"
    allowed, status = check_rate_limit(rate_key, "ip", "requests_per_minute", 10)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    
    # Get public group for context
    public_group = get_public_group_for_twin(twin_id)
    group_id = public_group["id"] if public_group else None
    
    # Emit message_received event for trigger matching
    triggered_actions = []
    try:
        event_id = EventEmitter.emit(
            twin_id=twin_id,
            event_type='message_received',
            payload={
                'user_message': request.message,
                'user_id': 'anonymous'
            },
            source_context={
                'group_id': group_id,
                'channel': 'public_share'
            }
        )
        if event_id:
            pending_drafts = ActionDraftManager.get_pending_drafts(twin_id)
            for draft in pending_drafts:
                if draft.get('event_id') == event_id:
                    triggered_actions.append(draft.get('proposed_action', {}).get('action_type'))
    except Exception as e:
        print(f"Warning: Could not emit event or check triggers: {e}")
    
    conversation_id = None
    # Build conversation history (tolerate extra fields)
    history = []
    if request.conversation_history:
        for msg in request.conversation_history:
            role = msg.get("role") if isinstance(msg, dict) else None
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, str):
                continue
            if role == "user":
                history.append(HumanMessage(content=content))
            elif role == "assistant":
                history.append(AIMessage(content=content))

    # Identity gate for public chat
    gate = await run_identity_gate(
        query=request.message,
        history=[{"role": "user", "content": m.content} for m in history[-6:]] if history else [],
        twin_id=twin_id,
        tenant_id=None,
        group_id=group_id,
        mode="public"
    )

    if gate.get("decision") == "CLARIFY":
        clarif = create_clarification_thread(
            twin_id=twin_id,
            tenant_id=None,
            question=gate.get("question", ""),
            options=gate.get("options", []),
            memory_write_proposal=gate.get("memory_write_proposal", {}),
            original_query=request.message,
            conversation_id=None,
            mode="public",
            requested_by="public",
            created_by=None
        )
        return {
            "status": "queued",
            "message": "Queued for owner confirmation.",
            "clarification_id": clarif.get("id") if clarif else None,
            "question": gate.get("question"),
            "options": gate.get("options", [])
        }

    owner_memory_context = gate.get("owner_memory_context", "")
    owner_memory_refs = gate.get("owner_memory_refs", [])
    owner_memory_candidates = gate.get("owner_memory") or []
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]

    try:
        final_response = ""
        citations = []
        async for event in run_agent_stream(
            twin_id,
            request.message,
            history,
            group_id=group_id,
            conversation_id=conversation_id,
            owner_memory_context=owner_memory_context
        ):
            if "tools" in event:
                citations = event["tools"].get("citations", citations)
            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                if isinstance(msg, AIMessage) and msg.content:
                    final_response = msg.content
        
        # If actions were triggered, append acknowledgment
        if triggered_actions:
            acknowledgments = []
            for action in triggered_actions:
                if action == 'escalate' or action == 'notify_owner':
                    acknowledgments.append("I've notified the owner about your request.")
                elif action == 'draft_email':
                    acknowledgments.append("I'm drafting an email for the owner to review.")
                elif action == 'draft_calendar_event':
                    acknowledgments.append("I'm preparing a calendar event for the owner to review.")
            
            if acknowledgments:
                final_response += "\n\n" + " ".join(acknowledgments)
        
        citations = _normalize_json(citations)
        owner_memory_refs = _normalize_json(owner_memory_refs)
        owner_memory_topics = _normalize_json(owner_memory_topics)

        return {
            "status": "answer",
            "response": final_response,
            "citations": citations,
            "owner_memory_refs": owner_memory_refs,
            "owner_memory_topics": owner_memory_topics,
            "used_owner_memory": bool(owner_memory_refs)
        }
    except Exception as e:
        print(f"Error in public chat: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process message")
