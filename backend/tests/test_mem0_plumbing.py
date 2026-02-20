from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import _load_mem0_preferences_for_turn, planner_node


class _FailingProvider:
    provider_name = "mem0"

    async def recall_preferences(self, *, twin_id: str, query: str, limit: int = 3):
        raise RuntimeError("mem0 unavailable")


class _PreferenceProvider:
    provider_name = "mem0"

    async def recall_preferences(self, *, twin_id: str, query: str, limit: int = 3):
        from modules.memory_provider import MemoryRecallItem

        return [
            MemoryRecallItem(
                memory_type="preference",
                value="Keep feedback concise and recommendation-first.",
                source_label="explicit_user",
                metadata={"source": "mem0-test"},
            ),
            MemoryRecallItem(
                memory_type="belief",
                value="This should be filtered out in prefs-only mode.",
                source_label="inferred",
                metadata={},
            ),
        ]


def test_mem0_flags_off_uses_noop_provider(monkeypatch):
    import modules.mem0_client as mem0_client

    monkeypatch.setattr(mem0_client, "MEM0_ENABLED", False)
    monkeypatch.setattr(mem0_client, "MEM0_READ_ENABLED", False)
    monkeypatch.setattr(mem0_client, "_MEM0_CLIENT_SINGLETON", None)
    provider = mem0_client.get_memory_provider()
    assert provider.provider_name == "noop"


@pytest.mark.asyncio
async def test_mem0_fallback_when_provider_down(monkeypatch):
    monkeypatch.setattr("modules.agent.get_memory_provider", lambda: _FailingProvider())
    rows, context_text, source = await _load_mem0_preferences_for_turn(
        twin_id="twin-1",
        query="How should I respond?",
        limit=3,
    )
    assert rows == []
    assert context_text == ""
    assert source.endswith(":fallback")


@pytest.mark.asyncio
async def test_mem0_preferences_context_is_formatted(monkeypatch):
    monkeypatch.setattr("modules.agent.get_memory_provider", lambda: _PreferenceProvider())
    rows, context_text, source = await _load_mem0_preferences_for_turn(
        twin_id="twin-1",
        query="How should I respond?",
        limit=3,
    )
    assert source == "mem0"
    assert len(rows) == 1
    assert rows[0]["memory_type"] == "preference"
    assert "recommendation-first" in context_text.lower()
    assert "source=explicit_user" in context_text


@pytest.mark.asyncio
async def test_mem0_prompt_context_does_not_change_retrieval_stats_or_evidence_rows(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )

    seen_eval_chunks = []

    async def _fake_eval(_query, chunks):
        seen_eval_chunks.extend(chunks)
        return {
            "answerability": "derivable",
            "confidence": 0.64,
            "reasoning": "Derivable from evidence.",
            "missing_information": [],
            "ambiguity_level": "medium",
        }

    seen_prompt = {"value": ""}

    async def _fake_invoke(messages, **_kwargs):
        seen_prompt["value"] = str(messages[0]["content"])
        return (
            {
                "answer_points": ["Recommendation: Focus on concise, practical founder guidance."],
                "citations": ["kb-1"],
                "confidence": 0.71,
                "reasoning_trace": "grounded",
            },
            {"provider": "test"},
        )

    monkeypatch.setattr("modules.agent.evaluate_answerability", AsyncMock(side_effect=_fake_eval))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=_fake_invoke))

    state = {
        "twin_id": "twin-sham",
        "messages": [HumanMessage(content="What do you see in the founders?")],
        "dialogue_mode": "QA_FACT",
        "query_class": "evaluative",
        "quote_intent": False,
        "mem0_preferences_context": "- Keep feedback concise and recommendation-first. (source=explicit_user)",
        "retrieved_context": {
            "results": [
                {
                    "source_id": "kb-1",
                    "text": "Decision rubric: prioritize clarity, execution discipline, and learning speed.",
                    "block_type": "answer_text",
                    "is_answer_text": True,
                    "retrieval_stats": {
                        "dense_top1": 0.82,
                        "dense_top5_avg": 0.77,
                        "confidence_floor_value": 0.82,
                        "confidence_floor_threshold": 0.55,
                        "meets_confidence_floor": True,
                    },
                }
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    assert out["routing_decision"]["action"] == "answer"
    assert out["planning_output"]["citations"] == ["kb-1"]
    assert seen_eval_chunks
    assert all("recommendation-first" not in str(row.get("text", "")).lower() for row in seen_eval_chunks)
    assert "MEMORY PREFERENCES (read-only):" in seen_prompt["value"]
    assert "recommendation-first" in seen_prompt["value"].lower()


@pytest.mark.asyncio
async def test_mem0_inferred_preferences_are_blocked_for_identity_queries(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )

    seen_prompt = {"value": ""}
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "direct",
                "confidence": 0.7,
                "reasoning": "direct",
                "missing_information": [],
                "ambiguity_level": "low",
            }
        ),
    )

    async def _fake_invoke(messages, **_kwargs):
        seen_prompt["value"] = str(messages[0]["content"])
        return (
            {
                "answer_points": ["Who I am: grounded identity answer."],
                "citations": ["kb-identity-1"],
                "confidence": 0.75,
                "reasoning_trace": "grounded",
            },
            {"provider": "test"},
        )

    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=_fake_invoke))

    state = {
        "twin_id": "twin-identity",
        "messages": [HumanMessage(content="who are you")],
        "dialogue_mode": "QA_FACT",
        "query_class": "identity",
        "quote_intent": False,
        "mem0_preferences_context": "- Use witty tone. (source=inferred)",
        "mem0_preferences": [
            {
                "memory_type": "preference",
                "value": "Use witty tone.",
                "source_label": "inferred",
                "metadata": {},
            }
        ],
        "retrieved_context": {
            "results": [
                {
                    "source_id": "kb-identity-1",
                    "text": "I am a founder-focused operator with practical startup guidance.",
                    "block_type": "answer_text",
                    "is_answer_text": True,
                }
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    assert out["routing_decision"]["action"] == "answer"
    assert "witty tone" not in seen_prompt["value"].lower()
