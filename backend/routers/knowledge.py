from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from modules.auth_guard import verify_owner, get_current_user
from modules.schemas import (
    KnowledgeProfile, VerifiedQnASchema, VerifiedQnACreateRequest, VerifiedQnAUpdateRequest
)
from modules.observability import get_knowledge_profile, supabase
from modules.verified_qna import (
    list_verified_qna, get_verified_qna, edit_verified_qna
)

router = APIRouter(tags=["knowledge"])

@router.get("/twins/{twin_id}/knowledge-profile", response_model=KnowledgeProfile)
async def knowledge_profile(twin_id: str, user=Depends(get_current_user)):
    try:
        profile = await get_knowledge_profile(twin_id)
        return profile
    except Exception as e:
        print(f"Error fetching knowledge profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/twins/{twin_id}/verified-qna")
async def list_twin_verified_qna(twin_id: str, visibility: Optional[str] = None, user=Depends(get_current_user)):
    """
    List all verified QnA entries for a twin.
    Optional visibility filter: 'private', 'shared', 'public'
    """
    try:
        qna_list = await list_verified_qna(twin_id, visibility, group_id=None)
        # Format with citations and patches for each entry
        result = []
        for qna in qna_list:
            try:
                full_qna = await get_verified_qna(qna["id"])
                if full_qna:
                    result.append(full_qna)
            except Exception as e:
                # Log error but continue processing other entries
                print(f"Error fetching full QnA for {qna.get('id')}: {e}")
                # Still include the basic QnA entry even if fetching full details fails
                result.append(qna)
        return result
    except Exception as e:
        import traceback
        print(f"Error listing verified QnA: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/verified-qna/{qna_id}", response_model=VerifiedQnASchema)
async def get_verified_qna_endpoint(qna_id: str, user=Depends(get_current_user)):
    """Get specific verified QnA with citations and patch history."""
    try:
        qna = await get_verified_qna(qna_id)
        if not qna:
            raise HTTPException(status_code=404, detail="Verified QnA not found")
        return qna
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/verified-qna/{qna_id}")
async def update_verified_qna(qna_id: str, request: VerifiedQnAUpdateRequest, user=Depends(verify_owner)):
    """
    Edit verified answer (creates patch entry for version history).
    Body: { "answer": "...", "reason": "..." }
    """
    try:
        await edit_verified_qna(
            qna_id=qna_id,
            new_answer=request.answer,
            reason=request.reason,
            owner_id=user.get("user_id")
        )
        return {"status": "success", "message": "Verified QnA updated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/verified-qna/{qna_id}")
async def delete_verified_qna(qna_id: str, user=Depends(verify_owner)):
    """
    Soft delete verified QnA (set is_active = false).
    """
    try:
        # Check if QnA exists
        qna_res = supabase.table("verified_qna").select("twin_id, twins(tenant_id)").eq("id", qna_id).single().execute()
        if not qna_res.data:
            raise HTTPException(status_code=404, detail="Verified QnA not found")
        
        # Verify the QnA belongs to a twin in the user's tenant
        twin_tenant_id = qna_res.data.get("twins", {}).get("tenant_id")
        if twin_tenant_id and twin_tenant_id != user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="Verified QnA does not belong to your tenant")
        
        # Soft delete
        supabase.table("verified_qna").update({"is_active": False}).eq("id", qna_id).execute()
        
        return {"status": "success", "message": "Verified QnA deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
