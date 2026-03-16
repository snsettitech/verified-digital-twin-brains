"""
Share Links Module

Handles generation and validation of public share tokens for twins.
"""
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from modules.observability import supabase
from modules.governance import AuditLogger

PUBLIC_TWIN_STATUSES = {"active", "persona_built"}


def _missing_column_error(exc: Exception, column_name: str) -> bool:
    message = str(exc).lower()
    return column_name in message and (
        "does not exist" in message
        or "could not find" in message
        or "pgrst204" in message
    )


def _fetch_twin_row(twin_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a twin row with the fields needed for public-share decisions."""
    try:
        response = (
            supabase.table("twins")
            .select("id, tenant_id, status, is_active, settings")
            .eq("id", twin_id)
            .single()
            .execute()
        )
    except Exception as exc:
        if _missing_column_error(exc, "is_active"):
            response = (
                supabase.table("twins")
                .select("id, tenant_id, status, settings")
                .eq("id", twin_id)
                .single()
                .execute()
            )
        else:
            raise
    return response.data or None


def _get_tenant_id(twin_id: str) -> Optional[str]:
    """Helper to resolve tenant_id from twin_id."""
    try:
        row = _fetch_twin_row(twin_id)
        return row.get("tenant_id") if row else None
    except Exception:
        return None


def is_marketplace_public_twin_record(twin: Optional[Dict[str, Any]]) -> bool:
    """Marketplace visibility rule for the current all-public phase."""
    if not twin:
        return False

    settings = twin.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}

    if settings.get("deleted_at"):
        return False

    status_value = str(twin.get("status") or "").lower()
    return bool(twin.get("is_active") is True) or status_value in PUBLIC_TWIN_STATUSES


def is_publicly_accessible_twin_record(twin: Optional[Dict[str, Any]]) -> bool:
    """A twin is publicly accessible if legacy sharing is on or marketplace-public."""
    if not twin:
        return False

    settings = twin.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    widget_settings = settings.get("widget_settings") or {}
    return bool(widget_settings.get("public_share_enabled", False)) or is_marketplace_public_twin_record(twin)


def ensure_share_token(
    twin_id: str,
    *,
    enable_public_share: bool = False,
    twin_row: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Ensure a twin has a share token.

    For marketplace access we can mint a token without flipping the legacy
    public-share toggle. Legacy direct-share flows can still opt into toggling.
    """
    row = twin_row or _fetch_twin_row(twin_id)
    if not row:
        raise ValueError(f"Twin {twin_id} not found")

    settings = dict(row.get("settings") or {})
    widget_settings = dict(settings.get("widget_settings") or {})
    existing_token = widget_settings.get("share_token")

    if existing_token and not enable_public_share:
        return existing_token

    if existing_token and enable_public_share and widget_settings.get("public_share_enabled", False):
        return existing_token

    share_token = existing_token or str(uuid.uuid4())
    widget_settings["share_token"] = share_token
    if enable_public_share:
        widget_settings["public_share_enabled"] = True

    settings["widget_settings"] = widget_settings
    supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
    return share_token


def build_public_share_path(
    twin_id: str,
    settings: Optional[Dict[str, Any]],
    *,
    ensure_token_if_missing: bool = False,
    enable_public_share: bool = False,
) -> Optional[str]:
    """Build the relative public URL for a twin using handle-first resolution."""
    settings = settings if isinstance(settings, dict) else {}

    handle = str(settings.get("handle") or "").strip()
    if handle:
        return f"/share/{handle}"

    widget_settings = settings.get("widget_settings") or {}
    share_token = widget_settings.get("share_token")
    if not share_token and ensure_token_if_missing:
        share_token = ensure_share_token(
            twin_id,
            enable_public_share=enable_public_share,
            twin_row={"id": twin_id, "settings": settings},
        )

    if not share_token:
        return None

    return f"/share/{twin_id}/{share_token}"



def generate_share_token(twin_id: str) -> str:
    """
    Generate or retrieve existing share token for a twin.
    Returns the share token UUID.
    """
    return ensure_share_token(twin_id, enable_public_share=True)


def regenerate_share_token(twin_id: str) -> str:
    """
    Generate a new share token (regenerates even if one exists).
    Returns the new share token UUID.
    """
    # Generate new token
    share_token = str(uuid.uuid4())
    
    # Get current twin settings
    twin_response = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
    
    if not twin_response.data:
        raise ValueError(f"Twin {twin_id} not found")
    
    settings = twin_response.data.get("settings", {})
    
    if "widget_settings" not in settings:
        settings["widget_settings"] = {}
    
    settings["widget_settings"]["share_token"] = share_token
    
    # Update twin
    supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
    
    return share_token


def validate_share_token(token: str, twin_id: str) -> bool:
    """
    Validate that a share token matches the twin and sharing is enabled.
    Includes expiry check and audit logging.
    """
    try:
        twin = _fetch_twin_row(twin_id)

        if not twin:
            AuditLogger.log(
                tenant_id=_get_tenant_id(twin_id),
                twin_id=twin_id, 
                event_type="SECURITY", 
                action="SHARE_TOKEN_INVALID", 
                metadata={"reason": "twin_not_found", "token_prefix": token[:8] if token else "none"}
            )
            return False

        settings = twin.get("settings") or {}
        widget_settings = settings.get("widget_settings", {})
        
        # Block archived/deleted twins
        if settings.get("deleted_at"):
            AuditLogger.log(
                tenant_id=_get_tenant_id(twin_id),
                twin_id=twin_id,
                event_type="SECURITY",
                action="SHARE_TOKEN_INVALID",
                metadata={"reason": "twin_deleted"}
            )
            return False
        
        # V1 public marketplace: allow twins that are marketplace-public even if
        # the legacy direct-share toggle is off.
        if not is_publicly_accessible_twin_record(twin):
            AuditLogger.log(
                tenant_id=_get_tenant_id(twin_id),
                twin_id=twin_id, 
                event_type="SECURITY", 
                action="SHARE_TOKEN_INVALID", 
                metadata={"reason": "sharing_disabled"}
            )
            return False

        
        # Check if token matches
        stored_token = widget_settings.get("share_token")
        if stored_token != token:
            AuditLogger.log(
                tenant_id=_get_tenant_id(twin_id),
                twin_id=twin_id, 
                event_type="SECURITY", 
                action="SHARE_TOKEN_INVALID", 
                metadata={"reason": "token_mismatch", "token_prefix": token[:8] if token else "none"}
            )
            return False

        
        # Check expiry if set
        expires_at_str = widget_settings.get("share_token_expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            except Exception as parse_err:
                print(f"Error parsing share token expiry: {parse_err}")
            else:
                if datetime.now(expires_at.tzinfo) > expires_at:
                    try:
                        AuditLogger.log(
                            tenant_id=_get_tenant_id(twin_id),
                            twin_id=twin_id,
                            event_type="SECURITY",
                            action="SHARE_TOKEN_EXPIRED",
                            metadata={"expired_at": expires_at_str}
                        )
                    except Exception as log_err:
                        print(f"Error logging share token expiry: {log_err}")
                    return False
        
        # Log successful access (at reduced frequency to avoid log spam)
        # AuditLogger.log(twin_id, "ACCESS", "SHARE_LINK_ACCESSED", metadata={})
        
        return True
    except Exception as e:
        print(f"Error validating share token: {e}")
        return False


def get_public_group_for_twin(twin_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the public access group for a twin.
    Returns None if no public group exists.
    """
    try:
        response = (
            supabase.table("access_groups")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("is_public", True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as e:
        print(f"Error getting public group for twin: {e}")
        return None


def get_share_link_info(twin_id: str) -> Dict[str, Any]:
    """
    Get share link information for a twin.
    Returns dict with share_token, share_url, and public_share_enabled.
    """
    try:
        twin = _fetch_twin_row(twin_id)

        if not twin:
            raise ValueError(f"Twin {twin_id} not found")
        
        settings = twin.get("settings", {})
        if settings.get("deleted_at"):
            raise ValueError("Twin is archived or deleted")
        widget_settings = settings.get("widget_settings", {})
        
        share_token = widget_settings.get("share_token")
        public_share_enabled = widget_settings.get("public_share_enabled", False)

        if not share_token and is_publicly_accessible_twin_record(twin):
            share_token = ensure_share_token(
                twin_id,
                enable_public_share=bool(public_share_enabled),
                twin_row=twin,
            )
            widget_settings["share_token"] = share_token

        share_path = build_public_share_path(
            twin_id,
            settings,
            ensure_token_if_missing=is_publicly_accessible_twin_record(twin),
            enable_public_share=bool(public_share_enabled),
        )
        share_url = None
        if share_path:
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
            share_url = f"{frontend_url}{share_path}"
        
        return {
            "twin_id": twin_id,
            "share_token": share_token,
            "share_url": share_url,
            "public_share_enabled": public_share_enabled
        }
    except Exception as e:
        print(f"Error getting share link info: {e}")
        raise


def toggle_public_sharing(twin_id: str, enabled: bool) -> bool:
    """
    Enable or disable public sharing for a twin.
    """
    try:
        twin_response = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        
        if not twin_response.data:
            raise ValueError(f"Twin {twin_id} not found")
        
        settings = twin_response.data.get("settings", {})
        
        if "widget_settings" not in settings:
            settings["widget_settings"] = {}
        
        settings["widget_settings"]["public_share_enabled"] = enabled
        
        # Update twin
        supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
        
        # Phase 9: Log the action
        AuditLogger.log(
            tenant_id=_get_tenant_id(twin_id),
            twin_id=twin_id, 
            event_type="CONFIGURATION_CHANGE", 
            action="SHARING_TOGGLED", 
            metadata={"enabled": enabled}
        )

        
        return True
    except Exception as e:
        print(f"Error toggling public sharing: {e}")
        return False
