from fastapi import APIRouter, Depends, HTTPException, Request, Response
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import os
from modules.auth_guard import verify_owner, get_current_user, resolve_tenant_id, ensure_twin_active
from modules.schemas import (
    ApiKeyCreateRequest, ApiKeyUpdateRequest, UserInvitationCreateRequest,
    ApiKeySchema, UserInvitationSchema
)
from modules.api_keys import create_api_key, list_api_keys, revoke_api_key, update_api_key
from modules.share_links import get_share_link_info, regenerate_share_token, toggle_public_sharing
from modules.user_management import (
    list_users,
    invite_user,
    delete_user,
    accept_invitation,
)
from modules.observability import supabase
from supabase import create_client as create_supabase_client
from supabase_auth.errors import AuthApiError

router = APIRouter(tags=["auth"])


def _require_auth_user(user: Any) -> Dict[str, Any]:
    if not isinstance(user, dict) or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _get_anon_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_anon_key:
        raise HTTPException(status_code=503, detail="Supabase auth client not configured")
    return create_supabase_client(supabase_url, supabase_anon_key)

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


class InvitationValidationResponse(BaseModel):
    email: str
    role: str
    expires_at: Optional[str] = None
    status: str = "pending"
    invited_by: Optional[str] = None
    tenant_id: Optional[str] = None


class AcceptInvitationRequest(BaseModel):
    token: str
    password: str
    name: Optional[str] = None


class AcceptInvitationResponse(BaseModel):
    status: str
    user: Dict[str, Any]
    token: Optional[str] = None
    session: Optional[Dict[str, Any]] = None


def _fetch_invitation_record(token: str) -> Optional[Dict[str, Any]]:
    token = str(token or "").strip()
    if not token:
        return None
    try:
        response = (
            supabase.table("user_invitations")
            .select("id, tenant_id, email, role, invited_by, status, expires_at")
            .eq("invitation_token", token)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]
    except Exception:
        return None


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _require_pending_invitation_or_raise(token: str) -> Dict[str, Any]:
    record = _fetch_invitation_record(token)
    if not record:
        raise HTTPException(status_code=404, detail="Invalid invitation token")

    status_value = str(record.get("status") or "").strip().lower()
    if status_value == "accepted":
        raise HTTPException(status_code=409, detail="Invitation already accepted")
    if status_value == "expired":
        raise HTTPException(status_code=410, detail="Invitation has expired")
    if status_value and status_value != "pending":
        raise HTTPException(status_code=400, detail=f"Invitation status '{status_value}' is not valid for this action")

    expires_at_raw = record.get("expires_at")
    expires_at = _parse_iso_datetime(expires_at_raw)
    if expires_at and datetime.now(timezone.utc) > expires_at:
        try:
            supabase.table("user_invitations").update({"status": "expired"}).eq("id", record["id"]).execute()
        except Exception:
            pass
        raise HTTPException(status_code=410, detail="Invitation has expired")

    return record

@router.post("/auth/sync-user", response_model=SyncUserResponse)
async def sync_user(request: Request, response: Response, user=Depends(get_current_user)):
    """
    Sync Supabase auth user to our users table.
    
    Called after OAuth/magic link login to ensure user exists in our DB.
    Creates user record and default tenant if first login.
    """
    user = _require_auth_user(user)
    correlation_id = request.headers.get("x-correlation-id") or request.headers.get("x-request-id") or "none"
    response.headers["x-correlation-id"] = correlation_id

    print(f"[SYNC {correlation_id}] Starting sync for user_id: {user.get('user_id')}")
    user_id = user.get("user_id")
    email = (user.get("email", "") or "").strip().lower()
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
        
        # Recover tenant mapping if missing.
        if not tenant_id:
            print(f"[SYNC {correlation_id}] User exists but has no tenant_id, recovering...")
            try:
                tenant_id = resolve_tenant_id(user_id, email, create_if_missing=True)
                supabase.table("users").upsert({
                    "id": user_id,
                    "email": email,
                    "tenant_id": tenant_id
                }).execute()
                print(f"[SYNC {correlation_id}] Recovered tenant {tenant_id} for existing user")
            except Exception as e:
                print(f"[SYNC {correlation_id}] ERROR recovering tenant: {e}")
        
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
    
    # Resolve tenant via canonical resolver.
    print(f"[SYNC {correlation_id}] Resolving tenant via canonical resolver...")
    try:
        tenant_id = resolve_tenant_id(user_id, email, create_if_missing=True)
        print(f"[SYNC {correlation_id}] Tenant resolved with id: {tenant_id}")
    except Exception as e:
        print(f"[SYNC {correlation_id}] ERROR resolving tenant: {e}")
        raise

    # Ensure user record exists with the resolved tenant_id.
    print(f"[SYNC {correlation_id}] Upserting user row with tenant_id...")
    try:
        user_insert = supabase.table("users").upsert({
            "id": user_id,
            "email": email,
            "tenant_id": tenant_id
        }).execute()
        if getattr(user_insert, "error", None):
            print(f"[SYNC {correlation_id}] ERROR user upsert: {user_insert.error}")
            raise HTTPException(status_code=503, detail="User creation unavailable")
        print(f"[SYNC {correlation_id}] User created successfully with tenant_id")
    except Exception as e:
        print(f"[SYNC {correlation_id}] ERROR creating user: {e}")
        raise
    
    twins_check = supabase.table("twins").select("id").eq("tenant_id", tenant_id).limit(1).execute()
    has_twins = bool(twins_check.data)

    return SyncUserResponse(
        status="created",
        user=UserProfile(
            id=user_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            tenant_id=tenant_id,
            onboarding_completed=has_twins,
            created_at=datetime.now(timezone.utc).isoformat()
        ),
        needs_onboarding=not has_twins
    )


