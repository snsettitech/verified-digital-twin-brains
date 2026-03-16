"""
Public Profile Router

Public-safe profile data for share pages and the public marketplace.
Never returns private claims, unverified claims, or sensitive data.
"""

from collections import Counter, defaultdict
from fastapi import APIRouter, HTTPException, Query, status
from typing import Dict, Any, List, Optional
import logging

from modules.observability import supabase
from modules.public_profile_pack import (
    build_marketplace_persona_payload,
    build_public_profile_pack,
)
from modules.share_links import (
    build_public_share_path,
    is_marketplace_public_twin_record,
    validate_share_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile-public"])


def _missing_column_error(exc: Exception, column_name: str) -> bool:
    message = str(exc).lower()
    return column_name in message and (
        "does not exist" in message
        or "could not find" in message
        or "pgrst204" in message
    )


def _fetch_public_twin(twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("twins")
            .select("id, name, settings, status, is_active")
            .eq("id", twin_id)
            .single()
            .execute()
        )
    except Exception as exc:
        if _missing_column_error(exc, "is_active"):
            result = (
                supabase.table("twins")
                .select("id, name, settings, status")
                .eq("id", twin_id)
                .single()
                .execute()
            )
        else:
            raise
    return result.data or None


def _fetch_marketplace_twin_rows() -> List[Dict[str, Any]]:
    base_fields = "id, name, settings, status, created_at"
    try:
        result = (
            supabase.table("twins")
            .select(f"{base_fields}, is_active, updated_at")
            .execute()
        )
    except Exception as exc:
        if _missing_column_error(exc, "is_active"):
            try:
                result = (
                    supabase.table("twins")
                    .select(f"{base_fields}, updated_at")
                    .execute()
                )
            except Exception as nested_exc:
                if _missing_column_error(nested_exc, "updated_at"):
                    result = (
                        supabase.table("twins")
                        .select(base_fields)
                        .execute()
                    )
                else:
                    raise
        elif _missing_column_error(exc, "updated_at"):
            try:
                result = (
                    supabase.table("twins")
                    .select(f"{base_fields}, is_active")
                    .execute()
                )
            except Exception as nested_exc:
                if _missing_column_error(nested_exc, "is_active"):
                    result = (
                        supabase.table("twins")
                        .select(base_fields)
                        .execute()
                    )
                else:
                    raise
        else:
            raise
    return result.data or []


def _normalize_public_profile(twin: Dict[str, Any]) -> Dict[str, Any]:
    settings = twin.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    public_profile = settings.get("public_profile") or {}
    if not isinstance(public_profile, dict):
        public_profile = {}

    tagline = settings.get("tagline") if isinstance(settings.get("tagline"), str) else ""
    public_intro = settings.get("public_intro") if isinstance(settings.get("public_intro"), str) else ""
    display_name = (
        str(public_profile.get("display_name") or "").strip()
        or str(twin.get("name") or "").strip()
        or "Persona"
    )
    organization = str(public_profile.get("organization") or "").strip()
    role = str(public_profile.get("role") or "").strip()
    headline = str(public_profile.get("headline") or "").strip() or tagline
    bio = str(public_profile.get("bio") or "").strip() or public_intro
    avatar_url = str(public_profile.get("avatar_url") or "").strip()
    mind_label = str(public_profile.get("mind_label") or "").strip()
    pinned = public_profile.get("pinned_questions") if isinstance(public_profile.get("pinned_questions"), list) else []
    pinned_questions = [
        str(item).strip()
        for item in pinned
        if isinstance(item, str) and str(item).strip()
    ][:3]

    return {
        "display_name": display_name,
        "organization": organization,
        "role": role,
        "headline": headline,
        "bio": bio,
        "avatar_url": avatar_url,
        "mind_label": mind_label,
        "pinned_questions": pinned_questions,
        "handle": str(settings.get("handle") or "").strip(),
        "settings": settings,
    }


def _coerce_score(value: Any) -> float:
    try:
        score = float(value or 0)
        if score <= 1.0:
            score *= 100.0
        return max(0.0, min(score, 100.0))
    except Exception:
        return 0.0


def _marketplace_search_blob(item: Dict[str, Any]) -> str:
    topic_names = " ".join(
        f"{topic.get('name', '')} {topic.get('slug', '')}".strip()
        for topic in item.get("public_topics", [])
    )
    expertise = " ".join(str(value or "") for value in item.get("areas_of_expertise", []))
    return " ".join(
        [
            str(item.get("display_name") or ""),
            str(item.get("occupation") or ""),
            str(item.get("headline") or ""),
            str(item.get("bio") or ""),
            str(item.get("short_description") or ""),
            str(item.get("organization") or ""),
            str(item.get("role") or ""),
            str(item.get("handle") or ""),
            expertise,
            topic_names,
        ]
    ).lower()


def _get_score_rows(twin_ids: List[str]) -> Dict[str, float]:
    if not twin_ids:
        return {}
    try:
        result = (
            supabase.table("person_answerability_scores")
            .select("twin_id, answerability_score")
            .in_("twin_id", twin_ids)
            .eq("scope_type", "global")
            .eq("scope_key", "global")
            .execute()
        )
        return {
            row.get("twin_id"): _coerce_score(row.get("answerability_score"))
            for row in (result.data or [])
            if row.get("twin_id")
        }
    except Exception as exc:
        logger.warning("Error fetching marketplace answerability scores: %s", exc)
        return {}


def _get_public_topics(twin_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not twin_ids:
        return {}
    result = None
    slug_key = "slug"
    name_key = "name"
    topic_select_variants = [
        ("twin_id, slug, name, answerability_score", "slug", "name"),
        ("twin_id, topic_slug, name, answerability_score", "topic_slug", "name"),
        ("twin_id, topic_slug, topic_name, answerability_score", "topic_slug", "topic_name"),
    ]

    last_exc: Optional[Exception] = None
    for select_clause, slug_key, name_key in topic_select_variants:
        try:
            result = (
                supabase.table("person_topic_profiles")
                .select(select_clause)
                .in_("twin_id", twin_ids)
                .gte("answerability_score", 60)
                .order("answerability_score", desc=True)
                .execute()
            )
            break
        except Exception as exc:
            last_exc = exc
            if not any(
                _missing_column_error(exc, column_name)
                for column_name in ("slug", "topic_slug", "name", "topic_name")
            ):
                logger.warning("Error fetching marketplace public topics: %s", exc)
                return {}

    if result is None:
        if last_exc:
            logger.warning("Error fetching marketplace public topics: %s", last_exc)
        return {}

    topics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in result.data or []:
        twin_id = row.get("twin_id")
        if not twin_id:
            continue
        topics[twin_id].append(
            {
                "slug": row.get(slug_key) or row.get("slug") or row.get("topic_slug"),
                "name": row.get(name_key) or row.get("name") or row.get("topic_name") or row.get(slug_key),
                "answerability_score": _coerce_score(row.get("answerability_score")),
            }
        )
    return topics


def _get_verified_claim_counts(twin_ids: List[str]) -> Dict[str, int]:
    if not twin_ids:
        return {}
    try:
        result = (
            supabase.table("person_claims")
            .select("twin_id")
            .in_("twin_id", twin_ids)
            .eq("verification_status", "verified")
            .eq("public_visibility", "public")
            .execute()
        )
    except Exception as exc:
        logger.warning("Error fetching marketplace verified claim counts: %s", exc)
        return {}

    counts: Dict[str, int] = Counter()
    for row in result.data or []:
        twin_id = row.get("twin_id")
        if twin_id:
            counts[twin_id] += 1
    return dict(counts)


@router.get("/public/marketplace")
async def get_public_marketplace(
    q: str = Query("", max_length=200),
    topic: Optional[str] = Query(None, max_length=120),
    cursor: Optional[str] = Query(None),
    limit: int = Query(24, ge=1, le=60),
):
    """
    Public marketplace listing of eligible personas across all tenants.

    V1 treats every non-archived active/persona_built twin as publicly
    discoverable, regardless of the legacy direct-share toggle.
    """
    twin_rows = [row for row in _fetch_marketplace_twin_rows() if is_marketplace_public_twin_record(row)]
    twin_ids = [row.get("id") for row in twin_rows if row.get("id")]

    score_map = _get_score_rows(twin_ids)
    topics_map = _get_public_topics(twin_ids)
    claims_map = _get_verified_claim_counts(twin_ids)

    items: List[Dict[str, Any]] = []
    normalized_query = q.strip().lower()
    normalized_topic = topic.strip().lower() if isinstance(topic, str) and topic.strip() else None

    for twin in twin_rows:
        twin_id = twin.get("id")
        if not twin_id:
            continue

        public_topics = topics_map.get(twin_id, [])[:6]
        item = build_marketplace_persona_payload(
            twin,
            public_topics=public_topics,
            answerability_score=score_map.get(twin_id, 0.0),
            verified_claims_count=claims_map.get(twin_id, 0),
        )
        item["updated_at"] = twin.get("updated_at") or twin.get("created_at") or ""
        item["settings"] = _normalize_public_profile(twin)["settings"]

        if normalized_topic:
            topic_slugs = {str(entry.get("slug") or "").lower() for entry in public_topics}
            if normalized_topic not in topic_slugs:
                continue

        if normalized_query and normalized_query not in _marketplace_search_blob(item):
            continue

        items.append(item)

    items.sort(
        key=lambda row: (
            float(row.get("answerability_score") or 0.0),
            int(row.get("verified_claims_count") or 0),
            str(row.get("updated_at") or ""),
        ),
        reverse=True,
    )

    topic_counter: Counter = Counter()
    topic_labels: Dict[str, str] = {}
    for item in items:
        for topic_entry in item.get("public_topics", []):
            slug = str(topic_entry.get("slug") or "").strip().lower()
            name = str(topic_entry.get("name") or "").strip() or slug
            if not slug:
                continue
            topic_counter[slug] += 1
            topic_labels[slug] = name

    try:
        offset = max(int(cursor or "0"), 0)
    except ValueError:
        offset = 0

    page_items = items[offset : offset + limit]
    next_cursor = str(offset + limit) if offset + limit < len(items) else None

    for item in page_items:
        public_url = build_public_share_path(
            item["twin_id"],
            item.get("settings"),
            ensure_token_if_missing=True,
            enable_public_share=False,
        )
        item["public_url"] = public_url
        item.pop("settings", None)
        item.pop("updated_at", None)

    return {
        "items": page_items,
        "facets": {
            "topics": [
                {"slug": slug, "name": topic_labels.get(slug, slug), "count": count}
                for slug, count in topic_counter.most_common(12)
            ]
        },
        "next_cursor": next_cursor,
    }


@router.get("/share/{twin_id}/{token}/profile")
async def get_public_profile(twin_id: str, token: str):
    """
    Get public-safe profile data for a shared profile.
    Validates token and respects public visibility settings.
    """
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

    twin = _fetch_public_twin(twin_id)
    if not twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Profile not found", "code": "PROFILE_NOT_FOUND"}
        )

    settings = twin.get("settings") or {}
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

    policies = {
        "require_citation": True,
        "confidence_threshold": 0.5,
    }
    try:
        policy_result = (
            supabase.table("person_runtime_policies")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("is_active", True)
            .or_("audience.eq.public,audience.is.null")
            .order("priority", desc=True)
            .limit(1)
            .execute()
        )
        if policy_result.data:
            policy = policy_result.data[0]
            policies["require_citation"] = policy.get("require_citation", True)
            policies["confidence_threshold"] = policy.get("confidence_threshold_answer", 0.5)
    except Exception:
        pass

    profile_pack = build_public_profile_pack(twin)
    profile_pack["citations_enabled"] = policies["require_citation"]
    profile_pack["confidence_threshold"] = policies["confidence_threshold"]
    profile_pack["share_config"] = {
        "allow_chat": True,
        "show_topics": len(profile_pack.get("public_topics") or []) > 0,
    }

    return profile_pack
