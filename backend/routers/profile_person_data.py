"""
Profile Person Data Router

Endpoints for sources, claims, timeline, topics, contradictions, and policies.
These are thin wrappers around the twin-scoped tables that use /profile/* URLs.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import logging

from modules.auth_guard import require_tenant
from modules.observability import supabase
from routers.profile import get_or_create_profile_for_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile-data"])


# =============================================================================
# Sources
# =============================================================================

class SourceResponse(BaseModel):
    id: str
    url: str
    title: str
    source_type: str
    authority_tier: int
    owner_verified_status: str
    quality_score: int
    is_active: bool
    discovered_at: str
    claims_count: int = 0


class UpdateSourceRequest(BaseModel):
    owner_verified_status: Optional[str] = Field(None, pattern="^(verified|rejected)$")
    is_active: Optional[bool] = None


@router.get("/profile/sources")
async def get_profile_sources(
    filter: Optional[str] = Query(None),
    user: dict = Depends(require_tenant)
):
    """Get sources for the user's profile."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    query = supabase.table("person_source_registry") \
        .select("*") \
        .eq("twin_id", profile["id"])
    
    if filter == "verified":
        query = query.eq("owner_verified_status", "verified")
    elif filter == "unverified":
        query = query.eq("owner_verified_status", "unverified")
    elif filter == "excluded":
        query = query.eq("is_active", False)
    else:
        query = query.eq("is_active", True)
    
    result = query.order("discovered_at", desc=True).execute()
    
    sources = []
    for source in result.data or []:
        # Get claims count for this source
        claims_count = 0
        try:
            claims_result = supabase.table("person_claims") \
                .select("id", count="exact") \
                .eq("twin_id", profile["id"]) \
                .eq("source_registry_id", source["id"]).execute()
            claims_count = claims_result.count or 0
        except Exception:
            pass
        
        sources.append({
            "id": source["id"],
            "url": source["url"],
            "title": source.get("title", "Untitled"),
            "source_type": source.get("source_type", "unknown"),
            "authority_tier": source.get("authority_tier", 7),
            "owner_verified_status": source.get("owner_verified_status", "unverified"),
            "quality_score": source.get("quality_score", 0),
            "is_active": source.get("is_active", True),
            "discovered_at": source.get("discovered_at"),
            "claims_count": claims_count,
        })
    
    return {"sources": sources, "total": len(sources)}


@router.patch("/profile/sources/{source_id}")
async def update_profile_source(
    source_id: str,
    request: UpdateSourceRequest,
    user: dict = Depends(require_tenant)
):
    """Update a source (verify, reject, or exclude)."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    update_data = {}
    if request.owner_verified_status is not None:
        update_data["owner_verified_status"] = request.owner_verified_status
    if request.is_active is not None:
        update_data["is_active"] = request.is_active
    
    if not update_data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    
    result = supabase.table("person_source_registry") \
        .update(update_data) \
        .eq("id", source_id) \
        .eq("twin_id", profile["id"]) \
        .execute()
    
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    
    return {"success": True, "source": result.data[0]}


# =============================================================================
# Claims
# =============================================================================

class ClaimResponse(BaseModel):
    id: str
    claim_text: str
    claim_type: str
    verification_status: str
    owner_approval_status: str
    confidence: float
    evidence_count: int
    public_visibility: str
    first_seen_at: str


class UpdateClaimRequest(BaseModel):
    owner_approval_status: Optional[str] = Field(None, pattern="^(approved|rejected)$")
    public_visibility: Optional[str] = Field(None, pattern="^(public|private)$")


@router.get("/profile/claims")
async def get_profile_claims(
    claim_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: dict = Depends(require_tenant)
):
    """Get claims for the user's profile."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    query = supabase.table("person_claims") \
        .select("*") \
        .eq("twin_id", profile["id"])
    
    if claim_type:
        query = query.eq("claim_type", claim_type)
    if status:
        query = query.eq("verification_status", status)
    
    result = query.order("first_seen_at", desc=True).execute()
    
    claims = []
    for claim in result.data or []:
        # Get evidence count
        evidence_count = 0
        try:
            evidence_result = supabase.table("person_claim_evidence_spans") \
                .select("id", count="exact") \
                .eq("claim_id", claim["id"]).execute()
            evidence_count = evidence_result.count or 0
        except Exception:
            pass
        
        claims.append({
            "id": claim["id"],
            "claim_text": claim.get("claim_text", ""),
            "claim_type": claim.get("claim_type", "unknown"),
            "verification_status": claim.get("verification_status", "pending"),
            "owner_approval_status": claim.get("owner_approval_status", "pending"),
            "confidence": claim.get("extraction_confidence", 0),
            "evidence_count": evidence_count,
            "public_visibility": claim.get("public_visibility", "private"),
            "first_seen_at": claim.get("first_seen_at"),
        })
    
    return {"claims": claims, "total": len(claims)}


