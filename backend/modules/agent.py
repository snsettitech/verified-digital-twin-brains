"""Minimal compatibility layer over the new ADK chat runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

from adk_core.runtime import stream_chat_turn
from modules.observability import supabase


@dataclass
class AssistantMessage:
    """Small compatibility payload for residual callers expecting `.content`."""

    content: str


async def run_agent_stream(
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
    Legacy entrypoint kept only so residual routers do not crash during the rewrite.
    """
    del history
    del system_prompt
    del group_id
    del owner_memory_context
    del enforce_group_filtering
    del identity_gate_clarification_hint

    if not tenant_id:
        twin_row = (
            supabase.table("twins")
            .select("tenant_id")
            .eq("id", twin_id)
            .maybe_single()
            .execute()
        )
        tenant_id = (twin_row.data or {}).get("tenant_id")

    surface = "owner" if interaction_context == "owner_chat" else "widget" if interaction_context == "public_widget" else "public"
    user_id = actor_user_id or f"legacy:{surface}:{twin_id}"

    async for event in stream_chat_turn(
        twin_id=twin_id,
        tenant_id=tenant_id,
        user_id=user_id,
        surface=surface,
        message=query,
        conversation_id=conversation_id,
        client_context={"legacy_runtime": True, "interaction_context": interaction_context},
    ):
        event_type = str(event.get("type") or "")
        if event_type == "assistant_final":
            yield {"agent": {"messages": [AssistantMessage(content=str(event.get("message") or ""))]}}
        elif event_type == "citations":
            yield {"retrieve": {"citations": event.get("citations") or []}}
        elif event_type == "error":
            yield {"agent": {"messages": [AssistantMessage(content=str(event.get("message") or ""))]}}
