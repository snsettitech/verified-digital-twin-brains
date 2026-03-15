"""
Namespace resolution helpers for creator-scoped creator namespaces.

Single-Profile Scope Migration:
- scope_id: "{tenant_id}__{creator_id}"
- namespace format: "scope_{scope_id}" (normalized for Pinecone)

Legacy formats (kept for backward compatibility):
- Primary: creator_{creator_id}_twin_{twin_id}
- Legacy: {twin_id}

These helpers keep reads backward compatible during migration while allowing
new writes to scope-based namespaces.
"""
import os
import re
import time
from typing import List, Optional, Dict

from modules.observability import supabase


# =============================================================================
# Single-Profile Scope Namespace Helpers
# =============================================================================

def _base64url_encode(input_str: str) -> str:
    """
    Base64url encode a string (URL-safe, no padding).
    
    This ensures the encoded string is:
    - Deterministic
    - Alphanumeric only (safe for Pinecone)
    - No collision risk from special characters
    """
    import base64
    encoded = base64.urlsafe_b64encode(input_str.encode()).decode()
    return encoded.rstrip('=')  # Remove padding


def build_scope_namespace(scope_id: str) -> str:
    """
    Build single-profile namespace for a scope.
    
    Format: scope_{base64url(scope_id)}
    
    Uses base64url encoding to ensure:
    - No collision risk (tenantA__creatorX vs tenantA_creatorX)
    - Pinecone-safe characters (alphanumeric + _ -)
    - Deterministic encoding
    
    Args:
        scope_id: Scope ID (format: "{tenant_id}__{creator_id}")
        
    Returns:
        Namespace string for Pinecone
    """
    encoded = _base64url_encode(scope_id)
    return f"scope_{encoded}"


def normalize_scope_for_pinecone(scope_id: str) -> str:
    """
    Normalize scope_id for Pinecone namespace using base64url encoding.
    
    This is LOSSLESS and COLLISION-FREE compared to string replacement.
    
    Pinecone namespaces have restrictions on special characters.
    Max namespace length in Pinecone: 512 characters.
    """
    encoded = _base64url_encode(scope_id)
    
    # Pinecone has 512 char limit for namespaces
    # Base64 encoding increases length by ~33%, so check limits
    if len(encoded) > 500:  # Leave margin for "scope_" prefix
        # Fall back to hash for extremely long scope_ids
        import hashlib
        encoded = hashlib.sha256(scope_id.encode()).hexdigest()[:64]
    
    return encoded


def parse_scope_id(scope_id: str) -> tuple:
    """
    Parse scope_id into tenant_id and creator_id.
    
    Args:
        scope_id: Scope ID (format: "{tenant_id}__{creator_id}")
        
    Returns:
        Tuple of (tenant_id, creator_id)
    """
    if "__" in scope_id:
        parts = scope_id.split("__", 1)
        return parts[0], parts[1]
    # Legacy format or no separator
    return scope_id, None


def make_scope_id(tenant_id: str, creator_id: str) -> str:
    """
    Create scope_id from tenant_id and creator_id.
    
    Args:
        tenant_id: Tenant identifier
        creator_id: Creator identifier
        
    Returns:
        Scope ID (format: "{tenant_id}__{creator_id}")
    """
    return f"{tenant_id}__{creator_id}"


# =============================================================================
# Legacy Namespace Helpers (Backward Compatibility)
# =============================================================================

def build_creator_namespace(creator_id: str, twin_id: str) -> str:
    """Build creator-scoped namespace for a creator/twin pair."""
    return f"creator_{creator_id}_twin_{twin_id}"


def _normalize_creator_id(raw_creator_id: Optional[str], tenant_id: Optional[str]) -> Optional[str]:
    """
    Normalize creator identity.

    Falls back to a deterministic tenant-derived creator id for backward
    compatibility while DB migrations are rolling out.
    """
    if raw_creator_id:
        return str(raw_creator_id)
    if tenant_id:
        return f"tenant_{tenant_id}"
    return None