@router.get("/profile/claims/{claim_id}/evidence")
async def get_claim_evidence(
    claim_id: str,
    user: dict = Depends(require_tenant)
):
    """Get evidence spans for a claim."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    # Verify claim belongs to profile
    claim_result = supabase.table("person_claims") \
        .select("id") \
        .eq("id", claim_id) \
        .eq("twin_id", profile["id"]) \
        .single().execute()
    
    if not claim_result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    
    result = supabase.table("person_claim_evidence_spans") \
        .select("*") \
        .eq("claim_id", claim_id).execute()
    
    evidence = []
    for ev in result.data or []:
        # Get source info
        source_title = None
        source_url = None
        if ev.get("source_registry_id"):
            try:
                source_result = supabase.table("person_source_registry") \
                    .select("title, url") \
                    .eq("id", ev["source_registry_id"]) \
                    .single().execute()
                if source_result.data:
                    source_title = source_result.data.get("title")
                    source_url = source_result.data.get("url")
            except Exception:
                pass
        
        evidence.append({
            "id": ev["id"],
            "evidence_text": ev.get("evidence_text", ""),
            "evidence_type": ev.get("evidence_type", "quote"),
            "source_title": source_title,
            "source_url": source_url,
            "quote": ev.get("evidence_text", ""),
            "timestamp_start": ev.get("timestamp_start_sec"),
            "timestamp_end": ev.get("timestamp_end_sec"),
        })
    
    return {"evidence": evidence}


@router.patch("/profile/claims/{claim_id}")
async def update_profile_claim(
    claim_id: str,
    request: UpdateClaimRequest,
    user: dict = Depends(require_tenant)
):
    """Update a claim (approve, reject, change visibility)."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    update_data = {}
    if request.owner_approval_status is not None:
        update_data["owner_approval_status"] = request.owner_approval_status
    if request.public_visibility is not None:
        update_data["public_visibility"] = request.public_visibility
    
    if not update_data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    
    result = supabase.table("person_claims") \
        .update(update_data) \
        .eq("id", claim_id) \
        .eq("twin_id", profile["id"]) \
        .execute()
    
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    
    return {"success": True, "claim": result.data[0]}


# =============================================================================
# Timeline
# =============================================================================

