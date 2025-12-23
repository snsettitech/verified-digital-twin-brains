from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional
from modules.schemas import (
    ChatRequest, ChatMetadata, ChatWidgetRequest, PublicChatRequest, 
    MessageSchema, ConversationSchema
)
from modules.auth_guard import get_current_user
from modules.access_groups import get_user_group, get_default_group
from modules.observability import (
    supabase, get_conversations, get_messages, 
    log_interaction, create_conversation
)
from modules.agent import run_agent_stream
from langchain_core.messages import HumanMessage, AIMessage
from datetime import datetime
import json
import asyncio

router = APIRouter(tags=["chat"])

@router.post("/chat/{twin_id}")
async def chat(twin_id: str, request: ChatRequest, user=Depends(get_current_user)):
    query = request.query
    conversation_id = request.conversation_id
    group_id = request.group_id
    
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
                    print(f"Warning: Could not fetch conversation group_id: {e}")
            
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
        import traceback
        with open("error.log", "a") as f:
            f.write(f"\n--- Chat Setup Error at {datetime.now()} ---\n")
            f.write(traceback.format_exc())
            f.write(f"User: {user}\n")
        # Don't raise, let stream generator handle it or default to None
        print(f"Chat Setup Failed: {e}")

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
            
            async for chunk in run_agent_stream(
                twin_id=twin_id,
                query=query,
                history=langchain_history,
                group_id=group_id
            ):
                # Capture metadata from tools
                if "tools" in chunk:
                    data = chunk["tools"]
                    citations = data.get("citations", citations)
                    confidence_score = data.get("confidence_score", confidence_score)

                # Capture final response from agent (only if has content, not just tool calls)
                if "agent" in chunk:
                    msgs = chunk["agent"]["messages"]
                    if msgs and isinstance(msgs[-1], AIMessage):
                        msg = msgs[-1]
                        # Only update if there's actual content (not just tool calls)
                        if msg.content and not getattr(msg, 'tool_calls', None):
                            full_response = msg.content
            
            # 3. Send metadata first (so frontend knows context is found)
            metadata = {
                "type": "metadata",
                "citations": citations,
                "confidence_score": confidence_score,
                "conversation_id": conversation_id
            }
            yield json.dumps(metadata) + "\n"
            
            # 4. Send final content
            if full_response:
                yield json.dumps({"type": "content", "content": full_response}) + "\n"
            else:
                yield json.dumps({"type": "content", "content": "I couldn't generate a response."}) + "\n"
            
            # 5. Log conversation
            if full_response:
                # Create conversation if needed
                if not conversation_id:
                    user_id = user.get("user_id") if user else None
                    conv = create_conversation(twin_id, user_id, group_id=group_id)
                    conversation_id = conv["id"]
                
                log_interaction(conversation_id, "user", query)
                log_interaction(conversation_id, "assistant", full_response, citations, confidence_score)
            
            # 6. Trigger Scribe (Fire-and-forget for learning)
            from modules._core.scribe_engine import process_interaction
            if full_response:
                asyncio.create_task(process_interaction(
                    twin_id=twin_id,
                    user_message=query,
                    assistant_message=full_response,
                    history=raw_history
                ))

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "error": str(e)}) + "\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@router.get("/conversations/{twin_id}")
async def list_conversations_endpoint(twin_id: str, user=Depends(get_current_user)):
    return get_conversations(twin_id)

@router.get("/conversations/{conversation_id}/messages")
async def list_messages_endpoint(conversation_id: str, user=Depends(get_current_user)):
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
    query = request.query
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
    
    history = get_messages(conversation_id)
    
    async def widget_stream_generator():
        final_content = ""
        citations = []
        confidence_score = 0.0
        sent_metadata = False

        async for event in run_agent_stream(twin_id, query, history, system_prompt, group_id=group_id):
            if "tools" in event:
                citations = event["tools"].get("citations", citations)
                confidence_score = event["tools"].get("confidence_score", confidence_score)
                
                if not sent_metadata:
                    metadata = ChatMetadata(
                        confidence_score=confidence_score,
                        citations=citations,
                        conversation_id=conversation_id
                    )
                    # Include session_id in the first metadata chunk
                    output = metadata.model_dump()
                    output["session_id"] = session_id
                    yield json.dumps(output) + "\n"
                    sent_metadata = True

            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                if isinstance(msg, AIMessage):
                    final_content += msg.content
                    yield json.dumps({"type": "content", "content": msg.content}) + "\n"

        # Record usage
        record_request(session_id, "session", "requests_per_hour")
        
        # Log interaction
        log_interaction(conversation_id, "assistant", final_content, citations, confidence_score)
        
        yield json.dumps({"type": "done", "escalated": confidence_score < 0.7}) + "\n"

    return StreamingResponse(widget_stream_generator(), media_type="text/event-stream")

@router.post("/public/chat/{twin_id}/{token}")
async def public_chat_endpoint(twin_id: str, token: str, request: PublicChatRequest):
    """Handle public chat via share link"""
    from modules.share_links import validate_share_token, get_public_group_for_twin
    from modules.actions_engine import EventEmitter, TriggerMatcher, ActionDraftManager
    
    # Validate share token
    if not validate_share_token(token, twin_id):
        raise HTTPException(status_code=403, detail="Invalid or expired share link")
    
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
    
    # Build conversation history
    history = []
    if request.conversation_history:
        for msg in request.conversation_history:
            if msg.get("role") == "user":
                history.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                history.append(AIMessage(content=msg.get("content", "")))
    
    try:
        final_response = ""
        async for event in run_agent_stream(twin_id, request.message, history, group_id=group_id):
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
        
        return {"response": final_response}
    except Exception as e:
        print(f"Error in public chat: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process message")
