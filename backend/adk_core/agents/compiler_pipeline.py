"""ADK persona compiler workflow."""

from __future__ import annotations

import json
from typing import Dict

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import ToolContext

from adk_core.schemas.artifacts import ResearchArtifact
from adk_core.services.persona_materializer import materialize_persona_artifact


def materialize_persona_seed(tool_context: ToolContext) -> Dict[str, object]:
    """
    Build the deterministic persona seed from the current research artifact.
    """
    research_artifact_json = tool_context.state.get("research_artifact_json")
    twin_id = str(tool_context.state.get("twin_id") or "").strip()
    if not research_artifact_json or not twin_id:
        return {"status": "error", "error_message": "Missing research_artifact_json or twin_id."}
    research_artifact = ResearchArtifact.model_validate_json(research_artifact_json)
    persona_artifact = materialize_persona_artifact(twin_id=twin_id, research_artifact=research_artifact)
    tool_context.state["persona_seed_json"] = persona_artifact.model_dump_json()
    tool_context.state["quote_pack_json"] = json.dumps([item.model_dump() for item in persona_artifact.quote_pack])
    tool_context.state["persona_prompt_block"] = json.dumps(
        {
            "identity_frame": persona_artifact.identity_frame,
            "thinking_style": persona_artifact.thinking_style,
            "values_and_decision_heuristics": persona_artifact.values_and_decision_heuristics,
            "communication_rules": persona_artifact.communication_rules,
            "voice_dna": persona_artifact.voice_dna.model_dump(),
        }
    )
    return {
        "status": "success",
        "quote_count": len(persona_artifact.quote_pack),
        "seed_version": persona_artifact.version,
    }


def build_compiler_pipeline_agent(*, model: str) -> SequentialAgent:
    seed_agent = LlmAgent(
        name="persona_seed_materializer",
        model=model,
        instruction="""
Call materialize_persona_seed exactly once.

This creates the deterministic persona seed from the research artifact.
Do not write the final persona yet.
""".strip(),
        tools=[materialize_persona_seed],
        output_key="persona_seed_status",
    )
    voice_agent = LlmAgent(
        name="voice_analyst",
        model=model,
        instruction="""
Read the persona seed JSON: {persona_seed_json}

Return a compact JSON object with:
- tonal_traits
- sentence_style
- lexical_preferences
- signature_phrases
- voice_warnings
""".strip(),
        output_key="voice_analysis_json",
    )
    author_agent = LlmAgent(
        name="persona_author",
        model=model,
        instruction="""
You are finalizing the canonical persona artifact.

Inputs:
- persona seed JSON: {persona_seed_json}
- voice analysis JSON: {voice_analysis_json}

Return one JSON object representing the final persona artifact.
Preserve the deterministic seed structure, but refine the voice_dna and
communication_rules if needed. Keep it grounded in the research artifact.
""".strip(),
        output_key="persona_artifact_json",
    )
    return SequentialAgent(
        name="compiler_pipeline",
        sub_agents=[seed_agent, voice_agent, author_agent],
    )
