"""
Pipeline state for the ADK twin agent.

Replaces LangGraph's TwinState TypedDict with a plain dataclass.
All node functions read/write from this state dict.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def create_initial_state(
    *,
    twin_id: str,
    query: str,
    history: Optional[List[Dict[str, Any]]] = None,
    settings: Optional[Dict[str, Any]] = None,
    group_id: Optional[str] = None,
    enforce_group_filtering: bool = True,
    system_prompt_override: Optional[str] = None,
    graph_context: str = "",
    owner_memory_context: str = "",
    interaction_context: str = "owner_chat",
    actor_user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    identity_gate_clarification_hint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the initial pipeline state dict.

    This is the single source of truth for all fields the pipeline nodes
    read and write.  Keeping it as a plain dict (not a TypedDict) means
    nodes can add ad-hoc keys without schema changes — matching how
    the LangGraph version already worked in practice.
    """
    from agents.message_types import human_message

    messages = list(history or [])
    messages.append(human_message(query))

    return {
        # -- core --
        "messages": messages,
        "twin_id": twin_id,
        "query": query,
        "citations": [],
        "sub_queries": [],
        "reasoning_history": [],
        "retrieved_context": {},

        # -- routing / dialogue --
        "dialogue_mode": "QA_FACT",
        "intent_label": "factual_with_evidence",
        "requires_evidence": True,
        "requires_teaching": False,
        "target_owner_scope": False,
        "planning_output": None,
        "persona_module_ids": [],
        "persona_spec_version": None,
        "persona_prompt_variant": None,
        "router_reason": None,
        "router_knowledge_available": None,
        "workflow_intent": "answer",
        "fastpath_intent": None,
        "fastpath_response": None,
        "query_class": None,
        "quote_intent": False,
        "execution_lane": False,
        "deepagents_plan": None,

        # -- context / identity --
        "retrieval_group_id": group_id if enforce_group_filtering else None,
        "resolve_default_group_filtering": enforce_group_filtering,
        "full_settings": settings or {},
        "graph_context": graph_context,
        "owner_memory_context": owner_memory_context,
        "system_prompt_override": system_prompt_override,
        "interaction_context": interaction_context,
        "identity_gate_clarification_hint": identity_gate_clarification_hint,
        "actor_user_id": actor_user_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,

        # -- routing decision envelope --
        "routing_decision": {
            "intent": "answer",
            "required_inputs_missing": [],
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
            "action": "answer",
            "clarifying_questions": [],
        },

        # -- 5-layer persona (Phase 4) --
        "persona_v2_enabled": None,
        "persona_v2_spec_version": None,
        "persona_v2_dimension_scores": None,
        "persona_v2_overall_score": None,
        "persona_v2_reasoning_steps": None,
        "persona_v2_values_prioritized": None,
    }
