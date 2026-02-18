from unittest.mock import AsyncMock

import pytest

from modules.answerability import evaluate_answerability


@pytest.mark.asyncio
async def test_evaluate_answerability_normalizes_model_output(monkeypatch):
    monkeypatch.setattr(
        "modules.answerability.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answerable": False,
                    "confidence": 0.34,
                    "reasoning": "Evidence misses deployment constraints.",
                    "missing_information": ["deployment deadline", "budget ceiling", "deployment deadline"],
                    "ambiguity_level": "HIGH",
                },
                {"provider": "test"},
            )
        ),
    )

    result = await evaluate_answerability(
        "What rollout should we use?",
        [{"source_id": "src-1", "text": "Use staged rollout for safety."}],
    )
    assert result["answerable"] is False
    assert result["confidence"] == pytest.approx(0.34)
    assert result["ambiguity_level"] == "high"
    assert result["missing_information"] == ["deployment deadline", "budget ceiling"]


@pytest.mark.asyncio
async def test_evaluate_answerability_handles_empty_evidence():
    result = await evaluate_answerability("Who are you?", [])
    assert result["answerable"] is False
    assert result["confidence"] == 0.0
    assert result["missing_information"]
