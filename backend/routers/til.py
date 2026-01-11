# backend/routers/til.py
"""TIL (Today I Learned) Feed Router

Provides endpoints for viewing and managing memory events.
Users can confirm, edit, or delete memories from their daily learning feed.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.memory_events import (
    get_til_feed, get_memory_events, 
    create_memory_event, update_memory_event
)
from modules.observability import supabase

router = APIRouter(tags=["til"])


class EditMemoryRequest(BaseModel):
    """Request body for editing a memory."""
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class ConfirmMemoryRequest(BaseModel):
    """Request body for confirming a memory."""
    notes: Optional[str] = None


@router.get("/twins/{twin_id}/til")
async def get_til_feed_endpoint(
    twin_id: str, 
    days: int = 1,
    user=Depends(get_current_user)
):
    """
    Get TIL (Today I Learned) feed for a twin.
    
    Returns recent memory events with human-readable summaries.
    """
    verify_twin_ownership(twin_id, user)
    
    try:
        events = await get_til_feed(twin_id, days=days)
        return {
            "twin_id": twin_id,
            "events": events,
            "count": len(events)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch TIL feed: {e}")


@router.get("/twins/{twin_id}/memory-events")
async def list_memory_events_endpoint(
    twin_id: str,
    limit: int = 50,
    event_type: Optional[str] = None,
    user=Depends(get_current_user)
):
    """
    List all memory events for a twin.
    
    Optional filters:
    - limit: Max events to return
    - event_type: Filter by type (auto_extract, manual_edit, confirm, delete)
    """
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    try:
        events = await get_memory_events(twin_id, limit=limit, event_type=event_type)
        return {
            "twin_id": twin_id,
            "events": events,
            "count": len(events)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch memory events: {e}")


@router.post("/twins/{twin_id}/til/{node_id}/confirm")
async def confirm_memory_endpoint(
    twin_id: str,
    node_id: str,
    request: ConfirmMemoryRequest = None,
    user=Depends(get_current_user)
):
    """
    Confirm a memory node.
    
    Creates a 'confirm' MemoryEvent to record the confirmation.
    """
    verify_twin_ownership(twin_id, user)
    tenant_id = user.get("tenant_id")
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID required")
    
    try:
        # Create confirm event
        event = await create_memory_event(
            twin_id=twin_id,
            tenant_id=tenant_id,
            event_type="confirm",
            payload={
                "node_id": node_id,
                "notes": request.notes if request else None,
                "confirmed_by": user.get("user_id")
            },
            status="applied"
        )
        
        # Optionally update node confidence or status
        # (Could increase weight/confidence of the node)
        
        return {
            "success": True,
            "message": "Memory confirmed",
            "event_id": event["id"] if event else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm memory: {e}")


@router.put("/twins/{twin_id}/til/{node_id}")
async def edit_memory_endpoint(
    twin_id: str,
    node_id: str,
    request: EditMemoryRequest,
    user=Depends(get_current_user)
):
    """
    Edit a memory node.
    
    Creates a 'manual_edit' MemoryEvent and updates the node.
    """
    verify_twin_ownership(twin_id, user)
    tenant_id = user.get("tenant_id")
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID required")
    
    try:
        # Get original node data for diff
        original_res = supabase.table("nodes").select("*").eq("id", node_id).eq("twin_id", twin_id).single().execute()
        
        if not original_res.data:
            raise HTTPException(status_code=404, detail="Node not found")
        
        original = original_res.data
        
        # Build update payload
        update_data = {}
        if request.name:
            update_data["name"] = request.name
        if request.description:
            update_data["description"] = request.description
        if request.properties:
            update_data["properties"] = request.properties
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No changes provided")
        
        # Create manual_edit event BEFORE updating
        event = await create_memory_event(
            twin_id=twin_id,
            tenant_id=tenant_id,
            event_type="manual_edit",
            payload={
                "node_id": node_id,
                "original": {
                    "name": original.get("name"),
                    "description": original.get("description"),
                    "properties": original.get("properties")
                },
                "changes": update_data,
                "edited_by": user.get("user_id")
            },
            status="applied"
        )
        
        # Update the node
        supabase.table("nodes").update(update_data).eq("id", node_id).eq("twin_id", twin_id).execute()
        
        return {
            "success": True,
            "message": "Memory updated",
            "event_id": event["id"] if event else None,
            "changes": update_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to edit memory: {e}")


@router.delete("/twins/{twin_id}/til/{node_id}")
async def delete_memory_endpoint(
    twin_id: str,
    node_id: str,
    user=Depends(get_current_user)
):
    """
    Delete a memory node.
    
    Creates a 'delete' MemoryEvent for audit trail, then archives the node.
    """
    verify_twin_ownership(twin_id, user)
    tenant_id = user.get("tenant_id")
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID required")
    
    try:
        # Get node data for audit
        node_res = supabase.table("nodes").select("*").eq("id", node_id).eq("twin_id", twin_id).single().execute()
        
        if not node_res.data:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = node_res.data
        
        # Create delete event
        event = await create_memory_event(
            twin_id=twin_id,
            tenant_id=tenant_id,
            event_type="delete",
            payload={
                "node_id": node_id,
                "deleted_node": {
                    "name": node.get("name"),
                    "type": node.get("type"),
                    "description": node.get("description")
                },
                "deleted_by": user.get("user_id")
            },
            status="applied"
        )
        
        # Archive node (soft delete)
        supabase.table("nodes").update({"status": "archived"}).eq("id", node_id).eq("twin_id", twin_id).execute()
        
        return {
            "success": True,
            "message": "Memory deleted",
            "event_id": event["id"] if event else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {e}")
