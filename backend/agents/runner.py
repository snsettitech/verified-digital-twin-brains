"""
ADK Runner — entry point for the chat router to invoke the ADK pipeline.

Provides the same interface as run_agent_stream() so chat.py can switch
between LangGraph and ADK with a single feature flag.
"""

import os
from typing import Any, AsyncGenerator, Dict, List, Optional

# Feature flag: "adk" or "langgraph"
AGENT_RUNTIME = os.getenv("AGENT_RUNTIME", "langgraph")


async def run_agent(
    twin_id: str,
    query: str,
    history: Optional[List[Dict[str, Any]]] = None,
    system_prompt: Optional[str] = None,
    group_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    owner_memory_context: str = "",
    interaction_context: str = "owner_chat",
    enforce_group_filtering: bool = True,
    actor_user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    identity_gate_clarification_hint: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Unified entry point that routes to either the ADK pipeline or LangGraph
    based on the AGENT_RUNTIME env var.

    Yields event dicts in the same format for both runtimes:
      {"agent": {"messages": [...]}}
      {"router": {...}}
      etc.
    """
    if AGENT_RUNTIME == "adk":
        from agents.pipeline import run_adk_pipeline
        async for event in run_adk_pipeline(
            twin_id=twin_id,
            query=query,
            history=history,
            system_prompt=system_prompt,
            group_id=group_id,
            conversation_id=conversation_id,
            owner_memory_context=owner_memory_context,
            interaction_context=interaction_context,
            enforce_group_filtering=enforce_group_filtering,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            identity_gate_clarification_hint=identity_gate_clarification_hint,
        ):
            yield event
    else:
        # Legacy LangGraph path — preserves full backward compatibility
        from modules.agent import run_agent_stream
        # Convert plain-dict history to LangChain messages for legacy path
        lc_history = None
        if history:
            from langchain_core.messages import HumanMessage, AIMessage
            lc_history = []
            for msg in history:
                if msg.get("role") == "user":
                    lc_history.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    lc_history.append(AIMessage(content=msg.get("content", "")))

        async for event in run_agent_stream(
            twin_id=twin_id,
            query=query,
            history=lc_history,
            system_prompt=system_prompt,
            group_id=group_id,
            conversation_id=conversation_id,
            owner_memory_context=owner_memory_context,
            interaction_context=interaction_context,
            enforce_group_filtering=enforce_group_filtering,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            identity_gate_clarification_hint=identity_gate_clarification_hint,
        ):
            yield event
