from unittest.mock import AsyncMock, patch

import pytest

from modules.agent import realizer_node
from modules.response_policy import UNCERTAINTY_RESPONSE


@pytest.mark.asyncio
async def test_realizer_returns_generated_text_without_shadowing_ai_message():
    state = {
        "planning_output": {"answer_points": ["hello"], "confidence": 0.67},
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
    assert result["messages"][0].content == "Hello from twin."
    assert result["messages"][0].additional_kwargs["dialogue_mode"] == "QA_FACT"
    assert result["messages"][0].additional_kwargs["intent_label"] == "test_intent"
    assert result["messages"][0].additional_kwargs["confidence_score"] == pytest.approx(0.67)
    assert result["confidence_score"] == pytest.approx(0.67)


@pytest.mark.asyncio
async def test_realizer_fallback_message_on_invoke_failure():
    state = {"planning_output": {"confidence": 0.41}, "dialogue_mode": "QA_FACT"}

    with patch("modules.agent.invoke_text", new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await realizer_node(state)

    assert "messages" in result
    assert result["messages"][0].content == UNCERTAINTY_RESPONSE
    assert result["confidence_score"] == pytest.approx(0.41)
