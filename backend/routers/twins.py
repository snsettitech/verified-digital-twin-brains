from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
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


router = APIRouter(tags=["twins"])


# ============================================================================
# Twin Create Schema
# ============================================================================

class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None  # IGNORED: server always resolves tenant_id
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None


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
    Create a new twin.
    
    SECURITY: Client-provided tenant_id is IGNORED.
    Server uses resolve_tenant_id() to determine the correct tenant.
    """
    try:
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        email = user.get("email", "")
        
        # CRITICAL: Always use resolve_tenant_id - NEVER trust client tenant_id
        # This auto-creates tenant if missing
        tenant_id = resolve_tenant_id(user_id, email)
        
        # Log if client sent a different tenant_id (for debugging)
        if request.tenant_id and request.tenant_id != tenant_id:
            print(f"[TWINS] WARNING: Ignoring client tenant_id={request.tenant_id}, using resolved={tenant_id}")
        
        # Create the twin with the CORRECT tenant_id
        data = {
            "name": request.name,
            "tenant_id": tenant_id,  # Always from resolve_tenant_id
            "description": request.description or f"{request.name}'s digital twin",
            "specialization": request.specialization,
            "settings": request.settings or {}
        }
        
        print(f"[TWINS] Creating twin '{request.name}' for user={user_id}, tenant={tenant_id}")
        response = supabase.table("twins").insert(data).execute()
        
        if response.data:
            print(f"[TWINS] Twin created: {response.data[0].get('id')}")
            return response.data[0]
        else:
            raise HTTPException(status_code=400, detail="Failed to create twin")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/twins")
async def list_twins(user=Depends(get_current_user)):
    """List all twins for the authenticated user's tenant."""
    try:
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            # User has no tenant - return empty list (not an error)
            return []
        
        # Get twins where tenant_id matches user's tenant
        response = supabase.table("twins").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        
        twins_list = response.data if response.data else []
        print(f"[TWINS] Listing twins for tenant {tenant_id}: found {len(twins_list)}")
        
        return twins_list
    except Exception as e:
        print(f"[TWINS] ERROR listing twins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/twins/{twin_id}")
async def get_twin(twin_id: str, user=Depends(get_current_user)):
    """Get a specific twin. Verifies ownership."""
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
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    try:
        # Get twin to find its specialization
        response = supabase.table("twins").select("specialization").eq("id", twin_id).execute()
        if not response.data:
            spec_name = "vanilla"
        else:
            spec_name = response.data[0].get("specialization", "vanilla")
        
        # Load the specialization and get sidebar config
        spec = get_specialization(spec_name)
        return spec.get_sidebar_config()
    except Exception as e:
        # Fallback to vanilla sidebar
        spec = get_specialization("vanilla")
        return spec.get_sidebar_config()


@router.get("/twins/{twin_id}/graph-stats")
async def get_twin_graph_stats(twin_id: str, user=Depends(get_current_user)):
    """Get graph statistics for a twin (for UI display).
    
    Returns:
        - node_count: Total number of knowledge nodes
        - has_graph: Whether the twin has any graph data
        - top_nodes: Preview of key knowledge items
    """
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    from modules.graph_context import get_graph_stats
    try:
        stats = get_graph_stats(twin_id)
        return stats
    except Exception as e:
        return {
            "node_count": 0,
            "has_graph": False,
            "top_nodes": [],
            "error": str(e)
        }

@router.get("/twins/{twin_id}/graph-job-status")
async def get_graph_job_status(twin_id: str, user=Depends(get_current_user)):
    """Get graph extraction job status for a twin (P0-D).
    
    Returns:
        - last_success: Timestamp of last successful graph extraction
        - last_failure: Timestamp of last failed graph extraction
        - backlog_count: Number of pending/queued jobs
        - recent_errors: List of recent error messages
    """
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    from modules.jobs import JobType, JobStatus, list_jobs
    from modules.observability import supabase
    from datetime import datetime, timedelta
    
    try:
        # Get graph extraction jobs for this twin
        graph_jobs = list_jobs(
            twin_id=twin_id,
            job_type=JobType.GRAPH_EXTRACTION,
            limit=100
        )
        
        # Find last success and last failure
        last_success = None
        last_failure = None
        backlog_count = 0
        recent_errors = []
        
        for job in graph_jobs:
            # Check if completed
            if job.status == JobStatus.COMPLETE:
                if not last_success or (job.completed_at and job.completed_at > last_success):
                    last_success = job.completed_at
            # Check if failed
            elif job.status == JobStatus.FAILED:
                if not last_failure or (job.completed_at and job.completed_at > last_failure):
                    last_failure = job.completed_at
                    if job.error_message:
                        recent_errors.append({
                            "timestamp": job.completed_at.isoformat() if job.completed_at else None,
                            "error": job.error_message
                        })
            # Check if pending/queued
            elif job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
                backlog_count += 1
        
        # Limit recent errors to last 5
        recent_errors = sorted(recent_errors, key=lambda x: x["timestamp"] or "", reverse=True)[:5]
        
        return {
            "last_success": last_success.isoformat() if last_success else None,
            "last_failure": last_failure.isoformat() if last_failure else None,
            "backlog_count": backlog_count,
            "recent_errors": recent_errors
        }
    except Exception as e:
        print(f"Error fetching graph job status: {e}")
        return {
            "last_success": None,
            "last_failure": None,
            "backlog_count": 0,
            "recent_errors": [],
            "error": str(e)
        }

