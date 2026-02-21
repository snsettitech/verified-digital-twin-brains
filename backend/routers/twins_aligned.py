"""
twins_aligned.py

Modified twins router with Link-First architectural alignment.
This file shows the complete modified version for reference.
Apply these changes to backend/routers/twins.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os

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

# 5-Layer Persona Imports
from modules.persona_bootstrap import bootstrap_persona_from_onboarding
from modules.persona_spec_store_v2 import create_persona_spec_v2


router = APIRouter(tags=["twins"])

# Feature flag for Link-First
LINK_FIRST_ENABLED = os.getenv("LINK_FIRST_ENABLED", "false").lower() == "true"


# ============================================================================
# Twin Create Schema (Updated for Link-First Architecture)
# ============================================================================

class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None  # IGNORED: server always resolves tenant_id
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None
    # NEW: Structured 5-Layer Persona data from onboarding
    persona_v2_data: Optional[Dict[str, Any]] = None
    # NEW: Creation mode for Link-First architecture
    creation_mode: str = "manual"  # "manual" | "link_first"


class TwinActivateRequest(BaseModel):
    """Request to activate a link-first twin."""
    final_name: Optional[str] = None  # Optional rename on activation


# ============================================================================
# Twin Creation with State Machine
# ============================================================================

@router.post("/twins")
async def create_twin(request: TwinCreateRequest, user=Depends(get_current_user)):
    """
    Create a new twin with state machine initialization.
    
    Supports two creation modes:
    - manual: Traditional onboarding questionnaire (immediate active)
    - link_first: Content ingestion flow (draft -> ... -> active)
    
    SECURITY: Client-provided tenant_id is IGNORED.
    Server uses resolve_tenant_id() to determine the correct tenant.
    """
    try:
        user = _require_authenticated_user(user)
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        email = user.get("email", "")
        
        # CRITICAL: Always use resolve_tenant_id
        tenant_id = resolve_tenant_id(user_id, email)
        requested_name = (request.name or "").strip()
        if not requested_name:
            raise HTTPException(status_code=400, detail="Twin name is required")

        # Validate creation mode
        creation_mode = request.creation_mode or "manual"
        is_link_first = creation_mode == "link_first"
        
        # Feature flag check
        if is_link_first and not LINK_FIRST_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Link-First Persona is not enabled. Use creation_mode='manual' or contact admin."
            )
        
        # Log if client sent a different tenant_id
        if request.tenant_id and request.tenant_id != tenant_id:
            print(f"[TWINS] WARNING: Ignoring client tenant_id={request.tenant_id}, using resolved={tenant_id}")

        # Check for existing twin
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

        existing = _find_existing_active_twin()
        if existing:
            print(f"[TWINS] Reusing existing twin {existing.get('id')}")
            return existing
        
        # ====================================================================
        # STEP 1: Create twin with appropriate initial state
        # ====================================================================
        
        # Set initial status based on creation mode
        initial_status = "draft" if is_link_first else "active"
        
        settings = request.settings or {}
        settings["use_5layer_persona"] = True
        settings["persona_v2_version"] = "2.0.0"
        settings["creation_mode"] = creation_mode
        
        data = {
            "name": requested_name,
            "tenant_id": tenant_id,
            "creator_id": (derive_creator_ids(user) or [f"tenant_{tenant_id}"])[0],
            "description": request.description or f"{requested_name}'s digital twin",
            "specialization": request.specialization,
            "settings": settings,
            "status": initial_status,
            "creation_mode": creation_mode,
        }

        print(f"[TWINS] Creating twin '{requested_name}' mode={creation_mode} status={initial_status}")
        
        response = supabase.table("twins").insert(data).execute()
        
        if response.data:
            twin = response.data[0]
            twin_id = twin.get('id')
            
            # ====================================================================
            # STEP 2: Mode-specific persona initialization
            # ====================================================================
            
            if is_link_first:
                # Link-First: No persona yet, will be built from claims
                print(f"[TWINS] Link-First twin created in draft: {twin_id}")
                twin["persona_v2"] = {
                    "status": "pending_claims",
                    "message": "Submit content to build persona from claims",
                }
                
                # Add info about next steps
                twin["next_steps"] = {
                    "screen": "/onboarding/link-first/upload",
                    "action": "submit_content",
                }
                
            else:
                # Manual: Bootstrap persona from onboarding data
                try:
                    onboarding_data = request.persona_v2_data or {}
                    onboarding_data["twin_name"] = requested_name
                    onboarding_data["specialization"] = request.specialization
                    
                    persona_spec = bootstrap_persona_from_onboarding(onboarding_data)
                    
                    persona_record = create_persona_spec_v2(
                        twin_id=twin_id,
                        tenant_id=tenant_id,
                        created_by=user_id,
                        spec=persona_spec.model_dump(mode="json"),
                        status="active",
                        source="onboarding_v2",
                        metadata={
                            "onboarding_version": "2.0",
                            "specialization": request.specialization,
                            "auto_published": True,
                            "creation_mode": "manual",
                        }
                    )
                    
                    print(f"[TWINS] Persona created: {persona_record.get('id')}")
                    
                    twin["persona_v2"] = {
                        "id": persona_record.get("id"),
                        "version": "2.0.0",
                        "status": "active",
                        "auto_created": True,
                    }
                    
                except Exception as persona_error:
                    print(f"[TWINS] WARNING: Failed to create persona: {persona_error}")
                    twin["persona_v2_error"] = str(persona_error)
                
                # Create default group for manual twins
                try:
                    await create_group(
                        twin_id=twin_id,
                        name="Default Group",
                        description="Standard access group for all content",
                        is_default=True
                    )
                    print(f"[TWINS] Default group created: {twin_id}")
                except Exception as ge:
                    print(f"[TWINS] WARNING: Failed to create group: {ge}")
            
            return twin
        else:
            raise HTTPException(status_code=400, detail="Failed to create twin")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# State Transition Endpoints
# ============================================================================

@router.post("/twins/{twin_id}/transition/{new_status}")
async def transition_twin_status(
    twin_id: str,
    new_status: str,
    user=Depends(get_current_user),
):
    """
    Transition twin to new status (state machine enforcement).
    
    Valid transitions:
    - draft -> ingesting
    - ingesting -> claims_ready
    - claims_ready -> clarification_pending
    - clarification_pending -> persona_built
    - persona_built -> active
    """
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        "draft": ["ingesting"],
        "ingesting": ["claims_ready"],
        "claims_ready": ["clarification_pending"],
        "clarification_pending": ["persona_built"],
        "persona_built": ["active"],
    }
    
    # Get current status
    twin_res = supabase.table("twins").select("status, creation_mode").eq("id", twin_id).single().execute()
    if not twin_res.data:
        raise HTTPException(404, "Twin not found")
    
    current_status = twin_res.data.get("status")
    creation_mode = twin_res.data.get("creation_mode")
    
    # Validate transition
    if creation_mode != "link_first":
        raise HTTPException(400, "Status transitions only for link_first twins")
    
    allowed_next = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_next:
        raise HTTPException(
            400, 
            f"Invalid transition: {current_status} -> {new_status}. Allowed: {allowed_next}"
        )
    
    # Update status
    supabase.table("twins").update({
        "status": new_status,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", twin_id).execute()
    
    return {
        "twin_id": twin_id,
        "previous_status": current_status,
        "new_status": new_status,
    }


@router.post("/twins/{twin_id}/activate")
async def activate_twin(
    twin_id: str,
    request: TwinActivateRequest = None,
    user=Depends(get_current_user),
):
    """
    Activate a link-first twin (final step in state machine).
    """
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    # Get twin
    twin_res = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
    if not twin_res.data:
        raise HTTPException(404, "Twin not found")
    
    twin = twin_res.data
    
    # Only link_first twins in persona_built state can be activated
    if twin.get("creation_mode") != "link_first":
        raise HTTPException(400, "Only link_first twins need activation")
    
    if twin.get("status") != "persona_built":
        raise HTTPException(
            400, 
            f"Twin must be in 'persona_built' state, currently: {twin.get('status')}"
        )
    
    # Update name if provided
    updates = {
        "status": "active",
        "updated_at": datetime.utcnow().isoformat(),
    }
    
    if request and request.final_name:
        updates["name"] = request.final_name
    
    # Create default group
    try:
        await create_group(
            twin_id=twin_id,
            name="Default Group",
            description="Standard access group for all content",
            is_default=True
        )
    except Exception as e:
        print(f"[Activate] Group creation failed (may exist): {e}")
    
    # Update twin
    result = supabase.table("twins").update(updates).eq("id", twin_id).execute()
    
    return {
        "twin_id": twin_id,
        "status": "active",
        "message": "Twin activated. Chat is now enabled.",
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _require_authenticated_user(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure private twin endpoints fail closed with 401 when auth is missing."""
    if not isinstance(user, dict) or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def ensure_twin_owner_or_403(twin_id: str, user: dict) -> Dict[str, Any]:
    """Strict ownership check."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="User has no tenant association")
    
    twin_res = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
    if not twin_res.data:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    if twin_res.data.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return twin_res.data
