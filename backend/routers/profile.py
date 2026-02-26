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


class ResetProfileResponse(BaseModel):
    profile_id: str
    status: str  # "reset"
    message: str


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
        "status": map_status(twin.get("status"), twin.get("id")),
        "answerability_score": answerability_score,
        "created_at": twin.get("created_at"),
        "updated_at": twin.get("updated_at"),
    }


def map_status(twin_status: Optional[str], twin_id: Optional[str]) -> str:
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
        if twin_id:
            latest_run = supabase.table("person_completeness_runs") \
                .select("status") \
                .eq("twin_id", twin_id) \
                .order("created_at", desc=True) \
                .limit(1).execute()
        else:
            latest_run = None

        if latest_run and latest_run.data and latest_run.data[0].get("status") in ["running", "pending"]:
            return "building"
    except Exception:
        pass
    
    return mapped


def _normalize_name(value: Optional[str]) -> str:
    cleaned = " ".join((value or "").strip().split())
    if cleaned.lower().endswith(" (draft)"):
        cleaned = cleaned[:-8].strip()
    return cleaned


def _names_conflict(existing_name: Optional[str], requested_name: Optional[str]) -> bool:
    existing = _normalize_name(existing_name).lower()
    requested = _normalize_name(requested_name).lower()
    if not existing or not requested:
        return False
    return existing != requested


def _score_profile_candidate(twin: Dict[str, Any], user: Dict[str, Any], creator_candidates: set[str]) -> int:
    score = 0
    user_id = str(user.get("user_id") or "").strip()
    creator_id = str(twin.get("creator_id") or "").strip()
    settings = twin.get("settings") or {}
    owner_user_id = str(settings.get("owner_user_id") or "").strip()
    status = str(twin.get("status") or "").strip().lower()

    if owner_user_id and user_id and owner_user_id == user_id:
        score += 100
    if creator_id and user_id and creator_id == user_id:
        score += 80
    if creator_id and creator_id in creator_candidates:
        score += 40
    if status == "active":
        score += 20
    if status == "persona_built":
        score += 10
    return score


