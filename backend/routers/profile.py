"""
Profile Router - Person Completeness v1

Abstraction layer over twins that enforces "one profile per user" semantics.
All endpoints return "profile" terminology externally while using twin_id internally.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from modules.auth_guard import get_current_user, require_tenant
from modules.observability import supabase
from modules.tenant_guard import derive_creator_ids
from modules.person_completeness_pipeline import run_person_completeness_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])


# =============================================================================
# Schemas
# =============================================================================

class ProfileResponse(BaseModel):
    """Public profile representation (no "twin" terminology)."""
    id: str
    name: str
    headline: Optional[str] = None
    status: str  # 'draft' | 'building' | 'ready' | 'needs_attention'
    answerability_score: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateProfileRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    headline: Optional[str] = Field(None, max_length=280)
    build_mode: str = Field(..., pattern="^(with_links|name_only)$")


class UpdateProfileRequest(BaseModel):
    headline: Optional[str] = Field(None, max_length=280)
    role: Optional[str] = None
    location: Optional[str] = None
    expertise_tags: Optional[List[str]] = None


class BuildStatusResponse(BaseModel):
    """Unified build status for onboarding progress screen."""
    profile_id: str
    status: str  # 'pending' | 'building' | 'ready' | 'needs_attention' | 'failed'
    stage: str
    progress_percent: int
    stats: Dict[str, Any]
    quality_tier: Optional[str] = None  # 'high_confidence' | 'with_gaps' | 'low_confidence' | 'failed'
    last_updated_at: Optional[str] = None


class PersonCompletenessSummaryResponse(BaseModel):
    profile_id: str
    answerability_score: int
    grade: str  # 'A' | 'B' | 'C' | 'D' | 'F'
    status: str
    stats: Dict[str, int]
    top_topics: List[Dict[str, Any]]
    next_actions: List[Dict[str, Any]]


# =============================================================================
# Helpers
# =============================================================================

def map_twin_to_profile(twin: Dict[str, Any]) -> Dict[str, Any]:
    """Map twin record to profile response (terminology conversion)."""
    settings = twin.get("settings") or {}
    
    # Get answerability score if available
    answerability_score = 0
    try:
        score_result = supabase.table("person_answerability_scores") \
            .select("answerability_score") \
            .eq("twin_id", twin["id"]) \
            .eq("scope_type", "global") \
            .eq("scope_key", "global") \
            .single().execute()
        if score_result.data:
            answerability_score = score_result.data.get("answerability_score", 0)
    except Exception:
        pass
    
    return {
        "id": twin["id"],
        "name": twin["name"],
        "headline": settings.get("headline"),
        "status": map_status(twin.get("status"), twin.get("settings", {})),
        "answerability_score": answerability_score,
        "created_at": twin.get("created_at"),
        "updated_at": twin.get("updated_at"),
    }


def map_status(twin_status: Optional[str], settings: Dict[str, Any]) -> str:
    """Map internal twin status to profile status."""
    if not twin_status:
        return "draft"
    
    # Map existing statuses
    status_map = {
        "draft": "draft",
        "ingesting": "building",
        "claims_ready": "building",
        "clarification_pending": "building",
        "persona_built": "ready",
        "active": "ready",
    }
    
    mapped = status_map.get(twin_status, "draft")
    
    # Check if there's an active build
    try:
        latest_run = supabase.table("person_completeness_runs") \
            .select("status") \
            .eq("twin_id", settings.get("id")) \
            .order("created_at", desc=True) \
            .limit(1).execute()
        
        if latest_run.data and latest_run.data[0].get("status") in ["running", "pending"]:
            return "building"
    except Exception:
        pass
    
    return mapped


def get_or_create_profile_for_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Get existing profile or return None (doesn't create - creation is explicit)."""
    tenant_id = user.get("tenant_id")
    user_id = user.get("user_id")
    
    # Get most recent non-deleted twin for this tenant
    result = supabase.table("twins") \
        .select("*") \
        .eq("tenant_id", tenant_id) \
        .is_("settings->>deleted_at", "null") \
        .order("created_at", desc=True) \
        .limit(1).execute()
    
    if result.data:
        return map_twin_to_profile(result.data[0])
    
    return None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user: dict = Depends(require_tenant)):
    """
    Get the current user's single profile.
    Returns 404 if no profile exists (frontend routes to onboarding).
    """
    profile = get_or_create_profile_for_user(user)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Profile not found",
                "code": "PROFILE_NOT_FOUND",
                "message": "No profile exists for this user. Please complete onboarding."
            }
        )
    
    return profile


