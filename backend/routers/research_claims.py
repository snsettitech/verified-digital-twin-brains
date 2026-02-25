"""
Research Claims Router (Phases 8, 9, 10)

API endpoints for claim enrichment workflow:
- Phase 8: Local claim enrichment
- Phase 9: Web verification enrichment  
- Phase 10: Claim finalization + consistency review

Feature-gated by phase-specific environment variables.
"""

import logging
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.deep_research_config import get_config as get_dr_config
from modules.research_claim_service import (
    ResearchClaimService,
    EnrichmentStatus,
    EnrichmentSummary,
)
from modules.research_claim_extractor import VerificationStatus
from modules.research_claim_web_verification_service import (
    ResearchClaimWebVerificationService,
    WebVerificationRunStatus,
    WebVerificationStatus,
    WebVerificationSummary,
    ClaimWithVerification,
)
from modules.research_claim_web_verifier import WebEvidenceItem
from modules.research_claim_finalization_service import (
    ResearchClaimFinalizationService,
    FinalizationRunStatus,
    FinalClaimStatus,
    FinalizationSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research-claims"])


# =============================================================================
# Feature Flag Check
# =============================================================================

def _check_phase_8_enabled():
    """Check if Phase 8 claims enrichment is enabled."""
    config = get_dr_config()
    
    # Check master switch first
    if not config.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Deep Research feature is not enabled",
                "code": "FEATURE_DISABLED",
                "message": "Set DEEP_RESEARCH_ENABLED=true to enable this feature"
            }
        )
    
    # Check Phase 8 specific flag
    if config.phase_8_claims_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Phase 8 claims enrichment is disabled",
                "code": "PHASE_8_DISABLED",
                "message": "Set DR_PHASE_8_CLAIMS_DISABLED=false to enable"
            }
        )


def _check_phase_9_enabled():
    """Check if Phase 9 web verification is enabled."""
    config = get_dr_config()
    
    # Check master switch first
    if not config.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Deep Research feature is not enabled",
                "code": "FEATURE_DISABLED",
                "message": "Set DEEP_RESEARCH_ENABLED=true to enable this feature"
            }
        )
    
    # Check Phase 9 specific flag
    if config.phase_9_web_verification_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Phase 9 web verification is disabled",
                "code": "PHASE_9_DISABLED",
                "message": "Set DR_PHASE_9_WEB_VERIFICATION_DISABLED=false to enable"
            }
        )
    
    # Phase 8 must also be enabled (dependency)
    if config.phase_8_claims_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Phase 8 claims enrichment is required for Phase 9",
                "code": "PHASE_8_REQUIRED",
                "message": "Enable Phase 8 before using Phase 9"
            }
        )


def _check_phase_10_enabled():
    """Check if Phase 10 claim finalization is enabled."""
    config = get_dr_config()
    
    # Check master switch first
    if not config.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Deep Research feature is not enabled",
                "code": "FEATURE_DISABLED",
                "message": "Set DEEP_RESEARCH_ENABLED=true to enable this feature"
            }
        )
    
    # Check Phase 10 specific flag
    if config.phase_10_claim_finalization_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Phase 10 claim finalization is disabled",
                "code": "PHASE_10_DISABLED",
                "message": "Set DR_PHASE_10_CLAIM_FINALIZATION_DISABLED=false to enable"
            }
        )
    
    # Phase 8 must be enabled (dependency)
    if config.phase_8_claims_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Phase 8 claims enrichment is required for Phase 10",
                "code": "PHASE_8_REQUIRED",
                "message": "Enable Phase 8 before using Phase 10"
            }
        )


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ContinueClaimsResponse(BaseModel):
    """Response from continue-claims endpoint."""
    research_run_id: str
    twin_id: str
    status: str
    total_claims: int
    supported_count: int
    insufficient_count: int
    conflicting_count: int
    needs_review_count: int
    message: str


class ClaimsStatusResponse(BaseModel):
    """Response for enrichment status."""
    research_run_id: str
    twin_id: str
    status: str
    total_claims: int
    supported_count: int
    insufficient_count: int
    conflicting_count: int
    needs_review_count: int
    pending_count: int
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ClaimEvidenceItem(BaseModel):
    """Evidence item for a claim."""
    quote: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    relevance: float


class ClaimResponse(BaseModel):
    """Single claim response."""
    id: str
    claim_text: str
    claim_type: str
    verification_status: str
    confidence: float
    authority: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    evidence_quotes: List[ClaimEvidenceItem]
    created_at: str
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None


