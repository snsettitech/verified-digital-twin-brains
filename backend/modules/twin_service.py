"""
Twin Service Module

Core twin creation and management functionality used by other modules.
Provides a clean interface for creating twins in different modes.
"""

from typing import Any, Dict, Optional
import logging

from modules.observability import supabase

logger = logging.getLogger(__name__)


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
    
    # Check for existing twin with same name for this tenant
    existing = (
        db.table("twins")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("name", normalized_name)
        .is_("settings->>deleted_at", "null")  # Not soft-deleted
        .limit(1)
        .execute()
    )
    
    if existing.data:
        twin_id = existing.data[0]["id"]
        logger.info(
            "Reusing existing twin for name-research: twin_id=%s tenant_id=%s name=%s",
            twin_id, tenant_id, normalized_name
        )
        return twin_id
    
    # Build settings with name_first metadata
    settings = {
        "use_5layer_persona": True,
        "persona_v2_version": "2.0.0",
        "creation_mode": "name_first",
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
                if column in insert_data and f"column \"{column}\" does not exist" in error_msg:
                    removed_column = column
                    break
            
            if removed_column:
                removed_columns.add(removed_column)
                insert_data.pop(removed_column, None)
                logger.warning(
                    "Legacy schema detected, retrying without column '%s'", removed_column
                )
                continue
            
            # Check for duplicate key race condition
            if "duplicate key" in error_msg or "already exists" in error_msg:
                # Try to fetch the existing twin
                race_check = (
                    db.table("twins")
                    .select("id")
                    .eq("tenant_id", tenant_id)
                    .eq("name", normalized_name)
                    .limit(1)
                    .execute()
                )
                if race_check.data:
                    twin_id = race_check.data[0]["id"]
                    logger.info(
                        "Race condition: reusing twin created by another request: %s", twin_id
                    )
                    return twin_id
            
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
) -> None:
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
        # Extract key information from research result
        claimed_identity = research_result.get("claimed_identity", {})
        bio = research_result.get("bio", {})
        profile = research_result.get("profile_summary", {})
        
        # Build update payload
        update_data: Dict[str, Any] = {
            "settings": {
                "use_5layer_persona": True,
                "persona_v2_version": "2.0.0",
                "creation_mode": "name_first",
                "name_first_state": "complete",
                "research_completed_at": research_result.get("crawl_stats", {}).get("run_completed_at"),
            }
        }
        
        # If we have a canonical name, update the twin name
        canonical_name = claimed_identity.get("canonical_name")
        if canonical_name:
            update_data["name"] = canonical_name
        
        # Update description with bio if available
        short_bio = bio.get("short")
        if short_bio:
            update_data["description"] = short_bio
        
        # Update specialization if expertise topics found
        expertise_topics = profile.get("expertise_topics", [])
        if expertise_topics:
            # Take top topic as specialization
            top_topic = expertise_topics[0].get("topic", "")
            if top_topic:
                update_data["specialization"] = top_topic
        
        # Mark as active now that research is complete
        update_data["status"] = "active"
        update_data["is_active"] = True
        
        # Perform update
        result = (
            db.table("twins")
            .update(update_data)
            .eq("id", twin_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        
        if result.data:
            logger.info(
                "Updated twin from research: twin_id=%s name=%s",
                twin_id, update_data.get("name", "unchanged")
            )
        else:
            logger.warning("No twin updated: twin_id=%s tenant_id=%s", twin_id, tenant_id)
            
    except Exception as e:
        logger.exception("Failed to update twin from research: twin_id=%s error=%s", twin_id, e)
        # Don't raise - this is a best-effort update
