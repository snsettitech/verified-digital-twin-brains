"""
Twin Service Module

Core twin creation and management functionality used by other modules.
Provides a clean interface for creating twins in different modes.
"""

from typing import Any, Dict, Optional
import logging

from modules.observability import supabase
from modules.public_profile_pack import build_research_profile_projection, merge_materialized_profile_settings

logger = logging.getLogger(__name__)


def _is_missing_column_error(error: Exception, column_name: str) -> bool:
    """Detect Supabase/PostgREST missing-column errors across schema variants."""
    message = str(error).lower()
    col = (column_name or "").lower()
    return (
        bool(col)
        and col in message
        and (
            "pgrst204" in message
            or "could not find" in message
            or "column" in message
            or "does not exist" in message
        )
    )


def _is_creation_mode_constraint_error(error: Exception) -> bool:
    """
    Detect environments where twins.creation_mode CHECK still disallows `name_first`.
    """
    message = str(error).lower()
    return (
        "creation_mode" in message
        and (
            "twins_creation_mode_check" in message
            or "violates check constraint" in message
            or "23514" in message
        )
    )


async def create_twin_for_name_research(
    db: Any,
    tenant_id: str,
    user_id: str,
    name: str,
    hints: Dict[str, Optional[str]],
) -> str:
    """
    Create a twin in 'name_first' mode for name-only deep research.
    
    This creates a minimal twin record that will be enriched as the
    deep research pipeline discovers and processes information.
    
    Args:
        db: Database client (supabase)
        tenant_id: The tenant ID
        user_id: The user ID creating the twin
        name: The person's name (used as twin name)
        hints: Optional hints (location, company, website)
        
    Returns:
        The created twin ID
        
    Raises:
        RuntimeError: If twin creation fails
    """
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("name is required for twin creation")
    
    # Check for existing same-name twin owned by this user.
    existing_rows = (
        db.table("twins")
        .select("id, creator_id, settings, created_at")
        .eq("tenant_id", tenant_id)
        .eq("name", normalized_name)
        .is_("settings->>deleted_at", "null")  # Not soft-deleted
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    ).data or []

    user_owned = []
    for row in existing_rows:
        settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
        owner_user_id = str(settings.get("owner_user_id") or "").strip()
        creator_id = str(row.get("creator_id") or "").strip()
        if owner_user_id == user_id or creator_id == user_id:
            user_owned.append(row)

    if user_owned:
        twin_id = user_owned[0]["id"]
        logger.info(
            "Reusing existing user-owned twin for name-research: twin_id=%s tenant_id=%s name=%s",
            twin_id, tenant_id, normalized_name
        )
        return twin_id
    
    # Build settings with name_first metadata
    settings = {
        "use_5layer_persona": True,
        "persona_v2_version": "2.0.0",
        "creation_mode": "name_first",
        "owner_name": normalized_name,
        "owner_user_id": user_id,
        "name_first_hints": {
            "location": hints.get("location"),
            "company": hints.get("company"),
            "website": hints.get("website"),
        },
        "name_first_state": "researching",  # Will progress to "complete"
    }
    
    # Create the twin
    creator_id = user_id or f"tenant_{tenant_id}"
    
    insert_data = {
        "name": normalized_name,
        "tenant_id": tenant_id,
        "creator_id": creator_id,
        "description": f"{normalized_name}'s verified digital profile",
        "settings": settings,
        "status": "draft",  # name_first twins start as draft until research completes
        # Keep name-first semantics in settings; fall back to link_first column value
        # when older CHECK constraints don't allow name_first.
        "creation_mode": "name_first",
        "is_active": False,  # Not active until research completes
    }
    
    # Handle legacy schema by removing unsupported columns if needed
    removed_columns: set[str] = set()
    
    while True:
        try:
            result = db.table("twins").insert(insert_data).execute()
            break
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for missing column errors
            removed_column = None
            for column in ("status", "creation_mode", "is_active"):
                if column in insert_data and _is_missing_column_error(e, column):
                    removed_column = column
                    break
            
            if removed_column:
                removed_columns.add(removed_column)
                insert_data.pop(removed_column, None)
                logger.warning(
                    "Legacy schema detected, retrying without column '%s'", removed_column
                )
                continue

            if (
                "creation_mode" in insert_data
                and str(insert_data.get("creation_mode")).lower() == "name_first"
                and _is_creation_mode_constraint_error(e)
            ):
                insert_data["creation_mode"] = "link_first"
                logger.warning(
                    "twins.creation_mode rejects 'name_first'; retrying with 'link_first' column value"
                )
                continue
            
            # Check for duplicate key race condition
            if "duplicate key" in error_msg or "already exists" in error_msg:
                # Try to fetch a user-owned twin only (avoid same-name cross-user collisions).
                race_rows = (
                    db.table("twins")
                    .select("id, creator_id, settings, created_at")
                    .eq("tenant_id", tenant_id)
                    .eq("name", normalized_name)
                    .is_("settings->>deleted_at", "null")
                    .order("created_at", desc=True)
                    .limit(10)
                    .execute()
                ).data or []

                user_owned_rows = []
                for row in race_rows:
                    settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
                    owner_user_id = str(settings.get("owner_user_id") or "").strip()
                    creator_id = str(row.get("creator_id") or "").strip()
                    if owner_user_id == user_id or creator_id == user_id:
                        user_owned_rows.append(row)

                if not user_owned_rows and len(race_rows) == 1:
                    # Legacy fallback: one unclaimed tenant-scoped profile.
                    # SECURITY FIX: claim ownership immediately so no second user can claim it.
                    row = race_rows[0]
                    settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
                    owner_user_id = str(settings.get("owner_user_id") or "").strip()
                    creator_id = str(row.get("creator_id") or "").strip()
                    if not owner_user_id and creator_id == f"tenant_{tenant_id}":
                        # Claim this twin by writing owner_user_id to prevent another user
                        # from claiming it in a parallel race.
                        claimed_settings = dict(settings)
                        claimed_settings["owner_user_id"] = user_id
                        try:
                            db.table("twins").update({"settings": claimed_settings}).eq("id", row["id"]).execute()
                            logger.warning(
                                "Race condition: claimed unclaimed tenant-scoped twin %s for user %s",
                                row["id"], user_id,
                            )
                        except Exception as claim_err:
                            logger.warning("Could not claim twin %s: %s", row["id"], claim_err)
                        user_owned_rows = [row]

                if user_owned_rows:
                    twin_id = user_owned_rows[0]["id"]
                    logger.info(
                        "Race condition: reusing user-owned twin created by another request: %s", twin_id
                    )
                    return twin_id

                raise RuntimeError(
                    "Failed to create twin: duplicate profile name exists for another user in this tenant"
                )
            
            logger.exception("Failed to create twin for name-research: %s", e)
            raise RuntimeError(f"Failed to create twin: {e}")
    
    if not result.data:
        raise RuntimeError("Failed to create twin: no data returned")
    
    twin_id = result.data[0]["id"]
    logger.info(
        "Created twin for name-research: twin_id=%s tenant_id=%s name=%s",
        twin_id, tenant_id, normalized_name
    )
    
    # Create default group for the twin (fire-and-forget)
    try:
        from modules.access_groups import create_group
        await create_group(
            twin_id=twin_id,
            name="Default Group",
            description="Standard access group for all content",
            is_default=True
        )
        logger.info("Default group created for name-first twin: %s", twin_id)
    except Exception as e:
        logger.warning("Failed to create default group for twin %s: %s", twin_id, e)
    
    return twin_id


