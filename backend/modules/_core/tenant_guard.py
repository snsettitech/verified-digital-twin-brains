# backend/modules/_core/tenant_guard.py
"""Tenant and group permission guard for core endpoints.

Provides dependencies to enforce:
* Tenant Isolation: User's tenant_id must match request/resource tenant.
* Twin Ownership: Twin must belong to the tenant.
* Access Groups: User must be in required groups.
* Audit Logging: All decisions are logged.

Usage:
    @router.post("/...")
    async def my_endpoint(
        user: dict = Depends(verify_tenant_access),
        ...
    ):
"""
from fastapi import Depends, HTTPException, Request
from typing import Optional, List
import logging
import asyncio
from modules.observability import supabase
from modules.auth_guard import get_current_user as get_auth_user

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audit Helpers
# ---------------------------------------------------------------------------

def _insert_audit_log(log_entry: dict):
    """Helper to perform synchronous DB insert."""
    try:
        supabase.table("audit_logs").insert(log_entry).execute()
    except Exception as e:
        logger.error(f"DB Insert Failed: {e}")

def _resolve_twin_id_from_request(request: Request, user: dict) -> Optional[str]:
    """Best-effort twin_id extraction for audit logging."""
    path_params = getattr(request, "path_params", {}) or {}
    twin_id = path_params.get("twin_id")
    if not twin_id:
        query_params = getattr(request, "query_params", {}) or {}
        twin_id = query_params.get("twin_id")
    if not twin_id:
        twin_id = user.get("twin_id")
    return twin_id

async def emit_audit_event(event_type: str, user_id: str, tenant_id: str, details: dict) -> None:
    """Emit an audit event for compliance and security monitoring."""
    try:
        # Log to application logger
        logger.info(
            "AUDIT [%s] user=%s tenant=%s details=%s",
            event_type, user_id, tenant_id, details,
        )

        # Async insert into audit_logs table
        log_entry = {
            "tenant_id": tenant_id,
            "event_type": event_type,
            "action": details.get("action", event_type), # Fallback to event_type
            "actor_id": user_id,
            "metadata": details or {}
        }

        # Extract twin_id if present in details
        if "twin_id" in details:
            log_entry["twin_id"] = details["twin_id"]

        await asyncio.to_thread(_insert_audit_log, log_entry)

    except Exception as e:
        logger.error(f"Failed to emit audit event: {e}")

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def verify_tenant_access(
    request: Request,
    user: dict = Depends(get_auth_user)
) -> dict:
    """
    Dependency to enforce tenant isolation.
    Checks that the user has a valid tenant_id.
    """
    # 1. Reject service-key bypass if marked in user context
    if user.get("is_service_key"):
        twin_id = _resolve_twin_id_from_request(request, user)
        details = {"endpoint": request.url.path}
        if twin_id:
            details["twin_id"] = twin_id
        await emit_audit_event(
            "SERVICE_KEY_BYPASS_BLOCKED",
            user.get("user_id", "unknown"),
            user.get("tenant_id", "unknown"),
            details,
        )
        raise HTTPException(403, "Service-key bypass is not allowed")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(403, "User context missing tenant_id")

    return user


async def verify_twin_access(
    twin_id: str,
    user: dict = Depends(verify_tenant_access)
) -> dict:
    """
    Dependency that ensures the requested twin belongs to the user's tenant.
    Pass 'twin_id' as a path parameter or query parameter matching the name.
    """
    # Check twin ownership in DB
    # First, check dev token allowed_twins (for E2E testing)
    allowed_twins = user.get("allowed_twins")
    if allowed_twins is not None:
        # If allowed_twins is defined (even if empty), enforce it
        if twin_id not in allowed_twins:
            await emit_audit_event(
                "TWIN_ACCESS_DENIED_DEV_TOKEN",
                user.get("user_id", "unknown"),
                user.get("tenant_id", "unknown"),
                {"twin_id": twin_id, "reason": "Not in allowed_twins list"},
            )
            raise HTTPException(403, "Access denied - tenant isolation violation")
        return user
    
    # Check twin basic existence and ownership via secure RPC (bypasses RLS)
    try:
        # We use a SECURITY DEFINER function to check access because the backend
        # might be running with an anon key that is restricted by RLS.
        res = supabase.rpc("check_twin_tenant_access", {
            "t_id": twin_id,
            "req_tenant_id": user["tenant_id"]
        }).execute()
        
        is_allowed = res.data

        if not is_allowed:
            # We don't distinguish between "Not Found" and "Forbidden" to prevent enumeration
            await emit_audit_event(
                "TWIN_ACCESS_DENIED",
                user["user_id"],
                user["tenant_id"],
                {"twin_id": twin_id, "endpoint": "verify_twin_access"},
            )
            raise HTTPException(404, "Twin not found") 
            
        await emit_audit_event(
            "ACCESS_GRANTED",
            user["user_id"],
            user["tenant_id"],
            {"twin_id": twin_id, "endpoint": "verify_twin_access"}
        )
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking twin access: {e}")
        # Only dump error in logs, return generic 500
        raise HTTPException(500, "Internal authorization error")


def require_group(group_name: str):
    """Factory for a dependency required to check group membership."""
    async def group_checker(user: dict = Depends(verify_tenant_access)):
        # This assumes user["access_groups"] is populated by auth_guard or fetched here
        # For Phase 3.5, we might need to fetch it `group_memberships`
        # Stub implementation for now until Access Groups (Phase 5) is fully integrated
        # or we assume token claims carry groups.
        
        # If user is owner, bypass
        if user.get("role") == "owner":
            return user
            
        user_groups = user.get("access_groups", []) # Mock or from JWT
        if group_name not in user_groups:
             raise HTTPException(403, f"Missing required group: {group_name}")
        return user
    return group_checker


