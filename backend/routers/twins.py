from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership, resolve_tenant_id
from modules.schemas import (
    TwinSettingsUpdate, GroupCreateRequest, GroupUpdateRequest,
    AssignUserRequest, ContentPermissionRequest,
    AccessGroupSchema, GroupMembershipSchema, ContentPermissionSchema,
    GroupLimitSchema, GroupOverrideSchema
)
from modules.access_groups import (
    get_user_group, get_default_group, create_group, assign_user_to_group,
    add_content_permission, remove_content_permission, get_group_permissions,
    get_groups_for_content, list_groups, get_group, update_group, delete_group,
    get_group_members, set_group_limit, get_group_limits, set_group_override, get_group_overrides
)
from modules.observability import supabase
from modules.specializations import get_specialization, get_all_specializations
from modules.clients import get_pinecone_index
from modules.graph_context import get_graph_stats
from modules.governance import AuditLogger
from modules.tenant_guard import derive_creator_ids
from datetime import datetime

# =============================================================================
# 5-Layer Persona Imports
# =============================================================================
from modules.persona_bootstrap import bootstrap_persona_from_onboarding
from modules.persona_spec_store_v2 import create_persona_spec_v2



router = APIRouter(tags=["twins"])


def ensure_twin_owner_or_403(twin_id: str, user: dict) -> Dict[str, Any]:
    """
    Strict ownership check:
    - 404 if twin does not exist
    - 403 if twin exists but belongs to different tenant
    Returns the twin record.
    """
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="User has no tenant association")
    
    twin_res = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
    if not twin_res.data:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    if twin_res.data.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return twin_res.data


