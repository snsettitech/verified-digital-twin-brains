"""Persistence for ADK Session objects."""

from __future__ import annotations

from typing import List, Optional

from google.adk.sessions import Session

from adk_core.repositories.base import compact_dict, is_empty_lookup_error, utc_now_iso
from modules.observability import supabase


class SessionRepository:
    """Stores the full serialized ADK Session payload."""

    def save(
        self,
        *,
        session: Session,
        tenant_id: Optional[str] = None,
        twin_id: Optional[str] = None,
    ) -> dict:
        payload = compact_dict(
            {
                "id": session.id,
                "app_name": session.app_name,
                "user_id": session.user_id,
                "tenant_id": tenant_id,
                "twin_id": twin_id,
                "session_json": session.model_dump(mode="json"),
                "updated_at": utc_now_iso(),
            }
        )
        try:
            existing = (
                supabase.table("adk_sessions")
                .select("id")
                .eq("id", session.id)
                .maybe_single()
                .execute()
            )
        except Exception as exc:
            if is_empty_lookup_error(exc):
                existing = None
            else:
                raise
        existing_data = (existing.data if existing else None) or None
        if existing_data:
            response = supabase.table("adk_sessions").update(payload).eq("id", session.id).execute()
        else:
            payload["created_at"] = utc_now_iso()
            response = supabase.table("adk_sessions").insert(payload).execute()
        response_data = response.data if response else None
        return (response_data or [None])[0]

    def get(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> Optional[Session]:
        try:
            response = (
                supabase.table("adk_sessions")
                .select("session_json")
                .eq("id", session_id)
                .eq("app_name", app_name)
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
        except Exception as exc:
            if is_empty_lookup_error(exc):
                return None
            raise
        if not response or not response.data:
            return None
        return Session.model_validate(response.data["session_json"])

    def list(self, *, app_name: str, user_id: Optional[str] = None) -> List[Session]:
        query = supabase.table("adk_sessions").select("session_json").eq("app_name", app_name)
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.execute()
        response_data = response.data if response else []
        return [Session.model_validate(row["session_json"]) for row in (response_data or [])]

    def delete(self, *, app_name: str, user_id: str, session_id: str) -> None:
        (
            supabase.table("adk_sessions")
            .delete()
            .eq("id", session_id)
            .eq("app_name", app_name)
            .eq("user_id", user_id)
            .execute()
        )
