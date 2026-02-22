from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from modules.auth_guard import get_current_user
from modules.observability import supabase
from modules.access_groups import (
    add_content_permission,
    assign_user_to_group,
    create_group,
    delete_group,
    get_group,
    get_group_limits,
    get_group_members,
    get_group_overrides,
    get_group_permissions,
    remove_content_permission,
    set_group_limit,
    set_group_override,
)


router = APIRouter(tags=["access-groups"])

ALLOWED_CONTENT_TYPES = {"source", "verified_qna"}
ALLOWED_LIMIT_TYPES = {
    "requests_per_hour",
    "requests_per_day",
    "tokens_per_request",
    "tokens_per_day",
}
ALLOWED_OVERRIDE_TYPES = {"system_prompt", "temperature", "max_tokens", "tool_access"}


class AccessGroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False
    twin_id: Optional[str] = None


class AccessGroupPermissionRequest(BaseModel):
    content_type: str
    content_ids: List[str]


class AccessGroupOverrideRequest(BaseModel):
    override_type: str
    override_value: Any


class GroupMembershipCreateRequest(BaseModel):
    user_id: str
    group_id: str


def _require_authenticated_user(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(user, dict) or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _require_tenant_id(user: Dict[str, Any]) -> str:
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="User has no tenant association")
    return tenant_id


def _verify_twin_belongs_to_tenant_or_403(twin_id: str, tenant_id: str) -> None:
    twin_res = supabase.table("twins").select("id, tenant_id").eq("id", twin_id).single().execute()
    if not twin_res.data:
        raise HTTPException(status_code=404, detail="Twin not found")
    if twin_res.data.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")


async def _get_group_for_tenant_or_403(group_id: str, tenant_id: str) -> Dict[str, Any]:
    group = await get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    _verify_twin_belongs_to_tenant_or_403(str(group.get("twin_id")), tenant_id)
    return group


def _list_twin_ids_for_tenant(tenant_id: str) -> List[str]:
    twins_res = supabase.table("twins").select("id").eq("tenant_id", tenant_id).execute()
    return [str(row["id"]) for row in (twins_res.data or []) if row.get("id")]