@router.get("/profile/timeline")
async def get_profile_timeline(
    user: dict = Depends(require_tenant)
):
    """Get timeline events for the user's profile."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    result = supabase.table("person_timeline_events") \
        .select("*") \
        .eq("twin_id", profile["id"]) \
        .order("start_date", desc=True).execute()
    
    events = []
    for event in result.data or []:
        # Check for conflicts
        has_conflict = False
        try:
            conflict_result = supabase.table("person_contradictions") \
                .select("id") \
                .eq("twin_id", profile["id"]) \
                .eq("status", "open") \
                .or_(f"claim_a_id.eq.{event.get('derived_from_claim_ids', [None])[0]},claim_b_id.eq.{event.get('derived_from_claim_ids', [None])[0]}") \
                .execute()
            has_conflict = len(conflict_result.data or []) > 0
        except Exception:
            pass
        
        events.append({
            "id": event["id"],
            "event_type": event.get("event_type", "unknown"),
            "title": event.get("title", ""),
            "description": event.get("description", ""),
            "start_date": event.get("start_date"),
            "end_date": event.get("end_date"),
            "organization": event.get("organization"),
            "role_title": event.get("role_title"),
            "confidence": event.get("confidence", 0),
            "has_conflict": has_conflict,
            "derived_from_claim_ids": event.get("derived_from_claim_ids", []),
        })
    
    return {"events": events}


# =============================================================================
# Topics
# =============================================================================

@router.get("/profile/topics")
async def get_profile_topics(
    user: dict = Depends(require_tenant)
):
    """Get topic profiles for the user's profile."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    result = supabase.table("person_topic_profiles") \
        .select("*") \
        .eq("twin_id", profile["id"]) \
        .order("answerability_score", desc=True).execute()
    
    topics = []
    for topic in result.data or []:
        topics.append({
            "id": topic["id"],
            "slug": topic.get("slug", ""),
            "name": topic.get("name", "Unknown"),
            "answerability_score": topic.get("answerability_score", 0),
            "coverage_score": topic.get("coverage_score", 0),
            "verification_score": topic.get("verification_score", 0),
            "recency_score": topic.get("recency_score", 0),
            "consistency_score": topic.get("consistency_score", 0),
            "evidence_count": topic.get("evidence_count", 0),
        })
    
    # Identify gaps (low coverage topics)
    gaps = [t for t in topics if t["answerability_score"] < 50]
    
    return {"topics": topics, "gaps": gaps}


# =============================================================================
# Contradictions (Review Queue)
# =============================================================================

class ResolveContradictionRequest(BaseModel):
    resolution: str = Field(..., pattern="^(approve_a|approve_b|approve_both|reject_both|dismiss)$")
    notes: Optional[str] = None


@router.get("/profile/contradictions")
async def get_profile_contradictions(
    user: dict = Depends(require_tenant)
):
    """Get open contradictions for review queue."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    result = supabase.table("person_contradictions") \
        .select("*") \
        .eq("twin_id", profile["id"]) \
        .eq("status", "open") \
        .order("detected_at", desc=True).execute()
    
    contradictions = []
    for contra in result.data or []:
        # Get claim details
        claim_a = None
        claim_b = None
        
        if contra.get("claim_a_id"):
            try:
                claim_result = supabase.table("person_claims") \
                    .select("claim_text, claim_type") \
                    .eq("id", contra["claim_a_id"]).single().execute()
                claim_a = claim_result.data
            except Exception:
                pass
        
        if contra.get("claim_b_id"):
            try:
                claim_result = supabase.table("person_claims") \
                    .select("claim_text, claim_type") \
                    .eq("id", contra["claim_b_id"]).single().execute()
                claim_b = claim_result.data
            except Exception:
                pass
        
        contradictions.append({
            "id": contra["id"],
            "contradiction_type": contra.get("contradiction_type", "unknown"),
            "severity": contra.get("severity", "medium"),
            "description": contra.get("description", ""),
            "auto_resolution_suggestion": contra.get("auto_resolution_suggestion"),
            "claim_a": claim_a,
            "claim_b": claim_b,
            "detected_at": contra.get("detected_at"),
        })
    
    return {"contradictions": contradictions, "total": len(contradictions)}


@router.post("/profile/contradictions/{contradiction_id}/resolve")
async def resolve_profile_contradiction(
    contradiction_id: str,
    request: ResolveContradictionRequest,
    user: dict = Depends(require_tenant)
):
    """Resolve a contradiction."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    # Update contradiction
    result = supabase.table("person_contradictions") \
        .update({
            "status": "resolved",
            "resolution": request.resolution,
            "resolution_notes": request.notes,
            "resolved_at": "now()",
        }) \
        .eq("id", contradiction_id) \
        .eq("twin_id", profile["id"]) \
        .execute()
    
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contradiction not found")
    
    return {"success": True}


