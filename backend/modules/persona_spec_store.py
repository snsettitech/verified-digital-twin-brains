"""
Persona Spec Store

Persistence and bootstrap helpers for versioned persona specs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.observability import supabase
from modules.owner_memory_store import list_owner_memories
from modules.persona_spec import PersonaSpec, next_patch_version


def _load_twin_settings(twin_id: str) -> Dict[str, Any]:
    try:
        res = supabase.table("twins").select("tenant_id,settings").eq("id", twin_id).single().execute()
        if res.data:
            return res.data
    except Exception:
        return {}
    return {}


def list_persona_specs(twin_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_specs")
            .select("*")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[PersonaSpec] list failed: {e}")
        return []


def get_persona_spec(twin_id: str, version: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_specs")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("version", version)
            .single()
            .execute()
        )
        return res.data if res.data else None
    except Exception:
        return None


def get_active_persona_spec(twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_specs")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("status", "active")
            .order("published_at", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(res, "data", None)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
    except Exception:
        return None
    return None


def _latest_version(twin_id: str) -> Optional[str]:
    try:
        res = (
            supabase.table("persona_specs")
            .select("version")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0].get("version")
    except Exception:
        return None
    return None


def get_next_spec_version(twin_id: str) -> str:
    return next_patch_version(_latest_version(twin_id))


def create_persona_spec(
    twin_id: str,
    tenant_id: Optional[str],
    created_by: str,
    spec: PersonaSpec,
    status: str = "draft",
    source: str = "manual",
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "version": spec.version,
        "status": status,
        "spec": spec.model_dump(),
        "source": source,
        "notes": notes,
        "created_by": created_by,
    }
    try:
        res = supabase.table("persona_specs").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaSpec] create failed: {e}")
        return None


def publish_persona_spec(twin_id: str, version: str) -> Optional[Dict[str, Any]]:
    from datetime import datetime

    try:
        target = get_persona_spec(twin_id=twin_id, version=version)
        if not target:
            return None

        supabase.table("persona_specs").update({"status": "archived"}).eq("twin_id", twin_id).eq(
            "status", "active"
        ).execute()
        res = (
            supabase.table("persona_specs")
            .update({"status": "active", "published_at": datetime.utcnow().isoformat()})
            .eq("twin_id", twin_id)
            .eq("version", version)
            .execute()
        )
        return res.data[0] if res.data else target
    except Exception as e:
        print(f"[PersonaSpec] publish failed: {e}")
        return None


def bootstrap_persona_spec_from_user_data(twin_id: str) -> PersonaSpec:
    twin = _load_twin_settings(twin_id)
    settings = (twin or {}).get("settings") or {}
    intent_profile = settings.get("intent_profile") or {}
    memories = list_owner_memories(twin_id=twin_id, status="active", limit=60)

    signature_phrases = settings.get("signature_phrases") or []
    persona_profile = settings.get("persona_profile") or "Professional, direct, and helpful."
    public_intro = settings.get("public_intro") or ""

    stance_values: Dict[str, Any] = {}
    for memory in memories[:15]:
        topic = memory.get("topic_normalized")
        value = memory.get("value")
        if topic and value:
            stance_values[topic] = {
                "value": value,
                "stance": memory.get("stance"),
                "intensity": memory.get("intensity"),
            }

    identity_voice = {
        "persona_profile": persona_profile,
        "signature_phrases": signature_phrases,
        "public_intro": public_intro,
    }
    decision_policy = {
        "clarify_when_ambiguous": True,
        "cite_when_factual": True,
        "assumption_policy": "state assumptions explicitly when data is missing",
    }
    interaction_style = {
        "brevity_default": "concise",
        "structure_default": "answer_then_reasoning",
        "disagreement_style": "direct_respectful",
    }
    if intent_profile:
        interaction_style["intent_profile"] = intent_profile

    procedural_modules = [
        {
            "id": "procedural.decision.clarify_before_advice",
            "intent_labels": ["advice_or_stance", "ambiguity_or_clarify"],
            "when": {"missing_material_parameters": True},
            "do": ["ask_one_clarifying_question", "state_assumptions_if_answering"],
            "say_style": {"tone": "direct", "max_questions": 1},
            "ban": ["I might be wrong but", "As an AI model"],
            "priority": 50,
            "active": True,
        },
        {
            "id": "procedural.factual.cite_or_disclose_uncertainty",
            "intent_labels": ["factual_with_evidence"],
            "when": {"requires_evidence": True},
            "do": ["retrieve_evidence_first", "cite_sources", "disclose_uncertainty_if_low_confidence"],
            "say_style": {"format": "concise_bullets"},
            "ban": ["without evidence"],
            "priority": 40,
            "active": True,
        },
    ]

    deterministic_rules = {
        "banned_phrases": ["As an AI language model", "I cannot access real-time data unless provided"],
        "anti_style_rules": ["Do not over-explain simple answers", "Avoid generic motivational filler"],
    }

    latest = _latest_version(twin_id)
    spec = PersonaSpec(
        version=next_patch_version(latest),
        identity_voice=identity_voice,
        decision_policy=decision_policy,
        stance_values=stance_values,
        interaction_style=interaction_style,
        constitution=[
            "Never fabricate sources or certainty.",
            "If uncertain, disclose limits and request clarification when needed.",
            "Prioritize user intent while preserving safety and factual integrity.",
        ],
        canonical_examples=[],
        anti_examples=[],
        procedural_modules=procedural_modules,
        deterministic_rules=deterministic_rules,
        metadata={"generated_from": "twins.settings+owner_memory"},
    )
    return spec
