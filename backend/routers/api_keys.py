"""
API Keys Router - Tenant-Scoped Endpoints

API keys are TENANT-OWNED resources, NOT twin-owned.
- GET /api-keys: List all keys for tenant
- POST /api-keys: Create key (optional allowed_twin_ids for restriction)
- DELETE /api-keys/{key_id}: Revoke key

Security: All operations filter by tenant_id from JWT.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from modules.auth_guard import require_tenant, require_twin_access
from modules.observability import supabase
from modules.governance import AuditLogger
import secrets
import bcrypt

router = APIRouter(tags=["api-keys"])


# ============================================================================
# Schemas
# ============================================================================

class ApiKeyCreateRequest(BaseModel):
    name: str
    allowed_domains: Optional[List[str]] = None
    allowed_twin_ids: Optional[List[str]] = None  # Optional: restrict to specific twins
    scopes: Optional[List[str]] = None  # Optional: API scopes (read, write, chat)
    expires_days: Optional[int] = None  # Optional: days until expiration


class ApiKeyResponse(BaseModel):
    id: str
    key_prefix: str
    name: str
    allowed_domains: List[str]
    is_active: bool
    created_at: str
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    allowed_twin_ids: Optional[List[str]] = None
    scopes: Optional[List[str]] = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    key: str  # Full key, shown only once on creation


# ============================================================================
# Helper Functions
# ============================================================================

def generate_tenant_api_key(tenant_id: str) -> tuple[str, str, str]:
    """Generate API key for tenant. Returns (full_key, hash, prefix)."""
    tenant_prefix = tenant_id[:8].replace('-', '')
    random_part = secrets.token_urlsafe(32)
    full_key = f"tenant_{tenant_prefix}_{random_part}"
    key_hash = bcrypt.hashpw(full_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    key_prefix = full_key[:24] + "..."
    return full_key, key_hash, key_prefix


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(user=Depends(require_tenant)):
    """
    List all API keys for the tenant.
    TENANT-SCOPED: Filters by tenant_id from JWT.
    """
    tenant_id = user["tenant_id"]
    
    try:
        response = supabase.table("tenant_api_keys").select("*").eq(
            "tenant_id", tenant_id
        ).order("created_at", desc=True).execute()
        
        if not response.data:
            return []
        
        return [
            {
                "id": key["id"],
                "key_prefix": key["key_prefix"],
                "name": key["name"],
                "allowed_domains": key.get("allowed_domains", []),
                "is_active": key["is_active"],
                "created_at": key.get("created_at", ""),
                "last_used_at": key.get("last_used_at"),
                "expires_at": key.get("expires_at"),
                "allowed_twin_ids": key.get("allowed_twin_ids"),
                "scopes": key.get("scopes"),
            }
            for key in response.data
        ]
    except Exception as e:
        print(f"[api-keys] List failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.post("/api-keys", response_model=ApiKeyCreatedResponse)
async def create_api_key(request: ApiKeyCreateRequest, user=Depends(require_tenant)):
    """
    Create a new API key for the tenant.
    TENANT-SCOPED: Key is owned by tenant, not a specific twin.
    
    Optional restrictions:
    - allowed_twin_ids: Restrict key to specific twins (validate they belong to tenant)
    - scopes: Restrict key to specific operations
    - allowed_domains: Restrict key to specific domains (CORS)
    """
    tenant_id = user["tenant_id"]
    user_id = user["user_id"]
    
    # Validate allowed_twin_ids belong to tenant
    if request.allowed_twin_ids:
        for twin_id in request.allowed_twin_ids:
            try:
                require_twin_access(twin_id, user)
            except HTTPException:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Twin {twin_id} not found or doesn't belong to tenant"
                )
    
    # Generate key
    full_key, key_hash, key_prefix = generate_tenant_api_key(tenant_id)
    
    # Calculate expiration
    expires_at = None
    if request.expires_days:
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(days=request.expires_days)).isoformat()
    
    # Insert key
    key_data = {
        "tenant_id": tenant_id,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "name": request.name,
        "allowed_domains": request.allowed_domains or [],
        "allowed_twin_ids": request.allowed_twin_ids,
        "scopes": request.scopes,
        "is_active": True,
        "created_by": user_id,
    }
    
    if expires_at:
        key_data["expires_at"] = expires_at
    
    try:
        response = supabase.table("tenant_api_keys").insert(key_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create API key")
        
        created = response.data[0]
        
        # Audit log
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=None,
            event_type="CONFIGURATION_CHANGE",
            action="TENANT_API_KEY_CREATED",
            actor_id=user_id,
            metadata={"key_id": created["id"], "name": request.name}
        )

        
        return {
            "id": created["id"],
            "key": full_key,  # Only returned once
            "key_prefix": key_prefix,
            "name": request.name,
            "allowed_domains": request.allowed_domains or [],
            "is_active": True,
            "created_at": created.get("created_at", ""),
            "expires_at": expires_at,
            "allowed_twin_ids": request.allowed_twin_ids,
            "scopes": request.scopes,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[api-keys] Create failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user=Depends(require_tenant)):
    """
    Revoke (deactivate) an API key.
    TENANT-SCOPED: Only keys belonging to tenant can be revoked.
    """
    tenant_id = user["tenant_id"]
    user_id = user["user_id"]
    
    try:
        # Verify key belongs to tenant
        key_check = supabase.table("tenant_api_keys").select("id, tenant_id").eq(
            "id", key_id
        ).single().execute()
        
        if not key_check.data:
            raise HTTPException(status_code=404, detail="API key not found")
        
        if key_check.data["tenant_id"] != tenant_id:
            raise HTTPException(status_code=403, detail="API key does not belong to your tenant")
        
        # Deactivate
        supabase.table("tenant_api_keys").update({"is_active": False}).eq(
            "id", key_id
        ).execute()
        
        # Audit log
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=None,
            event_type="CONFIGURATION_CHANGE",
            action="TENANT_API_KEY_REVOKED",
            actor_id=user_id,
            metadata={"key_id": key_id}
        )

        
        return {"status": "success", "message": "API key revoked"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[api-keys] Revoke failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")
