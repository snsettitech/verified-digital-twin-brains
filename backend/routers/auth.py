from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
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

# ============================================================================
# User Registration & Profile
# ============================================================================

class UserProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    tenant_id: Optional[str] = None
    onboarding_completed: bool = False
    created_at: Optional[str] = None

class SyncUserResponse(BaseModel):
    status: str  # 'created' or 'exists'
    user: UserProfile
    needs_onboarding: bool = False

@router.post("/auth/sync-user", response_model=SyncUserResponse)
async def sync_user(user=Depends(get_current_user)):
    """
    Sync Supabase auth user to our users table.
    
    Called after OAuth/magic link login to ensure user exists in our DB.
    Creates user record and default tenant if first login.
    """
    user_id = user.get("user_id")
    email = user.get("email", "")
    
    # Check if user already exists in our users table
    existing = supabase.table("users").select("*, tenants(id, name)").eq("id", user_id).execute()
    
    if existing.data and len(existing.data) > 0:
        # User exists - return profile
        user_data = existing.data[0]
        tenant_id = None
        if user_data.get("tenants"):
            tenant_id = user_data["tenants"].get("id") if isinstance(user_data["tenants"], dict) else None
        
        # Check if they have any twins (onboarding complete if yes)
        twins_check = supabase.table("twins").select("id").eq("owner_id", user_id).limit(1).execute()
        has_twins = bool(twins_check.data)
        
        return SyncUserResponse(
            status="exists",
            user=UserProfile(
                id=user_id,
                email=user_data.get("email", email),
                full_name=user_data.get("full_name"),
                avatar_url=user_data.get("avatar_url"),
                tenant_id=tenant_id,
                onboarding_completed=has_twins,
                created_at=user_data.get("created_at")
            ),
            needs_onboarding=not has_twins
        )
    
    # First login - create user record
    # Get additional metadata from the auth token
    full_name = user.get("name") or user.get("user_metadata", {}).get("full_name") or email.split("@")[0]
    avatar_url = user.get("avatar_url") or user.get("user_metadata", {}).get("avatar_url")
    
    # Create user record
    user_insert = supabase.table("users").insert({
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "avatar_url": avatar_url,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    
    # Create default tenant for this user
    tenant_insert = supabase.table("tenants").insert({
        "owner_id": user_id,
        "name": f"{full_name}'s Workspace"
    }).execute()
    
    tenant_id = tenant_insert.data[0]["id"] if tenant_insert.data else None
    
    return SyncUserResponse(
        status="created",
        user=UserProfile(
            id=user_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            tenant_id=tenant_id,
            onboarding_completed=False,
            created_at=datetime.utcnow().isoformat()
        ),
        needs_onboarding=True
    )

@router.get("/auth/me", response_model=UserProfile)
async def get_current_user_profile(user=Depends(get_current_user)):
    """Get current user's profile including tenant and onboarding status."""
    user_id = user.get("user_id")
    
    # Get user with tenant
    result = supabase.table("users").select("*, tenants(id, name)").eq("id", user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="User profile not found. Please call /auth/sync-user first.")
    
    user_data = result.data[0]
    tenant_id = None
    if user_data.get("tenants"):
        tenant_id = user_data["tenants"].get("id") if isinstance(user_data["tenants"], dict) else None
    
    # Check onboarding status
    twins_check = supabase.table("twins").select("id").eq("owner_id", user_id).limit(1).execute()
    has_twins = bool(twins_check.data)
    
    return UserProfile(
        id=user_id,
        email=user_data.get("email", ""),
        full_name=user_data.get("full_name"),
        avatar_url=user_data.get("avatar_url"),
        tenant_id=tenant_id,
        onboarding_completed=has_twins,
        created_at=user_data.get("created_at")
    )

@router.get("/auth/my-twins")
async def get_my_twins(user=Depends(get_current_user)):
    """Get all twins owned by the current user."""
    user_id = user.get("user_id")
    
    result = supabase.table("twins").select("*").eq("owner_id", user_id).execute()
    
    return {
        "twins": result.data if result.data else [],
        "count": len(result.data) if result.data else 0
    }

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
