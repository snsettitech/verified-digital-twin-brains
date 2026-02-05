from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from modules.auth_guard import verify_owner, verify_twin_ownership, verify_source_ownership
from modules.schemas import (
    AuditLogSchema, GovernancePolicySchema, TwinVerificationRequest,
    GovernancePolicyCreateRequest, DeepScrubRequest
)
from modules.governance import (
    get_audit_logs, request_verification, get_governance_policies,
    create_governance_policy, deep_scrub_source
)

router = APIRouter(tags=["governance"])

@router.get("/governance/audit-logs", response_model=List[AuditLogSchema])
async def list_audit_logs(twin_id: str, event_type: Optional[str] = None, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return get_audit_logs(twin_id, event_type=event_type)

@router.post("/governance/verify")
async def request_twin_verification(twin_id: str, request: TwinVerificationRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    status = request_verification(twin_id, method=request.verification_method, metadata=request.metadata)
    return {"status": status, "message": f"Verification request {status}"}

@router.get("/governance/policies", response_model=List[GovernancePolicySchema])
async def list_policies(twin_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return get_governance_policies(twin_id)

@router.post("/governance/policies", response_model=GovernancePolicySchema)
async def create_policy(twin_id: str, request: GovernancePolicyCreateRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return create_governance_policy(twin_id, request.policy_type, request.name, request.content)

@router.delete("/sources/{source_id}/deep-scrub")
async def deep_scrub_source_endpoint(source_id: str, request: DeepScrubRequest, user=Depends(verify_owner)):
    verify_source_ownership(source_id, user)
    try:
        await deep_scrub_source(source_id, reason=request.reason)
        return {"status": "success", "message": "Source and all derived vectors permanently purged"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
