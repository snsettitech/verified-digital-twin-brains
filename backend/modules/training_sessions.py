"""
Training Session Store

Tracks explicit owner training windows used to derive owner_training interaction context.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from modules.observability import supabase


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
        return res.data if res.data else None
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
            return res.data[0]
        return None
    except Exception:
        return None

