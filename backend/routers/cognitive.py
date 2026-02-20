# backend/routers/cognitive.py
"""Cognitive Brain interview endpoints.

Integrates the Host and Scribe engines for structured knowledge elicitation:
- Host engine: determines next slot to fill based on host_policy.json
- Scribe engine: extracts structured output from conversation turns

Endpoints:
- POST /cognitive/interview/{twin_id}: Start or continue a cognitive interview
- GET /cognitive/graph/{twin_id}: Get the current cognitive graph state
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json

from modules.auth_guard import get_current_user, require_twin_access, require_tenant, verify_twin_ownership
from modules.governance import AuditLogger

from modules.observability import supabase, get_messages, log_interaction, create_conversation
from modules.agent import run_agent_stream
from modules._core.host_engine import get_next_slot, get_next_question, process_turn, generate_contextual_question
from modules._core.interview_controller import InterviewController, InterviewStage, INTENT_QUESTIONS
from modules._core.scribe_engine import extract_structured_output, score_confidence, detect_contradictions, extract_for_slot
from modules._core.response_evaluator import ResponseEvaluator
from modules._core.repair_strategies import RepairManager
from modules._core.registry_loader import get_specialization_manifest
from modules._core.interview_controller import InterviewController, InterviewStage
from modules.specializations import get_specialization
from langchain_core.messages import AIMessage

router = APIRouter(tags=["cognitive"])


class InterviewRequest(BaseModel):
    """Request for cognitive interview turn."""
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None  # Interview session ID
    current_slot: Optional[str] = None  # Which slot we're currently filling
    metadata: Optional[Dict[str, Any]] = None


class InterviewResponse(BaseModel):
    """Response from cognitive interview turn."""
    response: str
    conversation_id: str
    session_id: Optional[str] = None  # Interview session ID
    stage: str = "opening"  # Current interview stage
    intent_summary: Optional[str] = None  # For confirmation stage
    next_slot: Optional[Dict[str, Any]] = None  # Host's suggested next slot
    suggested_question: Optional[str] = None  # Question template for next slot
    follow_up_question: Optional[str] = None  # Follow-up if response is vague
    extracted_data: Optional[Dict[str, Any]] = None  # Scribe's structured output
    confidence: float = 0.0
    contradictions: List[Dict[str, Any]] = []
    missing_slots: List[Dict[str, Any]] = []
    progress: Dict[str, Any] = {}  # { "intent_complete": bool, "slots_filled": 5, "total_slots": 12 }


class ApproveProfileRequest(BaseModel):
    """Optional approval metadata for compatibility endpoint."""
    notes: Optional[str] = None


def _load_host_policy(spec_name: str) -> Dict[str, Any]:
    """Load host policy from specialization manifest."""
    from pathlib import Path
    try:
        manifest = get_specialization_manifest(spec_name)
        policy_path = manifest.get("host_policy")
        if policy_path:
            backend_base = Path(__file__).parent.parent
            full_path = backend_base / policy_path
            if full_path.is_file():
                with full_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load host policy: {e}")
    return {}


@router.post("/cognitive/interview/{twin_id}", response_model=InterviewResponse)
async def cognitive_interview(
    twin_id: str,
    request: InterviewRequest,
    user=Depends(require_tenant)
):
    spec = get_specialization()
    host_policy = _load_host_policy(spec.name)

    # Validate twin belongs to tenant and get user context
    twin = require_twin_access(twin_id, user)
    tenant_id = user["tenant_id"]


    # Get or create conversation

    conversation_id = request.conversation_id
    if not conversation_id:
        conv_obj = create_conversation(twin_id, user.get("user_id") if user else None)
        conversation_id = conv_obj["id"]

    # Get or create interview session
    session = InterviewController.get_or_create_session(twin_id, conversation_id)
    session_id = session.get("id")

    # Load specialization and host policy
    # Assuming twin has 'specialization_name' or similar, defaulting to 'vanilla'
    # In a real implementation we would fetch this from the twin metadata
    spec_name = twin.get("specialization", "vanilla")
    from modules.specializations import get_specialization
    spec = get_specialization(spec_name)
    host_policy = _load_host_policy(spec_name)

    stage = InterviewController.get_stage(session)
    stage_label = stage.value.upper()
    
    # Get conversation history
    history = get_messages(conversation_id)
    
    # Fetch existing nodes
    existing_nodes = []
    intent_nodes = []
    filled_slots = {}
    try:
        nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 100}).execute()
        existing_nodes = nodes_res.data or []
        
        for node in existing_nodes:
            ntype = node.get("type", "").lower()
            nname = node.get("name", "").lower()
            
            # Track intent nodes separately
            if "intent" in ntype:
                intent_nodes.append(node)
                if "confirmed" in ntype and node.get("description", "").lower() == "true":
                    filled_slots["intent_confirmed"] = True
            
            # Map other nodes to slots
            if "thesis" in ntype or "thesis" in nname:
                filled_slots["investment_thesis"] = node
            elif "sector" in ntype or "focus" in nname:
                filled_slots["sector_focus"] = node
            elif "check" in nname and "size" in nname:
                filled_slots["check_size_range"] = node
            elif "stage" in ntype or "stage" in nname:
                filled_slots["stage_focus"] = node
            elif "deal" in nname and "source" in nname:
                filled_slots["deal_flow_sources"] = node
    except Exception as e:
        print(f"Error fetching graph state: {e}")

    # ========== BUILD FULL KNOWLEDGE FROM GRAPH ==========
    # Include descriptions so we actually know what was learned
    knowledge_items = []
    agent_context = ""
    
    if existing_nodes:
        for node in existing_nodes:
            name = node.get("name", "")
            desc = node.get("description", "")
            ntype = node.get("type", "").lower()
            
            if not name:
                continue
            
            # Skip internal nodes
            if "intent" in ntype and "confirmed" in ntype:
                continue
            
            # Build knowledge item with description
            if desc and len(desc) > 5:
                knowledge_items.append(f"- {name}: {desc}")
            else:
                knowledge_items.append(f"- {name}")
    
    # Short summary (3 items max)
    short_summary = ", ".join([k.split(":")[0].replace("- ", "") for k in knowledge_items[:3]])
    if len(knowledge_items) > 3:
        short_summary += f" (+{len(knowledge_items) - 3} more)"
    
    # Full context for agent (with descriptions)
    if knowledge_items:
        agent_context = "What I know about you from our interviews:\n" + "\n".join(knowledge_items[:15])
    
    # ========== COMMAND DETECTION ==========
    msg_lower = request.message.lower().strip()
    
    # "What do you know?" - Show FULL knowledge with descriptions
    if any(p in msg_lower for p in ["what do you know", "what have we", "remember"]):
        if knowledge_items:
            full_knowledge = "\n".join(knowledge_items[:10])
            return InterviewResponse(
                response=f"Here's what I've learned about you:\n\n{full_knowledge}\n\nWhat would you like to explore or add?",
                conversation_id=conversation_id, session_id=session_id,
                stage=stage_label, progress={"slots_filled": len(knowledge_items)}
            )
        else:
            return InterviewResponse(
                response="Nothing yet. Let's start — what's this twin for?",
                conversation_id=conversation_id, session_id=session_id,
                stage=InterviewStage.INTENT_CAPTURE.value.upper()
            )
    
    # "Start fresh" - Clear and go
    if any(p in msg_lower for p in ["start fresh", "start over", "reset", "delete", "clear", "forget"]):
        try:
            supabase.table("nodes").delete().eq("twin_id", twin_id).execute()
            supabase.table("edges").delete().eq("twin_id", twin_id).execute()
            InterviewController.update_session(session_id, new_stage=InterviewStage.OPENING.value, new_intent_confirmed=False)
        except: pass
        return InterviewResponse(
            response="Done. Starting fresh.\n\nWhat's this twin for?",
            conversation_id=conversation_id, session_id=session_id,
            stage=InterviewStage.INTENT_CAPTURE.value.upper()
        )
    
    # "Continue" - Just proceed
    if any(p in msg_lower for p in ["continue", "yes", "proceed", "go ahead", "next", "let's go"]):
        next_slot = get_next_slot(host_policy, filled_slots)
        if next_slot:
            q = get_next_question(host_policy, filled_slots, spec.name)
            question = q.get("question") if q else f"What's your {next_slot['slot_id'].replace('_', ' ')}?"
            return InterviewResponse(
                response=question,
                conversation_id=conversation_id, session_id=session_id,
                stage=InterviewStage.DEEP_INTERVIEW.value.upper(),
                suggested_question=question
            )
            
        print(f"DEBUG: Continuing Interview. Next Slot: {next_slot['slot_id']}")

    # ========== STAGE-BASED ROUTING ==========
    
    final_response = ""
    suggested_question = None
    follow_up_question = None
    intent_summary = None
    next_stage = stage.value
    scribe_result = {}  # Initialize to empty dict for return statement
    
    # STAGE 0: OPENING
    if stage == InterviewStage.OPENING:
        if short_summary and len(existing_nodes) > 3:
            # Returning user - show what we know and offer to help
            final_response = f"Welcome back! Here's what I know:\n\n{chr(10).join(knowledge_items[:5])}\n\nHow can I help?"
            next_stage = InterviewStage.COMPLETE.value
            InterviewController.update_session(session_id, new_stage=next_stage, increment_turn=True)
        else:
            # Fresh user - one question
            final_response = "Let's build your twin. What's it for?"
            next_stage = InterviewStage.INTENT_CAPTURE.value
            InterviewController.update_session(session_id, new_stage=next_stage, increment_turn=True)
    
    # STAGE 1: INTENT CAPTURE
    elif stage == InterviewStage.INTENT_CAPTURE:
        log_interaction(conversation_id, "user", request.message)
        
        # Get current question
        next_intent_q = InterviewController.get_next_intent_question(session)
        current_question = next_intent_q if next_intent_q else INTENT_QUESTIONS[0]
        
        # Evaluate response quality
        quality_result = await ResponseEvaluator.evaluate_response(
            request.message,
            current_question=current_question,
            use_llm=True
        )
        
        # Track quality score
        InterviewController.append_quality_score(session_id, {
            "turn": session.get("turn_count", 0) + 1,
            "stage": "intent_capture",
            "slot": current_question.get("id", "unknown"),
            "quality_score": quality_result.quality_score,
            "tier": quality_result.tier,
            "is_substantive": quality_result.is_substantive
        })
        
        # Check if response is sufficient
        if not quality_result.is_substantive or quality_result.quality_score < 0.5:
            # Response insufficient - use repair strategy
            clarification_attempts = InterviewController.get_clarification_attempts(session) + 1
            InterviewController.increment_clarification_attempts(session_id)
            
            repair = RepairManager.get_repair_strategy(
                clarification_attempts,
                current_question=current_question,
                user_message=request.message
            )
            
            InterviewController.update_repair_strategy(session_id, repair.strategy_type)
            final_response = repair.message
            next_stage = InterviewStage.INTENT_CAPTURE.value  # Stay in same stage
            InterviewController.update_session(session_id, increment_turn=True)
            log_interaction(conversation_id, "assistant", final_response)
        else:
            # Response sufficient - extract and process
            InterviewController.reset_clarification_attempts(session_id)
            
            # Extract from response using slot-aware extraction
            tenant_id = user.get("tenant_id") if user else None
            scribe_result = await extract_for_slot(
                twin_id=twin_id,
                user_message=request.message,
                assistant_message=current_question.get("question", ""),
                slot_id=current_question.get("id", ""),
                target_node_type=current_question.get("target_node"),
                current_question=current_question.get("question"),
                history=history,
                tenant_id=tenant_id,
                conversation_id=conversation_id
            )
            
            # Check how many intent nodes we have now
            intent_count = len([n for n in (scribe_result.get("nodes") or []) if "intent" in str(n.get("type", "")).lower()])
            total_intent = len(intent_nodes) + intent_count
            
            if total_intent >= 2:
                # Enough intent captured - move to profile
                first_slot = get_next_slot(host_policy, filled_slots)
                if first_slot:
                    q = get_next_question(host_policy, filled_slots, spec.name)
                    question = q.get("question") if q else f"What's your {first_slot['slot_id'].replace('_', ' ')}?"
                    final_response = f"Got it. Building your profile now.\n\n{question}"
                else:
                    final_response = "Got it. Let me start building your profile."
                next_stage = InterviewStage.DEEP_INTERVIEW.value
                InterviewController.update_session(session_id, new_stage=next_stage, increment_turn=True)
                log_interaction(conversation_id, "assistant", final_response)
            else:
                # Need more intent info
                next_intent_q = InterviewController.get_next_intent_question(session)
                if next_intent_q:
                    final_response = next_intent_q["question"]
                    InterviewController.update_current_question(session_id, next_intent_q["id"])
                    InterviewController.update_session(session_id, add_template_id=next_intent_q["id"], increment_turn=True)
                    log_interaction(conversation_id, "assistant", final_response)
                else:
                    # All intent questions asked - skip confirmation, go straight to profile
                    first_slot = get_next_slot(host_policy, filled_slots)
                    if first_slot:
                        q = get_next_question(host_policy, filled_slots, spec.name)
                        question = q.get("question") if q else f"What's your {first_slot['slot_id'].replace('_', ' ')}?"
                        final_response = f"Got it. Now building your profile.\n\n{question}"
                    else:
                        final_response = "Got it. Your profile is set."
                    next_stage = InterviewStage.DEEP_INTERVIEW.value
                    InterviewController.update_session(session_id, new_stage=next_stage, new_intent_confirmed=True, increment_turn=True)
                log_interaction(conversation_id, "assistant", final_response)
    
    # STAGE 1.5: CONFIRM INTENT (simplified - mostly auto-confirm now)
    elif stage == InterviewStage.CONFIRM_INTENT:
        user_msg_lower = request.message.lower().strip()
        
        log_interaction(conversation_id, "user", request.message)
        
        # Unless they explicitly say "no", just continue
        if "no" in user_msg_lower and len(user_msg_lower) < 20:
            final_response = "What would you like to correct?"
            next_stage = InterviewStage.INTENT_CAPTURE.value
        else:
            # Confirmed - move to profile
            supabase.rpc("create_node_system", {
                "t_id": twin_id, "n_name": "Intent Confirmed", 
                "n_type": "intent.confirmed", "n_desc": "true", "n_props": {}
            }).execute()
            
            next_slot = get_next_slot(host_policy, filled_slots)
            if next_slot:
                q = get_next_question(host_policy, filled_slots, spec.name)
                question = q.get("question") if q else f"What's your {next_slot['slot_id'].replace('_', ' ')}?"
                final_response = question
            else:
                final_response = "Profile complete."
            next_stage = InterviewStage.DEEP_INTERVIEW.value
        
        InterviewController.update_session(session_id, new_stage=next_stage, new_intent_confirmed=True, increment_turn=True)
        log_interaction(conversation_id, "assistant", final_response)
    
    # STAGE 2: DEEP INTERVIEW (concise questions)
    elif stage == InterviewStage.DEEP_INTERVIEW:
        log_interaction(conversation_id, "user", request.message)
        
        # Get current slot being filled
        current_slot = get_next_slot(host_policy, filled_slots)
        
        if not current_slot:
            # No more slots - we're done!
            final_response = "Profile complete. Your twin is ready."
            next_stage = InterviewStage.COMPLETE.value
            InterviewController.update_session(session_id, new_stage=next_stage, increment_turn=True)
            log_interaction(conversation_id, "assistant", final_response)
        else:
            # Get current question
            q = get_next_question(host_policy, filled_slots, spec.name, session.get("asked_template_ids", []))
            current_question = {
                "question": q.get("question") if q else f"What's your {current_slot['slot_id'].replace('_', ' ')}?",
                "id": q.get("template_id") if q else current_slot.get("slot_id"),
                "target_node": q.get("target_node") if q else None
            }
            
            # Evaluate response quality
            quality_result = await ResponseEvaluator.evaluate_response(
                request.message,
                current_question=current_question,
                current_slot=current_slot,
                use_llm=True
            )
            
            # Track quality score
            InterviewController.append_quality_score(session_id, {
                "turn": session.get("turn_count", 0) + 1,
                "stage": "deep_interview",
                "slot": current_slot.get("slot_id", "unknown"),
                "quality_score": quality_result.quality_score,
                "tier": quality_result.tier,
                "is_substantive": quality_result.is_substantive,
                "relevance_score": quality_result.relevance_score
            })
            
            # Check if response is sufficient (quality > 0.5 and scribe confidence > 0.4)
            if not quality_result.is_substantive or quality_result.quality_score < 0.5:
                # Response insufficient - use repair strategy
                clarification_attempts = InterviewController.get_clarification_attempts(session) + 1
                InterviewController.increment_clarification_attempts(session_id)
                
                repair = RepairManager.get_repair_strategy(
                    clarification_attempts,
                    current_question=current_question,
                    current_slot=current_slot,
                    user_message=request.message
                )
                
                InterviewController.update_repair_strategy(session_id, repair.strategy_type)
                
                # Handle skip request
                if repair.should_skip and RepairManager.detect_skip_request(request.message):
                    InterviewController.add_skipped_slot(session_id, current_slot.get("slot_id"))
                    # Move to next slot
                    next_slot = get_next_slot(host_policy, filled_slots)
                    if next_slot:
                        q = get_next_question(host_policy, filled_slots, spec.name, session.get("asked_template_ids", []))
                        question = q.get("question") if q else f"What's your {next_slot['slot_id'].replace('_', ' ')}?"
                        final_response = f"Skipped. {question}"
                    else:
                        final_response = "Profile complete. Your twin is ready."
                        next_stage = InterviewStage.COMPLETE.value
                        InterviewController.update_session(session_id, new_stage=next_stage, increment_turn=True)
                else:
                    final_response = repair.message
                    next_stage = InterviewStage.DEEP_INTERVIEW.value  # Stay in same stage
                    InterviewController.update_session(session_id, increment_turn=True)
                
                log_interaction(conversation_id, "assistant", final_response)
            else:
                # Response sufficient - extract and process
                InterviewController.reset_clarification_attempts(session_id)
                
                # Extract using slot-aware extraction
                tenant_id = user.get("tenant_id") if user else None
                scribe_result = await extract_for_slot(
                    twin_id=twin_id,
                    user_message=request.message,
                    assistant_message=current_question.get("question", ""),
                    slot_id=current_slot.get("slot_id", ""),
                    target_node_type=current_question.get("target_node"),
                    current_question=current_question.get("question"),
                    history=history,
                    tenant_id=tenant_id,
                    conversation_id=conversation_id
                )
                
                # Only advance if extraction was successful (confidence > 0.4 and nodes extracted)
                scribe_confidence = scribe_result.get("confidence", 0.0)
                nodes_extracted = len(scribe_result.get("nodes", []))
                
                if scribe_confidence > 0.4 and nodes_extracted > 0:
                    # Extraction successful - move to next slot
                    next_slot = get_next_slot(host_policy, filled_slots)
                    
                    if next_slot:
                        q = get_next_question(host_policy, filled_slots, spec.name, session.get("asked_template_ids", []))
                        question_text = q.get("question") if q else f"What's your {next_slot['slot_id'].replace('_', ' ')}?"
                        
                        # Generate contextual question if we have existing nodes
                        if existing_nodes:
                            question_text = generate_contextual_question(
                                question_text,
                                next_slot,
                                existing_nodes=existing_nodes,
                                history=history,
                                use_llm=False
                            )
                        
                        final_response = question_text
                        suggested_question = question_text
                        InterviewController.update_current_question(session_id, q.get("template_id") if q else next_slot.get("slot_id"))
                        InterviewController.update_session(session_id, add_template_id=q.get("template_id") if q else None, increment_turn=True)
                    else:
                        # Done!
                        final_response = "Profile complete. Your twin is ready."
                        next_stage = InterviewStage.COMPLETE.value
                        InterviewController.update_session(session_id, new_stage=next_stage, increment_turn=True)
                else:
                    # Extraction failed - ask again with repair strategy
                    clarification_attempts = InterviewController.get_clarification_attempts(session) + 1
                    InterviewController.increment_clarification_attempts(session_id)
                    
                    repair = RepairManager.get_repair_strategy(
                        clarification_attempts,
                        current_question=current_question,
                        current_slot=current_slot,
                        user_message=request.message
                    )
                    
                    InterviewController.update_repair_strategy(session_id, repair.strategy_type)
                    final_response = repair.message
                    next_stage = InterviewStage.DEEP_INTERVIEW.value
                    InterviewController.update_session(session_id, increment_turn=True)
                
                log_interaction(conversation_id, "assistant", final_response)
    
    # STAGE 3: COMPLETE (conversational with full context)
    elif stage == InterviewStage.COMPLETE:
        # Build context-aware system prompt for agent
        context_prompt = f"""You are a Cognitive Host who has learned about this user through interviews.