@router.get("/twins/{twin_id}/verification-status")
async def get_twin_verification_status(twin_id: str, user=Depends(get_current_user)):
    """
    Check twin readiness for publishing.
    Verifies vectors, graph nodes, and basic retrieval health.
    """
    verify_twin_ownership(twin_id, user)
    
    status = {
        "vectors_count": 0,
        "graph_nodes": 0,
        "is_ready": False,
        "issues": []
    }
    
    try:
        # 1. Check Vectors in Pinecone
        index = get_pinecone_index()
        p_stats = index.describe_index_stats()
        if twin_id in p_stats.get("namespaces", {}):
            status["vectors_count"] = p_stats["namespaces"][twin_id]["vector_count"]
        
        if status["vectors_count"] == 0:
            status["issues"].append("No knowledge vectors found (upload documents first)")

        # 2. Check Graph Nodes
        try:
            g_stats = get_graph_stats(twin_id)
            status["graph_nodes"] = g_stats.get("node_count", 0)
        except Exception:
            pass # Graph is optional
            
        # 3. Check for recent PASS verification
        # Look for a PASS in the last 24 hours (or just latest)
        try:
            ver_res = supabase.table("twin_verifications") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
                
            last_ver = ver_res.data[0] if ver_res.data else None
            status["last_verified_at"] = last_ver["created_at"] if last_ver else None
            status["last_verified_status"] = last_ver["status"] if last_ver else "NONE"
            
            if not last_ver or last_ver["status"] != "PASS":
                status["issues"].append("Twin has not been verified recently. Run 'Verify Retrieval' in Simulator.")
            else:
                # Valid PASS found
                pass
                
        except Exception as e:
            print(f"[Verification] Error fetching history: {e}")
            status["issues"].append("Could not fetch verification history.")

        # 4. Decision
        # Ready only if vectors > 0 AND latest verification is PASS
        if status["vectors_count"] > 0 and status.get("last_verified_status") == "PASS":
            status["is_ready"] = True
            
        return status
        
    except Exception as e:
        print(f"[Verification] Error checking status: {e}")
        status["issues"].append(f"System error: {str(e)}")
        return status

@router.patch("/twins/{twin_id}")
async def update_twin(twin_id: str, update: TwinSettingsUpdate, user=Depends(verify_owner)):
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    # NEW: Reinforce Publish Gating
    if update_data.get("is_public") is True:
        status = await get_twin_verification_status(twin_id, user)
        if not status.get("is_ready"):
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "Twin cannot be published. Verification required.",
                    "issues": status.get("issues", [])
                }
            )
    
    # Sync is_public with settings.widget_settings.public_share_enabled if present
    if "is_public" in update_data:
        # Fetch current settings 
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        current_settings = twin_res.data.get("settings", {}) if twin_res.data else {}
        
        if "widget_settings" not in current_settings:
            current_settings["widget_settings"] = {}
        
        # Store in two places in settings for redundancy (since top-level column is missing)
        public_val = update_data["is_public"]
        current_settings["widget_settings"]["public_share_enabled"] = public_val
        current_settings["is_public"] = public_val  # Virtual column in settings
        
        # Merge back into update_data
        update_data["settings"] = current_settings
        
        # CRITICAL: Remove is_public from top-level update as column likely doesn't exist
        # This fixes the PGRST204 error
        del update_data["is_public"]

    response = supabase.table("twins").update(update_data).eq("id", twin_id).execute()
    return response.data

# Access Groups Endpoints

@router.get("/twins/{twin_id}/access-groups")
async def list_access_groups(twin_id: str, user=Depends(verify_owner)):
    """List all access groups for a twin."""
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    try:
        groups = await list_groups(twin_id)
        return groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twins/{twin_id}/access-groups")
