"""
ADK-free async pipeline that replaces the LangGraph StateGraph.

This is the core orchestrator: it runs the 6 node functions in sequence
with one conditional branch after the router, then yields SSE-compatible
events exactly matching the contract the frontend expects.

    router ─┬─► deepagents ──────────────► realizer ──► END
            ├─► retrieve ► gate ► planner ► realizer ──► END
            └─► planner ────────────────► realizer ──► END
"""

import asyncio
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from agents.message_types import (
    ai_message,
    get_last_human_content,
    human_message,
    is_human,
    set_additional_kwarg,
)
from agents.state import create_initial_state
from modules.langfuse_sdk import langfuse_context, observe


# ---------------------------------------------------------------------------
# Node imports — these are the EXISTING node functions from agent.py,
# progressively migrated to work with plain-dict state instead of
# LangChain BaseMessage.  During Phase 1 we keep them in agent.py and
# import; later phases move them into dedicated agent files.
# ---------------------------------------------------------------------------

# NOTE: Phase 1 — these are thin wrappers around the existing node functions.
# They will be replaced with native ADK agents in Phase 2.


async def _run_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper around the existing router_node."""
    from modules.agent import router_node
    updates = await router_node(state)
    return {**state, **updates}


async def _run_deepagents(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper around the existing deepagents_node."""
    from modules.agent import deepagents_node
    updates = await deepagents_node(state)
    return {**state, **updates}


async def _run_retrieve(state: Dict[str, Any], retrieval_tool) -> Dict[str, Any]:
    """Wrapper around the existing retrieve_hybrid_node.

    The retrieve node is created inside create_twin_agent() so we need
    to pass the retrieval tool explicitly.
    """
    from modules.agent import _build_query_ranked_profile_seed_rows, _merge_context_rows
    from agents.message_types import get_last_human_content
    import json as _json

    sub_queries = state.get("sub_queries", [])
    all_results = []
    citations = []
    user_query = get_last_human_content(state.get("messages", []))

    PLANNER_SECOND_PASS_RETRIEVAL_TOP_K = int(
        os.getenv("PLANNER_SECOND_PASS_RETRIEVAL_TOP_K", "12")
    )

    async def safe_retrieve(query):
        try:
            res_str = await retrieval_tool(query)
            return _json.loads(res_str)
        except Exception as e:
            print(f"Retrieval error: {e}")
            return []

    tasks = [safe_retrieve(q) for q in sub_queries]
    results_list = await asyncio.gather(*tasks)
    for res_data in results_list:
        if isinstance(res_data, list):
            for item in res_data:
                all_results.append(item)
                if "source_id" in item:
                    citations.append(item["source_id"])

    interaction_context = str(state.get("interaction_context") or "").strip().lower()
    use_profile_seed = interaction_context in {"public_share", "public_widget"} or not all_results
    profile_seed_rows: List[Dict[str, Any]] = []
    if use_profile_seed:
        profile_seed_rows = _build_query_ranked_profile_seed_rows(
            state.get("full_settings"),
            user_query,
            limit=6 if not all_results else 4,
        )
        if profile_seed_rows:
            all_results = _merge_context_rows(
                all_results,
                profile_seed_rows,
                limit=max(PLANNER_SECOND_PASS_RETRIEVAL_TOP_K, 10),
            )

    if all_results:
        citations = []
        for item in all_results:
            source_id = item.get("source_id")
            if isinstance(source_id, str) and source_id and source_id not in citations:
                citations.append(source_id)

    return {
        **state,
        "retrieved_context": {"results": all_results},
        "citations": citations,
        "reasoning_history": (state.get("reasoning_history") or [])
        + [
            f"Retrieval: Executed {len(sub_queries)} queries."
            + (
                f" Added {len(profile_seed_rows)} canonical profile seed rows."
                if profile_seed_rows
                else ""
            )
        ],
    }


async def _run_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper around the existing evidence_gate_node."""
    from modules.agent import evidence_gate_node
    updates = await evidence_gate_node(state)
    return {**state, **updates}


async def _run_planner(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper around the existing planner_node."""
    from modules.agent import planner_node
    updates = await planner_node(state)
    return {**state, **updates}