{agent_context if agent_context else "You haven't learned much about this user yet."}

Use this knowledge to answer their questions intelligently.
If they ask about something you don't know, ask them about it to learn more.
Keep responses brief and conversational."""
        
        # Use agent with context (passing as part of history)
        history_with_context = [{"role": "system", "content": context_prompt}] + history
        
        async for event in run_agent_stream(twin_id, request.message, history_with_context):
            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                if isinstance(msg, AIMessage) and msg.content:
                    final_response = msg.content
        
        log_interaction(conversation_id, "user", request.message)
        if final_response:
            log_interaction(conversation_id, "assistant", final_response)
        else:
            # If agent didn't respond, ask a learning question
            final_response = "I'd like to learn more about you. What's your focus area?"
        
        next_stage = InterviewStage.COMPLETE.value
    
    # Calculate progress
    required_slots = host_policy.get("required_slots", [])
    slots_filled_count = len([s for s in required_slots if s.get("slot_id") in filled_slots])
    missing_slots = [s for s in required_slots if s.get("slot_id") not in filled_slots]
    
    progress = {
        "intent_complete": session.get("intent_confirmed", False) or filled_slots.get("intent_confirmed", False),
        "slots_filled": slots_filled_count,
        "total_slots": len(required_slots),
        "turn_count": session.get("turn_count", 0) + 1
    }
    
    return InterviewResponse(
        response=final_response,
        conversation_id=conversation_id,
        session_id=session_id,
        stage=next_stage.upper() if isinstance(next_stage, str) else stage_label,
        intent_summary=intent_summary or session.get("intent_summary"),
        next_slot=get_next_slot(host_policy, filled_slots),
        suggested_question=suggested_question,
        follow_up_question=follow_up_question,
        extracted_data=scribe_result if scribe_result else {},
        confidence=scribe_result.get("confidence", 0.0) if scribe_result else 0.0,
        contradictions=[],
        missing_slots=missing_slots[:5],
        progress=progress
    )


@router.get("/cognitive/graph/{twin_id}")
async def get_cognitive_graph(twin_id: str, user=Depends(require_tenant)):
    """
    Get the current cognitive graph state for a twin.

    Returns:
        - nodes: List of cognitive graph nodes
        - edges: List of cognitive graph edges
        - clusters: Cluster completion percentages
    """
    require_twin_access(twin_id, user)

    
    # TODO: Implement actual graph store query
    # For now return a placeholder structure
    return {
        "nodes": [],
        "edges": [],
        "clusters": {
            "thesis": {"completion": 0.0, "node_count": 0},
            "rubric": {"completion": 0.0, "node_count": 0},
            "moat": {"completion": 0.0, "node_count": 0},
            "process": {"completion": 0.0, "node_count": 0},
            "comms": {"completion": 0.0, "node_count": 0},
        },
    }


# NOTE: Approval workflow removed - all content auto-indexes now.
# Versioning endpoints below are kept for read-only history.


@router.post("/cognitive/profiles/{twin_id}/approve")
async def approve_profile(twin_id: str, request: Optional[ApproveProfileRequest] = None, user=Depends(get_current_user)):
    """
    Compatibility endpoint for clients that still perform explicit profile approval.

    Persists an immutable profile version snapshot and returns approval metadata.
    """
    verify_twin_ownership(twin_id, user)
    notes = (request.notes or "").strip() if request else ""
    approval_notes = notes or None

    from modules._core.versioning import create_snapshot, compute_diff

    try:
        nodes_res = supabase.table("nodes").select("*").eq("twin_id", twin_id).execute()
        edges_res = supabase.table("edges").select("*").eq("twin_id", twin_id).execute()
        nodes = nodes_res.data or []
        edges = edges_res.data or []

        snapshot = create_snapshot(nodes, edges)

        latest_version = 0
        previous_snapshot: Dict[str, Any] = {}
        latest_res = supabase.rpc("get_profile_versions_system", {"t_id": twin_id, "limit_val": 1}).execute()
        if latest_res.data:
            latest = latest_res.data[0]
            latest_version = int(latest.get("version") or 0)
            previous_snapshot = latest.get("snapshot_json") or {}

        next_version = latest_version + 1
        diff = compute_diff(previous_snapshot, snapshot)
        approver_id = user.get("user_id") if isinstance(user, dict) else None

        version_id = None
        used_fallback_insert = False
        try:
            insert_res = supabase.rpc(
                "insert_profile_version_system",
                {
                    "t_id": twin_id,
                    "ver": next_version,
                    "snapshot": snapshot,
                    "diff": diff,
                    "n_count": len(nodes),
                    "e_count": len(edges),
                    "approver": approver_id,
                    "approval_notes": approval_notes,
                },
            ).execute()
            version_id = insert_res.data
        except Exception:
            # Older deployments may not have the RPC. Fall back to direct insert.
            used_fallback_insert = True
            direct_res = (
                supabase.table("profile_versions")
                .insert(
                    {
                        "twin_id": twin_id,
                        "version": next_version,
                        "snapshot_json": snapshot,
                        "diff_json": diff,
                        "node_count": len(nodes),
                        "edge_count": len(edges),
                        "approved_by": approver_id,
                        "notes": approval_notes,
                    }
                )
                .execute()
            )
            if direct_res.data:
                version_id = (direct_res.data[0] or {}).get("id")

        approved_at = datetime.now(timezone.utc).isoformat()

        try:
            tenant_id = user.get("tenant_id") if isinstance(user, dict) else None
            if tenant_id:
                AuditLogger.log(
                    tenant_id=tenant_id,
                    twin_id=twin_id,
                    event_type="COGNITIVE_PROFILE",
                    action="PROFILE_APPROVED",
                    actor_id=approver_id,
                    metadata={
                        "version": next_version,
                        "node_count": len(nodes),
                        "edge_count": len(edges),
                    },
                )
        except Exception as audit_err:
            print(f"Cognitive approval audit log failed: {audit_err}")

        return {
            "status": "approved",
            "approved": True,
            "twin_id": twin_id,
            "version": next_version,
            "version_id": version_id,
            "approved_by": approver_id,
            "approved_at": approved_at,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "notes": approval_notes,
            "fallback_insert": used_fallback_insert,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error approving cognitive profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve profile: {str(e)}")


@router.get("/cognitive/profiles/{twin_id}/versions")
async def get_versions(twin_id: str, limit: int = 10, user=Depends(require_tenant)):
    """
    Get version history for a cognitive profile.
    
    Returns list of all approved versions with metadata.
    """
    require_twin_access(twin_id, user)

    
    from modules._core.versioning import summarize_diff
    
    try:
        versions_res = supabase.rpc("get_profile_versions_system", {"t_id": twin_id, "limit_val": limit}).execute()
        
        versions = []
        for v in (versions_res.data or []):
            diff = v.get("diff_json")
            versions.append({
                "version": v["version"],
                "node_count": v["node_count"],
                "edge_count": v["edge_count"],
                "approved_at": v["approved_at"],
                "approved_by": v.get("approved_by"),
                "notes": v.get("notes"),
                "diff_summary": summarize_diff(diff) if diff else "Initial version"
            })
        
        return {
            "twin_id": twin_id,
            "total_versions": len(versions),
            "versions": versions
        }
        
    except Exception as e:
        print(f"Error fetching versions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch versions: {str(e)}")


@router.get("/cognitive/profiles/{twin_id}/versions/{version}")
async def get_version_snapshot(twin_id: str, version: int, user=Depends(require_tenant)):
    """
    Get a specific version's full snapshot.
    
    Returns the complete graph state as it was when approved.
    """
    require_twin_access(twin_id, user)

    
    try:
        versions_res = supabase.rpc("get_profile_versions_system", {"t_id": twin_id, "limit_val": 100}).execute()
        
        for v in (versions_res.data or []):
            if v["version"] == version:
                return {
                    "version": v["version"],
                    "snapshot": v["snapshot_json"],
                    "diff": v.get("diff_json"),
                    "node_count": v["node_count"],
                    "edge_count": v["edge_count"],
                    "approved_at": v["approved_at"],
                    "notes": v.get("notes")
                }
        
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching version: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch version: {str(e)}")


@router.delete("/cognitive/profiles/{twin_id}/versions/{version}")
async def delete_version(twin_id: str, version: int, user=Depends(require_tenant)):
    """
    Delete a specific version (admin function).
    
    Note: This should be used sparingly as versions are meant to be immutable audit records.
    """
    require_twin_access(twin_id, user)

    
    try:
        result = supabase.rpc("delete_profile_version_system", {"t_id": twin_id, "ver": version}).execute()
        
        if result.data:
            return {"success": True, "message": f"Version {version} deleted"}
        else:
            raise HTTPException(status_code=404, detail=f"Version {version} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting version: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete version: {str(e)}")


@router.delete("/cognitive/profiles/{twin_id}/versions")
async def delete_all_versions(twin_id: str, user=Depends(get_current_user)):
    """
    Delete ALL versions for a twin (reset/cleanup function).
    
    Warning: This removes all version history and cannot be undone.
    """
    verify_twin_ownership(twin_id, user)
    
    try:
        result = supabase.rpc("delete_all_versions_system", {"t_id": twin_id}).execute()
        deleted_count = result.data if result.data else 0
        
        return {
            "success": True, 
            "message": f"Deleted {deleted_count} version(s)",
            "deleted_count": deleted_count
        }
            
    except Exception as e:
        print(f"Error deleting versions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete versions: {str(e)}")
