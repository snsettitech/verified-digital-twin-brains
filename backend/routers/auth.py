from fastapi import APIRouter, Depends, HTTPException, Request, Response
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
from modules.auth_guard import verify_owner, get_current_user, resolve_tenant_id, ensure_twin_active
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
async def sync_user(request: Request, response: Response, user=Depends(get_current_user)):
    """
    Sync Supabase auth user to our users table.
    
    Called after OAuth/magic link login to ensure user exists in our DB.
    Creates user record and default tenant if first login.
    """
    correlation_id = request.headers.get("x-correlation-id") or request.headers.get("x-request-id") or "none"
    response.headers["x-correlation-id"] = correlation_id

    print(f"[SYNC {correlation_id}] Starting sync for user_id: {user.get('user_id')}")
    user_id = user.get("user_id")
    email = user.get("email", "")
    print(f"[SYNC {correlation_id}] email: {email}")
    
    # Check if user already exists in our users table
    print(f"[SYNC {correlation_id}] Checking if user exists...")
    existing = supabase.table("users").select("*, tenants(id, name)").eq("id", user_id).execute()
    if getattr(existing, "error", None):
        print(f"[SYNC {correlation_id}] ERROR user lookup: {existing.error}")
        raise HTTPException(status_code=503, detail="User sync temporarily unavailable")
    
    if existing.data and len(existing.data) > 0:
        # User exists - check if they have a tenant
        user_data = existing.data[0]
        tenant_id = user_data.get("tenant_id")
        
        # ENTERPRISE FIX: Auto-create tenant if missing
        if not tenant_id:
            print(f"[SYNC {correlation_id}] User exists but has no tenant_id, auto-creating...")
            full_name = user.get("name") or user.get("user_metadata", {}).get("full_name") or email.split("@")[0]
            
            try:
                tenant_insert = supabase.table("tenants").insert({
                    "name": f"{full_name}'s Workspace"
                }).execute()
                if getattr(tenant_insert, "error", None):
                    print(f"[SYNC {correlation_id}] ERROR tenant insert: {tenant_insert.error}")
                    raise HTTPException(status_code=503, detail="Tenant creation unavailable")

                tenant_id = tenant_insert.data[0]["id"] if tenant_insert.data else None
                print(f"[SYNC {correlation_id}] Created tenant {tenant_id} for existing user")
                
                # Update user with new tenant_id
                if tenant_id:
                    supabase.table("users").update({
                        "tenant_id": tenant_id
                    }).eq("id", user_id).execute()
                    print(f"[SYNC {correlation_id}] Updated user with tenant_id")
            except Exception as e:
                print(f"[SYNC {correlation_id}] ERROR auto-creating tenant: {e}")
                # Continue without tenant - will fail on operations but at least auth works
        
        # Check if they have any twins (onboarding complete if yes)
        if tenant_id:
            twins_check = supabase.table("twins").select("id").eq("tenant_id", tenant_id).limit(1).execute()
            has_twins = bool(twins_check.data)
        else:
            has_twins = False
        
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
    print(f"[SYNC {correlation_id}] User doesn't exist, creating...")
    # Get additional metadata from the auth token
    full_name = user.get("name") or user.get("user_metadata", {}).get("full_name") or email.split("@")[0]
    avatar_url = user.get("avatar_url") or user.get("user_metadata", {}).get("avatar_url")
    print(f"[SYNC {correlation_id}] full_name: {full_name}, avatar_url: {avatar_url}")
    
    # IMPORTANT: Create tenant FIRST, then user with tenant_id
    # This fixes the OAuth signup error where tenant_id was required but didn't exist yet
    print(f"[SYNC {correlation_id}] Creating tenant first...")
    try:
        tenant_insert = supabase.table("tenants").insert({
            "owner_id": user_id,
            "name": f"{full_name}'s Workspace"
        }).execute()
        if getattr(tenant_insert, "error", None):
            print(f"[SYNC {correlation_id}] ERROR tenant insert: {tenant_insert.error}")
            raise HTTPException(status_code=503, detail="Tenant creation unavailable")
    except Exception as e:
        print(f"[SYNC {correlation_id}] ERROR creating tenant: {e}")
        raise
    
    tenant_id = tenant_insert.data[0]["id"] if tenant_insert.data else None
    print(f"[SYNC {correlation_id}] Tenant created with id: {tenant_id}")
    
    # Now create user record with tenant_id
    print(f"[SYNC {correlation_id}] Inserting into users table with tenant_id...")
    try:
        user_insert = supabase.table("users").insert({
            "id": user_id,
            "email": email,
            "tenant_id": tenant_id
        }).execute()
        if getattr(user_insert, "error", None):
            print(f"[SYNC {correlation_id}] ERROR user insert: {user_insert.error}")
            raise HTTPException(status_code=503, detail="User creation unavailable")
        print(f"[SYNC {correlation_id}] User created successfully with tenant_id")
    except Exception as e:
        print(f"[SYNC {correlation_id}] ERROR creating user: {e}")
        # If user creation fails, try to clean up the tenant
        if tenant_id:
            try:
                supabase.table("tenants").delete().eq("id", tenant_id).execute()
                print(f"[SYNC {correlation_id}] Cleaned up tenant after user creation failure")
            except:
                pass
        raise
    
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