def _require_authenticated_user(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure private twin endpoints fail closed with 401 when auth is missing/invalid."""
    if not isinstance(user, dict) or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ============================================================================
# Twin Create Schema (Updated for 5-Layer Persona)
# ============================================================================

class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None  # IGNORED: server always resolves tenant_id
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None
    # NEW: Structured 5-Layer Persona data from onboarding
    persona_v2_data: Optional[Dict[str, Any]] = None
    # NEW: Mode selector for Link-First vs Manual onboarding
    mode: Optional[str] = None  # "link_first" | "manual" (default: "manual")
    links: Optional[List[str]] = None  # URLs for link-first mode (Mode C)


class DeleteTwinResponse(BaseModel):
    """Response for archive/delete twin operations."""
    status: str  # "archived" | "deleted" | "already_archived" | "not_found"
    twin_id: str
    deleted_at: Optional[str] = None
    cleanup_status: str = "done"  # "done" | "pending"
    message: Optional[str] = None


# ============================================================================
# Specialization Endpoints
# ============================================================================


@router.get("/specializations")
async def list_specializations():
    """List all available specializations for UI selection."""
    return get_all_specializations()


# ============================================================================
# Twin CRUD Endpoints
# ============================================================================

@router.post("/twins")
async def create_twin(request: TwinCreateRequest, user=Depends(get_current_user)):
    """
    Create a new twin with 5-Layer Persona Spec v2.
    
    Supports TWO modes:
    1. MANUAL mode (default): Traditional onboarding flow with 6-step persona builder
       - Creates twin with status="active"
       - Auto-bootstraps 5-Layer Persona from onboarding data
       
    2. LINK-FIRST mode: Ingests external content to build persona from claims
       - Creates twin with status="draft"
       - Skips persona bootstrap (will be built from claims)
       - Links are queued for ingestion via /persona/link-compile endpoints
    
    SECURITY: Client-provided tenant_id is IGNORED.
    Server uses resolve_tenant_id() to determine the correct tenant.
    """
    try:
        user = _require_authenticated_user(user)
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        email = user.get("email", "")
        
        # CRITICAL: Always use resolve_tenant_id - NEVER trust client tenant_id
        # This auto-creates tenant if missing
        tenant_id = resolve_tenant_id(user_id, email)
        requested_name = (request.name or "").strip()
        if not requested_name:
            raise HTTPException(status_code=400, detail="Twin name is required")

        # Log if client sent a different tenant_id (for debugging)
        if request.tenant_id and request.tenant_id != tenant_id:
            print(f"[TWINS] WARNING: Ignoring client tenant_id={request.tenant_id}, using resolved={tenant_id}")

        def _find_existing_active_twin() -> Optional[Dict[str, Any]]:
            existing_res = (
                supabase.table("twins")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("name", requested_name)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            for row in existing_res.data or []:
                if not (row.get("settings") or {}).get("deleted_at"):
                    return row
            return None

        # Idempotency guard: retries from onboarding/network should not create duplicates.
        existing = _find_existing_active_twin()
        if existing:
            print(f"[TWINS] Reusing existing twin {existing.get('id')} for tenant={tenant_id}, name='{requested_name}'")
            return existing
        
        # ====================================================================
        # STEP 1: Create the twin with 5-Layer Persona enabled
        # ====================================================================
        
        # Determine mode: link_first vs manual (default: manual)
        is_link_first = request.mode == "link_first"
        
        # Enhanced settings with 5-Layer Persona configuration
        settings = request.settings or {}
        settings["use_5layer_persona"] = True  # NEW: Always true for new twins
        settings["persona_v2_version"] = "2.0.0"  # NEW: Track persona version
        
        # Store links in settings for link-first mode
        if is_link_first and request.links:
            settings["link_first_urls"] = request.links[:10]  # Max 10 links
        
        # Status based on mode:
        # - manual: active (ready to chat immediately)
        # - link_first: draft (requires ingestion → claims → clarification → active)
        twin_status = "draft" if is_link_first else "active"
        
        data = {
            "name": requested_name,
            "tenant_id": tenant_id,  # Always from resolve_tenant_id
            # Creator ID is the isolation root for Delphi namespace strategy.
            # Use authenticated creator claim first; fallback is deterministic tenant mapping.
            "creator_id": (derive_creator_ids(user) or [f"tenant_{tenant_id}"])[0],
            "description": request.description or f"{requested_name}'s digital twin",
            "specialization": request.specialization,
            "settings": settings,
            "status": twin_status,  # NEW: State machine for link-first
        }

        print(f"[TWINS] Creating twin '{requested_name}' for user={user_id}, tenant={tenant_id}")
        try:
            response = supabase.table("twins").insert(data).execute()
        except Exception as insert_error:
            insert_msg = str(insert_error).lower()
            if "duplicate key" in insert_msg or "already exists" in insert_msg:
                existing_after_race = _find_existing_active_twin()
                if existing_after_race:
                    print(
                        "[TWINS] Detected duplicate create race; returning existing twin "
                        f"{existing_after_race.get('id')}"
                    )
                    return existing_after_race
            raise
        
        if response.data:
            twin = response.data[0]
            twin_id = twin.get('id')
            print(f"[TWINS] Twin created: {twin_id}")
            
            # ====================================================================
            # STEP 2: Auto-Create 5-Layer Persona Spec v2 (MANUAL MODE ONLY)
            # ====================================================================
            
            if not is_link_first:
                # MANUAL MODE: Bootstrap persona from onboarding answers
                try:
                    # Merge persona data from request with defaults
                    onboarding_data = request.persona_v2_data or {}
                    onboarding_data["twin_name"] = requested_name
                    onboarding_data["specialization"] = request.specialization
                    
                    # Bootstrap the structured persona spec
                    persona_spec = bootstrap_persona_from_onboarding(onboarding_data)
                    
                    # Store in persona_specs table as ACTIVE
                    persona_record = create_persona_spec_v2(
                        twin_id=twin_id,
                        tenant_id=tenant_id,
                        created_by=user_id,
                        spec=persona_spec.model_dump(mode="json"),
                        status="active",  # Auto-publish
                        source="onboarding_v2",
                        metadata={
                            "onboarding_version": "2.0",
                            "specialization": request.specialization,
                            "auto_published": True,
                        }
                    )
                    
                    print(f"[TWINS] 5-Layer Persona Spec v2 created and activated: {persona_record.get('id')}")
                    
                    # Add persona info to twin response
                    twin["persona_v2"] = {
                        "id": persona_record.get("id"),
                        "version": "2.0.0",
                        "status": "active",
                        "auto_created": True,
                    }
                    
                except Exception as persona_error:
                    # Log but don't fail twin creation - persona can be created later
                    print(f"[TWINS] WARNING: Failed to auto-create persona spec for twin {twin_id}: {persona_error}")
                    twin["persona_v2_error"] = str(persona_error)
            else:
                # LINK-FIRST MODE: Skip bootstrap - persona will be built from claims
                print(f"[TWINS] Link-first mode: Skipping persona bootstrap for twin {twin_id}")
                print(f"[TWINS] Use /persona/link-compile endpoints to ingest content and build persona")
                twin["link_first"] = {
                    "status": "draft",
                    "links": request.links or [],
                    "next_step": "POST /persona/link-compile/jobs/mode-c (web fetch) or mode-b (paste/import)"
                }
            
            # ====================================================================
            # STEP 3: Auto-Create Default Group
            # ====================================================================
            
            try:
                await create_group(
                    twin_id=twin_id,
                    name="Default Group",
                    description="Standard access group for all content",
                    is_default=True
                )
                print(f"[TWINS] Default group created for twin: {twin_id}")
            except Exception as ge:
                print(f"[TWINS] WARNING: Failed to create default group for twin {twin_id}: {ge}")
                
            return twin
        else:
            raise HTTPException(status_code=400, detail="Failed to create twin")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/twins")
async def list_twins(user=Depends(get_current_user)):
    """List all twins for the authenticated user's tenant (excludes archived)."""
    try:
        user = _require_authenticated_user(user)
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            # User has no tenant - return empty list (not an error)
            return []
        
        # Get twins where tenant_id matches user's tenant
        response = supabase.table("twins").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        
        twins_list = response.data if response.data else []
        
        # Filter out archived twins (those with deleted_at in settings)
        twins_list = [t for t in twins_list if not (t.get("settings") or {}).get("deleted_at")]
        
        print(f"[TWINS] Listing twins for tenant {tenant_id}: found {len(twins_list)}")
        
        return twins_list
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR listing twins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}")
async def get_twin(twin_id: str, user=Depends(get_current_user)):
    """Get a specific twin. Verifies ownership."""
    user = _require_authenticated_user(user)
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    # Use RPC to bypass RLS for system lookup
    response = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Twin not found or access denied")
    return response.data


