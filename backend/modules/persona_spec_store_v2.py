"""
Persona Spec Store V2

Persistence layer for 5-Layer Persona Specs (Version 2).

This module provides:
- CRUD operations for v2 persona specs
- Backward compatibility with v1 specs
- Migration utilities integration
- Feature flag support
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from modules.observability import supabase
from modules.persona_spec_v2 import PersonaSpecV2, next_patch_version, is_v2_spec
from modules.persona_migration import migrate_v1_to_v2, MigrationResult
from modules.persona_spec_store import (
    list_persona_specs as list_v1_specs,
    get_persona_spec as get_v1_persona_spec,
    get_active_persona_spec as get_v1_active_persona_spec,
)


# =============================================================================
# Feature Flags
# =============================================================================

PERSONA_5LAYER_ENABLED = os.getenv("PERSONA_5LAYER_ENABLED", "false").strip().lower() == "true"


def is_5layer_enabled() -> bool:
    """Check if 5-Layer persona system is enabled"""
    return PERSONA_5LAYER_ENABLED


def set_5layer_enabled(enabled: bool):
    """Set 5-Layer persona enabled state (for testing)"""
    global PERSONA_5LAYER_ENABLED
    PERSONA_5LAYER_ENABLED = enabled


# =============================================================================
# V2 Spec CRUD Operations
# =============================================================================

async def list_persona_specs_v2(
    twin_id: str,
    limit: int = 50,
    include_v1: bool = False
) -> List[Dict[str, Any]]:
    """
    List persona specs for a twin
    
    Args:
        twin_id: The twin ID
        limit: Maximum number of specs to return
        include_v1: If True, also include v1 specs (marked with is_v1=True)
    """
    try:
        res = (
            supabase.table("persona_specs")
            .select("*")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        
        specs = res.data or []
        
        # Filter to v2 only unless include_v1
        result = []
        for spec in specs:
            spec_data = spec.get("spec", {})
            if is_v2_spec(spec_data):
                spec["is_v2"] = True
                result.append(spec)
            elif include_v1:
                spec["is_v1"] = True
                result.append(spec)
        
        return result
    except Exception as e:
        print(f"[PersonaSpecV2] list failed: {e}")
        return []


async def get_persona_spec_v2(
    twin_id: str,
    version: str
) -> Optional[PersonaSpecV2]:
    """Get a specific v2 persona spec"""
    try:
        res = (
            supabase.table("persona_specs")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("version", version)
            .single()
            .execute()
        )
        
        if not res.data:
            return None
        
        spec_data = res.data.get("spec", {})
        if not is_v2_spec(spec_data):
            return None
        
        return PersonaSpecV2.model_validate(spec_data)
    except Exception as e:
        print(f"[PersonaSpecV2] get failed: {e}")
        return None


async def get_active_persona_spec_v2(
    twin_id: str,
    auto_migrate: bool = True
) -> Optional[PersonaSpecV2]:
    """
    Get the active v2 persona spec for a twin
    
    Args:
        twin_id: The twin ID
        auto_migrate: If True, auto-migrate v1 to v2 if no v2 exists
    
    Returns:
        PersonaSpecV2 or None
    """
    try:
        # First try to get active v2 spec
        res = (
            supabase.table("persona_specs")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("status", "active")
            .order("published_at", desc=True)
            .limit(5)
            .execute()
        )
        
        data = getattr(res, "data", None)
        if isinstance(data, list):
            # Find first v2 spec
            for row in data:
                spec_data = row.get("spec", {})
                if is_v2_spec(spec_data):
                    return PersonaSpecV2.model_validate(spec_data)
        
        # No v2 spec found - try migration if enabled
        if auto_migrate and data:
            # Get the active v1 spec
            for row in data:
                spec_data = row.get("spec", {})
                if not is_v2_spec(spec_data):
                    # Migrate this v1 spec
                    result = migrate_v1_to_v2(row, add_defaults=True)
                    if result.success and result.v2_spec:
                        print(f"[PersonaSpecV2] Auto-migrated v1 spec to v2 for twin {twin_id}")
                        return result.v2_spec
        
        return None
    except Exception as e:
        print(f"[PersonaSpecV2] get_active failed: {e}")
        return None


async def create_persona_spec_v2(
    twin_id: str,
    tenant_id: Optional[str],
    created_by: str,
    spec: PersonaSpecV2,
    status: str = "draft",
    source: str = "manual",
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a new v2 persona spec
    
    Args:
        twin_id: The twin ID
        tenant_id: Optional tenant ID
        created_by: User ID creating the spec
        spec: The v2 persona spec
        status: "draft", "active", or "archived"
        source: Source of the spec
        notes: Optional notes
    
    Returns:
        Created row or None
    """
    # Ensure version is set
    if not spec.version or not spec.version.startswith("2."):
        # Get latest version for this twin
        latest = await _latest_version_v2(twin_id)
        spec.version = next_patch_version(latest)
    
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "version": spec.version,
        "status": status,
        "spec": spec.model_dump(),
        "source": source,
        "notes": notes,
        "created_by": created_by,
    }
    
    try:
        res = supabase.table("persona_specs").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaSpecV2] create failed: {e}")
        return None