@router.get("/access-groups")
async def list_access_groups(user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    twin_ids = _list_twin_ids_for_tenant(tenant_id)
    if not twin_ids:
        return []

    groups_res = (
        supabase.table("access_groups")
        .select("*")
        .in_("twin_id", twin_ids)
        .order("created_at")
        .execute()
    )
    return groups_res.data or []


@router.post("/access-groups")
async def create_access_group(request: AccessGroupCreateRequest, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)

    twin_id = request.twin_id
    if twin_id:
        _verify_twin_belongs_to_tenant_or_403(twin_id, tenant_id)
    else:
        fallback_twin_res = (
            supabase.table("twins")
            .select("id")
            .eq("tenant_id", tenant_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if not fallback_twin_res.data:
            raise HTTPException(
                status_code=400,
                detail="No twin found for tenant. Create a twin before creating access groups.",
            )
        twin_id = str(fallback_twin_res.data[0]["id"])

    group_id = await create_group(
        twin_id=twin_id,
        name=request.name,
        description=request.description,
        is_public=bool(request.is_public),
        is_default=False,
    )
    group = await get_group(group_id)
    return group or {"id": group_id, "twin_id": twin_id, "name": request.name}


@router.get("/access-groups/{group_id}")
async def get_access_group(group_id: str, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    return await _get_group_for_tenant_or_403(group_id, tenant_id)


@router.delete("/access-groups/{group_id}")
async def delete_access_group(group_id: str, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)

    try:
        await delete_group(group_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "deleted", "group_id": group_id}


@router.get("/access-groups/{group_id}/members")
async def get_access_group_members(group_id: str, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)
    return await get_group_members(group_id)


@router.get("/access-groups/{group_id}/permissions")
async def get_access_group_permissions(group_id: str, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)
    return await get_group_permissions(group_id)


@router.post("/access-groups/{group_id}/permissions")
async def add_access_group_permissions(
    group_id: str,
    request: AccessGroupPermissionRequest,
    user=Depends(get_current_user),
):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    group = await _get_group_for_tenant_or_403(group_id, tenant_id)

    if request.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content_type. Allowed values: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )
    if not request.content_ids:
        raise HTTPException(status_code=400, detail="content_ids cannot be empty")

    created = 0
    for content_id in request.content_ids:
        ok = await add_content_permission(
            group_id=group_id,
            content_type=request.content_type,
            content_id=content_id,
            twin_id=str(group.get("twin_id")),
        )
        if ok:
            created += 1

    return {"status": "ok", "created": created}


@router.delete("/access-groups/{group_id}/permissions/{content_type}/{content_id}")
async def remove_access_group_permission(
    group_id: str,
    content_type: str,
    content_id: str,
    user=Depends(get_current_user),
):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content_type. Allowed values: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    await remove_content_permission(group_id=group_id, content_type=content_type, content_id=content_id)
    return {"status": "removed", "group_id": group_id, "content_type": content_type, "content_id": content_id}


@router.get("/access-groups/{group_id}/limits")
async def get_access_group_limits(group_id: str, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)
    return await get_group_limits(group_id)


@router.post("/access-groups/{group_id}/limits")
async def set_access_group_limits(
    group_id: str,
    limit_type: str = Query(...),
    limit_value: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)

    if limit_type not in ALLOWED_LIMIT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid limit_type. Allowed values: {', '.join(sorted(ALLOWED_LIMIT_TYPES))}",
        )

    await set_group_limit(group_id=group_id, limit_type=limit_type, limit_value=limit_value)
    return {"status": "ok", "group_id": group_id, "limit_type": limit_type, "limit_value": limit_value}


@router.get("/access-groups/{group_id}/overrides")
async def get_access_group_overrides(group_id: str, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)
    return await get_group_overrides(group_id)


@router.post("/access-groups/{group_id}/overrides")
async def set_access_group_overrides(
    group_id: str,
    request: AccessGroupOverrideRequest,
    user=Depends(get_current_user),
):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    await _get_group_for_tenant_or_403(group_id, tenant_id)

    if request.override_type not in ALLOWED_OVERRIDE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid override_type. Allowed values: {', '.join(sorted(ALLOWED_OVERRIDE_TYPES))}",
        )

    await set_group_override(
        group_id=group_id,
        override_type=request.override_type,
        override_value=request.override_value,
    )
    return {"status": "ok", "group_id": group_id, "override_type": request.override_type}


@router.post("/twins/{twin_id}/group-memberships")
async def create_group_membership(
    twin_id: str,
    request: GroupMembershipCreateRequest,
    user=Depends(get_current_user),
):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)
    _verify_twin_belongs_to_tenant_or_403(twin_id, tenant_id)

    group = await _get_group_for_tenant_or_403(request.group_id, tenant_id)
    if str(group.get("twin_id")) != twin_id:
        raise HTTPException(status_code=400, detail="group_id does not belong to twin_id")

    await assign_user_to_group(user_id=request.user_id, twin_id=twin_id, group_id=request.group_id)

    membership_res = (
        supabase.table("group_memberships")
        .select("*")
        .eq("user_id", request.user_id)
        .eq("twin_id", twin_id)
        .eq("group_id", request.group_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if membership_res.data:
        return membership_res.data[0]
    return {"status": "assigned", "group_id": request.group_id, "user_id": request.user_id}


@router.delete("/group-memberships/{membership_id}")
async def delete_group_membership(membership_id: str, user=Depends(get_current_user)):
    user = _require_authenticated_user(user)
    tenant_id = _require_tenant_id(user)

    membership_res = (
        supabase.table("group_memberships")
        .select("id, twin_id")
        .eq("id", membership_id)
        .single()
        .execute()
    )
    if not membership_res.data:
        raise HTTPException(status_code=404, detail="Group membership not found")

    twin_id = str(membership_res.data.get("twin_id"))
    _verify_twin_belongs_to_tenant_or_403(twin_id, tenant_id)

    supabase.table("group_memberships").delete().eq("id", membership_id).execute()
    return {"status": "deleted", "membership_id": membership_id}
