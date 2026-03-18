"""Persistence for ADK conversations and message logs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from adk_core.repositories.base import compact_dict, utc_now_iso
from modules.observability import supabase


class ConversationRepository:
    """Stores chat turns independently of ADK session state."""

    def create_conversation(
        self,
        *,
        twin_id: str,
        tenant_id: Optional[str],
        user_id: Optional[str],
        surface: str,
        share_token: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = compact_dict(
            {
                "id": conversation_id,
                "twin_id": twin_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "surface": surface,
                "share_token": share_token,
                "metadata": metadata or {},
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            }
        )
        response = supabase.table("adk_conversations").insert(payload).execute()
        return (response.data or [None])[0]

    def get_conversation(
        self,
        *,
        conversation_id: str,
    ) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("adk_conversations")
            .select("*")
            .eq("id", conversation_id)
            .maybe_single()
            .execute()
        )
        return response.data or None

    def touch_conversation(self, conversation_id: str) -> None:
        (
            supabase.table("adk_conversations")
            .update({"updated_at": utc_now_iso()})
            .eq("id", conversation_id)
            .execute()
        )

    def add_message(
        self,
        *,
        conversation_id: str,
        twin_id: str,
        tenant_id: Optional[str],
        role: str,
        content: str,
        citations: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "conversation_id": conversation_id,
            "twin_id": twin_id,
            "tenant_id": tenant_id,
            "role": role,
            "content": content,
            "citations": citations or [],
            "metadata": metadata or {},
            "created_at": utc_now_iso(),
        }
        response = supabase.table("adk_messages").insert(payload).execute()
        self.touch_conversation(conversation_id)
        return (response.data or [None])[0]

    def list_messages(self, *, conversation_id: str) -> List[Dict[str, Any]]:
        response = (
            supabase.table("adk_messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []
