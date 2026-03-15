from unittest.mock import AsyncMock, patch

import pytest

from modules.agent import realizer_node


@pytest.mark.asyncio
async def test_realizer_returns_generated_text_without_shadowing_ai_message():
    state = {
        "planning_output": {
            "answer_points": ["hello"],
            "confidence": 0.67,
            "citations": ["src-1"],
            "render_strategy": "conversational_realizer",
        },
        "dialogue_mode": "QA_FACT",
        "intent_label": "test_intent",
        "persona_module_ids": ["m1"],
    }

    with patch(
        "modules.agent.invoke_text",
        new=AsyncMock(return_value=("Hello from twin.", {"provider": "openai", "model": "gpt-4o-mini", "latency_ms": 123})),
    ):
        result = await realizer_node(state)

    assert "messages" in result
    assert result["messages"][0].content == (
        "Hello from twin. What aspect of this would be most useful to go deeper on?"
    )
    assert result["messages"][0].additional_kwargs["dialogue_mode"] == "QA_FACT"
    assert result["messages"][0].additional_kwargs["intent_label"] == "test_intent"
    assert result["messages"][0].additional_kwargs["render_strategy"] == "conversational_realizer"
    assert result["messages"][0].additional_kwargs["inference_provider"] == "openai"
    assert result["messages"][0].additional_kwargs["confidence_score"] == pytest.approx(0.67)
    assert result["confidence_score"] == pytest.approx(0.67)


@pytest.mark.asyncio
async def test_realizer_fallback_message_on_invoke_failure():
    state = {
        "planning_output": {
            "confidence": 0.41,
            "answer_points": ["Fallback answer point."],
            "render_strategy": "conversational_realizer",
        },
        "dialogue_mode": "QA_FACT",
    }

    with patch("modules.agent.invoke_text", new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await realizer_node(state)

    assert "messages" in result
    assert result["messages"][0].content == (
        "Fallback answer point. What aspect of this would be most useful to go deeper on?"
    )
    assert result["messages"][0].additional_kwargs["render_strategy"] == "source_faithful"
    assert result["confidence_score"] == pytest.approx(0.41)


@pytest.mark.asyncio
async def test_realizer_source_faithful_keeps_clarification_metadata():
    state = {
        "planning_output": {
            "answer_points": ["Can you clarify which timeline you mean?", "1. Launch timeline", "2. Hiring timeline"],
            "confidence": 0.23,
            "render_strategy": "source_faithful",
            "clarification_hint": {"source": "identity_gate", "question": "Can you clarify which timeline you mean?"},
            "clarification_options": [{"label": "Launch timeline"}, {"label": "Hiring timeline"}],
        },
        "dialogue_mode": "QA_FACT",
    }

    result = await realizer_node(state)

    assert result["messages"][0].content.startswith("Can you clarify")
    assert result["messages"][0].additional_kwargs["clarification_hint"]["source"] == "identity_gate"
    assert len(result["messages"][0].additional_kwargs["clarification_options"]) == 2