def _select_profile_twin_for_user(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tenant_id = user.get("tenant_id")
    user_id = user.get("user_id")
    if not tenant_id:
        return None

    # Pull a bounded set then rank locally so legacy rows still work.
    result = (
        supabase.table("twins")
        .select("*")
        .eq("tenant_id", tenant_id)
        .is_("settings->>deleted_at", "null")
        .order("created_at", desc=True)
        .limit(25)
        .execute()
    )
    twins = result.data or []
    if not twins:
        return None

    creator_candidates = set(derive_creator_ids(user) or [])
    if user_id:
        creator_candidates.add(str(user_id))
    creator_candidates.add(f"tenant_{tenant_id}")

    ranked = sorted(
        twins,
        key=lambda twin: (
            _score_profile_candidate(twin, user, creator_candidates),
            str(twin.get("created_at") or ""),
        ),
        reverse=True,
    )
    if not ranked:
        return None
    return ranked[0]


def get_or_create_profile_for_user(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get existing profile or return None (doesn't create - creation is explicit)."""
    twin = _select_profile_twin_for_user(user)
    if not twin:
        return None
    return map_twin_to_profile(twin)


def _best_effort_delete_by_twin_id(table: str, twin_id: str) -> None:
    try:
        supabase.table(table).delete().eq("twin_id", twin_id).execute()
    except Exception as e:
        logger.warning("Profile reset: failed deleting %s for twin=%s (%s)", table, twin_id, e)


def _best_effort_purge_vectors(twin_id: str) -> None:
    try:
        from modules.clients import get_pinecone_index
        from modules.delphi_namespace import get_namespace_candidates_for_twin

        index = get_pinecone_index()
        for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
            try:
                index.delete(delete_all=True, namespace=namespace)
            except Exception as ns_err:
                logger.warning(
                    "Profile reset: failed deleting Pinecone namespace %s for twin=%s (%s)",
                    namespace,
                    twin_id,
                    ns_err,
                )
    except Exception as e:
        logger.warning("Profile reset: vector purge setup failed for twin=%s (%s)", twin_id, e)


def _safe_update_twin_reset(twin_id: str, payload: Dict[str, Any]) -> None:
    mutable_payload = dict(payload)
    removable_columns = {"status", "is_active"}

    while True:
        try:
            supabase.table("twins").update(mutable_payload).eq("id", twin_id).execute()
            return
        except Exception as e:
            err = str(e).lower()
            removed = None
            for column in list(removable_columns):
                if column in mutable_payload and column in err and (
                    "column" in err or "does not exist" in err or "pgrst204" in err
                ):
                    removed = column
                    break
            if removed:
                mutable_payload.pop(removed, None)
                removable_columns.discard(removed)
                continue
            raise


def _reset_profile_data(twin_id: str) -> None:
    # Child tables first where possible to avoid FK edge cases.
    delete_tables = [
        "person_claim_evidence_spans",
        "person_claims",
        "person_timeline_events",
        "person_topic_profiles",
        "person_contradictions",
        "person_answerability_scores",
        "person_style_profile",
        "person_source_registry",
        "person_completeness_runs",
        "research_claim_web_evidence",
        "research_claim_web_verifications",
        "research_claim_web_verification_status",
        "research_claim_finalizations",
        "research_claim_finalization_status",
        "research_claim_adjudication_events",
        "research_claim_adjudications",
        "research_claim_consistency_actions",
        "research_claim_consistency_issues",
        "research_claim_runtime_publication_audit",
        "research_claim_runtime_retraction_log",
        "research_claim_runtime_claims",
        "research_claim_runtime_publication_status",
        "research_claim_runtime_publication",
        "research_claims",
        "research_runs",
        "crawl_page_classifications",
        "crawl_page_extractions",
        "crawl_pages",
        "crawl_runs",
        "verified_qna_grounding_chunks",
        "verified_qna_summaries",
        "verified_qna",
        "training_decisions",
        "training_interactions",
        "training_sessions",
        "owner_memory_snapshots",
        "owner_memory_entries",
        "memory_events",
        "action_executions",
        "action_drafts",
        "action_triggers",
        "events",
        "tool_connectors",
        "products",
        "escalations",
        "conversations",
        "chunks",
        "sources",
    ]

    for table in delete_tables:
        _best_effort_delete_by_twin_id(table, twin_id)

    # Optional tables that may not exist in all environments.
    try:
        supabase.table("name_deep_research_runs").delete().eq("twin_id", twin_id).execute()
    except Exception as e:
        logger.warning("Profile reset: failed deleting name_deep_research_runs for twin=%s (%s)", twin_id, e)

    try:
        supabase.table("twin_api_keys").delete().eq("twin_id", twin_id).execute()
    except Exception as e:
        logger.warning("Profile reset: failed deleting twin_api_keys for twin=%s (%s)", twin_id, e)

    _best_effort_purge_vectors(twin_id)


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
        # Prevent/repair identity drift on stale drafts.
        requested_name = _normalize_name(request.full_name)
        existing_name = _normalize_name(existing.get("name"))
        if _names_conflict(existing_name, requested_name):
            if existing.get("status") == "draft":
                try:
                    twin_row = (
                        supabase.table("twins")
                        .select("settings")
                        .eq("id", existing["id"])
                        .single()
                        .execute()
                    )
                    current_settings = (twin_row.data or {}).get("settings") or {}
                    merged_settings = {
                        **current_settings,
                        "owner_name": requested_name,
                        "owner_user_id": user_id,
                        "build_mode": request.build_mode,
                    }
                    if request.headline:
                        merged_settings["headline"] = request.headline
                    update_payload = {
                        "name": requested_name,
                        "settings": merged_settings,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                    supabase.table("twins").update(update_payload).eq("id", existing["id"]).execute()
                    refreshed = get_or_create_profile_for_user(user)
                    if refreshed:
                        logger.info(
                            "Profile identity updated on existing draft: user=%s old=%s new=%s",
                            user_id,
                            existing_name,
                            requested_name,
                        )
                        return refreshed
                except Exception as e:
                    logger.warning("Failed to update stale draft identity: %s", e)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Profile identity conflict",
                    "code": "PROFILE_IDENTITY_CONFLICT",
                    "message": (
                        f"Existing profile belongs to '{existing_name}'. "
                        "Reset the profile before switching to a different person."
                    ),
                    "existing_name": existing_name,
                    "requested_name": requested_name,
                },
            )

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
            "owner_user_id": user_id,
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


@router.post("/profile/reset", response_model=ResetProfileResponse)
async def reset_profile(user: dict = Depends(require_tenant)):
    """
    Reset the current user's profile data while keeping the account.

    This keeps the twin identity row but clears accumulated research/knowledge/chat data
    so onboarding can be re-run cleanly.
    """
    profile = get_or_create_profile_for_user(user)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Profile not found", "code": "PROFILE_NOT_FOUND"},
        )

    twin_id = profile["id"]

    try:
        twin_row = (
            supabase.table("twins")
            .select("name, settings")
            .eq("id", twin_id)
            .single()
            .execute()
        )
        current = twin_row.data or {}
        settings = current.get("settings") or {}

        _reset_profile_data(twin_id)

        settings.pop("deleted_at", None)
        settings.pop("deleted_by", None)
        settings.pop("deleted_reason", None)
        settings["is_public"] = False
        settings["reset_at"] = datetime.utcnow().isoformat()
        settings["name_first_state"] = "planning"

        widget_settings = settings.get("widget_settings")
        if not isinstance(widget_settings, dict):
            widget_settings = {}
        widget_settings["public_share_enabled"] = False
        widget_settings.pop("share_token", None)
        widget_settings.pop("share_token_expires_at", None)
        settings["widget_settings"] = widget_settings

        update_payload: Dict[str, Any] = {
            "settings": settings,
            "status": "draft",
            "is_active": False,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if current.get("name"):
            update_payload["description"] = f"{current['name']}'s verified digital profile"

        _safe_update_twin_reset(twin_id, update_payload)

        logger.info("Profile reset completed for twin=%s user=%s", twin_id, user.get("user_id"))
        return ResetProfileResponse(
            profile_id=twin_id,
            status="reset",
            message="Profile has been reset. You can run onboarding again.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to reset profile twin=%s: %s", twin_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Profile reset failed", "code": "PROFILE_RESET_FAILED", "message": str(e)},
        )


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