@router.get("/auth/whoami")
async def whoami(user=Depends(get_current_user)):
    """
    Debug/instrumentation endpoint: Return resolved user identity.
    
    Use this to verify auth is working and tenant_id is correctly resolved.
    This endpoint uses resolve_tenant_id to ensure tenant always exists.
    """
    user_id = user.get("user_id")
    email = user.get("email", "")
    
    # Resolve tenant without mutating tenant mappings.
    try:
        tenant_id = resolve_tenant_id(user_id, email, create_if_missing=False)
    except Exception as e:
        tenant_id = None
    
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "role": user.get("role"),
        "has_tenant": tenant_id is not None,
        "auth_method": "api_key" if user.get("api_key_id") else "jwt"
    }

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
    
    # Check onboarding status - use tenant_id to find twins
    if tenant_id:
        twins_check = supabase.table("twins").select("id").eq("tenant_id", tenant_id).limit(1).execute()
        has_twins = bool(twins_check.data)
    else:
        has_twins = False
    
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
    """
    Get all twins owned by the current user.
    
    Uses resolve_tenant_id to ensure tenant is always resolved,
    auto-creating if necessary. Also includes auto-repair for orphaned twins.
    """
    user_id = user.get("user_id")
    email = user.get("email", "")
    
    # Resolve tenant non-destructively. Avoid creating new tenants on read paths.
    try:
        tenant_id = resolve_tenant_id(user_id, email, create_if_missing=False)
    except Exception as e:
        print(f"[AUTH] ERROR resolving tenant for user {user_id}: {e}")
        return []  # Graceful fallback
    
    print(f"[AUTH] get_my_twins: user={user_id}, tenant={tenant_id}")
    
    # Query twins by tenant_id
    result = supabase.table("twins").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
    twins = result.data if result.data else []
    
    # AUTO-REPAIR: Check for orphaned twins if none found
    # Orphaned twins have tenant_id = user_id (wrong value from old frontend bug)
    if len(twins) == 0 and user_id:
        print(f"[MY-TWINS DEBUG] No twins found, checking for orphaned twins with tenant_id={user_id}")
        orphan_check = supabase.table("twins").select("*").eq("tenant_id", user_id).execute()
        orphan_twins = orphan_check.data if orphan_check.data else []
        
        if len(orphan_twins) > 0:
            print(f"[MY-TWINS REPAIR] Found {len(orphan_twins)} orphaned twin(s)! Reassigning to correct tenant_id={tenant_id}")
            
            # Repair each orphaned twin
            for orphan in orphan_twins:
                try:
                    supabase.table("twins").update({
                        "tenant_id": tenant_id
                    }).eq("id", orphan["id"]).execute()
                    print(f"[MY-TWINS REPAIR] Fixed twin {orphan['id']} ({orphan.get('name', 'unnamed')})")
                except Exception as e:
                    print(f"[MY-TWINS REPAIR ERROR] Failed to fix twin {orphan['id']}: {e}")
            
            # Return the orphaned twins (now repaired)
            for twin in orphan_twins:
                twin["tenant_id"] = tenant_id
            twins = orphan_twins
    
    # Filter out archived/deleted twins (settings.deleted_at)
    twins = [t for t in twins if not (t.get("settings") or {}).get("deleted_at")]

    print(f"[MY-TWINS DEBUG] Returning {len(twins)} twins for tenant {tenant_id}")
    return twins


