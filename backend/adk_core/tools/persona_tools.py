"""Persona-loading tools for ADK chat and compile flows."""

from __future__ import annotations

import json
from typing import Dict

from google.adk.tools import ToolContext

from adk_core.repositories.persona_repository import PersonaRepository


_persona_repository = PersonaRepository()


def load_persona_runtime(tool_context: ToolContext) -> Dict[str, object]:
    """
    Load the active persona artifact and its quote pack into session state.
    """
    twin_id = str(tool_context.state.get("twin_id") or "").strip()
    tenant_id = tool_context.state.get("tenant_id")
    if not twin_id:
        return {"status": "error", "error_message": "Missing twin_id in session state."}

    artifact_row = _persona_repository.get_active_artifact(twin_id=twin_id, tenant_id=tenant_id)
    if not artifact_row:
        return {"status": "error", "error_message": "No active persona artifact available."}

    artifact = artifact_row.get("artifact_json") or {}
    tool_context.state["persona_artifact_json"] = json.dumps(artifact)
    tool_context.state["persona_version"] = artifact.get("version", "")
    tool_context.state["quote_pack_json"] = json.dumps(artifact.get("quote_pack") or [])
    tool_context.state["persona_prompt_block"] = json.dumps(
        {
            "identity_frame": artifact.get("identity_frame") or {},
            "thinking_style": artifact.get("thinking_style") or {},
            "values_and_decision_heuristics": artifact.get("values_and_decision_heuristics") or [],
            "communication_rules": artifact.get("communication_rules") or [],
            "voice_dna": artifact.get("voice_dna") or {},
        }
    )
    return {
        "status": "success",
        "version": artifact.get("version"),
        "subject_name": artifact.get("subject_name"),
        "quote_count": len(artifact.get("quote_pack") or []),
    }