async def update_persona_spec_v2(
    twin_id: str,
    version: str,
    spec: PersonaSpecV2,
    updated_by: str,
) -> Optional[Dict[str, Any]]:
    """Update an existing v2 persona spec (only if draft)"""
    try:
        # Check if spec exists and is draft
        existing = (
            supabase.table("persona_specs")
            .select("status")
            .eq("twin_id", twin_id)
            .eq("version", version)
            .single()
            .execute()
        )
        
        if not existing.data:
            print(f"[PersonaSpecV2] update failed: spec not found")
            return None
        
        if existing.data.get("status") != "draft":
            print(f"[PersonaSpecV2] update failed: can only update draft specs")
            return None
        
        payload = {
            "spec": spec.model_dump(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        res = (
            supabase.table("persona_specs")
            .update(payload)
            .eq("twin_id", twin_id)
            .eq("version", version)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaSpecV2] update failed: {e}")
        return None


async def publish_persona_spec_v2(
    twin_id: str,
    version: str
) -> Optional[Dict[str, Any]]:
    """Publish a v2 persona spec (set as active)"""
    try:
        target = await get_persona_spec_v2(twin_id=twin_id, version=version)
        if not target:
            print(f"[PersonaSpecV2] publish failed: spec not found or not v2")
            return None
        
        # Archive current active
        supabase.table("persona_specs").update({"status": "archived"}).eq(
            "twin_id", twin_id
        ).eq("status", "active").execute()
        
        # Set new active
        res = (
            supabase.table("persona_specs")
            .update({"status": "active", "published_at": datetime.utcnow().isoformat()})
            .eq("twin_id", twin_id)
            .eq("version", version)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaSpecV2] publish failed: {e}")
        return None


async def _latest_version_v2(twin_id: str) -> Optional[str]:
    """Get latest v2 version for a twin"""
    try:
        res = (
            supabase.table("persona_specs")
            .select("version, spec")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        
        if res.data:
            for row in res.data:
                spec = row.get("spec", {})
                if is_v2_spec(spec):
                    return row.get("version")
        return None
    except Exception:
        return None


# =============================================================================
# Unified Interface (v1/v2 Compatible)
# =============================================================================

async def get_active_persona_spec_unified(
    twin_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get active persona spec (v2 if available and enabled, else v1)
    
    This is the main interface for the agent to retrieve persona specs.
    """
    if PERSONA_5LAYER_ENABLED:
        # Try v2 first
        v2_spec = await get_active_persona_spec_v2(twin_id, auto_migrate=True)
        if v2_spec:
            return {
                "version": v2_spec.version,
                "spec": v2_spec.model_dump(),
                "is_v2": True,
            }
    
    # Fall back to v1
    v1_spec = get_v1_active_persona_spec(twin_id)
    if v1_spec:
        v1_spec["is_v1"] = True
        return v1_spec
    
    return None


async def get_persona_spec_unified(
    twin_id: str,
    version: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific persona spec (v2 or v1)
    """
    # Try v2 first
    if version.startswith("2."):
        v2_spec = await get_persona_spec_v2(twin_id, version)
        if v2_spec:
            return {
                "version": version,
                "spec": v2_spec.model_dump(),
                "is_v2": True,
            }
    
    # Fall back to v1
    return get_v1_persona_spec(twin_id, version)


# =============================================================================
# Bootstrap V2 Spec
# =============================================================================

async def bootstrap_persona_spec_v2(
    twin_id: str,
    tenant_id: Optional[str],
    created_by: str
) -> Optional[PersonaSpecV2]:
    """
    Bootstrap a new v2 persona spec from twin settings and memories
    
    This creates a complete 5-Layer spec with defaults.
    """
    from modules.owner_memory_store import list_owner_memories
    
    # Load twin settings
    try:
        res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        settings = (res.data or {}).get("settings", {}) if res.data else {}
    except Exception:
        settings = {}
    
    # Load memories
    memories = list_owner_memories(twin_id=twin_id, status="active", limit=30)
    
    # Build values from memories
    values = []
    priority = 1
    for memory in memories[:10]:
        topic = memory.get("topic_normalized")
        if topic:
            values.append({
                "name": topic,
                "priority": priority,
                "description": memory.get("value", ""),
            })
            priority += 1
    
    # Build spec
    spec = PersonaSpecV2(
        version="2.0.0",
        name=settings.get("persona_name", "Digital Twin"),
        description=settings.get("persona_profile", "Professional and helpful."),
        identity_frame={
            "role_definition": settings.get("persona_profile", "Professional advisor"),
            "expertise_domains": settings.get("expertise_domains", []),
            "background_summary": settings.get("background", ""),
            "reasoning_style": settings.get("reasoning_style", "balanced"),
            "relationship_to_user": settings.get("relationship", "advisor"),
            "communication_tendencies": {
                "directness": settings.get("directness", "moderate"),
                "formality": settings.get("formality", "professional"),
                "verbosity": settings.get("verbosity", "concise"),
            },
        },
        value_hierarchy={
            "values": values if values else [
                {"name": "transparency", "priority": 1, "description": "Open communication"},
                {"name": "quality", "priority": 2, "description": "High standards"},
            ],
        },
    )
    
    # Save
    await create_persona_spec_v2(
        twin_id=twin_id,
        tenant_id=tenant_id,
        created_by=created_by,
        spec=spec,
        status="draft",
        source="bootstrap",
    )
    
    return spec
