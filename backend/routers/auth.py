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
from modules.profile_selection import (
    build_creator_candidates,
    normalize_twin_status_shape,
    select_profile_twin_from_rows,
)
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


def _normalize_twin_status_shape(twin: Dict[str, Any]) -> Dict[str, Any]:
    """Keep API status field stable for legacy twins schemas without `status`."""
    return normalize_twin_status_shape(twin)


def _select_profile_twin_for_user(
    *,
    user: Dict[str, Any],
    tenant_id: str,
    twins: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Select canonical single profile twin for a user inside tenant.
    """
    user_id = user.get("user_id")
    creator_candidates = build_creator_candidates(
        user=user,
        user_id=str(user_id or ""),
        tenant_id=str(tenant_id or ""),
    )

    rows = twins
    if rows is None:
        query = (
            supabase.table("twins")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
        )
        if hasattr(query, "limit"):
            query = query.limit(50)
        result = query.execute()
        rows = result.data if result.data else []

    return select_profile_twin_from_rows(
        rows=rows or [],
        user_id=str(user_id or ""),
        creator_candidates=creator_candidates,
        allow_single_legacy_fallback=True,
    )


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


def _sync_connected_accounts(user_id: str, correlation_id: str) -> None:
    """
    Upsert connected_accounts from Supabase auth identities (e.g. LinkedIn).
    Best-effort; failures are logged but do not block sync.
    """
    try:
        auth_user = supabase.auth.admin.get_user_by_id(user_id)
        if not auth_user or not hasattr(auth_user, "user"):
            return
        user_obj = _model_to_dict(getattr(auth_user, "user", None))
        identities = user_obj.get("identities") or []
        for ident in identities:
            if not isinstance(ident, dict):
                ident = _model_to_dict(ident) if hasattr(ident, "model_dump") else {}
            provider = (ident.get("provider") or "").strip().lower()
            if provider not in {"linkedin", "linkedin_oidc"}:
                continue
            provider_user_id = ident.get("provider_id") or ident.get("id")
            identity_data = ident.get("identity_data") or {}
            profile_url = identity_data.get("profile_url") or identity_data.get("url")
            if not profile_url and provider_user_id:
                profile_url = f"https://www.linkedin.com/in/{provider_user_id}"
            display_name = identity_data.get("name") or identity_data.get("full_name")
            image_url = identity_data.get("picture") or identity_data.get("avatar_url") or identity_data.get("image_url")
            headline = (
                identity_data.get("headline")
                or identity_data.get("title")
                or identity_data.get("position")
            )
            profile_snapshot = {
                "profile_url": profile_url,
                "display_name": display_name,
                "image_url": image_url,
                "headline": headline,
            }
            supabase.table("connected_accounts").upsert(
                {
                    "user_id": user_id,
                    "provider": "linkedin",
                    "provider_user_id": provider_user_id,
                    "profile_snapshot": profile_snapshot,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="user_id,provider",
            ).execute()
            print(f"[SYNC {correlation_id}] Upserted connected_accounts for LinkedIn")
            break
    except Exception as e:
        print(f"[SYNC {correlation_id}] connected_accounts sync skipped: {e}")


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

    # Validate email before any DB writes — empty or malformed emails break tenant linking
    import re as _re
    if not email or not _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or missing email in auth token. Got: '{email}'"
        )
    
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
        
        # Single-profile mode: onboarding complete only if canonical profile twin exists.
        has_twins = False
        if tenant_id:
            has_twins = _select_profile_twin_for_user(
                user=user,
                tenant_id=tenant_id,
            ) is not None

        _sync_connected_accounts(user_id, correlation_id)

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
    
    has_twins = _select_profile_twin_for_user(
        user=user,
        tenant_id=tenant_id,
    ) is not None

    _sync_connected_accounts(user_id, correlation_id)

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

@router.get("/auth/connected-accounts")
async def get_connected_accounts(user=Depends(get_current_user)):
    """Get current user's OAuth-connected accounts (e.g. LinkedIn)."""
    user = _require_auth_user(user)
    user_id = user.get("user_id")
    try:
        result = supabase.table("connected_accounts").select("*").eq("user_id", user_id).execute()
        return {"accounts": result.data or []}
    except Exception as e:
        print(f"[auth] connected_accounts fetch error: {e}")
        return {"accounts": []}


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
    
    # Single-profile mode: onboarding complete only if canonical profile twin exists.
    has_twins = False
    if tenant_id:
        has_twins = _select_profile_twin_for_user(
            user=user,
            tenant_id=tenant_id,
        ) is not None
    
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
    
    # Resolve tenant, auto-creating if necessary to prevent 403 for new users
    try:
        tenant_id = resolve_tenant_id(user_id, email, create_if_missing=True)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH] ERROR resolving tenant for user {user_id}: {e}")
        raise HTTPException(status_code=503, detail="Unable to resolve tenant for this user")
    
    print(f"[AUTH] get_my_twins: user={user_id}, tenant={tenant_id}")
    
    # Query twins by tenant_id (bounded) and rank for current user first.
    twins_query = (
        supabase.table("twins")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
    )
    # Some query adapters used in tests/legacy integrations do not expose limit().
    if hasattr(twins_query, "limit"):
        twins_query = twins_query.limit(50)
    result = twins_query.execute()
    twins = result.data if result.data else []
    
    # NOTE: orphaned-twin repair is intentionally NOT performed in this read API.
    # Use backend/scripts/check_orphaned_twins.py and explicit migration scripts for repair.
    
    # Single-profile mode: return canonical twin only.
    canonical = _select_profile_twin_for_user(
        user=user,
        tenant_id=tenant_id,
        twins=twins,
    )
    if not canonical:
        print(f"[MY-TWINS DEBUG] Returning 0 twins for tenant {tenant_id}")
        return []

    print(f"[MY-TWINS DEBUG] Returning canonical twin {canonical.get('id')} for tenant {tenant_id}")
    return [canonical]


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
    from modules.public_profile_pack import build_public_profile_pack
    
    if not validate_share_token(token, twin_id):
        raise HTTPException(status_code=404, detail="Invalid or expired share link")
    
    payload = {
        "valid": True,
        "twin_id": twin_id,
        "twin_name": "AI Assistant",
    }

    try:
        try:
            twin_response = (
                supabase.table("twins")
                .select("id, name, settings, status, is_active, created_at, updated_at")
                .eq("id", twin_id)
                .single()
                .execute()
            )
        except Exception:
            twin_response = (
                supabase.table("twins")
                .select("id, name, settings, status, created_at, updated_at")
                .eq("id", twin_id)
                .single()
                .execute()
            )
        if twin_response.data:
            profile_pack = build_public_profile_pack(twin_response.data)
            payload.update(profile_pack)
            payload["twin_name"] = profile_pack.get("name") or twin_response.data.get("name") or "AI Assistant"
    except Exception:
        pass

    return payload


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
    1. Hard-deletes profile/twin data where possible
    2. Purges vector namespaces best-effort
    3. Removes or anonymizes user identity records
    4. Leaves cleanup_status='pending' if any best-effort step fails
    
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

    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Authentication required")

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

        # SECURITY: Only allow deletion of twins this user owns (owner_user_id match)
        # or twins they created. Never delete twins owned by other users in the same tenant.
        all_twins_res = supabase.table("twins").select("id, name, settings, creator_id").eq("tenant_id", tenant_id).execute()
        all_twins = all_twins_res.data or []

        twins_to_delete = []
        for twin in all_twins:
            settings = twin.get("settings") or {}
            owner_uid = str(settings.get("owner_user_id") or "").strip()
            creator = str(twin.get("creator_id") or "").strip()
            # Only include twins that belong to THIS user
            if owner_uid == user_id or creator == user_id or creator == f"tenant_{tenant_id}":
                twins_to_delete.append(twin)

        # If user has no own twins but there are tenant twins owned by others, deny full deletion
        if all_twins and not twins_to_delete:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete tenant data owned by other users. Contact the tenant owner."
            )
        total_twins = len(twins_to_delete)
        
        deleted_count = 0
        archived_fallback_count = 0
        cleanup_pending = False
        
        # Revoke tenant-level API keys up front
        try:
            supabase.table("tenant_api_keys").update({"is_active": False}).eq("tenant_id", tenant_id).execute()
        except Exception as e:
            print(f"[ACCOUNT] Error revoking tenant API keys: {e}")
            cleanup_pending = True

        for twin in twins_to_delete:
            twin_id = twin["id"]
            settings = twin.get("settings") or {}

            # Revoke twin-scoped API keys
            try:
                supabase.table("twin_api_keys").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[ACCOUNT] Error revoking twin API keys for {twin_id}: {e}")
                cleanup_pending = True

            # Best-effort Pinecone namespace purge
            try:
                from modules.clients import get_pinecone_index
                from modules.twin_namespace import get_namespace_candidates_for_twin
                index = get_pinecone_index()
                for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
                    index.delete(delete_all=True, namespace=namespace)
            except Exception as e:
                print(f"[ACCOUNT] Pinecone cleanup failed for {twin_id}: {e}")
                cleanup_pending = True

            # Hard-delete twin row (most tables should cascade via FK).
            deleted = False
            try:
                supabase.table("twins").delete().eq("id", twin_id).execute()
                exists_after_delete = (
                    supabase.table("twins").select("id").eq("id", twin_id).limit(1).execute()
                )
                if not (exists_after_delete.data or []):
                    deleted = True
                    deleted_count += 1
            except Exception as e:
                print(f"[ACCOUNT] Hard delete failed for twin {twin_id}: {e}")

            # Fallback for environments where FK constraints block hard delete:
            # archive the twin so it is inaccessible while cleanup is completed.
            if not deleted:
                cleanup_pending = True
                archived_fallback_count += 1
                try:
                    settings["deleted_at"] = datetime.utcnow().isoformat()
                    settings["deleted_by"] = user_id
                    settings["deleted_reason"] = "account_deletion_pending_cleanup"
                    settings["is_public"] = False
                    widget_settings = settings.get("widget_settings")
                    if isinstance(widget_settings, dict):
                        widget_settings["public_share_enabled"] = False
                        widget_settings.pop("share_token", None)
                        widget_settings.pop("share_token_expires_at", None)
                    supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
                except Exception as archive_err:
                    print(f"[ACCOUNT] Archive fallback failed for twin {twin_id}: {archive_err}")
                    cleanup_pending = True
        
        # 2. Delete auth user first (Supabase auth layer)
        try:
            supabase.auth.admin.delete_user(user_id)
        except Exception as e:
            # Not fatal; some Supabase clients don't expose admin.delete_user
            print(f"[ACCOUNT] Auth admin delete failed or unsupported: {e}")
            cleanup_pending = True

        # 2b. Hard-delete the public.users row — do NOT just anonymize.
        # Anonymizing leaves orphaned ghost records that break re-registration and GDPR compliance.
        try:
            supabase.table("users").delete().eq("id", user_id).execute()
            print(f"[ACCOUNT] Deleted users row for {user_id}")
        except Exception as e:
            print(f"[ACCOUNT] Error deleting user row: {e}")
            # Fallback: anonymize so PII is not retained if hard-delete fails
            try:
                supabase.table("users").update({
                    "email": f"deleted_{user_id}@deleted.local",
                    "avatar_url": None,
                    "full_name": None,
                    "last_active_at": datetime.utcnow().isoformat()
                }).eq("id", user_id).execute()
            except Exception as anon_err:
                print(f"[ACCOUNT] Anonymization fallback also failed: {anon_err}")
            cleanup_pending = True
        
        # 3. Log the completed deletion
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=None,
            event_type="ACCOUNT_ACTION",
            action="ACCOUNT_DELETED",
            actor_id=user_id,
            metadata={
                "twins_deleted": deleted_count,
                "twins_archived_fallback": archived_fallback_count,
                "cleanup_pending": cleanup_pending
            }
        )

        print(
            f"[ACCOUNT] Deleted account {user_id}: deleted={deleted_count}, "
            f"archived_fallback={archived_fallback_count}, total={total_twins}"
        )
        
        return DeleteAccountResponse(
            status="deleted",
            message=(
                f"Account deleted. {deleted_count} profiles deleted."
                + (
                    f" {archived_fallback_count} profile(s) archived pending cleanup."
                    if archived_fallback_count > 0
                    else ""
                )
            ),
            cleanup_status="pending" if cleanup_pending else "done"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ACCOUNT] Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))