class ClaimsListResponse(BaseModel):
    """List of claims response."""
    items: List[ClaimResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ResolveClaimRequest(BaseModel):
    """Request to resolve a claim."""
    status: str = Field(..., description="New status: supported, insufficient_evidence, conflicting, needs_review")
    notes: Optional[str] = Field(default=None, description="Optional review notes")
    
    @field_validator('status')
    def validate_status(cls, v):
        valid = ['supported', 'insufficient_evidence', 'conflicting', 'needs_review']
        if v not in valid:
            raise ValueError(f"Status must be one of: {valid}")
        return v


class ResolveClaimResponse(BaseModel):
    """Response from claim resolution."""
    claim_id: str
    research_run_id: str
    previous_status: str
    new_status: str
    resolved_at: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    code: str
    message: str


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/twins/{twin_id}/research/{research_run_id}/continue-claims",
    response_model=ContinueClaimsResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def continue_claims_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Start or continue claim enrichment for a research run (Phase 8).
    
    Idempotent: 
    - If already completed, returns existing summary
    - If in progress, returns current status
    - If not started, begins enrichment process
    
    Enrichment extracts claims from confirmed sources and verifies them
    against ingested content.
    """
    # Check feature flag
    _check_phase_8_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimService()
        
        # Start enrichment (idempotent)
        summary = await service.start_enrichment(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build message
        if summary.status == EnrichmentStatus.COMPLETED:
            message = f"Claim enrichment completed: {summary.total_claims} claims extracted"
        elif summary.status == EnrichmentStatus.ENRICHING:
            message = "Claim enrichment in progress"
        elif summary.status == EnrichmentStatus.FAILED:
            message = f"Claim enrichment failed: {summary.error_message}"
        else:
            message = "Claim enrichment pending"
        
        return ContinueClaimsResponse(
            research_run_id=research_run_id,
            twin_id=twin_id,
            status=summary.status.value,
            total_claims=summary.total_claims,
            supported_count=summary.supported_count,
            insufficient_count=summary.insufficient_count,
            conflicting_count=summary.conflicting_count,
            needs_review_count=summary.needs_review_count,
            message=message,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Continue claims failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Claim enrichment failed",
                "code": "ENRICHMENT_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/claims-status",
    response_model=ClaimsStatusResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_claims_status_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get claim enrichment status for a research run (Phase 8).
    
    Returns current enrichment progress and claim counts by status.
    """
    # Check feature flag
    _check_phase_8_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimService()
        summary = await service.get_enrichment_status(research_run_id, twin_id)
        
        if not summary:
            # Not started yet
            return ClaimsStatusResponse(
                research_run_id=research_run_id,
                twin_id=twin_id,
                status="not_started",
                total_claims=0,
                supported_count=0,
                insufficient_count=0,
                conflicting_count=0,
                needs_review_count=0,
                pending_count=0,
            )
        
        return ClaimsStatusResponse(
            research_run_id=summary.research_run_id,
            twin_id=twin_id,
            status=summary.status.value,
            total_claims=summary.total_claims,
            supported_count=summary.supported_count,
            insufficient_count=summary.insufficient_count,
            conflicting_count=summary.conflicting_count,
            needs_review_count=summary.needs_review_count,
            pending_count=summary.pending_count,
            error_message=summary.error_message,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get claims status failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get claims status",
                "code": "STATUS_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/claims",
    response_model=ClaimsListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def list_claims_endpoint(
    twin_id: str,
    research_run_id: str,
    verification_status: Optional[str] = None,
    claim_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    List claims for a research run with optional filters (Phase 8).
    
    Filters:
    - verification_status: pending, supported, insufficient_evidence, conflicting, needs_review
    - claim_type: preference, belief, heuristic, value, experience, boundary, uncertain
    """
    # Check feature flag
    _check_phase_8_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    # Validate filters
    status_filter = None
    if verification_status:
        try:
            status_filter = VerificationStatus(verification_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid verification_status",
                    "code": "INVALID_FILTER",
                    "message": f"Must be one of: {[s.value for s in VerificationStatus]}"
                }
            )
    
    try:
        service = ResearchClaimService()
        
        claims = await service.list_claims(
            research_run_id=research_run_id,
            twin_id=twin_id,
            verification_status=status_filter,
            claim_type=claim_type,
            limit=limit,
            offset=offset,
        )
        
        # Convert to response format
        items = []
        for claim in claims:
            items.append(ClaimResponse(
                id=claim.id or "",
                claim_text=claim.claim_text,
                claim_type=claim.claim_type.value,
                verification_status=claim.verification_status.value,
                confidence=claim.confidence,
                authority=claim.authority,
                source_id=claim.source_id,
                source_url=claim.source_url,
                source_title=claim.source_title,
                evidence_quotes=[
                    ClaimEvidenceItem(
                        quote=e.quote,
                        source_id=e.source_id,
                        source_url=e.source_url,
                        relevance=e.relevance,
                    )
                    for e in claim.evidence_quotes
                ],
                created_at=claim.extracted_at.isoformat() if claim.extracted_at else "",
                reviewed_at=None,  # Would need to fetch from DB
                review_notes=None,
            ))
        
        return ClaimsListResponse(
            items=items,
            total=len(items),  # Simplified; in production, do COUNT query
            limit=limit,
            offset=offset,
            has_more=len(items) == limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List claims failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list claims",
                "code": "LIST_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/resolve",
    response_model=ResolveClaimResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
    }
)
async def resolve_claim_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    request: ResolveClaimRequest,
    user: dict = Depends(get_current_user)
):
    """
    Manually resolve a claim's verification status (Phase 8).
    
    Allows users to confirm, reject, or mark claims for review.
    """
    # Check feature flag
    _check_phase_8_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        # Parse and validate status
        try:
            new_status = VerificationStatus(request.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid status",
                    "code": "INVALID_STATUS",
                    "message": f"Must be one of: {[s.value for s in VerificationStatus if s != VerificationStatus.PENDING]}"
                }
            )
        
        service = ResearchClaimService()
        
        # Get current claim status (to return previous_status)
        claims = await service.list_claims(
            research_run_id=research_run_id,
            twin_id=twin_id,
            limit=1,
        )
        
        previous_status = "unknown"
        for claim in claims:
            if claim.id == claim_id:
                previous_status = claim.verification_status.value
                break
        
        # Resolve claim
        success = await service.resolve_claim(
            claim_id=claim_id,
            research_run_id=research_run_id,
            twin_id=twin_id,
            new_status=new_status,
            reviewed_by=user.get("id"),
            review_notes=request.notes,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Claim not found",
                    "code": "NOT_FOUND",
                    "message": f"Claim {claim_id} not found in this research run"
                }
            )
        
        return ResolveClaimResponse(
            claim_id=claim_id,
            research_run_id=research_run_id,
            previous_status=previous_status,
            new_status=new_status.value,
            resolved_at=datetime.utcnow().isoformat(),
            message=f"Claim resolved to {new_status.value}",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve claim failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to resolve claim",
                "code": "RESOLVE_FAILED",
                "message": str(e)
            }
        )


# =============================================================================
# Phase 9: Web Verification Schemas
# =============================================================================

class WebVerificationStatusResponse(BaseModel):
    """Response for web verification status."""
    research_run_id: str
    twin_id: str
    status: str
    total_claims: int
    verified_count: int
    failed_count: int
    skipped_count: int
    by_status: Dict[str, int]
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WebVerificationResponse(BaseModel):
    """Response from continue-web-verification endpoint."""
    research_run_id: str
    twin_id: str
    status: str
    total_claims: int
    verified_count: int
    failed_count: int
    skipped_count: int
    by_status: Dict[str, int]
    message: str


class WebEvidenceResponseItem(BaseModel):
    """Single web evidence item in response."""
    source_url: str
    source_title: str
    source_snippet: str
    extracted_quote: str
    relevance_score: float
    evidence_type: str
    content_quality: str
    domain_tier: Optional[int]


class ClaimWithWebVerificationResponse(BaseModel):
    """Claim with both local and web verification."""
    id: str
    claim_text: str
    claim_type: str
    # Phase 8 local verification
    local_verification_status: str
    local_confidence: float
    # Phase 9 web verification
    web_verification_status: Optional[str] = None
    web_verification_confidence: float = 0.0
    web_verification_notes: Optional[str] = None
    web_verified_at: Optional[str] = None
    web_evidence_count: int = 0
    created_at: str


class ClaimsWithWebVerificationListResponse(BaseModel):
    """List of claims with web verification."""
    items: List[ClaimWithWebVerificationResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class WebEvidenceListResponse(BaseModel):
    """List of web evidence for a claim."""
    claim_id: str
    items: List[WebEvidenceResponseItem]
    total: int


class ResolveWebVerificationRequest(BaseModel):
    """Request to resolve web verification."""
    status: str = Field(..., description="New status: supported, conflicting, insufficient_evidence, needs_review")
    notes: Optional[str] = Field(default=None, description="Optional review notes")
    
    @field_validator('status')
    def validate_status(cls, v):
        valid = ['supported', 'conflicting', 'insufficient_evidence', 'needs_review']
        if v not in valid:
            raise ValueError(f"Status must be one of: {valid}")
        return v


class ResolveWebVerificationResponse(BaseModel):
    """Response from web verification resolution."""
    claim_id: str
    research_run_id: str
    previous_status: str
    new_status: str
    resolved_at: str
    message: str


# =============================================================================
# Phase 9: Web Verification Endpoints
# =============================================================================

@router.post(
    "/twins/{twin_id}/research/{research_run_id}/continue-web-verification",
    response_model=WebVerificationResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def continue_web_verification_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Start or continue web verification for a research run (Phase 9).
    
    Idempotent:
    - If already completed, returns existing summary
    - If in progress, returns current status
    - If not started, begins verification process
    
    Web verification searches public web sources to verify claims
    extracted during Phase 8.
    """
    # Check feature flags
    _check_phase_9_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimWebVerificationService()
        
        # Start verification (idempotent)
        summary = await service.verify_research_run(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build message
        if summary.status == WebVerificationRunStatus.COMPLETED:
            message = f"Web verification completed: {summary.verified_count} claims verified"
        elif summary.status == WebVerificationRunStatus.PARTIAL:
            message = f"Web verification partial: {summary.verified_count} verified, {summary.failed_count} failed"
        elif summary.status == WebVerificationRunStatus.RUNNING:
            message = "Web verification in progress"
        elif summary.status == WebVerificationRunStatus.FAILED:
            message = f"Web verification failed: {summary.error_message}"
        else:
            message = "Web verification pending"
        
        return WebVerificationResponse(
            research_run_id=research_run_id,
            twin_id=twin_id,
            status=summary.status.value,
            total_claims=summary.total_claims,
            verified_count=summary.verified_count,
            failed_count=summary.failed_count,
            skipped_count=summary.skipped_count,
            by_status=summary.by_status,
            message=message,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Continue web verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Web verification failed",
                "code": "VERIFICATION_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/web-verification-status",
    response_model=WebVerificationStatusResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_web_verification_status_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get web verification status for a research run (Phase 9).
    
    Returns current verification progress and claim counts by status.
    """
    # Check feature flags
    _check_phase_9_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimWebVerificationService()
        summary = await service.get_verification_status(research_run_id, twin_id)
        
        if not summary:
            # Not started yet
            return WebVerificationStatusResponse(
                research_run_id=research_run_id,
                twin_id=twin_id,
                status="not_started",
                total_claims=0,
                verified_count=0,
                failed_count=0,
                skipped_count=0,
                by_status={},
            )
        
        return WebVerificationStatusResponse(
            research_run_id=summary.research_run_id,
            twin_id=twin_id,
            status=summary.status.value,
            total_claims=summary.total_claims,
            verified_count=summary.verified_count,
            failed_count=summary.failed_count,
            skipped_count=summary.skipped_count,
            by_status=summary.by_status,
            error_message=summary.error_message,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get web verification status failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get web verification status",
                "code": "STATUS_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/claims-with-web-verification",
    response_model=ClaimsWithWebVerificationListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def list_claims_with_web_verification_endpoint(
    twin_id: str,
    research_run_id: str,
    web_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    List claims with both Phase 8 local and Phase 9 web verification.
    
    Filters:
    - web_status: pending, supported, conflicting, insufficient_evidence, needs_review
    """
    # Check feature flags (Phase 8 required, Phase 9 optional for viewing)
    config = get_dr_config()
    if not config.is_enabled() or config.phase_8_claims_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Claims enrichment is disabled",
                "code": "PHASE_8_DISABLED",
                "message": "Enable Phase 8 to view claims"
            }
        )
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimWebVerificationService()
        
        claims = await service.list_claims_with_verification(
            research_run_id=research_run_id,
            twin_id=twin_id,
            include_web=True,
            verification_status=web_status,
            limit=limit,
            offset=offset,
        )
        
        # Convert to response format
        items = []
        for cwv in claims:
            claim = cwv.claim
            items.append(ClaimWithWebVerificationResponse(
                id=claim.id or "",
                claim_text=claim.claim_text,
                claim_type=claim.claim_type.value,
                local_verification_status=claim.verification_status.value,
                local_confidence=claim.confidence,
                web_verification_status=cwv.web_verification_status.value if cwv.web_verification_status else None,
                web_verification_confidence=cwv.web_verification_confidence,
                web_verification_notes=cwv.web_verification_notes,
                web_verified_at=cwv.web_verified_at,
                web_evidence_count=cwv.web_evidence_count,
                created_at=claim.extracted_at.isoformat() if claim.extracted_at else "",
            ))
        
        return ClaimsWithWebVerificationListResponse(
            items=items,
            total=len(items),
            limit=limit,
            offset=offset,
            has_more=len(items) == limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List claims with web verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list claims",
                "code": "LIST_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/web-evidence",
    response_model=WebEvidenceListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_web_evidence_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get web evidence for a specific claim (Phase 9).
    
    Returns supporting/conflicting evidence found during web verification.
    """
    # Check feature flags
    _check_phase_9_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimWebVerificationService()
        evidence = await service.get_web_evidence(claim_id, research_run_id, twin_id)
        
        items = [
            WebEvidenceResponseItem(
                source_url=e["source_url"],
                source_title=e.get("source_title", ""),
                source_snippet=e.get("source_snippet", ""),
                extracted_quote=e.get("extracted_quote", ""),
                relevance_score=e.get("relevance_score", 0.0),
                evidence_type=e.get("evidence_type", "neutral"),
                content_quality=e.get("content_quality", "full"),
                domain_tier=e.get("domain_tier"),
            )
            for e in evidence
        ]
        
        return WebEvidenceListResponse(
            claim_id=claim_id,
            items=items,
            total=len(items),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get web evidence failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get web evidence",
                "code": "EVIDENCE_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/resolve-web",
    response_model=ResolveWebVerificationResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
    }
)
async def resolve_web_verification_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    request: ResolveWebVerificationRequest,
    user: dict = Depends(get_current_user)
):
    """
    Manually resolve a claim's web verification status (Phase 9).
    
    Allows users to override web verification results.
    """
    # Check feature flags
    _check_phase_9_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        # Parse and validate status
        try:
            new_status = WebVerificationStatus(request.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid status",
                    "code": "INVALID_STATUS",
                    "message": f"Must be one of: {[s.value for s in WebVerificationStatus if s not in [WebVerificationStatus.PENDING, WebVerificationStatus.BLOCKED, WebVerificationStatus.ERROR, WebVerificationStatus.SKIPPED]]}"
                }
            )
        
        service = ResearchClaimWebVerificationService()
        
        # Get current status
        claims = await service.list_claims_with_verification(
            research_run_id=research_run_id,
            twin_id=twin_id,
            limit=1,
        )
        
        previous_status = "unknown"
        for cwv in claims:
            if cwv.claim.id == claim_id:
                previous_status = cwv.web_verification_status.value if cwv.web_verification_status else "pending"
                break
        
        # Resolve
        success = await service.resolve_web_verification(
            claim_id=claim_id,
            research_run_id=research_run_id,
            twin_id=twin_id,
            new_status=new_status,
            reviewed_by=user.get("id"),
            review_notes=request.notes,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Claim not found",
                    "code": "NOT_FOUND",
                    "message": f"Claim {claim_id} not found in this research run"
                }
            )
        
        return ResolveWebVerificationResponse(
            claim_id=claim_id,
            research_run_id=research_run_id,
            previous_status=previous_status,
            new_status=new_status.value,
            resolved_at=datetime.utcnow().isoformat(),
            message=f"Web verification resolved to {new_status.value}",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve web verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to resolve web verification",
                "code": "RESOLVE_FAILED",
                "message": str(e)
            }
        )


# =============================================================================
# Phase 10: Claim Finalization Schemas
# =============================================================================

class FinalizationStatusResponse(BaseModel):
    """Response for finalization status."""
    research_run_id: str
    twin_id: str
    status: str
    total_claims: int
    finalized_count: int
    issues_found: int
    by_final_status: Dict[str, int]
    by_issue_type: Dict[str, int]
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class FinalizationResponse(BaseModel):
    """Response from continue-claim-finalization endpoint."""
    research_run_id: str
    twin_id: str
    status: str
    total_claims: int
    finalized_count: int
    issues_found: int
    by_final_status: Dict[str, int]
    message: str


class FinalizedClaimResponse(BaseModel):
    """Single finalized claim response."""
    claim_id: str
    claim_text: str
    claim_type: str
    local_status: str
    local_confidence: float
    web_status: Optional[str]
    web_confidence: float
    final_status: str
    final_confidence: float
    final_reason_codes: List[str]
    resolution_source: str
    finalized_at: Optional[str]
    notes: Optional[str]


class FinalizedClaimsListResponse(BaseModel):
    """List of finalized claims."""
    items: List[FinalizedClaimResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ConsistencyIssueResponse(BaseModel):
    """Single consistency issue response."""
    id: str
    issue_type: str
    severity: str
    status: str
    claim_ids: List[str]
    title: str
    description: Optional[str]
    detection_rule: Optional[str]
    confidence: float
    created_at: str


class ConsistencyIssuesListResponse(BaseModel):
    """List of consistency issues."""
    items: List[ConsistencyIssueResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ResolveConsistencyIssueRequest(BaseModel):
    """Request to resolve a consistency issue."""
    action: str = Field(..., description="Action: dismissed, claims_updated, manual_override")
    notes: str = Field(..., description="Resolution notes")
    
    @field_validator('action')
    def validate_action(cls, v):
        valid = ['dismissed', 'claims_updated', 'manual_override']
        if v not in valid:
            raise ValueError(f"Action must be one of: {valid}")
        return v


class ResolveConsistencyIssueResponse(BaseModel):
    """Response from resolving a consistency issue."""
    issue_id: str
    research_run_id: str
    action: str
    resolved_at: str
    message: str


class FinalizeOverrideRequest(BaseModel):
    """Request to manually override final status."""
    status: str = Field(..., description="New status: accepted, rejected, needs_review")
    reason: str = Field(..., description="Override reason")
    
    @field_validator('status')
    def validate_status(cls, v):
        valid = ['accepted', 'rejected', 'needs_review']
        if v not in valid:
            raise ValueError(f"Status must be one of: {valid}")
        return v


class FinalizeOverrideResponse(BaseModel):
    """Response from final status override."""
    claim_id: str
    research_run_id: str
    previous_status: str
    new_status: str
    overridden_at: str
    message: str


# =============================================================================
# Phase 10: Claim Finalization Endpoints
# =============================================================================

@router.post(
    "/twins/{twin_id}/research/{research_run_id}/continue-claim-finalization",
    response_model=FinalizationResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def continue_claim_finalization_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Start or continue claim finalization for a research run (Phase 10).
    
    Idempotent:
    - If already completed, returns existing summary
    - If in progress, returns current status
    - If not started, begins finalization process
    
    Finalization combines Phase 8 local + Phase 9 web verification into
    final claim decisions and runs consistency checks.
    """
    # Check feature flags
    _check_phase_10_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimFinalizationService()
        
        # Start finalization (idempotent)
        summary = await service.finalize_research_run(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build message
        if summary.status == FinalizationRunStatus.COMPLETED:
            message = f"Finalization completed: {summary.finalized_count} claims, {summary.issues_found} issues"
        elif summary.status == FinalizationRunStatus.PARTIAL:
            message = f"Finalization partial: {summary.finalized_count} claims finalized"
        elif summary.status == FinalizationRunStatus.RUNNING:
            message = "Finalization in progress"
        elif summary.status == FinalizationRunStatus.FAILED:
            message = f"Finalization failed: {summary.error_message}"
        else:
            message = "Finalization pending"
        
        return FinalizationResponse(
            research_run_id=research_run_id,
            twin_id=twin_id,
            status=summary.status.value,
            total_claims=summary.total_claims,
            finalized_count=summary.finalized_count,
            issues_found=summary.issues_found,
            by_final_status=summary.by_final_status,
            message=message,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Continue claim finalization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Claim finalization failed",
                "code": "FINALIZATION_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/finalization-status",
    response_model=FinalizationStatusResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_finalization_status_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get claim finalization status for a research run (Phase 10).
    
    Returns current finalization progress and claim/issue counts.
    """
    # Check feature flags
    _check_phase_10_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimFinalizationService()
        summary = await service.get_finalization_status(research_run_id, twin_id)
        
        if not summary:
            # Not started yet
            return FinalizationStatusResponse(
                research_run_id=research_run_id,
                twin_id=twin_id,
                status="not_started",
                total_claims=0,
                finalized_count=0,
                issues_found=0,
                by_final_status={},
                by_issue_type={},
            )
        
        return FinalizationStatusResponse(
            research_run_id=summary.research_run_id,
            twin_id=twin_id,
            status=summary.status.value,
            total_claims=summary.total_claims,
            finalized_count=summary.finalized_count,
            issues_found=summary.issues_found,
            by_final_status=summary.by_final_status,
            by_issue_type=summary.by_issue_type,
            error_message=summary.error_message,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get finalization status failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get finalization status",
                "code": "STATUS_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/finalized-claims",
    response_model=FinalizedClaimsListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def list_finalized_claims_endpoint(
    twin_id: str,
    research_run_id: str,
    final_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    List finalized claims with complete Phase 8/9/10 data.
    
    Filters:
    - final_status: accepted, rejected, needs_review, unresolved, overridden
    """
    # Check feature flags
    _check_phase_10_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimFinalizationService()
        
        claims = await service.list_finalized_claims(
            research_run_id=research_run_id,
            twin_id=twin_id,
            final_status=final_status,
            limit=limit,
            offset=offset,
        )
        
        # Convert to response format
        items = [
            FinalizedClaimResponse(
                claim_id=c.claim_id,
                claim_text=c.claim_text,
                claim_type=c.claim_type,
                local_status=c.local_status,
                local_confidence=c.local_confidence,
                web_status=c.web_status,
                web_confidence=c.web_confidence,
                final_status=c.final_status,
                final_confidence=c.final_confidence,
                final_reason_codes=c.final_reason_codes,
                resolution_source=c.resolution_source,
                finalized_at=c.finalized_at,
                notes=c.notes,
            )
            for c in claims
        ]
        
        return FinalizedClaimsListResponse(
            items=items,
            total=len(items),
            limit=limit,
            offset=offset,
            has_more=len(items) == limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List finalized claims failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list finalized claims",
                "code": "LIST_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/consistency-issues",
    response_model=ConsistencyIssuesListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def list_consistency_issues_endpoint(
    twin_id: str,
    research_run_id: str,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    List consistency issues for a research run (Phase 10).
    
    Filters:
    - status: open, resolved, dismissed
    - severity: low, medium, high
    """
    # Check feature flags
    _check_phase_10_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimFinalizationService()
        
        issues = await service.list_consistency_issues(
            research_run_id=research_run_id,
            twin_id=twin_id,
            status=status,
            severity=severity,
            limit=limit,
            offset=offset,
        )
        
        # Convert to response format
        items = [
            ConsistencyIssueResponse(
                id=issue["id"],
                issue_type=issue["issue_type"],
                severity=issue["severity"],
                status=issue["status"],
                claim_ids=issue.get("claim_ids", []),
                title=issue["title"],
                description=issue.get("description"),
                detection_rule=issue.get("detection_rule"),
                confidence=issue.get("confidence", 0.0),
                created_at=issue["created_at"],
            )
            for issue in issues
        ]
        
        return ConsistencyIssuesListResponse(
            items=items,
            total=len(items),
            limit=limit,
            offset=offset,
            has_more=len(items) == limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List consistency issues failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list consistency issues",
                "code": "LIST_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/consistency-issues/{issue_id}/resolve",
    response_model=ResolveConsistencyIssueResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Issue not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
    }
)
async def resolve_consistency_issue_endpoint(
    twin_id: str,
    research_run_id: str,
    issue_id: str,
    request: ResolveConsistencyIssueRequest,
    user: dict = Depends(get_current_user)
):
    """
    Resolve a consistency issue (Phase 10).
    
    Actions:
    - dismissed: Issue is not valid/won't fix
    - claims_updated: Underlying claims were modified
    - manual_override: Manual resolution applied
    """
    # Check feature flags
    _check_phase_10_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        service = ResearchClaimFinalizationService()
        
        success = await service.resolve_consistency_issue(
            issue_id=issue_id,
            research_run_id=research_run_id,
            twin_id=twin_id,
            action=request.action,
            notes=request.notes,
            user_id=user.get("id"),
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Issue not found",
                    "code": "NOT_FOUND",
                    "message": f"Issue {issue_id} not found in this research run"
                }
            )
        
        return ResolveConsistencyIssueResponse(
            issue_id=issue_id,
            research_run_id=research_run_id,
            action=request.action,
            resolved_at=datetime.utcnow().isoformat(),
            message=f"Issue resolved with action: {request.action}",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve consistency issue failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to resolve consistency issue",
                "code": "RESOLVE_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/finalize-override",
    response_model=FinalizeOverrideResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
    }
)
async def finalize_override_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    request: FinalizeOverrideRequest,
    user: dict = Depends(get_current_user)
):
    """
    Manually override a claim's final status (Phase 10).
    
    Use with caution - creates audit trail with user ID and reason.
    """
    # Check feature flags
    _check_phase_10_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        # Parse status
        try:
            new_status = FinalClaimStatus(request.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid status",
                    "code": "INVALID_STATUS",
                    "message": f"Must be one of: {[s.value for s in FinalClaimStatus if s != FinalClaimStatus.OVERRIDDEN]}"
                }
            )
        
        # Get current status
        service = ResearchClaimFinalizationService()
        claims = await service.list_finalized_claims(
            research_run_id=research_run_id,
            twin_id=twin_id,
            limit=1,
        )
        
        previous_status = "unknown"
        for c in claims:
            if c.claim_id == claim_id:
                previous_status = c.final_status
                break
        
        # Apply override
        success = await service.manual_override_final_status(
            claim_id=claim_id,
            research_run_id=research_run_id,
            twin_id=twin_id,
            new_status=new_status,
            reason=request.reason,
            user_id=user.get("id"),
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Claim not found",
                    "code": "NOT_FOUND",
                    "message": f"Claim {claim_id} not found in this research run"
                }
            )
        
        return FinalizeOverrideResponse(
            claim_id=claim_id,
            research_run_id=research_run_id,
            previous_status=previous_status,
            new_status=new_status.value,
            overridden_at=datetime.utcnow().isoformat(),
            message=f"Final status overridden to {new_status.value}",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Finalize override failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to override final status",
                "code": "OVERRIDE_FAILED",
                "message": str(e)
            }
        )


from datetime import datetime  # Import at end to avoid circular issues


# =============================================================================
# Phase 11: Human Adjudication + Canonical Claim Review
# =============================================================================

def _check_phase_11_enabled():
    """Check if Phase 11 human adjudication is enabled."""
    config = get_dr_config()
    
    # Check master switch first
    if not config.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Deep Research feature is not enabled",
                "code": "FEATURE_DISABLED",
                "message": "Set DEEP_RESEARCH_ENABLED=true to enable this feature"
            }
        )
    
    # Check Phase 11 specific flag
    if config.phase_11_human_adjudication_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Phase 11 human adjudication is disabled",
                "code": "PHASE_11_DISABLED",
                "message": "Set DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=false to enable"
            }
        )


# Phase 11 schemas
class ReviewQueueItemResponse(BaseModel):
    """Single item in review queue."""
    claim_id: str
    claim_text: str
    claim_type: str
    research_run_id: str
    twin_id: str
    finalization_status: Optional[str]
    canonical_status: Optional[str]
    locked: bool
    locked_by: Optional[str]
    has_open_issues: bool
    issue_count: int
    adjudication_count: int
    created_at: str


class ReviewQueueListResponse(BaseModel):
    """List of review queue items."""
    items: List[ReviewQueueItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ReviewQueueSummaryResponse(BaseModel):
    """Summary statistics for review queue."""
    total_claims: int
    needs_review: int
    unresolved: int
    accepted: int
    rejected: int
    locked: int
    has_open_issues: int


class AdjudicateClaimRequest(BaseModel):
    """Request to adjudicate a claim."""
    action: str = Field(..., description="Action: approve, reject, mark_needs_review, mark_unresolved")
    notes: Optional[str] = Field(default=None, description="Optional notes about the decision")
    reason_code: Optional[str] = Field(default=None, description="Optional reason code")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key for retries")
    
    @field_validator('action')
    def validate_action(cls, v):
        valid = ['approve', 'reject', 'mark_needs_review', 'mark_unresolved']
        if v not in valid:
            raise ValueError(f"Action must be one of: {valid}")
        return v


class AdjudicateClaimResponse(BaseModel):
    """Response from claim adjudication."""
    success: bool
    claim_id: str
    action: str
    previous_status: Optional[str]
    new_status: Optional[str]
    canonical_id: Optional[str]
    is_new_canonical: bool
    adjudicated_at: str
    message: str


class AdjudicationHistoryItemResponse(BaseModel):
    """Single adjudication history item."""
    id: str
    action: str
    previous_status: Optional[str]
    new_status: Optional[str]
    actor_id: Optional[str]
    actor_type: str
    reason_code: Optional[str]
    notes: Optional[str]
    created_at: str


class AdjudicationHistoryResponse(BaseModel):
    """Adjudication history for a claim."""
    claim_id: str
    items: List[AdjudicationHistoryItemResponse]
    total: int


class LockClaimRequest(BaseModel):
    """Request to lock/unlock a claim."""
    reason: Optional[str] = Field(default=None, description="Reason for locking")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key")


class LockClaimResponse(BaseModel):
    """Response from lock/unlock operation."""
    success: bool
    claim_id: str
    action: str  # locked or unlocked
    locked_by: str
    locked_at: str
    reason: Optional[str]
    message: str


class IssueActionRequest(BaseModel):
    """Request to take action on a consistency issue."""
    action: str = Field(..., description="Action: confirm_conflict, dismiss, merge_duplicate, split_context, defer")
    notes: Optional[str] = Field(default=None)
    reason_code: Optional[str] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None)
    
    @field_validator('action')
    def validate_action(cls, v):
        valid = ['confirm_conflict', 'dismiss', 'merge_duplicate', 'split_context', 'defer']
        if v not in valid:
            raise ValueError(f"Action must be one of: {valid}")
        return v


class IssueActionResponse(BaseModel):
    """Response from issue action."""
    success: bool
    issue_id: str
    action: str
    previous_status: Optional[str]
    new_status: Optional[str]
    actioned_at: str
    message: str


# Phase 11 endpoints
@router.get(
    "/twins/{twin_id}/research/{research_run_id}/review-queue",
    response_model=ReviewQueueListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_review_queue_endpoint(
    twin_id: str,
    research_run_id: str,
    status_filter: Optional[str] = None,
    has_issues: Optional[bool] = None,
    locked_only: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    Get the review queue for owner/admin adjudication (Phase 11).
    
    Returns claims that need review with their current canonical status.
    """
    _check_phase_11_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_adjudication_service import (
            ResearchClaimAdjudicationService,
        )
        
        service = ResearchClaimAdjudicationService()
        
        filters = {}
        if status_filter:
            filters["status"] = status_filter
        if has_issues is not None:
            filters["has_issues"] = has_issues
        if locked_only is not None:
            filters["locked_only"] = locked_only
        
        items = await service.get_review_queue(
            research_run_id=research_run_id,
            twin_id=twin_id,
            filters=filters if filters else None,
            limit=limit,
            offset=offset,
        )
        
        return ReviewQueueListResponse(
            items=[
                ReviewQueueItemResponse(
                    claim_id=item.claim_id,
                    claim_text=item.claim_text,
                    claim_type=item.claim_type,
                    research_run_id=item.research_run_id,
                    twin_id=item.twin_id,
                    finalization_status=item.finalization_status,
                    canonical_status=item.canonical_status,
                    locked=item.locked,
                    locked_by=item.locked_by,
                    has_open_issues=item.has_open_issues,
                    issue_count=item.issue_count,
                    adjudication_count=item.adjudication_count,
                    created_at=item.created_at,
                )
                for item in items
            ],
            total=len(items),
            limit=limit,
            offset=offset,
            has_more=len(items) == limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get review queue failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get review queue",
                "code": "QUEUE_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/review-queue/summary",
    response_model=ReviewQueueSummaryResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_review_queue_summary_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get summary statistics for the review queue (Phase 11).
    """
    _check_phase_11_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_adjudication_service import (
            ResearchClaimAdjudicationService,
        )
        
        service = ResearchClaimAdjudicationService()
        summary = await service.get_review_queue_summary(research_run_id, twin_id)
        
        return ReviewQueueSummaryResponse(
            total_claims=summary.total_claims,
            needs_review=summary.needs_review,
            unresolved=summary.unresolved,
            accepted=summary.accepted,
            rejected=summary.rejected,
            locked=summary.locked,
            has_open_issues=summary.has_open_issues,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get review queue summary failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get review queue summary",
                "code": "SUMMARY_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/adjudicate",
    response_model=AdjudicateClaimResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        403: {"model": ErrorResponse, "description": "Access denied or claim locked"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
    }
)
async def adjudicate_claim_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    request: AdjudicateClaimRequest,
    user: dict = Depends(get_current_user)
):
    """
    Adjudicate a claim (approve/reject/mark for review) (Phase 11).
    
    Idempotent via idempotency_key.
    """
    _check_phase_11_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_adjudication_service import (
            ResearchClaimAdjudicationService,
        )
        
        service = ResearchClaimAdjudicationService()
        
        result = await service.adjudicate_claim(
            claim_id=claim_id,
            twin_id=twin_id,
            action=request.action,
            actor_id=user.get("id"),
            notes=request.notes,
            reason_code=request.reason_code,
            idempotency_key=request.idempotency_key,
            actor_type="user",
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST if "locked" in (result.error or "") else status.HTTP_404_NOT_FOUND,
                detail={
                    "error": result.error or "Adjudication failed",
                    "code": "ADJUDICATION_FAILED",
                    "message": result.error or "Failed to adjudicate claim"
                }
            )
        
        return AdjudicateClaimResponse(
            success=True,
            claim_id=claim_id,
            action=request.action,
            previous_status=result.previous_status,
            new_status=result.new_status,
            canonical_id=result.canonical_id,
            is_new_canonical=result.is_new_canonical,
            adjudicated_at=datetime.utcnow().isoformat(),
            message=f"Claim adjudicated: {result.previous_status} -> {result.new_status}",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Adjudicate claim failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to adjudicate claim",
                "code": "ADJUDICATION_ERROR",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/lock",
    response_model=LockClaimResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def lock_claim_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    request: LockClaimRequest,
    user: dict = Depends(get_current_user)
):
    """
    Lock a claim to prevent further modifications (Phase 11).
    
    Only admins can unlock locked claims.
    """
    _check_phase_11_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_adjudication_service import (
            ResearchClaimAdjudicationService,
        )
        
        service = ResearchClaimAdjudicationService()
        
        result = await service.lock_claim(
            claim_id=claim_id,
            twin_id=twin_id,
            actor_id=user.get("id"),
            reason=request.reason,
            idempotency_key=request.idempotency_key,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": result.error or "Lock failed",
                    "code": "LOCK_FAILED",
                    "message": result.error or "Failed to lock claim"
                }
            )
        
        return LockClaimResponse(
            success=True,
            claim_id=claim_id,
            action="locked",
            locked_by=user.get("id"),
            locked_at=datetime.utcnow().isoformat(),
            reason=request.reason,
            message="Claim locked successfully",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lock claim failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to lock claim",
                "code": "LOCK_ERROR",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/unlock",
    response_model=LockClaimResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        403: {"model": ErrorResponse, "description": "Access denied or not admin"},
    }
)
async def unlock_claim_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    request: LockClaimRequest,
    user: dict = Depends(get_current_user)
):
    """
    Unlock a previously locked claim (Phase 11).
    
    Requires admin privileges if locked by another user.
    """
    _check_phase_11_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_adjudication_service import (
            ResearchClaimAdjudicationService,
        )
        
        service = ResearchClaimAdjudicationService()
        
        result = await service.unlock_claim(
            claim_id=claim_id,
            twin_id=twin_id,
            actor_id=user.get("id"),
            idempotency_key=request.idempotency_key,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": result.error or "Unlock failed",
                    "code": "UNLOCK_FAILED",
                    "message": result.error or "Failed to unlock claim"
                }
            )
        
        return LockClaimResponse(
            success=True,
            claim_id=claim_id,
            action="unlocked",
            locked_by=user.get("id"),
            locked_at=datetime.utcnow().isoformat(),
            reason=None,
            message="Claim unlocked successfully",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlock claim failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to unlock claim",
                "code": "UNLOCK_ERROR",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/adjudication-history",
    response_model=AdjudicationHistoryResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_adjudication_history_endpoint(
    twin_id: str,
    research_run_id: str,
    claim_id: str,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    Get the adjudication history (audit trail) for a claim (Phase 11).
    """
    _check_phase_11_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_adjudication_service import (
            ResearchClaimAdjudicationService,
        )
        
        service = ResearchClaimAdjudicationService()
        
        items = await service.get_adjudication_history(
            claim_id=claim_id,
            limit=limit,
            offset=offset,
        )
        
        return AdjudicationHistoryResponse(
            claim_id=claim_id,
            items=[
                AdjudicationHistoryItemResponse(
                    id=item.id,
                    action=item.action,
                    previous_status=item.previous_status,
                    new_status=item.new_status,
                    actor_id=item.actor_id,
                    actor_type=item.actor_type,
                    reason_code=item.reason_code,
                    notes=item.notes,
                    created_at=item.created_at,
                )
                for item in items
            ],
            total=len(items),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get adjudication history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get adjudication history",
                "code": "HISTORY_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/consistency-issues/{issue_id}/action",
    response_model=IssueActionResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Issue not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def apply_issue_action_endpoint(
    twin_id: str,
    research_run_id: str,
    issue_id: str,
    request: IssueActionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Take action on a consistency issue (Phase 11).
    
    Actions: confirm_conflict, dismiss, merge_duplicate, split_context, defer
    """
    _check_phase_11_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_adjudication_service import (
            ResearchClaimAdjudicationService,
        )
        
        service = ResearchClaimAdjudicationService()
        
        result = await service.apply_issue_action(
            issue_id=issue_id,
            twin_id=twin_id,
            action=request.action,
            actor_id=user.get("id"),
            notes=request.notes,
            reason_code=request.reason_code,
            idempotency_key=request.idempotency_key,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND if "not found" in (result.error or "").lower() else status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": result.error or "Action failed",
                    "code": "ACTION_FAILED",
                    "message": result.error or "Failed to apply issue action"
                }
            )
        
        return IssueActionResponse(
            success=True,
            issue_id=issue_id,
            action=request.action,
            previous_status=result.previous_status,
            new_status=result.new_status,
            actioned_at=datetime.utcnow().isoformat(),
            message=f"Issue action applied: {result.previous_status} -> {result.new_status}",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply issue action failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to apply issue action",
                "code": "ACTION_ERROR",
                "message": str(e)
            }
        )


# =============================================================================
# Phase 12: Runtime Publication + Deployment Readiness
# =============================================================================

def _check_phase_12_enabled():
    """Check if Phase 12 runtime publication is enabled."""
    config = get_dr_config()
    
    # Check master switch first
    if not config.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Deep Research feature is not enabled",
                "code": "FEATURE_DISABLED",
                "message": "Set DEEP_RESEARCH_ENABLED=true to enable this feature"
            }
        )
    
    # Check Phase 12 specific flag
    if config.phase_12_runtime_publication_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Phase 12 runtime publication is disabled",
                "code": "PHASE_12_DISABLED",
                "message": "Set DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED=false to enable"
            }
        )


# Phase 12 schemas
class PublishRuntimeClaimsRequest(BaseModel):
    """Request to publish runtime claims."""
    auto_publish: bool = Field(default=False, description="Auto-publish without manual review")
    correlation_id: Optional[str] = Field(default=None, description="Correlation ID for tracing")


class PublishRuntimeClaimsResponse(BaseModel):
    """Response from runtime publication."""
    success: bool
    research_run_id: str
    status: str
    total_claims: int
    published_count: int
    suppressed_count: int
    skipped_count: int
    errors: List[str] = Field(default_factory=list)
    published_at: str


class RuntimeClaimResponse(BaseModel):
    """Single runtime claim."""
    id: str
    claim_id: str
    research_run_id: str
    twin_id: str
    publishable: bool
    published: bool
    suppressed: bool
    suppression_reason: Optional[str]
    runtime_claim_text: str
    runtime_status: str
    runtime_confidence: float
    runtime_issue_flags: List[str]
    published_at: Optional[str]
    published_version: int
    created_at: str


class RuntimeClaimsListResponse(BaseModel):
    """List of runtime claims."""
    items: List[RuntimeClaimResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class PublicationStatusResponse(BaseModel):
    """Publication run status."""
    research_run_id: str
    status: str
    total_claims: int
    published_count: int
    suppressed_count: int
    started_at: Optional[str]
    completed_at: Optional[str]


class BackfillPublicationRequest(BaseModel):
    """Request to backfill runtime publication."""
    twin_id: Optional[str] = Field(default=None, description="Limit to specific twin")
    research_run_ids: Optional[List[str]] = Field(default=None, description="Specific runs to backfill")
    dry_run: bool = Field(default=False, description="Preview without publishing")
    batch_size: int = Field(default=100, ge=1, le=1000, description="Batch size")


class BackfillPublicationResponse(BaseModel):
    """Response from backfill operation."""
    success: bool
    total_runs: int
    processed_runs: int
    failed_runs: int
    total_claims: int
    published_count: int
    suppressed_count: int
    errors: List[str] = Field(default_factory=list)
    resume_token: Optional[str]


class ExportRuntimeClaimsRequest(BaseModel):
    """Request to export runtime claims."""
    format: str = Field(default="json", description="Export format: json, csv")
    published_only: bool = Field(default=True, description="Only export published claims")
    
    @field_validator('format')
    def validate_format(cls, v):
        if v not in ['json', 'csv']:
            raise ValueError("Format must be 'json' or 'csv'")
        return v


class ExportRuntimeClaimsResponse(BaseModel):
    """Response from export operation."""
    success: bool
    format: str
    record_count: int
    data: Any
    error: Optional[str] = None


# Phase 12 endpoints
@router.post(
    "/twins/{twin_id}/research/{research_run_id}/publish-runtime-claims",
    response_model=PublishRuntimeClaimsResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def publish_runtime_claims_endpoint(
    twin_id: str,
    research_run_id: str,
    request: PublishRuntimeClaimsRequest,
    user: dict = Depends(get_current_user)
):
    """
    Publish claims to the runtime layer (Phase 12).
    
    Idempotent: Can be safely retried. Uses correlation_id for tracing.
    Applies publication rules to determine which claims are publishable.
    """
    _check_phase_12_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_runtime_service import (
            ResearchClaimRuntimeService,
        )
        
        service = ResearchClaimRuntimeService()
        
        result = await service.publish_runtime_claims(
            research_run_id=research_run_id,
            twin_id=twin_id,
            auto_publish=request.auto_publish,
            correlation_id=request.correlation_id,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Publication failed",
                    "code": "PUBLICATION_FAILED",
                    "message": result.errors[0] if result.errors else "Unknown error"
                }
            )
        
        return PublishRuntimeClaimsResponse(
            success=True,
            research_run_id=research_run_id,
            status=result.status,
            total_claims=result.total_claims,
            published_count=result.published_count,
            suppressed_count=result.suppressed_count,
            skipped_count=result.skipped_count,
            errors=result.errors,
            published_at=datetime.utcnow().isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish runtime claims failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to publish runtime claims",
                "code": "PUBLICATION_ERROR",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/runtime-claims",
    response_model=RuntimeClaimsListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def list_runtime_claims_endpoint(
    twin_id: str,
    published: Optional[bool] = None,
    suppressed: Optional[bool] = None,
    status: Optional[str] = None,
    research_run_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    List runtime claims for a twin (Phase 12).
    
    Returns claims in the runtime publication layer with their publication status.
    """
    _check_phase_12_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_runtime_service import (
            ResearchClaimRuntimeService,
        )
        
        service = ResearchClaimRuntimeService()
        
        filters = {"twin_id": twin_id}
        if published is not None:
            filters["published"] = published
        if suppressed is not None:
            filters["suppressed"] = suppressed
        if status is not None:
            filters["status"] = status
        if research_run_id is not None:
            filters["research_run_id"] = research_run_id
        
        claims = await service.get_runtime_claims(
            twin_id=twin_id,
            filters=filters,
            limit=limit,
            offset=offset,
        )
        
        return RuntimeClaimsListResponse(
            items=[
                RuntimeClaimResponse(
                    id=claim.id,
                    claim_id=claim.claim_id,
                    research_run_id=claim.research_run_id,
                    twin_id=claim.twin_id,
                    publishable=claim.publishable,
                    published=claim.published,
                    suppressed=claim.suppressed,
                    suppression_reason=claim.suppression_reason,
                    runtime_claim_text=claim.runtime_claim_text,
                    runtime_status=claim.runtime_status,
                    runtime_confidence=claim.runtime_confidence,
                    runtime_issue_flags=claim.runtime_issue_flags,
                    published_at=claim.published_at,
                    published_version=claim.published_version,
                    created_at=claim.created_at,
                )
                for claim in claims
            ],
            total=len(claims),
            limit=limit,
            offset=offset,
            has_more=len(claims) == limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List runtime claims failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list runtime claims",
                "code": "LIST_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/runtime-claims/status",
    response_model=PublicationStatusResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_publication_status_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get the publication status for a research run (Phase 12).
    """
    _check_phase_12_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_runtime_service import (
            ResearchClaimRuntimeService,
        )
        
        service = ResearchClaimRuntimeService()
        status_result = await service.get_publication_status(research_run_id)
        
        if not status_result:
            return PublicationStatusResponse(
                research_run_id=research_run_id,
                status="not_started",
                total_claims=0,
                published_count=0,
                suppressed_count=0,
                started_at=None,
                completed_at=None,
            )
        
        return PublicationStatusResponse(
            research_run_id=status_result.get("research_run_id", research_run_id),
            status=status_result.get("status", "unknown"),
            total_claims=status_result.get("total_claims", 0),
            published_count=status_result.get("published_count", 0),
            suppressed_count=status_result.get("suppressed_count", 0),
            started_at=status_result.get("started_at"),
            completed_at=status_result.get("completed_at"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get publication status failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get publication status",
                "code": "STATUS_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/admin/runtime-claims/backfill",
    response_model=BackfillPublicationResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
    }
)
async def backfill_publication_endpoint(
    request: BackfillPublicationRequest,
    user: dict = Depends(get_current_user)
):
    """
    Backfill runtime publication for historical research runs (Phase 12).
    
    Admin-only endpoint. Supports dry-run mode for preview.
    """
    _check_phase_12_enabled()
    
    # Check admin access (simplified - should use proper admin check)
    if not user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Admin access required",
                "code": "ADMIN_REQUIRED",
                "message": "Only admins can trigger backfill operations"
            }
        )
    
    try:
        from modules.research_claim_runtime_service import (
            ResearchClaimRuntimeService,
        )
        
        service = ResearchClaimRuntimeService()
        
        result = await service.backfill_publication(
            twin_id=request.twin_id,
            research_run_ids=request.research_run_ids,
            dry_run=request.dry_run,
            batch_size=request.batch_size,
        )
        
        return BackfillPublicationResponse(
            success=result.success,
            total_runs=result.total_runs,
            processed_runs=result.processed_runs,
            failed_runs=result.failed_runs,
            total_claims=result.total_claims,
            published_count=result.published_count,
            suppressed_count=result.suppressed_count,
            errors=result.errors,
            resume_token=result.resume_token,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backfill publication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Backfill operation failed",
                "code": "BACKFILL_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/runtime-claims/export",
    response_model=ExportRuntimeClaimsResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def export_runtime_claims_endpoint(
    twin_id: str,
    request: ExportRuntimeClaimsRequest,
    user: dict = Depends(get_current_user)
):
    """
    Export runtime claims in various formats (Phase 12).
    
    Formats: json, csv
    """
    _check_phase_12_enabled()
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_claim_runtime_service import (
            ResearchClaimRuntimeService,
        )
        
        service = ResearchClaimRuntimeService()
        
        filters = {"published": request.published_only}
        
        result = await service.export_runtime_claims(
            twin_id=twin_id,
            format=request.format,
            filters=filters,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Export failed",
                    "code": "EXPORT_FAILED",
                    "message": result.error or "Failed to export claims"
                }
            )
        
        return ExportRuntimeClaimsResponse(
            success=True,
            format=result.format,
            record_count=result.record_count,
            data=result.data,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export runtime claims failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to export runtime claims",
                "code": "EXPORT_ERROR",
                "message": str(e)
            }
        )


# Ensure datetime import is available
from datetime import datetime
