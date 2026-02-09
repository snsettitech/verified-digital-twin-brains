"""
Persona Prompt Variant Store

Persistence helpers for Phase 5 prompt optimization runs and active render
variants.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.observability import supabase


DEFAULT_PERSONA_PROMPT_VARIANT = "baseline_v1"


def list_persona_prompt_variants(twin_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_prompt_variants")
            .select("*")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[PersonaPromptVariant] list failed: {e}")
        return []


def get_persona_prompt_variant(twin_id: str, variant_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_prompt_variants")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("variant_id", variant_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[PersonaPromptVariant] get failed: {e}")
    return None


def get_active_persona_prompt_variant(twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_prompt_variants")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("status", "active")
            .order("activated_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[PersonaPromptVariant] active fetch failed: {e}")
    return None


def get_active_variant_id_or_default(twin_id: str) -> str:
    active = get_active_persona_prompt_variant(twin_id=twin_id)
    if active and active.get("variant_id"):
        return str(active["variant_id"])
    return DEFAULT_PERSONA_PROMPT_VARIANT


def create_persona_prompt_variant(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    created_by: Optional[str],
    variant_id: str,
    render_options: Dict[str, Any],
    status: str = "draft",
    source: str = "optimizer",
    objective_score: Optional[float] = None,
    metrics: Optional[Dict[str, Any]] = None,
    optimization_run_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "variant_id": variant_id,
        "render_options": render_options or {},
        "status": status,
        "source": source,
        "objective_score": objective_score,
        "metrics": metrics or {},
        "optimization_run_id": optimization_run_id,
        "created_by": created_by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = supabase.table("persona_prompt_variants").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaPromptVariant] create failed: {e}")
        return None


def activate_persona_prompt_variant(*, twin_id: str, variant_id: str) -> Optional[Dict[str, Any]]:
    try:
        target = get_persona_prompt_variant(twin_id=twin_id, variant_id=variant_id)
        if not target:
            return None
        return activate_persona_prompt_variant_record(twin_id=twin_id, record_id=target["id"])
    except Exception as e:
        print(f"[PersonaPromptVariant] activate failed: {e}")
        return None


def activate_persona_prompt_variant_record(*, twin_id: str, record_id: str) -> Optional[Dict[str, Any]]:
    try:
        res_target = (
            supabase.table("persona_prompt_variants")
            .select("*")
            .eq("id", record_id)
            .eq("twin_id", twin_id)
            .limit(1)
            .execute()
        )
        target = (res_target.data or [None])[0]
        if not target:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        supabase.table("persona_prompt_variants").update(
            {"status": "archived", "updated_at": now_iso}
        ).eq("twin_id", twin_id).eq("status", "active").execute()

        res = (
            supabase.table("persona_prompt_variants")
            .update({"status": "active", "activated_at": now_iso, "updated_at": now_iso})
            .eq("id", target["id"])
            .execute()
        )
        if res.data:
            return res.data[0]
        return (
            supabase.table("persona_prompt_variants")
            .select("*")
            .eq("id", record_id)
            .limit(1)
            .execute()
            .data
            or [None]
        )[0]
    except Exception as e:
        print(f"[PersonaPromptVariant] activate failed: {e}")
        return None


def create_prompt_optimization_run(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    created_by: Optional[str],
    base_persona_spec_version: Optional[str],
    dataset_version: Optional[str],
    run_mode: str,
    candidate_count: int,
) -> Optional[Dict[str, Any]]:
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "base_persona_spec_version": base_persona_spec_version,
        "dataset_version": dataset_version,
        "run_mode": run_mode,
        "status": "running",
        "candidate_count": candidate_count,
        "created_by": created_by,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = supabase.table("persona_prompt_optimization_runs").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaPromptVariant] create run failed: {e}")
        return None


def finalize_prompt_optimization_run(
    *,
    run_id: str,
    status: str,
    summary: Dict[str, Any],
    best_variant_id: Optional[str],
    best_objective_score: Optional[float],
) -> Optional[Dict[str, Any]]:
    payload = {
        "status": status,
        "summary": summary or {},
        "best_variant_id": best_variant_id,
        "best_objective_score": best_objective_score,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = (
            supabase.table("persona_prompt_optimization_runs")
            .update(payload)
            .eq("id", run_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaPromptVariant] finalize run failed: {e}")
        return None