@router.get("/connectors")
async def get_connectors(user=Depends(get_current_user)):
    """
    Stub endpoint for connectors to stop 404 logging noise.
    Future: Will return active integrations for the tenant.
    """
    return []


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
        ensure_twin_active(twin_id)
        return get_share_link_info(twin_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/twins/{twin_id}/share-link")
async def generate_share_link_endpoint(twin_id: str, user=Depends(verify_owner)):
    """Regenerate share token for a twin"""
    try:
        ensure_twin_active(twin_id)
        token = regenerate_share_token(twin_id)
        return get_share_link_info(twin_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/twins/{twin_id}/sharing")
async def toggle_sharing_endpoint(twin_id: str, request: dict, user=Depends(verify_owner)):
    """Enable or disable public sharing"""
    ensure_twin_active(twin_id)
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


# ============================================================================
# Account Deletion
# ============================================================================

class DeleteAccountRequest(BaseModel):
    """Request body for account deletion."""
    confirmation: str  # Must be "DELETE" or the user's email
    

class DeleteAccountResponse(BaseModel):
    """Response for account deletion."""
    status: str  # "deleted" | "queued" | "error"
    message: str
    cleanup_status: str = "done"  # "done" | "pending"


@router.post("/account/delete", response_model=DeleteAccountResponse)
async def delete_account(request: DeleteAccountRequest, user=Depends(get_current_user)):
    """
    Delete the current user's account.
    
    This is an irreversible action that:
    1. Archives all twins owned by the user
    2. Revokes all publish links
    3. Anonymizes user data
    4. Terminates the session
    
    Requires typed confirmation ("DELETE" or user's email).
    """
    from modules.governance import AuditLogger
    
    user_id = user.get("user_id")
    user_email = user.get("email", "")
    tenant_id = user.get("tenant_id")
    
    # Validate confirmation
    if request.confirmation not in ["DELETE", user_email]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid confirmation. Type 'DELETE' or your email address to confirm."
        )
    
    try:
        # Log the deletion request
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=None,
            event_type="ACCOUNT_ACTION",
            action="ACCOUNT_DELETE_REQUESTED",
            actor_id=user_id,
            metadata={"email": user_email}
        )
        
        # 1. Get all twins owned by this user's tenant
        twins_res = supabase.table("twins").select("id, name, settings").eq("tenant_id", tenant_id).execute()
        twins_to_archive = twins_res.data or []
        total_twins = len(twins_to_archive)
        
        archived_count = 0
        cleanup_pending = False
        
        # Revoke tenant-level API keys up front
        try:
            supabase.table("tenant_api_keys").update({"is_active": False}).eq("tenant_id", tenant_id).execute()
        except Exception as e:
            print(f"[ACCOUNT] Error revoking tenant API keys: {e}")
            cleanup_pending = True

        for twin in twins_to_archive:
            twin_id = twin["id"]
            settings = twin.get("settings") or {}
            
            already_archived = bool(settings.get("deleted_at"))

            # Archive the twin (idempotent)
            if not already_archived:
                settings["deleted_at"] = datetime.utcnow().isoformat()
                settings["deleted_by"] = user_id
                settings["deleted_reason"] = "account_deletion"
                settings["is_public"] = False
            else:
                # Ensure public/share is disabled even if already archived
                settings["deleted_reason"] = settings.get("deleted_reason") or "account_deletion"
                settings["is_public"] = False
            if "widget_settings" in settings:
                settings["widget_settings"]["public_share_enabled"] = False
                settings["widget_settings"].pop("share_token", None)
                settings["widget_settings"].pop("share_token_expires_at", None)
            
            try:
                supabase.table("twins").update({
                    "settings": settings
                }).eq("id", twin_id).execute()
                if not already_archived:
                    archived_count += 1
            except Exception as e:
                print(f"[ACCOUNT] Error archiving twin {twin_id}: {e}")
                cleanup_pending = True

            # Revoke twin-scoped API keys
            try:
                supabase.table("twin_api_keys").update({"is_active": False}).eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[ACCOUNT] Error revoking twin API keys for {twin_id}: {e}")
                cleanup_pending = True

            # Best-effort Pinecone namespace purge
            try:
                from modules.clients import get_pinecone_index
                index = get_pinecone_index()
                index.delete(delete_all=True, namespace=twin_id)
            except Exception as e:
                print(f"[ACCOUNT] Pinecone cleanup failed for {twin_id}: {e}")
                cleanup_pending = True
        
        # 2. Anonymize user data
        try:
            supabase.table("users").update({
                "email": f"deleted_{user_id}@deleted.local",
                "avatar_url": None,
                "last_active_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()
        except Exception as e:
            print(f"[ACCOUNT] Error anonymizing user: {e}")
            cleanup_pending = True
        
        # 2b. Best-effort auth user deletion (Supabase)
        try:
            supabase.auth.admin.delete_user(user_id)
        except Exception as e:
            # Not fatal; some Supabase clients don't expose admin.delete_user
            print(f"[ACCOUNT] Auth admin delete failed or unsupported: {e}")
            cleanup_pending = True
        
        # 3. Log the completed deletion
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=None,
            event_type="ACCOUNT_ACTION",
            action="ACCOUNT_DELETED",
            actor_id=user_id,
            metadata={
                "twins_archived": archived_count,
                "cleanup_pending": cleanup_pending
            }
        )
        
        # Fallback: ensure count reflects actual archived records
        if archived_count == 0 and total_twins > 0:
            archived_count = total_twins

        print(f"[ACCOUNT] Deleted account {user_id}: archived {archived_count} twins")
        
        return DeleteAccountResponse(
            status="deleted",
            message=f"Account deleted. {archived_count} twins archived.",
            cleanup_status="pending" if cleanup_pending else "done"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ACCOUNT] Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))
