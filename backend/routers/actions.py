from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership
from modules.schemas import (
    EventSchema, ActionTriggerSchema, TriggerCreateRequest, TriggerUpdateRequest,
    ActionDraftSchema, DraftApproveRequest, DraftRejectRequest, DraftRespondRequest,
    ActionExecutionSchema, ToolConnectorSchema, ConnectorCreateRequest, ConnectorTestResponse,
    EventEmitRequest
)
from modules.actions_engine import (
    EventEmitter, TriggerManager, ActionDraftManager, ActionExecutor, ConnectorManager
)
from modules.observability import supabase

router = APIRouter(tags=["actions"])


class ActionExecuteRequest(BaseModel):
    action_type: str = Field(..., description="draft_email|draft_calendar_event|notify_owner|escalate|webhook")
    inputs: dict = Field(default_factory=dict)
    connector_id: Optional[str] = None
    requires_approval: bool = True


class ActionApproveRequest(BaseModel):
    approval_note: Optional[str] = None


class ActionCancelRequest(BaseModel):
    rejection_note: Optional[str] = None


@router.get("/twins/{twin_id}/actions")
async def list_actions_summary(
    twin_id: str,
    limit: int = 50,
    user=Depends(verify_owner),
):
    """
    Twin-scoped summary endpoint for action inbox/history screens.
    """
    verify_twin_ownership(twin_id, user)
    pending = ActionDraftManager.get_pending_drafts(twin_id)
    history = ActionExecutor.get_executions(twin_id=twin_id, limit=max(1, min(limit, 200)))
    return {"active": pending, "history": history}


@router.post("/twins/{twin_id}/actions/execute")
async def execute_twin_action(
    twin_id: str,
    request: ActionExecuteRequest,
    user=Depends(verify_owner),
):
    """
    Create a pending action draft by default. Immediate execution is explicit-only.
    """
    verify_twin_ownership(twin_id, user)

    if request.requires_approval:
        draft_id = ActionDraftManager.create_draft(
            twin_id=twin_id,
            trigger_id=None,
            event_id=None,
            proposed_action={
                "action_type": request.action_type,
                "connector_id": request.connector_id,
                "config": request.inputs or {},
            },
            context={
                "trigger_name": "manual_execute",
                "event_type": "manual",
                "user_message": "manual action execution request",
                "match_conditions": {},
            },
        )
        if not draft_id:
            raise HTTPException(status_code=500, detail="Failed to create action draft")
        return {"status": "pending_approval", "action_id": draft_id}

    execution_id = ActionExecutor.execute_action(
        twin_id=twin_id,
        action_type=request.action_type,
        inputs=request.inputs or {},
        connector_id=request.connector_id,
        executed_by=user.get("user_id"),
    )
    if not execution_id:
        raise HTTPException(status_code=500, detail="Action execution failed")
    return {"status": "executed", "execution_id": execution_id}


