from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from modules.auth_guard import verify_owner, get_current_user
from modules.schemas import (
    ApiKeyCreateRequest, ApiKeyUpdateRequest, UserInvitationCreateRequest,
    ApiKeySchema, UserInvitationSchema
)
from modules.api_keys import create_api_key, list_api_keys, revoke_api_key, update_api_key
from modules.share_links import get_share_link_info, regenerate_share_token, toggle_public_sharing
from modules.user_management import list_users, invite_user, delete_user
from modules.observability import supabase

router = APIRouter(tags=["auth"])

# API Keys
@router.post("/api-keys")
async def create_api_key_endpoint(request: ApiKeyCreateRequest, user=Depends(verify_owner)):
    """Create a new API key for a twin"""
    try:
        return create_api_key(
            twin_id=request.twin_id,
            group_id=request.group_id,
            name=request.name,
            allowed_domains=request.allowed_domains
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api-keys")
async def list_api_keys_endpoint(twin_id: str, user=Depends(verify_owner)):
    """List all API keys for a twin"""
    return list_api_keys(twin_id)

@router.delete("/api-keys/{key_id}")
async def revoke_api_key_endpoint(key_id: str, user=Depends(verify_owner)):
    """Revoke an API key"""
    success = revoke_api_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "success"}

@router.patch("/api-keys/{key_id}")
async def update_api_key_endpoint(key_id: str, request: ApiKeyUpdateRequest, user=Depends(verify_owner)):
    """Update API key metadata"""
    success = update_api_key(
        key_id=key_id,
        name=request.name,
        allowed_domains=request.allowed_domains
    )
    if not success:
        raise HTTPException(status_code=404, detail="API key not found or no changes")
    return {"status": "success"}

# Sharing
@router.get("/twins/{twin_id}/share-link")
async def get_share_link_endpoint(twin_id: str, user=Depends(verify_owner)):
    """Get share link info for a twin"""
    try:
        return get_share_link_info(twin_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/twins/{twin_id}/share-link")
async def generate_share_link_endpoint(twin_id: str, user=Depends(verify_owner)):
    """Regenerate share token for a twin"""
    try:
        token = regenerate_share_token(twin_id)
        return get_share_link_info(twin_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/twins/{twin_id}/sharing")
async def toggle_sharing_endpoint(twin_id: str, request: dict, user=Depends(verify_owner)):
    """Enable or disable public sharing"""
    enabled = request.get("is_public", False)
    success = toggle_public_sharing(twin_id, enabled)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update sharing settings")
    return {"status": "success", "is_public": enabled}

# Users & Invitations
@router.get("/users")
async def list_users_endpoint(user=Depends(verify_owner)):
    """List all users in the tenant"""
    tenant_id = user.get("tenant_id")
    return list_users(tenant_id)

@router.post("/users/invite")
async def invite_user_endpoint(request: UserInvitationCreateRequest, user=Depends(verify_owner)):
    """Invite a new user to the tenant"""
    tenant_id = user.get("tenant_id")
    invited_by = user.get("user_id")
    try:
        return invite_user(tenant_id, request.email, request.role, invited_by)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/users/{user_id}")
async def delete_user_endpoint(user_id: str, user=Depends(verify_owner)):
    """Delete a user from the tenant"""
    deleted_by = user.get("user_id")
    if user_id == deleted_by:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    success = delete_user(user_id, deleted_by)
    return {"status": "success"}

# Public Validation
@router.get("/public/validate-share/{twin_id}/{token}")
async def validate_share_token_endpoint(twin_id: str, token: str):
    """Validate a public share token and return twin info"""
    from modules.share_links import validate_share_token
    
    if not validate_share_token(token, twin_id):
        raise HTTPException(status_code=404, detail="Invalid or expired share link")
    
    # Get twin name
    try:
        twin_response = supabase.table("twins").select("name").eq("id", twin_id).single().execute()
        twin_name = twin_response.data.get("name", "AI Assistant") if twin_response.data else "AI Assistant"
    except:
        twin_name = "AI Assistant"
    
    return {
        "valid": True,
        "twin_id": twin_id,
        "twin_name": twin_name
    }