async def create_access_group(twin_id: str, request: GroupCreateRequest, user=Depends(verify_owner)):
    """Create a new access group for a twin."""
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    try:
        group_id = await create_group(
            twin_id=twin_id,
            name=request.name,
            description=request.description,
            is_public=request.is_public,
            settings=request.settings or {}
        )
        group = await get_group(group_id)
        return group
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/access-groups/{group_id}")
async def get_access_group(group_id: str, user=Depends(get_current_user)):
    """Get access group details."""
    try:
        group = await get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Access group not found")
        return group
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/access-groups/{group_id}")
async def update_access_group(group_id: str, request: GroupUpdateRequest, user=Depends(verify_owner)):
    """Update access group."""
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        await update_group(group_id, updates)
        group = await get_group(group_id)
        return group
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/access-groups/{group_id}")
async def delete_access_group(group_id: str, user=Depends(verify_owner)):
    """Delete an access group (cannot delete default group)."""
    try:
        await delete_group(group_id)
        return {"message": "Access group deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/access-groups/{group_id}/members")
async def list_group_members(group_id: str, user=Depends(get_current_user)):
    """List all members of an access group."""
    try:
        members = await get_group_members(group_id)
        return members
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twins/{twin_id}/group-memberships")
async def assign_user_to_group_endpoint(twin_id: str, request: AssignUserRequest, user=Depends(verify_owner)):
    """Assign user to a group (replaces existing membership for that twin)."""
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    try:
        await assign_user_to_group(request.user_id, twin_id, request.group_id)
        return {"message": "User assigned to group successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/group-memberships/{membership_id}")
async def remove_group_membership(membership_id: str, user=Depends(verify_owner)):
    """Remove user from group (deactivate membership)."""
    try:
        supabase.table("group_memberships").update({"is_active": False}).eq("id", membership_id).execute()
        return {"message": "User removed from group successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/access-groups/{group_id}/permissions")
async def grant_content_permissions(group_id: str, request: ContentPermissionRequest, user=Depends(verify_owner)):
    """Grant group access to content (sources or verified QnA)."""
    try:
        # Get twin_id from group
        group = await get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        twin_id = group["twin_id"]
        
        # Grant permissions for each content_id
        for content_id in request.content_ids:
            await add_content_permission(group_id, request.content_type, content_id, twin_id)
        
        return {"message": f"Granted access to {len(request.content_ids)} content item(s)"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/access-groups/{group_id}/permissions/{content_type}/{content_id}")
async def revoke_content_permission(group_id: str, content_type: str, content_id: str, user=Depends(verify_owner)):
    """Revoke group access to specific content."""
    try:
        await remove_content_permission(group_id, content_type, content_id)
        return {"message": "Permission revoked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/access-groups/{group_id}/permissions")
async def list_group_permissions(group_id: str, user=Depends(get_current_user)):
    """List all content accessible to a group."""
    try:
        permissions = await get_group_permissions(group_id)
        return permissions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/content/{content_type}/{content_id}/groups")
async def get_content_groups(content_type: str, content_id: str, user=Depends(get_current_user)):
    """Get all groups that have access to specific content."""
    try:
        group_ids = await get_groups_for_content(content_type, content_id)
        # Fetch group details
        groups = []
        for gid in group_ids:
            group = await get_group(gid)
            if group:
                groups.append(group)
        return groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/access-groups/{group_id}/limits")
async def set_group_limit_endpoint(
    group_id: str,
    limit_type: str = Query(...),
    limit_value: int = Query(...),
    user=Depends(verify_owner)
):
    """Set a limit for a group."""
    try:
        await set_group_limit(group_id, limit_type, limit_value)
        return {"message": f"Limit {limit_type} set to {limit_value}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/access-groups/{group_id}/limits")
async def list_group_limits(group_id: str, user=Depends(get_current_user)):
    """List all limits for a group."""
    try:
        limits = await get_group_limits(group_id)
        return limits
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/access-groups/{group_id}/overrides")
async def set_group_override_endpoint(group_id: str, request: Dict[str, Any], user=Depends(verify_owner)):
    """
    Set an override for a group.
    Body: { "override_type": "...", "override_value": ... }
    override_type: 'system_prompt', 'temperature', 'max_tokens', 'tool_access'
    """
    try:
        override_type = request.get("override_type")
        override_value = request.get("override_value")
        if not override_type or override_value is None:
            raise HTTPException(status_code=400, detail="override_type and override_value are required")
        await set_group_override(group_id, override_type, override_value)
        return {"message": f"Override {override_type} set successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/access-groups/{group_id}/overrides")
async def list_group_overrides(group_id: str, user=Depends(get_current_user)):
    """List all overrides for a group."""
    try:
        overrides = await get_group_overrides(group_id)
        return overrides
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
