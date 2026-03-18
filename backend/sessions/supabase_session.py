"""
Supabase-backed session service replacing LangGraph's PostgresSaver.

Stores conversation thread state in the existing Supabase database
so that multi-turn conversations persist across API calls.
"""

import json
import time
from typing import Any, Dict, Optional

from modules.observability import supabase


async def save_session_state(
    conversation_id: str,
    twin_id: str,
    state_snapshot: Dict[str, Any],
) -> None:
    """Persist the pipeline state for a conversation thread.

    Stores a minimal state snapshot (routing decision, dialogue mode,
    last planning output) — NOT the full message history, which is
    already stored in the conversations/messages tables.
    """
    serializable_state = {
        "dialogue_mode": state_snapshot.get("dialogue_mode"),
        "intent_label": state_snapshot.get("intent_label"),
        "workflow_intent": state_snapshot.get("workflow_intent"),
        "routing_decision": state_snapshot.get("routing_decision"),
        "persona_spec_version": state_snapshot.get("persona_spec_version"),
        "persona_v2_enabled": state_snapshot.get("persona_v2_enabled"),
        "reasoning_history": (state_snapshot.get("reasoning_history") or [])[-5:],
        "updated_at": time.time(),
    }

    try:
        supabase.table("conversation_state").upsert({
            "conversation_id": conversation_id,
            "twin_id": twin_id,
            "state": json.dumps(serializable_state),
            "updated_at": "now()",
        }, on_conflict="conversation_id").execute()
    except Exception as e:
        # Non-critical — state persistence failure should not block chat
        print(f"[Session] Failed to save state for {conversation_id}: {e}")


async def load_session_state(
    conversation_id: str,
) -> Optional[Dict[str, Any]]:
    """Load persisted pipeline state for a conversation thread."""
    try:
        result = supabase.table("conversation_state").select("state").eq(
            "conversation_id", conversation_id
        ).maybe_single().execute()

        if result.data and result.data.get("state"):
            return json.loads(result.data["state"])
    except Exception as e:
        print(f"[Session] Failed to load state for {conversation_id}: {e}")

    return None


async def delete_session_state(conversation_id: str) -> None:
    """Remove persisted state for a conversation."""
    try:
        supabase.table("conversation_state").delete().eq(
            "conversation_id", conversation_id
        ).execute()
    except Exception as e:
        print(f"[Session] Failed to delete state for {conversation_id}: {e}")