# =============================================================================
# Runtime Policies
# =============================================================================

class RuntimePoliciesResponse(BaseModel):
    audience: str
    confidence_threshold_answer: float
    confidence_threshold_style: float
    require_citation: bool
    blocked_topics: List[str]
    fallback_behavior: str


class UpdateRuntimePoliciesRequest(BaseModel):
    audience: Optional[str] = Field(None, pattern="^(public|recruiter|investor|internal)$")
    confidence_threshold_answer: Optional[float] = Field(None, ge=0, le=1)
    confidence_threshold_style: Optional[float] = Field(None, ge=0, le=1)
    require_citation: Optional[bool] = None
    blocked_topics: Optional[List[str]] = None
    fallback_behavior: Optional[str] = Field(None, pattern="^(i_dont_know|clarify|escalate)$")


@router.get("/profile/runtime-policies", response_model=RuntimePoliciesResponse)
async def get_profile_runtime_policies(
    user: dict = Depends(require_tenant)
):
    """Get runtime policies for the user's profile."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    # Get active policy
    result = supabase.table("person_runtime_policies") \
        .select("*") \
        .eq("twin_id", profile["id"]) \
        .eq("is_active", True) \
        .order("priority", desc=True) \
        .limit(1).execute()
    
    if result.data:
        policy = result.data[0]
        return {
            "audience": policy.get("audience", "public"),
            "confidence_threshold_answer": policy.get("confidence_threshold_answer", 0.5),
            "confidence_threshold_style": policy.get("confidence_threshold_style", 0.6),
            "require_citation": policy.get("require_citation", True),
            "blocked_topics": policy.get("blocked_topics", []),
            "fallback_behavior": policy.get("fallback_behavior", "i_dont_know"),
        }
    
    # Default policy
    return {
        "audience": "public",
        "confidence_threshold_answer": 0.5,
        "confidence_threshold_style": 0.6,
        "require_citation": True,
        "blocked_topics": [],
        "fallback_behavior": "i_dont_know",
    }


@router.put("/profile/runtime-policies")
async def update_profile_runtime_policies(
    request: UpdateRuntimePoliciesRequest,
    user: dict = Depends(require_tenant)
):
    """Update runtime policies for the user's profile."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    
    # Build update data
    update_data = {"updated_at": "now()"}
    if request.audience is not None:
        update_data["audience"] = request.audience
    if request.confidence_threshold_answer is not None:
        update_data["confidence_threshold_answer"] = request.confidence_threshold_answer
    if request.confidence_threshold_style is not None:
        update_data["confidence_threshold_style"] = request.confidence_threshold_style
    if request.require_citation is not None:
        update_data["require_citation"] = request.require_citation
    if request.blocked_topics is not None:
        update_data["blocked_topics"] = request.blocked_topics
    if request.fallback_behavior is not None:
        update_data["fallback_behavior"] = request.fallback_behavior
    
    # Check if policy exists
    existing = supabase.table("person_runtime_policies") \
        .select("id") \
        .eq("twin_id", profile["id"]) \
        .eq("is_active", True).execute()
    
    if existing.data:
        # Update existing
        result = supabase.table("person_runtime_policies") \
            .update(update_data) \
            .eq("id", existing.data[0]["id"]) \
            .execute()
    else:
        # Create new
        update_data["twin_id"] = profile["id"]
        update_data["is_active"] = True
        update_data["priority"] = 1
        result = supabase.table("person_runtime_policies") \
            .insert(update_data).execute()
    
    return {"success": True, "policy": result.data[0] if result.data else None}