@router.post("/profile", response_model=ProfileResponse)
async def create_profile(
    request: CreateProfileRequest,
    user: dict = Depends(require_tenant)
):
    """
    Idempotent profile creation.
    If profile already exists, returns it (no duplicate creation).
    """
    tenant_id = user.get("tenant_id")
    user_id = user.get("user_id")
    
    # Check for existing profile (idempotency)
    existing = get_or_create_profile_for_user(user)
    if existing:
        logger.info(f"Profile already exists for user {user_id}, returning existing")
        return existing
    
    # Create new twin (internal representation)
    creator_ids = derive_creator_ids(user)
    creator_id = creator_ids[0] if creator_ids else f"tenant_{tenant_id}"
    
    twin_data = {
        "name": request.full_name.strip(),
        "tenant_id": tenant_id,
        "creator_id": creator_id,
        "status": "draft",
        "specialization": "vanilla",
        "settings": {
            "headline": request.headline,
            "build_mode": request.build_mode,
            "use_person_completeness": True,
            "created_via": "profile_api",
            "owner_name": request.full_name.strip(),
        },
        "is_active": False,
    }
    
    try:
        result = supabase.table("twins").insert(twin_data).execute()
        twin = result.data[0]
        
        logger.info(f"Created profile {twin['id']} for user {user_id}")
        
        return map_twin_to_profile(twin)
        
    except Exception as e:
        logger.exception(f"Failed to create profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Profile creation failed",
                "code": "PROFILE_CREATE_FAILED",
                "message": str(e)
            }
        )


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    user: dict = Depends(require_tenant)
):
    """Update profile settings (headline, hints, etc)."""
    tenant_id = user.get("tenant_id")
    
    # Get existing profile
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Profile not found", "code": "PROFILE_NOT_FOUND"}
        )
    
    # Build update
    update_data = {"updated_at": datetime.utcnow().isoformat()}
    settings_updates = {}
    
    if request.headline is not None:
        settings_updates["headline"] = request.headline
    
    if request.role is not None or request.location is not None or request.expertise_tags is not None:
        hints = {}
        if request.role is not None:
            hints["role"] = request.role
        if request.location is not None:
            hints["location"] = request.location
        if request.expertise_tags is not None:
            hints["expertise_tags"] = request.expertise_tags
        settings_updates["onboarding_hints"] = hints
    
    if settings_updates:
        # Get current settings and merge
        twin_result = supabase.table("twins").select("settings").eq("id", profile["id"]).single().execute()
        current_settings = twin_result.data.get("settings") or {}
        updated_settings = {**current_settings, **settings_updates}
        update_data["settings"] = updated_settings
    
    # Apply update
    result = supabase.table("twins").update(update_data).eq("id", profile["id"]).execute()
    
    return map_twin_to_profile(result.data[0])


@router.get("/profile/build-status", response_model=BuildStatusResponse)
async def get_build_status(user: dict = Depends(require_tenant)):
    """
    Unified build status for profile readiness.
    Combines deep research + person completeness + ingestion status.
    """
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Profile not found", "code": "PROFILE_NOT_FOUND"}
        )
    
    twin_id = profile["id"]
    
    # Get latest person completeness run
    pc_run = None
    try:
        pc_result = supabase.table("person_completeness_runs") \
            .select("*") \
            .eq("twin_id", twin_id) \
            .order("created_at", desc=True) \
            .limit(1).execute()
        if pc_result.data:
            pc_run = pc_result.data[0]
    except Exception as e:
        logger.warning(f"Error fetching PC run: {e}")
    
    # Get stats
    stats = {
        "sources_count": 0,
        "claims_count": 0,
        "contradictions_open": 0,
        "topics_count": 0,
    }
    
    try:
        sources_result = supabase.table("person_source_registry") \
            .select("id", count="exact") \
            .eq("twin_id", twin_id).execute()
        stats["sources_count"] = sources_result.count or 0
        
        claims_result = supabase.table("person_claims") \
            .select("id", count="exact") \
            .eq("twin_id", twin_id).execute()
        stats["claims_count"] = claims_result.count or 0
        
        contradictions_result = supabase.table("person_contradictions") \
            .select("id", count="exact") \
            .eq("twin_id", twin_id) \
            .eq("status", "open").execute()
        stats["contradictions_open"] = contradictions_result.count or 0
        
        topics_result = supabase.table("person_topic_profiles") \
            .select("id", count="exact") \
            .eq("twin_id", twin_id).execute()
        stats["topics_count"] = topics_result.count or 0
    except Exception as e:
        logger.warning(f"Error fetching stats: {e}")
    
    # Determine status and stage
    if pc_run:
        pc_status = pc_run.get("status")
        current_stage = pc_run.get("current_stage", "")
        
        if pc_status == "running":
            status = "building"
            # Map stage to progress
            stage_progress = {
                "source_registry_built": 15,
                "claims_extracted": 35,
                "timeline_built": 50,
                "topic_graph_built": 65,
                "style_profile_built": 75,
                "contradictions_detected": 85,
                "answerability_scored": 95,
            }
            progress = stage_progress.get(current_stage, 50)
            stage = current_stage
        elif pc_status == "completed":
            status = "ready"
            progress = 100
            stage = "completed"
        elif pc_status == "failed":
            status = "failed"
            progress = 0
            stage = "failed"
        else:
            status = "pending"
            progress = 5
            stage = "planning"
    else:
        # No PC run yet
        status = "draft"
        progress = 0
        stage = "planning"
    
    # Determine quality tier
    quality_tier = None
    if status == "ready":
        score = profile.get("answerability_score", 0)
        if score >= 75:
            quality_tier = "high_confidence"
        elif score >= 50:
            quality_tier = "with_gaps"
        else:
            quality_tier = "low_confidence"
    
    return {
        "profile_id": twin_id,
        "status": status,
        "stage": stage,
        "progress_percent": progress,
        "stats": stats,
        "quality_tier": quality_tier,
        "last_updated_at": pc_run.get("updated_at") if pc_run else None,
    }