async def _run_realizer(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper around the existing realizer_node."""
    from modules.agent import realizer_node
    updates = await realizer_node(state)
    return {**state, **updates}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

@observe(name="adk_agent_response")
async def run_adk_pipeline(
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
    Main entry point — replaces run_agent_stream().

    Yields SSE-compatible event dicts that match the existing frontend contract:
      {"agent": {"messages": [msg_dict]}}

    This allows chat.py to consume events identically to the LangGraph path.
    """
    from modules.safety import apply_guardrails
    from modules.observability import supabase
    from modules.agent import _merge_twin_row_settings, get_owner_style_profile
    from modules.metrics_collector import MetricsCollector

    # 0. Safety guardrails
    refusal_message = apply_guardrails(twin_id, query)
    if refusal_message:
        refusal_msg = ai_message(refusal_message)
        refusal_msg = set_additional_kwarg(refusal_msg, "routing_decision", {
            "intent": "answer",
            "required_inputs_missing": [],
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
            "action": "refuse",
            "clarifying_questions": [],
        })
        refusal_msg = set_additional_kwarg(refusal_msg, "workflow_intent", "answer")
        yield {"agent": {"messages": [refusal_msg]}}
        return

    # 1. Fetch twin settings
    twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
    settings = _merge_twin_row_settings(twin_res.data)

    if group_id:
        try:
            from modules.access_groups import get_group_settings
            group_settings = await get_group_settings(group_id)
            settings = {**settings, **group_settings}
        except Exception as e:
            print(f"Warning: Failed to load group settings: {e}")

    # 2. Ensure style analysis
    if "persona_profile" not in settings:
        await get_owner_style_profile(twin_id)
        twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
        settings = _merge_twin_row_settings(twin_res.data)
        if group_id:
            try:
                from modules.access_groups import get_group_settings
                group_settings = await get_group_settings(group_id)
                settings = {**settings, **group_settings}
            except Exception:
                pass

    # 3. Graph context (optional)
    graph_context = ""
    if os.getenv("GRAPH_MEMORY_ENABLED", "false").lower() == "true" and tenant_id:
        try:
            from modules.graph_context_builder import get_graph_context_for_chat
            result = await get_graph_context_for_chat(
                tenant_id=tenant_id,
                twin_id=twin_id,
                query=query,
                correlation_id=conversation_id or "no-conversation",
            )
            if result.context:
                graph_context = result.context
        except Exception as e:
            print(f"[GraphMemory] Retrieval failed: {e}")

    effective_group_id = group_id if enforce_group_filtering else None

    # 4. Build initial state
    state = create_initial_state(
        twin_id=twin_id,
        query=query,
        history=history,
        settings=settings,
        group_id=effective_group_id,
        enforce_group_filtering=enforce_group_filtering,
        system_prompt_override=system_prompt,
        graph_context=graph_context,
        owner_memory_context=owner_memory_context,
        interaction_context=interaction_context,
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        identity_gate_clarification_hint=identity_gate_clarification_hint,
    )

    # 5. Build retrieval tool
    from modules.retrieval import retrieve_context_with_intent

    async def retrieval_tool_fn(query_text: str) -> str:
        """Plain async function replacing the LangChain @tool."""
        from modules.tools import get_retrieval_tool
        # Reuse existing retrieval logic but call it directly
        tool = get_retrieval_tool(
            twin_id,
            group_id=effective_group_id,
            conversation_history=state.get("messages"),
            resolve_default_group=enforce_group_filtering,
        )
        return await tool.ainvoke({"query": query_text})

    # 6. Metrics
    metrics = MetricsCollector(twin_id=twin_id)
    metrics.record_request()
    pipeline_start = time.time()

    try:
        # ===== PIPELINE EXECUTION =====

        # Step 1: Router
        state = await _run_router(state)
        yield {"router": {k: state.get(k) for k in [
            "dialogue_mode", "intent_label", "requires_evidence",
            "execution_lane", "routing_decision", "fastpath_response",
        ]}}

        # Step 2: Conditional branch
        if state.get("execution_lane"):
            state = await _run_deepagents(state)
            yield {"deepagents": {"planning_output": state.get("planning_output")}}
        elif state.get("requires_evidence"):
            state = await _run_retrieve(state, retrieval_tool_fn)
            yield {"retrieve": {
                "citations": state.get("citations", []),
                "context_count": len((state.get("retrieved_context") or {}).get("results", [])),
            }}
            state = await _run_gate(state)
            state = await _run_planner(state)
            yield {"planner": {"planning_output": state.get("planning_output")}}
        else:
            state = await _run_planner(state)
            yield {"planner": {"planning_output": state.get("planning_output")}}

        # Step 3: Realizer (always runs last)
        state = await _run_realizer(state)

        # Step 4: Yield the final response in the same format chat.py expects
        messages = state.get("messages", [])
        # The realizer appends messages to state — get the last AI message
        final_messages = []
        if messages:
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("role") == "assistant":
                    final_messages = [m]
                    break
                # Handle case where realizer returned messages in update dict
                elif hasattr(m, "content"):
                    # LangChain AIMessage from legacy node — convert
                    from agents.message_types import from_langchain
                    final_messages = [from_langchain(m)]
                    break

        # If realizer returned in update format (not appended to messages)
        if not final_messages and isinstance(state.get("_realizer_messages"), list):
            final_messages = state["_realizer_messages"]

        yield {"agent": {"messages": final_messages}}

    finally:
        pipeline_latency = (time.time() - pipeline_start) * 1000
        metrics.record_latency("agent", pipeline_latency)
        metrics.flush()
