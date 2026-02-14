"""
Training Session Store

Tracks explicit owner training windows used to derive owner_training interaction context.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Optional

from modules.observability import supabase


def _session_ttl_minutes() -> int:
    raw = str(os.getenv("TRAINING_SESSION_TTL_MINUTES", "240")).strip()
    try:
        minutes = int(raw)
        return max(5, minutes)
    except Exception:
        return 240


def _parse_iso_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_active_session_expired(session: Dict[str, Any]) -> bool:
    if (session or {}).get("status") != "active":
        return False
    started_at = _parse_iso_utc((session or {}).get("started_at"))
    if not started_at:
        return False
    ttl_minutes = _session_ttl_minutes()
    expires_at = started_at + timedelta(minutes=ttl_minutes)
    return datetime.now(timezone.utc) > expires_at


def _expire_training_session(session_id: str) -> None:
    now = datetime.utcnow().isoformat()
    try:
        (
            supabase.table("training_sessions")
            .update(
                {
                    "status": "expired",
                    "ended_at": now,
                    "updated_at": now,
                }
            )
            .eq("id", session_id)
            .eq("status", "active")
            .execute()
        )
    except Exception:
        # Non-blocking during context resolution.
        pass


def start_training_session(
    twin_id: str,
    tenant_id: Optional[str],
    owner_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()

    # Stop prior active sessions for this owner+twin.
    try:
        supabase.table("training_sessions").update(
            {
                "status": "stopped",
                "ended_at": now,
                "updated_at": now,
            }
        ).eq("twin_id", twin_id).eq("owner_id", owner_id).eq("status", "active").execute()
    except Exception:
        # Non-blocking; insert below still determines availability.
        pass

    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "status": "active",
        "started_at": now,
        "metadata": metadata or {},
        "updated_at": now,
    }
    try:
        res = supabase.table("training_sessions").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[TrainingSession] start failed: {e}")
        return None


def get_training_session(session_id: str, twin_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        query = supabase.table("training_sessions").select("*").eq("id", session_id)
        if twin_id:
            query = query.eq("twin_id", twin_id)
        res = query.single().execute()
        session = res.data if res.data else None
        if session and _is_active_session_expired(session):
            _expire_training_session(str(session.get("id")))
            return None
        return session
    except Exception:
        return None


def stop_training_session(
    session_id: str,
    twin_id: str,
    owner_id: str,
) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    try:
        res = (
            supabase.table("training_sessions")
            .update(
                {
                    "status": "stopped",
                    "ended_at": now,
                    "updated_at": now,
                }
            )
            .eq("id", session_id)
            .eq("twin_id", twin_id)
            .eq("owner_id", owner_id)
            .eq("status", "active")
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[TrainingSession] stop failed: {e}")
        return None


def get_active_training_session(twin_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("training_sessions")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("owner_id", owner_id)
            .eq("status", "active")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            session = res.data[0]
            if _is_active_session_expired(session):
                _expire_training_session(str(session.get("id")))
                return None
            return session
        return None
    except Exception:
        return None
