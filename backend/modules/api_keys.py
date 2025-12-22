"""
API Key Management Module

Handles creation, validation, and management of API keys for widget authentication.
"""
import secrets
import bcrypt
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from modules.observability import supabase
from modules.governance import AuditLogger
import re


def generate_api_key(twin_id: str) -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns: (full_key, key_hash, key_prefix)
    """
    # Format: twin_<twin_id_prefix>_<random_32_char>
    twin_prefix = twin_id[:8].replace('-', '')
    random_part = secrets.token_urlsafe(32)
    full_key = f"twin_{twin_prefix}_{random_part}"
    
    # Hash the key with bcrypt
    key_hash = bcrypt.hashpw(full_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Store first 8 chars as prefix for display
    key_prefix = full_key[:20] + "..."  # Show prefix + ellipsis
    
    return full_key, key_hash, key_prefix


def create_api_key(
    twin_id: str,
    group_id: Optional[str],
    name: str,
    allowed_domains: Optional[List[str]] = None,
    expires_at: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Create a new API key for a twin.
    Returns dict with 'key' (full key, shown only once) and 'id'
    """
    full_key, key_hash, key_prefix = generate_api_key(twin_id)
    
    key_data = {
        "twin_id": twin_id,
        "group_id": group_id,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "name": name,
        "allowed_domains": allowed_domains or [],
        "is_active": True,
    }
    
    if expires_at:
        key_data["expires_at"] = expires_at.isoformat()
    
    response = supabase.table("twin_api_keys").insert(key_data).execute()
    
    if not response.data:
        raise ValueError("Failed to create API key")
    
    key_record = response.data[0]
    
    # Return the full key only once (caller should display it immediately)
    return {
        "id": key_record["id"],
        "key": full_key,  # Only returned on creation
        "key_prefix": key_prefix,
        "name": name,
        "created_at": key_record.get("created_at"),
        "expires_at": expires_at.isoformat() if expires_at else None
    }
    
    # Phase 9: Log the action
    AuditLogger.log(twin_id, "CONFIGURATION_CHANGE", "API_KEY_CREATED", metadata={"name": name, "key_id": key_record["id"]})
    
    return result


def validate_api_key(key: str) -> Optional[Dict[str, Any]]:
    """
    Validate an API key and return twin/group info if valid.
    Returns None if invalid or expired.
    """
    # Extract twin prefix to narrow down search
    if not key.startswith("twin_"):
        return None
    
    # Get all active keys for this twin prefix (approximate match)
    # We'll need to check all keys since we can't query by hash directly
    # In production, you might want to add an index or use a different approach
    try:
        # Get all active keys
        response = supabase.table("twin_api_keys").select("*").eq("is_active", True).execute()
        
        if not response.data:
            return None
        
        # Check each key hash
        for key_record in response.data:
            stored_hash = key_record["key_hash"]
            if bcrypt.checkpw(key.encode('utf-8'), stored_hash.encode('utf-8')):
                # Key matches, check expiration
                expires_at = key_record.get("expires_at")
                if expires_at:
                    expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.now(expires_dt.tzinfo) > expires_dt:
                        return None  # Expired
                
                # Update last_used_at
                record_api_key_usage(key_record["id"])
                
                return {
                    "id": key_record["id"],
                    "twin_id": key_record["twin_id"],
                    "group_id": key_record.get("group_id"),
                    "allowed_domains": key_record.get("allowed_domains", [])
                }
    except Exception as e:
        print(f"Error validating API key: {e}")
        return None
    
    return None


def validate_domain(domain: str, allowed_domains: List[str]) -> bool:
    """
    Validate if a domain matches the allowed_domains list.
    Supports wildcards: *.example.com matches sub.example.com
    Supports * for all domains (development only)
    """
    if not allowed_domains:
        return True  # No restrictions
    
    # Normalize domain (remove protocol, port, path)
    domain = domain.lower().strip()
    
    # Remove protocol
    if '://' in domain:
        domain = domain.split('://', 1)[1]
    
    # Remove port
    if ':' in domain:
        domain = domain.split(':')[0]
    
    # Remove path
    if '/' in domain:
        domain = domain.split('/', 1)[0]
    
    # Check each allowed domain
    for allowed in allowed_domains:
        allowed = allowed.lower().strip()
        
        # Wildcard for all domains (development only)
        if allowed == "*":
            return True
        
        # Exact match
        if domain == allowed:
            return True
        
        # Wildcard subdomain match: *.example.com
        if allowed.startswith("*."):
            base_domain = allowed[2:]  # Remove "*."
            if domain == base_domain or domain.endswith('.' + base_domain):
                return True
    
    return False


def list_api_keys(twin_id: str) -> List[Dict[str, Any]]:
    """
    List all API keys for a twin (never returns full keys, only prefixes).
    """
    response = supabase.table("twin_api_keys").select("*").eq("twin_id", twin_id).order("created_at", desc=True).execute()
    
    if not response.data:
        return []
    
    # Never return full keys
    keys = []
    for key_record in response.data:
        keys.append({
            "id": key_record["id"],
            "key_prefix": key_record["key_prefix"],
            "name": key_record["name"],
            "twin_id": key_record["twin_id"],
            "group_id": key_record.get("group_id"),
            "allowed_domains": key_record.get("allowed_domains", []),
            "is_active": key_record["is_active"],
            "created_at": key_record.get("created_at"),
            "last_used_at": key_record.get("last_used_at"),
            "expires_at": key_record.get("expires_at")
        })
    
    return keys


def revoke_api_key(key_id: str) -> bool:
    """
    Revoke (deactivate) an API key.
    """
    response = supabase.table("twin_api_keys").update({"is_active": False}).eq("id", key_id).execute()
    
    if response.data:
        twin_id = response.data[0]["twin_id"]
        AuditLogger.log(twin_id, "CONFIGURATION_CHANGE", "API_KEY_REVOKED", metadata={"key_id": key_id})
        
    return bool(response.data)


def update_api_key_allowed_domains(key_id: str, domains: List[str]) -> bool:
    """
    Update the allowed domains for an API key.
    """
    response = supabase.table("twin_api_keys").update({"allowed_domains": domains}).eq("id", key_id).execute()
    return bool(response.data)


def update_api_key(key_id: str, name: Optional[str] = None, allowed_domains: Optional[List[str]] = None, expires_at: Optional[datetime] = None) -> bool:
    """
    Update API key metadata.
    """
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if allowed_domains is not None:
        update_data["allowed_domains"] = allowed_domains
    if expires_at is not None:
        update_data["expires_at"] = expires_at.isoformat()
    
    if not update_data:
        return False
    
    response = supabase.table("twin_api_keys").update(update_data).eq("id", key_id).execute()
    
    if response.data:
        twin_id = response.data[0]["twin_id"]
        AuditLogger.log(twin_id, "CONFIGURATION_CHANGE", "API_KEY_UPDATED", metadata={"key_id": key_id, "updates": list(update_data.keys())})
        
    return bool(response.data)


def record_api_key_usage(key_id: str) -> None:
    """
    Update the last_used_at timestamp for an API key.
    """
    try:
        supabase.table("twin_api_keys").update({"last_used_at": datetime.utcnow().isoformat()}).eq("id", key_id).execute()
    except Exception as e:
        print(f"Error recording API key usage: {e}")
        # Don't fail on usage tracking errors