@router.get("/twins/{twin_id}/sidebar-config")
async def get_sidebar_config(twin_id: str, user=Depends(get_current_user)):
    """Get sidebar configuration based on twin's specialization."""
    user = _require_authenticated_user(user)
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    try:
        # Get twin to find its specialization
        response = supabase.table("twins").select("specialization").eq("id", twin_id).execute()
        if not response.data:
            spec_name = "vanilla"
        else:
            spec_name = response.data[0].get("specialization", "vanilla")
        
        # Get specialization config
        spec = get_specialization(spec_name)
        
        return {
            "sidebar": spec.get("sidebar", []),
            "specialization": spec_name,
            "name": spec.get("name", spec_name)
        }
    except Exception as e:
        print(f"[TWINS] ERROR getting sidebar config: {e}")
        # Return default config on error
        return {
            "sidebar": [
                {"type": "section", "title": "Navigation", "items": [
                    {"type": "link", "label": "Chat", "href": f"/twins/{twin_id}/chat"},
                    {"type": "link", "label": "Knowledge", "href": f"/twins/{twin_id}/knowledge"}
                ]}
            ],
            "specialization": "vanilla",
            "name": "Vanilla"
        }


@router.post("/twins/{twin_id}/settings")
async def update_twin_settings(
    twin_id: str,
    update: TwinSettingsUpdate,
    user=Depends(get_current_user)
):
    """Update twin settings with strict ownership verification."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Merge with existing settings
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        if not twin_res.data:
            raise HTTPException(status_code=404, detail="Twin not found")
        
        existing_settings = twin_res.data.get("settings") or {}
        updated_settings = {**existing_settings}
        
        if update.system_prompt is not None:
            updated_settings["system_prompt"] = update.system_prompt
        if update.handle is not None:
            updated_settings["handle"] = update.handle
        if update.tagline is not None:
            updated_settings["tagline"] = update.tagline
        if update.expertise is not None:
            updated_settings["expertise"] = update.expertise
        if update.personality is not None:
            updated_settings["personality"] = update.personality
        if update.intent_profile is not None:
            updated_settings["intent_profile"] = update.intent_profile
        
        # Update the settings
        response = supabase.table("twins").update({
            "settings": updated_settings
        }).eq("id", twin_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Twin not found or update failed")
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/settings")
async def get_twin_settings(twin_id: str, user=Depends(get_current_user)):
    """Get twin settings."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        response = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Twin not found")
        
        return response.data.get("settings") or {}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/graph-stats")
