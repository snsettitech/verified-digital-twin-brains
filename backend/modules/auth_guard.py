"""
Secure Authentication Module
============================

Provides authentication and authorization guards for API endpoints.

SECURITY FIXES:
- Removed DEV_MODE authentication bypass
- Added strict JWT validation with proper error handling
- Environment-based security hardening
- Comprehensive token validation (signature, expiration, structure)

BACKWARD COMPATIBILITY:
- Maintains existing function signatures for router compatibility
- verify_owner: Validates token and returns user dict
- get_current_user: Extracts and validates user from request
- resolve_tenant_id: Resolves/corrects tenant mapping for a user
- verify_twin_ownership: Checks twin ownership
- verify_source_ownership: Checks source ownership
- verify_conversation_ownership: Checks conversation ownership
- ensure_twin_active: Checks twin is active
"""

import os
import sys
import jwt
import time
from typing import Optional, Dict, Any, Tuple
from functools import wraps
from datetime import datetime, timedelta

# Import json for type hints
import json

# FastAPI imports for dependencies
from fastapi import Header, HTTPException, status, Depends, Request

# Security configuration from environment
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("SUPABASE_JWT_SECRET", ""))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "authenticated")

# Security hardening flags
STRICT_MODE = os.getenv("AUTH_STRICT_MODE", "true").lower() == "true"
MAX_TOKEN_AGE_SECONDS = int(os.getenv("MAX_TOKEN_AGE_SECONDS", "3600"))  # 1 hour default


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass


def validate_jwt_structure(token: str) -> Tuple[bool, str]:
    """
    Validate JWT structure before cryptographic verification.
    
    Args:
        token: JWT token string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not token or not isinstance(token, str):
        return False, "Token is empty or invalid type"
    
    parts = token.split(".")
    if len(parts) != 3:
        return False, f"Invalid JWT structure: expected 3 parts, got {len(parts)}"
    
    # Check header and payload are valid base64
    try:
        import base64
        # Pad with = to make valid base64
        header_b64 = parts[0] + "=" * (4 - len(parts[0]) % 4)
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        
        header_json = base64.urlsafe_b64decode(header_b64)
        payload_json = base64.urlsafe_b64decode(payload_b64)
        
        header = json.loads(header_json)
        
        # Verify algorithm
        alg = header.get("alg")
        if alg != JWT_ALGORITHM:
            return False, f"Invalid algorithm: {alg}, expected {JWT_ALGORITHM}"
        
        # Check for none algorithm (security vulnerability)
        if alg.lower() == "none":
            return False, "'none' algorithm not allowed"
        
        return True, ""
        
    except Exception as e:
        return False, f"Invalid JWT encoding: {str(e)}"


def verify_token_signature(token: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Cryptographically verify JWT signature.
    
    Args:
        token: JWT token string
        
    Returns:
        Tuple of (is_valid, payload_or_error)
    """
    if not JWT_SECRET:
        if STRICT_MODE:
            raise AuthenticationError("JWT_SECRET not configured and strict mode enabled")
        # In non-strict mode without secret, we can't verify
        print("[SECURITY WARNING] JWT_SECRET not configured, token verification disabled")
        return False, {"error": "JWT secret not configured"}
    
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_signature": True,
                "require": ["exp", "iat", "sub"]
            }
        )
        return True, payload
        
    except jwt.ExpiredSignatureError:
        return False, {"error": "Token has expired"}
    except jwt.InvalidAudienceError:
        return False, {"error": "Invalid token audience"}
    except jwt.InvalidIssuedAtError:
        return False, {"error": "Token issued in the future"}
    except jwt.InvalidSignatureError:
        return False, {"error": "Invalid token signature"}
    except jwt.DecodeError as e:
        return False, {"error": f"Token decode failed: {str(e)}"}
    except Exception as e:
        return False, {"error": f"Token verification failed: {str(e)}"}


