from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from modules.auth_guard import verify_owner, get_current_user
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

router = APIRouter(tags=["twins"])

from modules._core.tenant_guard import verify_twin_access

@router.get("/twins/{twin_id}")
async def get_twin(
    twin_id: str, 
    user=Depends(verify_owner),
    authorized=Depends(verify_twin_access)
):
    # Use RPC to bypass RLS for system lookup
    response = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Twin not found")
    return response.data

@router.patch("/twins/{twin_id}")
async def update_twin(twin_id: str, update: TwinSettingsUpdate, user=Depends(verify_owner)):
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    response = supabase.table("twins").update(update_data).eq("id", twin_id).execute()
    return response.data

# Access Groups Endpoints

@router.get("/twins/{twin_id}/access-groups")
async def list_access_groups(twin_id: str, user=Depends(verify_owner)):
    """List all access groups for a twin."""
    try:
        groups = await list_groups(twin_id)
        return groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twins/{twin_id}/access-groups")
async def create_access_group(twin_id: str, request: GroupCreateRequest, user=Depends(verify_owner)):
    """Create a new access group for a twin."""
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