async def get_twin_graph_stats(twin_id: str, user=Depends(get_current_user)):
    """Get graph statistics for a twin's content."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        stats = await get_graph_stats(twin_id)
        return stats
    except Exception as e:
        print(f"[TWINS] ERROR getting graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Archive / Soft Delete Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/archive", response_model=DeleteTwinResponse)
async def archive_twin(twin_id: str, user=Depends(get_current_user)):
    """
    Archive (soft-delete) a twin.
    Sets deleted_at timestamp in settings; twin remains queryable but hidden from listings.
    """
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Get current settings
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        if not twin_res.data:
            return DeleteTwinResponse(
                status="not_found",
                twin_id=twin_id,
                message="Twin not found"
            )
        
        settings = twin_res.data.get("settings") or {}
        
        # Check if already archived
        if settings.get("deleted_at"):
            return DeleteTwinResponse(
                status="already_archived",
                twin_id=twin_id,
                deleted_at=settings.get("deleted_at"),
                message="Twin is already archived"
            )
        
        # Set deleted_at timestamp
        deleted_at = datetime.utcnow().isoformat()
        settings["deleted_at"] = deleted_at
        
        # Update
        update_res = supabase.table("twins").update({
            "settings": settings
        }).eq("id", twin_id).execute()
        
        if not update_res.data:
            raise HTTPException(status_code=500, detail="Failed to archive twin")
        
        return DeleteTwinResponse(
            status="archived",
            twin_id=twin_id,
            deleted_at=deleted_at,
            message="Twin archived successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR archiving twin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/twins/{twin_id}", response_model=DeleteTwinResponse)
async def delete_twin(twin_id: str, user=Depends(get_current_user)):
    """
    Delete (hard-delete) a twin and all its associated data.
    WARNING: This is destructive and cannot be undone.
    """
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Get twin info for audit log
        twin_res = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
        if not twin_res.data:
            return DeleteTwinResponse(
                status="not_found",
                twin_id=twin_id,
                message="Twin not found"
            )
        
        # Hard delete - remove from database
        delete_res = supabase.table("twins").delete().eq("id", twin_id).execute()
        
        if not delete_res.data:
            raise HTTPException(status_code=500, detail="Failed to delete twin")
        
        # Audit log
        audit_logger = AuditLogger(supabase)
        await audit_logger.log(
            event_type="twin_deleted",
            user_id=user.get("user_id"),
            twin_id=twin_id,
            details={"twin_name": twin_res.data.get("name")}
        )
        
        return DeleteTwinResponse(
            status="deleted",
            twin_id=twin_id,
            cleanup_status="done",
            message="Twin permanently deleted"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR deleting twin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Access Group Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/groups")
async def create_twin_group(
    twin_id: str,
    request: GroupCreateRequest,
    user=Depends(get_current_user)
):
    """Create a new access group for a twin."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        group = await create_group(
            twin_id=twin_id,
            name=request.name,
            description=request.description,
            is_default=request.is_default
        )
        return group
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR creating group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups")
async def list_twin_groups(twin_id: str, user=Depends(get_current_user)):
    """List all access groups for a twin."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        groups = await list_groups(twin_id)
        return {"groups": groups}
    except Exception as e:
        print(f"[TWINS] ERROR listing groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}")
async def get_twin_group(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get a specific access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        return group
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twins/{twin_id}/groups/{group_id}")
async def update_twin_group(
    twin_id: str,
    group_id: str,
    request: GroupUpdateRequest,
    user=Depends(get_current_user)
):
    """Update an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        updated = await update_group(
            group_id=group_id,
            name=request.name,
            description=request.description,
            is_default=request.is_default
        )
        return updated
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR updating group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/twins/{twin_id}/groups/{group_id}")
async def delete_twin_group(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Delete an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        success = await delete_group(group_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete group")
        
        return {"status": "deleted", "group_id": group_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR deleting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twins/{twin_id}/groups/{group_id}/assign")
async def assign_user_to_twin_group(
    twin_id: str,
    group_id: str,
    request: AssignUserRequest,
    user=Depends(get_current_user)
):
    """Assign a user to an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        membership = await assign_user_to_group(
            group_id=group_id,
            user_id=request.user_id,
            role=request.role,
            permissions=request.permissions
        )
        return membership
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR assigning user to group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}/members")
async def get_group_members_list(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get members of an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        members = await get_group_members(group_id)
        return {"members": members}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Content Permission Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/content/{content_id}/permissions")
async def add_content_permissions(
    twin_id: str,
    content_id: str,
    request: ContentPermissionRequest,
    user=Depends(get_current_user)
):
    """Add content permission for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        permission = await add_content_permission(
            content_id=content_id,
            group_id=request.group_id,
            permission_type=request.permission_type,
            config=request.config
        )
        return permission
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR adding content permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/content/{content_id}/permissions")
async def get_content_permissions(twin_id: str, content_id: str, user=Depends(get_current_user)):
    """Get permissions for a content item."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        permissions = await get_group_permissions(content_id)
        return {"permissions": permissions}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting content permissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/twins/{twin_id}/content/{content_id}/permissions/{permission_id}")
async def remove_content_perm(
    twin_id: str,
    content_id: str,
    permission_id: str,
    user=Depends(get_current_user)
):
    """Remove a content permission."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        success = await remove_content_permission(permission_id)
        if not success:
            raise HTTPException(status_code=404, detail="Permission not found")
        return {"status": "removed", "permission_id": permission_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR removing content permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Group Limits Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/groups/{group_id}/limits")
async def set_group_limit_endpoint(
    twin_id: str,
    group_id: str,
    request: GroupLimitSchema,
    user=Depends(get_current_user)
):
    """Set rate and token limits for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        limit = await set_group_limit(
            group_id=group_id,
            rate_limit=request.rate_limit,
            token_limit=request.token_limit,
            reset_period=request.reset_period
        )
        return limit
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR setting group limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}/limits")
async def get_group_limit_endpoint(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get rate and token limits for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        limits = await get_group_limits(group_id)
        return {"limits": limits}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twins/{twin_id}/groups/{group_id}/overrides")
async def set_group_override_endpoint(
    twin_id: str,
    group_id: str,
    request: GroupOverrideSchema,
    user=Depends(get_current_user)
):
    """Set model override for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        override = await set_group_override(
            group_id=group_id,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        return override
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR setting group override: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}/overrides")
async def get_group_override_endpoint(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get model override for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        overrides = await get_group_overrides(group_id)
        return {"overrides": overrides}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group overrides: {e}")
        raise HTTPException(status_code=500, detail=str(e))
