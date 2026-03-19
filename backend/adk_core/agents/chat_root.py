"""Top-level ADK chat agent."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent, SequentialAgent

from adk_core.agents.persona_responder import build_persona_responder_agent
from adk_core.tools.persona_tools import load_persona_runtime
from adk_core.tools.retrieval_tools import (
    retrieve_fact_context,
    retrieve_quote_context,
    retrieve_recent_conversation,
)


def build_chat_root_agent(*, model: Any) -> SequentialAgent:
    coordinator = LlmAgent(
        name="chat_coordinator",
        model=model,
        instruction="""
You are the planning stage for a persona-locked digital twin.

You are not the final responder. Your job is to think dynamically, choose
tools, gather evidence, and leave a concise brief for the final responder.

You must:
- Load the persona runtime first if it is not already in state.
- Use at least one retrieval tool before finishing.
- Prefer both factual context and quote context for subjective questions.
- Produce a compact JSON brief with keys:
  answer_goal, stance, must_cover, facts_to_use, quotes_to_echo, tone_notes.

Do not answer the user directly. Output only the coordinator brief.
""".strip(),
        tools=[
            load_persona_runtime,
            retrieve_fact_context,
            retrieve_quote_context,
            retrieve_recent_conversation,
        ],
        output_key="coordinator_brief",
    )
    responder = build_persona_responder_agent(model=model)
    return SequentialAgent(
        name="chat_root",
        sub_agents=[coordinator, responder],
    )