async def update_twin_from_research(
    db: Any,
    twin_id: str,
    tenant_id: str,
    research_result: Dict[str, Any],
) -> bool:
    """
    Update a twin with data from completed name-only deep research.
    
    This populates the twin with discovered profile information.
    
    Args:
        db: Database client
        twin_id: The twin ID to update
        tenant_id: The tenant ID
        research_result: The synthesized research result
    """
    try:
        twin_row = (
            db.table("twins")
            .select("id, name, description, settings")
            .eq("id", twin_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not twin_row.data:
            logger.warning("No twin found to update from research: twin_id=%s tenant_id=%s", twin_id, tenant_id)
            return False

        current_settings = twin_row.data[0].get("settings") or {}

        # Extract key information from research result
        claimed_identity = research_result.get("claimed_identity", {})
        bio = research_result.get("bio", {})
        profile = research_result.get("profile_summary", {})
        
        # Build update payload
        update_data: Dict[str, Any] = {}

        merged_settings = {
            **current_settings,
            "use_5layer_persona": True,
            "persona_v2_version": "2.0.0",
            "creation_mode": "name_first",
            "name_first_state": "complete",
            "research_completed_at": research_result.get("crawl_stats", {}).get("run_completed_at"),
        }
        projection = build_research_profile_projection(
            {
                "id": twin_id,
                "name": twin_row.data[0].get("name") or current_settings.get("owner_name") or "",
                "settings": current_settings,
                "description": twin_row.data[0].get("description") or "",
            },
            research_result,
            source_flow="name_first",
        )
        merged_settings = merge_materialized_profile_settings(merged_settings, projection)
        projection_meta = projection.get("public_profile_meta") or {}
        logger.info(
            "name_first materialization complete twin=%s completeness=%s image_status=%s image_source_type=%s",
            twin_id,
            projection_meta.get("completeness_score"),
            projection_meta.get("image_status"),
            projection_meta.get("image_source_type"),
        )
        
        # If we have a canonical name, update the twin name
        canonical_name = claimed_identity.get("canonical_name")
        if canonical_name:
            normalized_name = canonical_name.strip()
            if normalized_name:
                update_data["name"] = normalized_name
                merged_settings["owner_name"] = normalized_name
        
        # Update description with the projected summary if available.
        short_bio = projection.get("description") or bio.get("short")
        if short_bio:
            update_data["description"] = short_bio
        
        # Update specialization if expertise topics found
        expertise_topics = profile.get("expertise_topics", [])
        top_topic = projection.get("specialization") or ""
        if not top_topic and expertise_topics:
            top_topic = expertise_topics[0].get("topic", "")
        if top_topic:
            update_data["specialization"] = top_topic
        
        # Mark as active now that research is complete
        update_data["status"] = "active"
        update_data["is_active"] = True
        update_data["settings"] = merged_settings
        
        # Perform update
        mutable_payload = dict(update_data)
        removable_columns = {"status", "is_active"}
        while True:
            try:
                result = (
                    db.table("twins")
                    .update(mutable_payload)
                    .eq("id", twin_id)
                    .eq("tenant_id", tenant_id)
                    .execute()
                )
                break
            except Exception as update_error:
                err = str(update_error).lower()
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
        
        if result.data:
            logger.info(
                "Updated twin from research: twin_id=%s name=%s",
                twin_id, mutable_payload.get("name", "unchanged")
            )
            return True
        else:
            logger.warning("No twin updated: twin_id=%s tenant_id=%s", twin_id, tenant_id)
            return False
            
    except Exception as e:
        logger.exception("Failed to update twin from research: twin_id=%s error=%s", twin_id, e)
        return False