@router.post("/twins/{twin_id}/actions/{action_id}/approve")
async def approve_twin_action(
    twin_id: str,
    action_id: str,
    request: ActionApproveRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ok = ActionDraftManager.approve_draft(action_id, user.get("user_id"), request.approval_note)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to approve action")
    return {"status": "approved", "action_id": action_id}


@router.post("/twins/{twin_id}/actions/{action_id}/cancel")
async def cancel_twin_action(
    twin_id: str,
    action_id: str,
    request: ActionCancelRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ok = ActionDraftManager.reject_draft(action_id, user.get("user_id"), request.rejection_note)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to cancel action")
    return {"status": "canceled", "action_id": action_id}

# Events
@router.get("/twins/{twin_id}/events", response_model=List[EventSchema])
async def list_events(twin_id: str, event_type: Optional[str] = None, limit: int = 50, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return EventEmitter.get_recent_events(twin_id, event_type=event_type, limit=limit)

@router.post("/twins/{twin_id}/events")
async def emit_event(twin_id: str, request: EventEmitRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    event_id = EventEmitter.emit(
        twin_id=twin_id,
        event_type=request.event_type,
        payload=request.payload,
        source_context=request.source_context
    )
    if event_id:
        return {"status": "success", "event_id": event_id}
    raise HTTPException(status_code=400, detail="Failed to emit event")

# Triggers
@router.get("/twins/{twin_id}/triggers", response_model=List[ActionTriggerSchema])
async def list_triggers(twin_id: str, include_inactive: bool = False, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return TriggerManager.get_triggers(twin_id, include_inactive=include_inactive)

@router.post("/twins/{twin_id}/triggers")
async def create_trigger(twin_id: str, request: TriggerCreateRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    trigger_id = TriggerManager.create_trigger(
        twin_id=twin_id,
        name=request.name,
        event_type=request.event_type,
        action_type=request.action_type,
        conditions=request.conditions,
        action_config=request.action_config,
        connector_id=request.connector_id,
        requires_approval=request.requires_approval,
        description=request.description
    )
    if trigger_id:
        return {"status": "success", "trigger_id": trigger_id}
    raise HTTPException(status_code=400, detail="Failed to create trigger")

@router.put("/twins/{twin_id}/triggers/{trigger_id}")
async def update_trigger(twin_id: str, trigger_id: str, request: TriggerUpdateRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if TriggerManager.update_trigger(trigger_id, updates):
        return {"status": "success", "message": "Trigger updated"}
    raise HTTPException(status_code=400, detail="Failed to update trigger")

@router.delete("/twins/{twin_id}/triggers/{trigger_id}")
async def delete_trigger(twin_id: str, trigger_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    if TriggerManager.delete_trigger(trigger_id):
        return {"status": "success", "message": "Trigger deleted"}
    raise HTTPException(status_code=404, detail="Trigger not found")

# Action Drafts
@router.get("/twins/{twin_id}/action-drafts", response_model=List[ActionDraftSchema])
async def list_action_drafts(twin_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return ActionDraftManager.get_pending_drafts(twin_id)

@router.get("/twins/{twin_id}/action-drafts-all")
async def list_all_action_drafts(twin_id: str, status: Optional[str] = None, limit: int = 50, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    query = supabase.table("action_drafts").select(
        "*, action_triggers(name, action_type)"
    ).eq("twin_id", twin_id)
    
    if status:
        query = query.eq("status", status)
    
    result = query.order("created_at", desc=True).limit(limit).execute()
    return result.data if result.data else []

@router.get("/twins/{twin_id}/action-drafts/{draft_id}")
async def get_action_draft(twin_id: str, draft_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    draft = ActionDraftManager.get_draft(draft_id)
    if draft:
        return draft
    raise HTTPException(status_code=404, detail="Draft not found")

@router.post("/twins/{twin_id}/action-drafts/{draft_id}/approve")
async def approve_action_draft(twin_id: str, draft_id: str, request: DraftApproveRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    user_id = user.get("user_id")
    if ActionDraftManager.approve_draft(draft_id, user_id, request.approval_note):
        return {"status": "success", "message": "Action approved and executed"}
    raise HTTPException(status_code=400, detail="Failed to approve draft")

@router.post("/twins/{twin_id}/action-drafts/{draft_id}/reject")
async def reject_action_draft(twin_id: str, draft_id: str, request: DraftRejectRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    user_id = user.get("user_id")
    if ActionDraftManager.reject_draft(draft_id, user_id, request.rejection_note):
        return {"status": "success", "message": "Action rejected"}
    raise HTTPException(status_code=400, detail="Failed to reject draft")

@router.post("/twins/{twin_id}/action-drafts/{draft_id}/respond")
async def respond_to_action_draft(twin_id: str, draft_id: str, request: DraftRespondRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    user_id = user.get("user_id")
    result = ActionDraftManager.respond_to_draft(
        draft_id, 
        user_id, 
        request.response_message,
        request.save_as_verified
    )
    if result.get("success"):
        return result
    raise HTTPException(status_code=400, detail=result.get("error", "Failed to respond"))

# Execution Logs
@router.get("/twins/{twin_id}/executions", response_model=List[ActionExecutionSchema])
async def list_executions(twin_id: str, action_type: Optional[str] = None, status: Optional[str] = None, limit: int = 50, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return ActionExecutor.get_executions(twin_id, action_type=action_type, status=status, limit=limit)

@router.get("/twins/{twin_id}/executions/{execution_id}")
async def get_execution_details(twin_id: str, execution_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    execution = ActionExecutor.get_execution_details(execution_id)
    if execution:
        return execution
    raise HTTPException(status_code=404, detail="Execution not found")

# Connectors
@router.get("/twins/{twin_id}/connectors", response_model=List[ToolConnectorSchema])
async def list_connectors(twin_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return ConnectorManager.get_connectors(twin_id)

@router.post("/twins/{twin_id}/connectors")
async def create_connector(twin_id: str, request: ConnectorCreateRequest, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    connector_id = ConnectorManager.create_connector(
        twin_id=twin_id,
        connector_type=request.connector_type,
        name=request.name,
        config=request.config
    )
    if connector_id:
        return {"status": "success", "connector_id": connector_id}
    raise HTTPException(status_code=400, detail="Failed to create connector")

@router.delete("/twins/{twin_id}/connectors/{connector_id}")
async def delete_connector(twin_id: str, connector_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    if ConnectorManager.delete_connector(connector_id):
        return {"status": "success", "message": "Connector deleted"}
    raise HTTPException(status_code=404, detail="Connector not found")

@router.post("/twins/{twin_id}/connectors/{connector_id}/test", response_model=ConnectorTestResponse)
async def test_connector(twin_id: str, connector_id: str, user=Depends(verify_owner)):
    verify_twin_ownership(twin_id, user)
    return ConnectorManager.test_connector(connector_id)
