"""
Governance Router - Mixed Tenant + Twin Scoped Endpoints

TENANT-SCOPED (control plane):
- GET /governance/policies: List policies for tenant
- POST /governance/policies: Create policy (tenant-wide)
- GET /governance/audit-logs: List audit logs (optional ?twin_id= filter)

TWIN-SCOPED (verification & data management):
- POST /twins/{twin_id}/governance/verify: Request verification
- DELETE /twins/{twin_id}/sources/{source_id}/deep-scrub: Permanently purge source
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from modules.auth_guard import require_tenant, require_twin_access, require_admin
from modules.schemas import (
    AuditLogSchema, GovernancePolicySchema, TwinVerificationRequest,
    GovernancePolicyCreateRequest, DeepScrubRequest
)
from modules.governance import (
    get_audit_logs, request_verification, get_governance_policies,
    create_governance_policy, deep_scrub_source, AuditLogger
)
from modules.observability import supabase

router = APIRouter(tags=["governance"])


# ============================================================================
# TENANT-SCOPED ENDPOINTS (Control Plane)
# ============================================================================

@router.get("/governance/audit-logs", response_model=List[AuditLogSchema])
async def list_audit_logs(
    twin_id: Optional[str] = Query(None, description="Optional: filter by twin (must belong to tenant)"),
    event_type: Optional[str] = Query(None),
    user=Depends(require_tenant)
):
    """
    List audit logs for the tenant.
    TENANT-SCOPED: Returns logs for all twins in tenant.
    """
    tenant_id = user["tenant_id"]
    
    # If twin_id provided, validate it belongs to tenant
    if twin_id:
        require_twin_access(twin_id, user)
        
    return get_audit_logs(tenant_id=tenant_id, twin_id=twin_id, event_type=event_type)



@router.get("/governance/policies", response_model=List[GovernancePolicySchema])
async def list_policies(user=Depends(require_tenant)):
    """
    List governance policies for the tenant.
    TENANT-SCOPED: Policies are tenant-wide.
    """
    tenant_id = user["tenant_id"]
    
    response = supabase.table("governance_policies").select("*").eq(
        "tenant_id", tenant_id
    ).eq("is_active", True).execute()
    
    return response.data if response.data else []


@router.post("/governance/policies", response_model=GovernancePolicySchema)
async def create_policy(request: GovernancePolicyCreateRequest, user=Depends(require_tenant)):
    """
    Create a governance policy for the tenant.
    TENANT-SCOPED: Policies apply tenant-wide.
    """
    tenant_id = user["tenant_id"]
    user_id = user["user_id"]
    
    response = supabase.table("governance_policies").insert({
        "tenant_id": tenant_id,
        "policy_type": request.policy_type,
        "name": request.name,
        "content": request.content
    }).execute()
    
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create policy")
    
    policy = response.data[0]
    
    AuditLogger.log(
        tenant_id=tenant_id,
        twin_id=None,
        event_type="CONFIGURATION_CHANGE",
        action="POLICY_CREATED",
        actor_id=user_id,
        metadata={"name": request.name, "type": request.policy_type}
    )

    
    return policy


# ============================================================================
# TWIN-SCOPED ENDPOINTS (Verification & Data Management)
# ============================================================================

@router.post("/twins/{twin_id}/governance/verify")
async def request_twin_verification(
    twin_id: str,
    request: TwinVerificationRequest,
    user=Depends(require_tenant)
):
    """
    Request verification for a specific twin.
    TWIN-SCOPED: Validation is per-twin.
    """
    # Validate twin belongs to tenant
    require_twin_access(twin_id, user)
    
    user_id = user["user_id"]
    tenant_id = user["tenant_id"]
    
    status = request_verification(
        twin_id,
        tenant_id=tenant_id,
        method=request.verification_method,
        metadata=request.metadata
    )
    
    # Manual log for verification requested (already handled inside request_verification but redundant log here for detail if needed)
    # Actually request_verification handles it, but we can add more context here.
    AuditLogger.log(
        tenant_id=tenant_id,
        twin_id=twin_id,
        event_type="CONFIGURATION_CHANGE",
        action="VERIFICATION_REQUESTED",
        actor_id=user_id,
        metadata={"method": request.verification_method, "status": status}
    )

    
    return {"status": status, "message": f"Verification request {status}"}


@router.delete("/twins/{twin_id}/sources/{source_id}/deep-scrub")
async def deep_scrub_source_endpoint(
    twin_id: str,
    source_id: str,
    request: DeepScrubRequest = None,
    user=Depends(require_tenant)
):
    """
    Permanently delete a source and all derived vectors.
    TWIN-SCOPED: Source must belong to twin, twin must belong to tenant.
    
    DANGER: This action is IRREVERSIBLE.
    
    Audit logged for compliance.
    """
    # Validate twin belongs to tenant
    require_twin_access(twin_id, user)
    
    user_id = user["user_id"]
    tenant_id = user["tenant_id"]
    
    from modules.auth_guard import verify_source_ownership
    
    # HARDENED: Use common security logic with pairing check enabled
    # This prevents cross-twin and cross-tenant resource pairing attempts
    verify_source_ownership(source_id, user, expected_twin_id=twin_id)
    
    # Fetch minimal metadata for logging
    source_check = supabase.table("sources").select("filename").eq("id", source_id).single().execute()
    filename = source_check.data.get("filename", "unknown") if source_check.data else "unknown"

    
    filename = source_check.data.get("filename", "unknown")
    reason = request.reason if request else None
    
    # Pre-log for audit trail
    AuditLogger.log(
        tenant_id=tenant_id,
        twin_id=twin_id,
        event_type="KNOWLEDGE_UPDATE",
        action="DEEP_SCRUB_INITIATED",
        actor_id=user_id,
        metadata={"source_id": source_id, "filename": filename, "reason": reason}
    )

    
    try:
        await deep_scrub_source(source_id, tenant_id=tenant_id, actor_id=user_id, reason=reason)
        
        # Success log
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=twin_id,
            event_type="KNOWLEDGE_UPDATE",
            action="DEEP_SCRUB_COMPLETED",
            actor_id=user_id,
            metadata={"source_id": source_id, "filename": filename}
        )

        
        return {"status": "success", "message": "Source and all derived vectors permanently purged"}
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Log failure
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=twin_id,
            event_type="KNOWLEDGE_UPDATE",
            action="DEEP_SCRUB_FAILED",
            actor_id=user_id,
            metadata={"source_id": source_id, "error": str(e)}
        )

        raise HTTPException(status_code=500, detail=str(e))