@router.post("/profile/person-completeness/run")
async def run_person_completeness(user: dict = Depends(require_tenant)):
    """Trigger person completeness pipeline for the user's profile."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Profile not found", "code": "PROFILE_NOT_FOUND"}
        )
    
    try:
        result = await run_person_completeness_pipeline(
            twin_id=profile["id"],
            force_rebuild=True
        )
        
        return {
            "run_id": result.run_id,
            "status": "started" if result.success else "failed",
            "profile_id": profile["id"],
        }
    except Exception as e:
        logger.exception(f"Failed to run person completeness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Pipeline failed", "code": "PIPELINE_FAILED", "message": str(e)}
        )


@router.get("/profile/person-completeness/summary", response_model=PersonCompletenessSummaryResponse)
async def get_person_completeness_summary(user: dict = Depends(require_tenant)):
    """Get person completeness summary for profile overview."""
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Profile not found", "code": "PROFILE_NOT_FOUND"}
        )
    
    twin_id = profile["id"]
    
    # Get stats
    stats = {
        "sources_count": 0,
        "claims_count": 0,
        "verified_claims": 0,
        "contradictions_open": 0,
        "timeline_events": 0,
        "topics_count": 0,
    }
    
    try:
        sources_result = supabase.table("person_source_registry") \
            .select("id", count="exact").eq("twin_id", twin_id).execute()
        stats["sources_count"] = sources_result.count or 0
        
        claims_result = supabase.table("person_claims") \
            .select("id, verification_status").eq("twin_id", twin_id).execute()
        if claims_result.data:
            stats["claims_count"] = len(claims_result.data)
            stats["verified_claims"] = sum(1 for c in claims_result.data if c.get("verification_status") == "verified")
        
        contradictions_result = supabase.table("person_contradictions") \
            .select("id", count="exact").eq("twin_id", twin_id).eq("status", "open").execute()
        stats["contradictions_open"] = contradictions_result.count or 0
        
        timeline_result = supabase.table("person_timeline_events") \
            .select("id", count="exact").eq("twin_id", twin_id).execute()
        stats["timeline_events"] = timeline_result.count or 0
        
        topics_result = supabase.table("person_topic_profiles") \
            .select("id", count="exact").eq("twin_id", twin_id).execute()
        stats["topics_count"] = topics_result.count or 0
    except Exception as e:
        logger.warning(f"Error fetching stats: {e}")
    
    # Get answerability score
    score = profile.get("answerability_score", 0)
    
    # Calculate grade
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    
    # Get top topics
    top_topics = []
    try:
        topics_result = supabase.table("person_topic_profiles") \
            .select("slug, name, answerability_score") \
            .eq("twin_id", twin_id) \
            .order("answerability_score", desc=True) \
            .limit(5).execute()
        if topics_result.data:
            top_topics = [
                {
                    "slug": t.get("slug"),
                    "name": t.get("name"),
                    "answerability_score": t.get("answerability_score", 0)
                }
                for t in topics_result.data
            ]
    except Exception as e:
        logger.warning(f"Error fetching topics: {e}")
    
    # Determine next actions
    next_actions = []
    if stats["contradictions_open"] > 0:
        next_actions.append({
            "type": "resolve_conflicts",
            "priority": "high",
            "description": f"{stats['contradictions_open']} timeline conflicts need resolution",
            "link": "/dashboard/profile/review"
        })
    if stats["sources_count"] == 0:
        next_actions.append({
            "type": "add_sources",
            "priority": "high",
            "description": "Add sources to build your profile",
            "link": "/dashboard/profile/sources"
        })
    
    return {
        "profile_id": twin_id,
        "answerability_score": score,
        "grade": grade,
        "status": profile.get("status", "draft"),
        "stats": stats,
        "top_topics": top_topics,
        "next_actions": next_actions,
    }
