from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from modules.auth_guard import verify_owner
from modules.observability import supabase, create_conversation
from modules.schemas import ConversationSchema
from modules.escalation import resolve_escalation as resolve_db_escalation
from modules.verified_qna import create_verified_qna

router = APIRouter(tags=["escalations"])

class ResolutionRequest(BaseModel):
    owner_answer: str

@router.get("/escalations")
async def list_escalations(user=Depends(verify_owner)):
    # Fetch escalations with assistant messages
    response = supabase.table("escalations").select("*, messages(*)").order("created_at", desc=True).execute()

    # For each escalation, fetch the user question
    result = []
    for esc in (response.data or []):
        assistant_msg = esc.get("messages")
        if assistant_msg:
            conversation_id = assistant_msg.get("conversation_id")
            assistant_created_at = assistant_msg.get("created_at")
            
            user_question = None
            try:
                # Fetch all user messages in the conversation, ordered by created_at descending
                all_user_msgs = supabase.table("messages").select("*").eq(
                    "conversation_id", conversation_id
                ).eq("role", "user").order("created_at", desc=True).execute()
                
                # Find the user message that comes before the assistant message
                if all_user_msgs.data:
                    from datetime import datetime
                    try:
                        if isinstance(assistant_created_at, str):
                            assistant_created_at_clean = assistant_created_at.replace('Z', '+00:00')
                            assistant_ts = datetime.fromisoformat(assistant_created_at_clean)
                        else:
                            assistant_ts = assistant_created_at
                        
                        for user_msg in all_user_msgs.data:
                            user_created_at = user_msg.get("created_at")
                            if isinstance(user_created_at, str):
                                user_created_at_clean = user_created_at.replace('Z', '+00:00')
                                user_ts = datetime.fromisoformat(user_created_at_clean)
                            else:
                                user_ts = user_created_at
                            
                            if user_ts < assistant_ts:
                                user_question = user_msg.get("content")
                                break
                    except Exception:
                        if all_user_msgs.data:
                            user_question = all_user_msgs.data[0].get("content")
            except Exception:
                user_question = None
            
            esc_dict = {}
            if isinstance(esc, dict):
                esc_dict.update(esc)
            else:
                esc_dict = dict(esc)
            
            if user_question:
                esc_dict["user_question"] = user_question
            else:
                esc_dict["user_question"] = assistant_msg.get("content")
        else:
            esc_dict = dict(esc) if isinstance(esc, dict) else {}
            esc_dict["user_question"] = None
        
        result.append(esc_dict)
    
    return result

@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(escalation_id: str, request: ResolutionRequest, user=Depends(verify_owner)):
    try:
        # 1. Update escalation status in DB
        escalation = await resolve_db_escalation(escalation_id, request.owner_answer, user.get("user_id"))
        
        # 2. Create Verified QnA from this resolution
        # Fetch the original question from the context of the escalation
        message_id = escalation["message_id"]
        
        # Fetch the assistant message that caused escalation
        msg_response = supabase.table("messages").select("*").eq("id", message_id).single().execute()
        if msg_response.data:
            conversation_id = msg_response.data["conversation_id"]
            created_at = msg_response.data["created_at"]
            
            # Fetch the user message immediately preceding it
            rows = supabase.table("messages").select("*").eq("conversation_id", conversation_id).eq("role", "user").lt("created_at", created_at).order("created_at", desc=True).limit(1).execute()
            
            if rows.data:
                original_question = rows.data[0]["content"]
                
                # Fetch twin_id
                conv_response = supabase.table("conversations").select("twin_id").eq("id", conversation_id).single().execute()
                twin_id = conv_response.data["twin_id"]

                # Create Verified QnA
                await create_verified_qna(
                    twin_id=twin_id,
                    question=original_question,
                    answer=request.owner_answer,
                    owner_id=user.get("user_id"),
                    group_id=None # Default to public/no group for now, or could inherit
                )
        
        return {
            "status": "success", 
            "message": "Escalation resolved and verified QnA created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