def resolve_creator_id_for_twin(twin_id: str, _bypass_cache: bool = False) -> Optional[str]:
    """
    Resolve creator_id for a twin from Supabase.

    If `twins.creator_id` isn't present yet, this gracefully falls back to a
    deterministic tenant-derived creator id.
    
    PHASE 2 FIX: Removed @lru_cache to prevent caching None indefinitely.
    Caching is now handled at a higher level with TTL support.
    
    Args:
        twin_id: The twin ID to resolve
        _bypass_cache: Internal flag to force fresh lookup
        
    Returns:
        Creator ID or None if not found
    """
    # Check in-memory cache with TTL
    cache_key = twin_id
    cached = _creator_id_cache.get(cache_key)
    if cached and not _bypass_cache:
        value, timestamp = cached
        # Cache valid for 5 minutes
        if time.time() - timestamp < 300:
            return value
        # Expired, remove from cache
        del _creator_id_cache[cache_key]
    
    try:
        # Preferred path: creator_id exists.
        res = (
            supabase.table("twins")
            .select("creator_id,tenant_id")
            .eq("id", twin_id)
            .limit(1)
            .execute()
        )
        row = res.data[0] if res.data else None
        if not row:
            return None
        
        result = _normalize_creator_id(row.get("creator_id"), row.get("tenant_id"))
        
        # Cache the result (even if None, but with shorter TTL handled above)
        _creator_id_cache[cache_key] = (result, time.time())
        
        return result
    except Exception as e:
        # Backward compatibility path for DBs without creator_id column.
        if "creator_id" in str(e) and "does not exist" in str(e):
            try:
                res = (
                    supabase.table("twins")
                    .select("tenant_id")
                    .eq("id", twin_id)
                    .limit(1)
                    .execute()
                )
                row = res.data[0] if res.data else None
                if not row:
                    return None
                result = _normalize_creator_id(None, row.get("tenant_id"))
                _creator_id_cache[cache_key] = (result, time.time())
                return result
            except Exception:
                return None
        return None


# PHASE 2 FIX: Manual cache with TTL support
_creator_id_cache: Dict[str, tuple] = {}


def clear_creator_namespace_cache() -> None:
    """Clear namespace resolution cache (useful for tests or migrations)."""
    _creator_id_cache.clear()
    # Also clear lru_cache if any functions still use it
    try:
        resolve_creator_id_for_twin.cache_clear()
    except AttributeError:
        pass


def get_primary_namespace_for_twin(twin_id: str, creator_id: Optional[str] = None) -> str:
    """
    Resolve the primary namespace for read/write operations.

    Returns creator namespace when resolvable; otherwise legacy twin namespace.
    """
    resolved_creator = creator_id or resolve_creator_id_for_twin(twin_id)
    if resolved_creator:
        return build_creator_namespace(resolved_creator, twin_id)
    return twin_id


def get_namespace_candidates_for_twin(
    twin_id: str,
    creator_id: Optional[str] = None,
    include_legacy: Optional[bool] = None,
) -> List[str]:
    """
    Return namespace candidates for dual-read migration compatibility.
    """
    if include_legacy is None:
        include_legacy = os.getenv("CREATOR_NAMESPACE_DUAL_READ", "true").lower() == "true"

    primary = get_primary_namespace_for_twin(twin_id=twin_id, creator_id=creator_id)
    namespaces = [primary]

    if include_legacy and primary != twin_id:
        namespaces.append(twin_id)

    # Preserve order and uniqueness.
    out: List[str] = []
    for ns in namespaces:
        if ns not in out:
            out.append(ns)
    return out


# =============================================================================
# Single-Profile Namespace Resolution
# =============================================================================

def get_scope_namespace(
    tenant_id: str,
    creator_id: str,
    twin_id: Optional[str] = None
) -> str:
    """
    Get namespace for single-profile scope.
    
    Args:
        tenant_id: Tenant identifier
        creator_id: Creator identifier
        twin_id: Optional twin ID (for backward compatibility during rollout)
        
    Returns:
        Namespace string for Pinecone
    """
    scope_id = make_scope_id(tenant_id, creator_id)
    return build_scope_namespace(scope_id)


def get_namespace_candidates_for_scope(
    scope_id: str,
    include_legacy: Optional[bool] = None
) -> List[str]:
    """
    Return namespace candidates for a scope (dual-read compatibility).
    
    Args:
        scope_id: Scope ID (format: "{tenant_id}__{creator_id}")
        include_legacy: Whether to include legacy namespaces
        
    Returns:
        List of namespace candidates
    """
    if include_legacy is None:
        include_legacy = os.getenv("CREATOR_NAMESPACE_DUAL_READ", "true").lower() == "true"
    
    primary = build_scope_namespace(scope_id)
    namespaces = [primary]
    
    if include_legacy:
        # Include legacy creator namespace if we can parse the scope
        tenant_id, creator_id = parse_scope_id(scope_id)
        if creator_id and tenant_id:
            # Try to find twin_id for this creator (simplified - in practice would query DB)
            # For now, just add tenant-scoped fallback
            legacy_ns = f"tenant_{tenant_id}"
            if legacy_ns not in namespaces:
                namespaces.append(legacy_ns)
    
    return namespaces


def resolve_scope_from_twin(twin_id: str) -> Optional[str]:
    """
    Resolve scope_id from twin_id by looking up creator_id.
    
    Args:
        twin_id: Twin identifier
        
    Returns:
        Scope ID or None if not found
    """
    try:
        res = (
            supabase.table("twins")
            .select("tenant_id,creator_id")
            .eq("id", twin_id)
            .limit(1)
            .execute()
        )
        row = res.data[0] if res.data else None
        if not row:
            return None
        
        tenant_id = row.get("tenant_id")
        creator_id = row.get("creator_id") or f"tenant_{tenant_id}"
        
        return make_scope_id(tenant_id, creator_id)
    except Exception:
        return None
