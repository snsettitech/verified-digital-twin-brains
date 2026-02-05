"""
Escalations Router - Hybrid Tenant + Twin Scoped Endpoints

TWIN-SCOPED:
- GET /twins/{twin_id}/escalations: List escalations for specific twin

ADMIN-ONLY (tenant rollup):
- GET /escalations: List ALL escalations across tenant (requires admin role)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from modules.auth_guard import require_tenant, require_admin, require_twin_access
from modules.observability import supabase, create_conversation
from modules.schemas import ConversationSchema
from modules.escalation import resolve_escalation as resolve_db_escalation
from modules.verified_qna import create_verified_qna
from modules.governance import AuditLogger

router = APIRouter(tags=["escalations"])


class ResolutionRequest(BaseModel):
    owner_answer: str


# ============================================================================
# Helper function for fetching user questions
# ============================================================================

def _enrich_escalations_with_questions(escalations: list) -> list:
    """
    For each escalation, fetch the original user question.
    """
    result = []
    for esc in escalations:
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


# ============================================================================
# TWIN-SCOPED ENDPOINTS
# ============================================================================

@router.get("/twins/{twin_id}/escalations")
async def list_twin_escalations(twin_id: str, user=Depends(require_tenant)):
    """
    List escalations for a specific twin.
    TWIN-SCOPED: Only returns escalations for the specified twin.
    """
    # Validate twin belongs to tenant
    require_twin_access(twin_id, user)
    
    # Fetch escalations for this twin only
    response = supabase.table("escalations").select("*, messages(*)").eq(
        "twin_id", twin_id
    ).order("created_at", desc=True).execute()
    
    return _enrich_escalations_with_questions(response.data or [])


# ============================================================================
# ADMIN-ONLY ENDPOINTS (Tenant Rollup)
# ============================================================================

@router.get("/escalations")
async def list_all_escalations(user=Depends(require_admin)):
    """
    List ALL escalations across the tenant.
    ADMIN-ONLY: Requires owner/admin/support role.
    
    This endpoint returns a tenant-wide rollup of all escalations.
    """
    tenant_id = user["tenant_id"]
    
    # Get all twins for this tenant
    twins_res = supabase.table("twins").select("id").eq("tenant_id", tenant_id).execute()
    
    if not twins_res.data:
        return []
    
    twin_ids = [t["id"] for t in twins_res.data]
    
    # Fetch escalations for all tenant twins
    response = supabase.table("escalations").select("*, messages(*)").in_(
        "twin_id", twin_ids
    ).order("created_at", desc=True).execute()
    
    return _enrich_escalations_with_questions(response.data or [])


# ============================================================================
# RESOLUTION ENDPOINT (Twin-Scoped)
# ============================================================================

@router.post("/twins/{twin_id}/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    twin_id: str,
    escalation_id: str,
    request: ResolutionRequest,
    user=Depends(require_tenant)
):
    """
    Resolve an escalation by providing an owner answer.
    TWIN-SCOPED: Validates escalation belongs to twin and twin belongs to tenant.
    """
    # Validate twin belongs to tenant
    require_twin_access(twin_id, user)
    
    user_id = user["user_id"]
    tenant_id = user["tenant_id"]
    
    # Verify escalation belongs to this twin
    esc_check = supabase.table("escalations").select("id, twin_id").eq(
        "id", escalation_id
    ).single().execute()
    
    if not esc_check.data:
        raise HTTPException(status_code=404, detail="Escalation not found")
    
    if esc_check.data.get("twin_id") != twin_id:
        raise HTTPException(status_code=403, detail="Escalation does not belong to this twin")
    
    try:
        # 1. Update escalation status in DB
        escalation = await resolve_db_escalation(escalation_id, request.owner_answer, user_id)
        
        # 2. Create Verified QnA from this resolution
        message_id = escalation["message_id"]
        
        # Fetch the assistant message that caused escalation
        msg_response = supabase.table("messages").select("*").eq("id", message_id).single().execute()
        if msg_response.data:
            conversation_id = msg_response.data["conversation_id"]
            created_at = msg_response.data["created_at"]
            
            # Fetch the user message immediately preceding it
            rows = supabase.table("messages").select("*").eq(
                "conversation_id", conversation_id
            ).eq("role", "user").lt("created_at", created_at).order(
                "created_at", desc=True
            ).limit(1).execute()
            
            if rows.data:
                original_question = rows.data[0]["content"]
                
                # Create Verified QnA
                await create_verified_qna(
                    twin_id=twin_id,
                    question=original_question,
                    answer=request.owner_answer,
                    owner_id=user_id,
                    group_id=None
                )
        
        # Audit log
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=twin_id,
            event_type="CONFIGURATION_CHANGE",
            action="ESCALATION_RESOLVED",
            actor_id=user_id,
            metadata={"escalation_id": escalation_id}
        )

        
        return {
            "status": "success", 
            "message": "Escalation resolved and verified QnA created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LEGACY ENDPOINT (Backward Compatibility - will be deprecated)
# ============================================================================

@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation_legacy(
    escalation_id: str,
    request: ResolutionRequest,
    user=Depends(require_admin)  # Require admin since we don't have twin context
):
    """
    DEPRECATED: Use POST /twins/{twin_id}/escalations/{escalation_id}/resolve instead.
    Legacy endpoint kept for backward compatibility but requires admin.
    """
    user_id = user["user_id"]
    tenant_id = user["tenant_id"]
    
    # Lookup escalation to get twin_id
    esc_check = supabase.table("escalations").select("id, twin_id").eq(
        "id", escalation_id
    ).single().execute()
    
    if not esc_check.data:
        raise HTTPException(status_code=404, detail="Escalation not found")
    
    twin_id = esc_check.data.get("twin_id")
    if not twin_id:
        raise HTTPException(status_code=400, detail="Escalation has no twin association")
    
    # Verify twin belongs to tenant
    require_twin_access(twin_id, user)
    
    try:
        escalation = await resolve_db_escalation(escalation_id, request.owner_answer, user_id)
        
        message_id = escalation["message_id"]
        msg_response = supabase.table("messages").select("*").eq("id", message_id).single().execute()
        if msg_response.data:
            conversation_id = msg_response.data["conversation_id"]
            created_at = msg_response.data["created_at"]
            
            rows = supabase.table("messages").select("*").eq(
                "conversation_id", conversation_id
            ).eq("role", "user").lt("created_at", created_at).order(
                "created_at", desc=True
            ).limit(1).execute()
            
            if rows.data:
                original_question = rows.data[0]["content"]
                await create_verified_qna(
                    twin_id=twin_id,
                    question=original_question,
                    answer=request.owner_answer,
                    owner_id=user_id,
                    group_id=None
                )
        
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=twin_id,
            event_type="CONFIGURATION_CHANGE",
            action="ESCALATION_RESOLVED",
            actor_id=user_id,
            metadata={"escalation_id": escalation_id, "legacy_endpoint": True}
        )

        
        return {
            "status": "success", 
            "message": "Escalation resolved and verified QnA created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
