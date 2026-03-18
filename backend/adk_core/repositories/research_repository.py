"""Persistence for research runs and research artifacts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from adk_core.repositories.base import compact_dict, utc_now_iso
from modules.observability import supabase


class ResearchRepository:
    """Stores authoritative research runs and artifacts."""

    def create_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        subject_name: str,
        twin_id: Optional[str] = None,
        hints: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if idempotency_key:
            existing = (
                supabase.table("adk_research_runs")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("idempotency_key", idempotency_key)
                .limit(1)
                .execute()
            )
            if existing.data:
                return existing.data[0]

        payload = compact_dict(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "twin_id": twin_id,
                "subject_name": subject_name,
                "hints": hints or {},
                "idempotency_key": idempotency_key,
                "status": "queued",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            }
        )
        response = supabase.table("adk_research_runs").insert(payload).execute()
        return (response.data or [None])[0]

    def get_run(self, *, run_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = supabase.table("adk_research_runs").select("*").eq("id", run_id)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.maybe_single().execute()
        return response.data or None

    def update_run(self, run_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
        payload = compact_dict({**updates, "updated_at": utc_now_iso()})
        response = (
            supabase.table("adk_research_runs")
            .update(payload)
            .eq("id", run_id)
            .execute()
        )
        return (response.data or [None])[0]

    def save_artifact(
        self,
        *,
        run_id: str,
        tenant_id: str,
        twin_id: Optional[str],
        artifact: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "twin_id": twin_id,
            "artifact_json": artifact,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        existing = (
            supabase.table("adk_research_artifacts")
            .select("id")
            .eq("run_id", run_id)
            .maybe_single()
            .execute()
        )
        if existing.data:
            response = (
                supabase.table("adk_research_artifacts")
                .update(payload)
                .eq("run_id", run_id)
                .execute()
            )
        else:
            response = supabase.table("adk_research_artifacts").insert(payload).execute()
        return (response.data or [None])[0]

    def get_artifact(self, *, run_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = supabase.table("adk_research_artifacts").select("*").eq("run_id", run_id)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.maybe_single().execute()
        return response.data or None
