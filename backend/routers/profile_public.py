"""
Public Profile Router

Public-safe profile data for share pages.
Never returns private claims, unverified claims, or sensitive data.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List, Optional
import logging

from modules.observability import supabase
from modules.share_links import validate_share_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile-public"])


@router.get("/share/{twin_id}/{token}/profile")
async def get_public_profile(twin_id: str, token: str):
    """
    Get public-safe profile data for a shared profile.
    Validates token and respects public visibility settings.
    """
    # Validate share token
    is_valid = validate_share_token(token, twin_id)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Invalid share token",
                "code": "TOKEN_INVALID",
                "message": "This share link is invalid or has expired."
            }
        )
    
    # Get twin (profile) basic info; tolerate older schemas without twins.is_active.
    try:
        twin_result = supabase.table("twins") \
            .select("name, settings, status, is_active") \
            .eq("id", twin_id).single().execute()
    except Exception as exc:
        msg = str(exc).lower()
        if "is_active" in msg and (
            "does not exist" in msg or "could not find" in msg or "pgrst204" in msg
        ):
            twin_result = supabase.table("twins") \
                .select("name, settings, status") \
                .eq("id", twin_id).single().execute()
        else:
            raise
    
    if not twin_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Profile not found", "code": "PROFILE_NOT_FOUND"}
        )
    
    twin = twin_result.data
    settings = twin.get("settings") or {}
    
    # Check if profile is active/published
    status_value = str(twin.get("status") or "").lower()
    is_published = (twin.get("is_active") is True) or status_value in ["active", "persona_built"]
    if not is_published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Profile not published",
                "code": "PROFILE_NOT_PUBLISHED",
                "message": "This profile is not yet ready for public sharing."
            }
        )
    
    # Get answerability score (public-safe metric)
    answerability_score = 0
    try:
        score_result = supabase.table("person_answerability_scores") \
            .select("answerability_score") \
            .eq("twin_id", twin_id) \
            .eq("scope_type", "global") \
            .eq("scope_key", "global").single().execute()
        if score_result.data:
            answerability_score = score_result.data.get("answerability_score", 0)
    except Exception:
        pass
    
    # Get runtime policies for audience=public
    policies = {
        "require_citation": True,
        "confidence_threshold": 0.5,
    }
    try:
        policy_result = supabase.table("person_runtime_policies") \
            .select("*") \
            .eq("twin_id", twin_id) \
            .eq("is_active", True) \
            .or_("audience.eq.public,audience.is.null") \
            .order("priority", desc=True) \
            .limit(1).execute()
        if policy_result.data:
            policy = policy_result.data[0]
            policies["require_citation"] = policy.get("require_citation", True)
            policies["confidence_threshold"] = policy.get("confidence_threshold_answer", 0.5)
    except Exception:
        pass
    
    # Get public topics (high confidence only)
    public_topics = []
    try:
        topics_result = supabase.table("person_topic_profiles") \
            .select("slug, name, answerability_score") \
            .eq("twin_id", twin_id) \
            .gte("answerability_score", 60) \
            .order("answerability_score", desc=True) \
            .limit(6).execute()
        
        for topic in topics_result.data or []:
            public_topics.append({
                "slug": topic.get("slug"),
                "name": topic.get("name"),
                "answerability_score": topic.get("answerability_score", 0),
            })
    except Exception as e:
        logger.warning(f"Error fetching public topics: {e}")
    
    # Count verified claims (public-safe count only, no details)
    verified_claims_count = 0
    try:
        claims_result = supabase.table("person_claims") \
            .select("id", count="exact") \
            .eq("twin_id", twin_id) \
            .eq("verification_status", "verified") \
            .eq("public_visibility", "public").execute()
        verified_claims_count = claims_result.count or 0
    except Exception:
        pass
    
    # Build response (NO internal IDs, NO private data)
    return {
        "name": twin["name"],
        "headline": settings.get("headline"),
        "answerability_score": answerability_score,
        "verified_claims_count": verified_claims_count,
        "public_topics": public_topics,
        "citations_enabled": policies["require_citation"],
        "confidence_threshold": policies["confidence_threshold"],
        "share_config": {
            "allow_chat": True,
            "show_topics": len(public_topics) > 0,
        }
    }