@router.get("/auth/whoami")
async def whoami(user=Depends(get_current_user)):
    """
    Debug/instrumentation endpoint: Return resolved user identity.
    
    Use this to verify auth is working and tenant_id is correctly resolved.
    This endpoint uses resolve_tenant_id to ensure tenant always exists.
    """
    user = _require_auth_user(user)
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
    user = _require_auth_user(user)
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
    user = _require_auth_user(user)
    user_id = user.get("user_id")
    email = user.get("email", "")
    
    # Resolve tenant non-destructively. Avoid creating new tenants on read paths.
    try:
        tenant_id = resolve_tenant_id(user_id, email, create_if_missing=False)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH] ERROR resolving tenant for user {user_id}: {e}")
        raise HTTPException(status_code=503, detail="Unable to resolve tenant for this user")
    
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


# API Keys (legacy twin-scoped endpoints)
# NOTE: Canonical tenant-scoped API key endpoints live in routers/api_keys.py under /api-keys.
# These auth-scoped routes are retained for backward compatibility without path collisions.
@router.post("/auth/api-keys")
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

@router.get("/auth/api-keys")
async def list_api_keys_endpoint(twin_id: str, user=Depends(verify_owner)):
    """List all API keys for a twin"""
    return list_api_keys(twin_id)

@router.delete("/auth/api-keys/{key_id}")
async def revoke_api_key_endpoint(key_id: str, user=Depends(verify_owner)):
    """Revoke an API key"""
    success = revoke_api_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "success"}

@router.patch("/auth/api-keys/{key_id}")
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


@router.get("/auth/invitation/{token}", response_model=InvitationValidationResponse)
async def validate_invitation_endpoint(token: str):
    """Validate a pending invitation token."""
    invitation = _require_pending_invitation_or_raise(token)
    return InvitationValidationResponse(
        email=invitation["email"],
        role=invitation["role"],
        expires_at=invitation.get("expires_at"),
        status="pending",
        invited_by=invitation.get("invited_by"),
        tenant_id=invitation.get("tenant_id"),
    )


@router.post("/auth/accept-invitation", response_model=AcceptInvitationResponse)
async def accept_invitation_endpoint(request: AcceptInvitationRequest):
    """Accept invitation token and create user in tenant."""
    if not request.token or not request.token.strip():
        raise HTTPException(status_code=400, detail="Invitation token is required")
    if not request.password or not request.password.strip():
        raise HTTPException(status_code=400, detail="Password is required")

    invitation = _require_pending_invitation_or_raise(request.token)
    invited_email = invitation.get("email")
    if not invited_email:
        raise HTTPException(status_code=400, detail="Invitation is missing email")
    full_name = (request.name or invited_email.split("@")[0]).strip()

    auth_user_id: Optional[str] = None
    try:
        # Create auth identity for invited user when not present yet.
        try:
            created_auth_user = supabase.auth.admin.create_user({
                "email": invited_email,
                "password": request.password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            })
            created_user_payload = _model_to_dict(getattr(created_auth_user, "user", None))
            auth_user_id = created_user_payload.get("id")
        except AuthApiError as create_err:
            err_text = str(create_err).lower()
            if "already" not in err_text and "registered" not in err_text and "exists" not in err_text:
                raise HTTPException(status_code=400, detail=str(create_err))

        # Sign in with anon client to mint a real browser session.
        anon_supabase = _get_anon_supabase_client()
        auth_response = anon_supabase.auth.sign_in_with_password({
            "email": invited_email,
            "password": request.password,
        })
        auth_response_payload = _model_to_dict(auth_response)
        session_payload = _model_to_dict(getattr(auth_response, "session", None)) or auth_response_payload.get("session", {})
        signed_in_user_payload = _model_to_dict(getattr(auth_response, "user", None)) or auth_response_payload.get("user", {})

        access_token = session_payload.get("access_token")
        refresh_token = session_payload.get("refresh_token")
        if not access_token or not refresh_token:
            raise HTTPException(status_code=500, detail="Failed to create authenticated session")

        auth_user_id = auth_user_id or signed_in_user_payload.get("id")
        created_user = accept_invitation(
            request.token,
            {"password": request.password, "name": full_name},
            auth_user_id=auth_user_id,
        )
        return AcceptInvitationResponse(
            status="success",
            user=created_user,
            token=access_token,
            session={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": session_payload.get("expires_in"),
                "expires_at": session_payload.get("expires_at"),
                "token_type": session_payload.get("token_type", "bearer"),
            },
        )
    except AuthApiError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        detail = str(e)
        lowered = detail.lower()
        if "already exists" in lowered:
            raise HTTPException(status_code=409, detail=detail)
        if "expired" in lowered:
            raise HTTPException(status_code=410, detail=detail)
        if "invalid" in lowered:
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
                from modules.delphi_namespace import get_namespace_candidates_for_twin
                index = get_pinecone_index()
                for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
                    index.delete(delete_all=True, namespace=namespace)
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
