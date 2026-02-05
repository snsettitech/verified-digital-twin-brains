"""
Share Links Module

Handles generation and validation of public share tokens for twins.
"""
import uuid
from typing import Optional, Dict, Any
from modules.observability import supabase
from modules.access_groups import get_default_group
from modules.governance import AuditLogger

def _get_tenant_id(twin_id: str) -> Optional[str]:
    """Helper to resolve tenant_id from twin_id."""
    try:
        res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
        return res.data.get("tenant_id") if res.data else None
    except Exception:
        return None



def generate_share_token(twin_id: str) -> str:
    """
    Generate or retrieve existing share token for a twin.
    Returns the share token UUID.
    """
    # Get current twin settings
    twin_response = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
    
    if not twin_response.data:
        raise ValueError(f"Twin {twin_id} not found")
    
    settings = twin_response.data.get("settings", {})
    widget_settings = settings.get("widget_settings", {})
    
    # Check if token already exists
    existing_token = widget_settings.get("share_token")
    if existing_token:
        return existing_token
    
    # Generate new token
    share_token = str(uuid.uuid4())
    
    # Update settings
    if "widget_settings" not in settings:
        settings["widget_settings"] = {}
    
    settings["widget_settings"]["share_token"] = share_token
    settings["widget_settings"]["public_share_enabled"] = True
    
    # Update twin
    supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
    
    return share_token


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
    from datetime import datetime
    
    try:
        # Get twin settings
        twin_response = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        
        if not twin_response.data:
            AuditLogger.log(
                tenant_id=_get_tenant_id(twin_id),
                twin_id=twin_id, 
                event_type="SECURITY", 
                action="SHARE_TOKEN_INVALID", 
                metadata={"reason": "twin_not_found", "token_prefix": token[:8] if token else "none"}
            )
            return False

        settings = twin_response.data.get("settings", {})
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
        
        # Check if sharing is enabled
        # Note: We now store 'is_public' inside settings as well, but 'public_share_enabled' is the legacy/widget key
        if not widget_settings.get("public_share_enabled", False):
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
                if datetime.now(expires_at.tzinfo) > expires_at:
                    AuditLogger.log(
                        tenant_id=_get_tenant_id(twin_id),
                        twin_id=twin_id, 
                        event_type="SECURITY", 
                        action="SHARE_TOKEN_EXPIRED", 
                        metadata={"expired_at": expires_at_str}
                    )
                    return False

            except Exception as parse_err:
                print(f"Error parsing share token expiry: {parse_err}")
        
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
        response = supabase.table("access_groups").select("*").eq("twin_id", twin_id).eq("is_public", True).single().execute()
        
        if response.data:
            return response.data
        else:
            return None
    except Exception as e:
        print(f"Error getting public group for twin: {e}")
        return None


def get_share_link_info(twin_id: str) -> Dict[str, Any]:
    """
    Get share link information for a twin.
    Returns dict with share_token, share_url, and public_share_enabled.
    """
    try:
        twin_response = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        
        if not twin_response.data:
            raise ValueError(f"Twin {twin_id} not found")
        
        settings = twin_response.data.get("settings", {})
        if settings.get("deleted_at"):
            raise ValueError("Twin is archived or deleted")
        widget_settings = settings.get("widget_settings", {})
        
        share_token = widget_settings.get("share_token")
        public_share_enabled = widget_settings.get("public_share_enabled", False)
        
        # Generate share URL if token exists
        share_url = None
        if share_token:
            # Assuming frontend base URL from environment or default
            import os
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            share_url = f"{frontend_url}/share/{twin_id}/{share_token}"
        
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