def verify_token_expiration(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Additional expiration checks beyond JWT library verification.
    
    Args:
        payload: Decoded JWT payload
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    now = datetime.utcnow()
    
    # Check issued at (iat)
    iat = payload.get("iat")
    if iat:
        issued_at = datetime.utcfromtimestamp(iat)
        # Token issued in the future (clock skew or attack)
        if issued_at > now + timedelta(minutes=5):
            return False, "Token issued in the future"
        
        # Token too old (even if not expired)
        max_age = timedelta(seconds=MAX_TOKEN_AGE_SECONDS)
        if now - issued_at > max_age:
            return False, f"Token exceeds maximum age of {MAX_TOKEN_AGE_SECONDS}s"
    
    return True, ""


def authenticate_request(token: str) -> Dict[str, Any]:
    """
    Authenticate a request using JWT token.
    
    All tokens must pass full validation - no bypass mechanisms exist.
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        Dict with user info if authentication succeeds
        
    Raises:
        AuthenticationError: If authentication fails
    """
    # Step 1: Structure validation
    is_valid, error = validate_jwt_structure(token)
    if not is_valid:
        raise AuthenticationError(error)
    
    # Step 2: Signature verification
    is_valid, result = verify_token_signature(token)
    if not is_valid:
        error_msg = result.get("error", "Unknown verification error")
        raise AuthenticationError(error_msg)
    
    payload = result
    
    # Step 3: Additional expiration checks
    is_valid, error = verify_token_expiration(payload)
    if not is_valid:
        raise AuthenticationError(error)
    
    # Step 4: Extract and validate user info
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token missing subject (sub) claim")
    
    # Step 5: Build auth context
    auth_context = {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
        "authenticated_at": payload.get("iat"),
        "expires_at": payload.get("exp"),
        "session_id": payload.get("session_id"),
        "verified": True
    }
    
    return auth_context


# =============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# =============================================================================

def get_token_from_header(authorization: str) -> Optional[str]:
    """
    Extract Bearer token from Authorization header.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Token string or None
    """
    if not authorization:
        return None
    
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    
    return None


def _is_deleted_email(email: str) -> bool:
    normalized = (email or "").lower().strip()
    return normalized.startswith("deleted_") or normalized.endswith("@deleted.local")


def resolve_tenant_id(user_id: str, email: str = None, create_if_missing: bool = True) -> str:
    """
    Resolve tenant_id for a user, recovering stale mappings when possible.

    Behavior:
    - Returns existing users.tenant_id when present.
    - Attempts non-destructive recovery via tenants.owner_id and then by email.
    - Creates a tenant only when create_if_missing=True.
    """
    from modules.observability import supabase as supabase_client

    # 1) Primary lookup from users table. Lookup failures are non-mutating.
    try:
        user_lookup = (
            supabase_client.table("users")
            .select("id, tenant_id")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if user_lookup.data and len(user_lookup.data) > 0:
            tenant_id = user_lookup.data[0].get("tenant_id")
            if tenant_id:
                print(f"[resolve_tenant_id] Found existing tenant {tenant_id} for user {user_id}")
                return tenant_id
    except Exception as e:
        print(f"[resolve_tenant_id] User lookup failed (non-mutating): {e}")
        raise HTTPException(status_code=503, detail="Tenant lookup temporarily unavailable")

    # 2) Recovery by owner_id where schema supports it.
    try:
        owner_tenant = (
            supabase_client.table("tenants")
            .select("id")
            .eq("owner_id", user_id)
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        if owner_tenant.data and len(owner_tenant.data) > 0:
            tenant_id = owner_tenant.data[0]["id"]
            user_data = {"id": user_id, "tenant_id": tenant_id}
            if email:
                user_data["email"] = email
            supabase_client.table("users").upsert(user_data).execute()
            print(f"[resolve_tenant_id] Re-linked user {user_id} to owner tenant {tenant_id}")
            return tenant_id
    except Exception as e:
        print(f"[resolve_tenant_id] Owner-tenant recovery skipped: {e}")

    # 3) Recovery by historical email mapping (prevents tenant drift after auth-id changes).
    normalized_email = (email or "").strip().lower()
    if normalized_email and not _is_deleted_email(normalized_email):
        try:
            email_matches = (
                supabase_client.table("users")
                .select("id, email, tenant_id, last_active_at, created_at")
                .eq("email", normalized_email)
                .execute()
            )
            candidates = []
            for row in email_matches.data or []:
                candidate_tenant_id = row.get("tenant_id")
                candidate_email = row.get("email")
                if not candidate_tenant_id:
                    continue
                if _is_deleted_email(candidate_email):
                    continue
                candidates.append(row)

            if candidates:
                candidates.sort(
                    key=lambda r: ((r.get("last_active_at") or ""), (r.get("created_at") or "")),
                    reverse=True,
                )
                tenant_id = candidates[0]["tenant_id"]
                supabase_client.table("users").upsert(
                    {"id": user_id, "tenant_id": tenant_id, "email": normalized_email}
                ).execute()
                print(
                    "[resolve_tenant_id] Re-linked user "
                    f"{user_id} to tenant {tenant_id} via email {normalized_email}"
                )
                return tenant_id
        except Exception as e:
            print(f"[resolve_tenant_id] Email-tenant recovery skipped: {e}")

    if not create_if_missing:
        raise HTTPException(status_code=404, detail="Tenant not found for user")

    # 4) Auto-create tenant only for write-enabled flows.
    try:
        name = email.split("@")[0] if email else f"User-{user_id[:8]}"
        tenant_insert = supabase_client.table("tenants").insert(
            {"name": f"{name}'s Workspace"}
        ).execute()
        if not tenant_insert.data:
            raise HTTPException(status_code=500, detail="Failed to auto-create tenant")

        tenant_id = tenant_insert.data[0]["id"]
        user_data = {"id": user_id, "tenant_id": tenant_id}
        if email:
            user_data["email"] = email
        supabase_client.table("users").upsert(user_data).execute()
        print(f"[resolve_tenant_id] Created tenant {tenant_id} and linked user {user_id}")
        return tenant_id
    except HTTPException:
        raise
    except Exception as e:
        print(f"[resolve_tenant_id] ERROR creating tenant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve tenant: {str(e)}")


def verify_owner(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Dependency for FastAPI to verify the request owner.
    
    Args:
        authorization: Authorization header
        
    Returns:
        User dict if authentication succeeds
        
    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = get_token_from_header(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        auth_context = authenticate_request(token)
        return auth_context
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


def get_current_user(
    request: Request = None,
    authorization: str = Header(None),
    x_twin_api_key: str = Header(None),
    origin: str = Header(None),
    referer: str = Header(None),
) -> Optional[Dict[str, Any]]:
    """
    Dependency to get current user without requiring authentication.
    
    Args:
        request: Optional request object (kept for backward compatibility)
        authorization: Authorization header
        x_twin_api_key: Optional API key header (legacy compatibility)
        origin: Optional request origin header (legacy compatibility)
        referer: Optional request referer header (legacy compatibility)
        
    Returns:
        User dict or None if not authenticated
    """
    if not authorization:
        return None
    
    token = get_token_from_header(authorization)
    if not token:
        return None
    
    try:
        return authenticate_request(token)
    except AuthenticationError:
        return None


def require_tenant(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Require an authenticated user with a resolvable tenant_id.
    """
    if not user or not user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        try:
            tenant_id = resolve_tenant_id(
                user_id=user.get("user_id"),
                email=user.get("email"),
                create_if_missing=False,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User has no tenant association",
                )
            raise

    user = dict(user)
    user["tenant_id"] = tenant_id
    return user


def require_admin(user: Dict[str, Any] = Depends(require_tenant)) -> Dict[str, Any]:
    """
    Require owner/admin/support role for tenant admin endpoints.
    """
    from modules.observability import supabase

    user_id = user.get("user_id")
    actual_role = "viewer"
    try:
        role_lookup = (
            supabase.table("users")
            .select("role")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if role_lookup.data:
            actual_role = role_lookup.data[0].get("role", "viewer")
    except Exception as e:
        print(f"[require_admin] Role lookup failed: {e}")

    if actual_role not in {"owner", "admin", "support"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )

    user = dict(user)
    user["actual_role"] = actual_role
    return user


def require_twin_access(twin_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the twin belongs to the user's tenant and return minimal twin metadata.
    """
    from modules.observability import supabase

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant association",
        )

    try:
        twin_res = (
            supabase.table("twins")
            .select("id, name, tenant_id, specialization")
            .eq("id", twin_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not twin_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Twin not found or access denied",
            )
        return twin_res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"[require_twin_access] Access validation failed for twin {twin_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Twin not found or access denied",
        )


def verify_twin_ownership(twin_id: str, user: Dict[str, Any]) -> bool:
    """
    Verify that a user owns a specific twin.
    
    Args:
        twin_id: Twin ID to check
        user: User dict from authentication
        
    Returns:
        True if user owns the twin
        
    Raises:
        HTTPException: If user doesn't own the twin
    """
    from modules.observability import supabase
    
    if not user or not user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    user_id = user.get("user_id")
    
    try:
        result = supabase.table("twins").select("user_id").eq("id", twin_id).single().execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Twin {twin_id} not found"
            )
        
        if result.data.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this twin"
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Twin ownership check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify twin ownership"
        )


def verify_source_ownership(source_id: str, user: Dict[str, Any]) -> bool:
    """
    Verify that a user owns a specific source.
    
    Args:
        source_id: Source ID to check
        user: User dict from authentication
        
    Returns:
        True if user owns the source
        
    Raises:
        HTTPException: If user doesn't own the source
    """
    from modules.observability import supabase
    
    if not user or not user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    user_id = user.get("user_id")
    
    try:
        # Get source and its twin
        source_result = supabase.table("sources").select("twin_id").eq("id", source_id).single().execute()
        
        if not source_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found"
            )
        
        twin_id = source_result.data.get("twin_id")
        
        # Check twin ownership
        twin_result = supabase.table("twins").select("user_id").eq("id", twin_id).single().execute()
        
        if not twin_result.data or twin_result.data.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this source"
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Source ownership check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify source ownership"
        )


def verify_conversation_ownership(conversation_id: str, user: Dict[str, Any]) -> bool:
    """
    Verify that a user owns a specific conversation.
    
    Args:
        conversation_id: Conversation ID to check
        user: User dict from authentication
        
    Returns:
        True if user owns the conversation
        
    Raises:
        HTTPException: If user doesn't own the conversation
    """
    from modules.observability import supabase
    
    if not user or not user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    user_id = user.get("user_id")
    
    try:
        # Get conversation
        result = supabase.table("conversations").select("user_id, twin_id").eq("id", conversation_id).single().execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found"
            )
        
        # Check if user owns the conversation directly
        if result.data.get("user_id") == user_id:
            return True
        
        # Or if user owns the twin this conversation belongs to
        twin_id = result.data.get("twin_id")
        if twin_id:
            twin_result = supabase.table("twins").select("user_id").eq("id", twin_id).single().execute()
            if twin_result.data and twin_result.data.get("user_id") == user_id:
                return True
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this conversation"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Conversation ownership check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify conversation ownership"
        )


def ensure_twin_active(twin_id: str) -> bool:
    """
    Verify that a twin exists and is active.
    
    Args:
        twin_id: Twin ID to check
        
    Returns:
        True if twin is active
        
    Raises:
        HTTPException: If twin doesn't exist or is inactive
    """
    from modules.observability import supabase
    
    try:
        result = supabase.table("twins").select("id, status").eq("id", twin_id).single().execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Twin {twin_id} not found"
            )
        
        # Check if twin is active (if status field exists)
        twin_status = result.data.get("status")
        if twin_status and twin_status not in ["active", "live", None]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Twin {twin_id} is not active (status: {twin_status})"
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Twin active check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify twin status"
        )
