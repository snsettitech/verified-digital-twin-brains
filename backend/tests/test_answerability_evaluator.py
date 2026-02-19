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
                    "answerability": "INSUFFICIENT",
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
    assert result["answerability"] == "insufficient"
    assert result["answerable"] is False
    assert result["confidence"] == pytest.approx(0.34)
    assert result["ambiguity_level"] == "high"
    assert result["missing_information"] == ["deployment deadline", "budget ceiling"]


@pytest.mark.asyncio
async def test_evaluate_answerability_handles_empty_evidence():
    result = await evaluate_answerability("Who are you?", [])
    assert result["answerability"] == "insufficient"
    assert result["answerable"] is False
    assert result["confidence"] == 0.0
    assert result["missing_information"]


@pytest.mark.asyncio
async def test_identity_query_prefers_identity_evidence(monkeypatch):
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))

    result = await evaluate_answerability(
        "Who are you?",
        [
            {
                "source_id": "id-1",
                "text": "I am Sainath Setti. I focus on cloud reliability and AI systems.",
            }
        ],
    )
    assert result["answerability"] == "direct"
    assert result["missing_information"] == []


@pytest.mark.asyncio
async def test_identity_query_without_identity_evidence_is_insufficient(monkeypatch):
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))

    result = await evaluate_answerability(
        "Who are you?",
        [{"source_id": "x-1", "text": "This section describes deployment steps only."}],
    )
    assert result["answerability"] == "insufficient"
    assert any("identity" in item.lower() for item in result["missing_information"])


@pytest.mark.asyncio
async def test_contract_overrides_do_not_downgrade_when_evidence_exists(monkeypatch):
    monkeypatch.setattr(
        "modules.answerability.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answerability": "direct",
                    "confidence": 0.78,
                    "reasoning": "Directly answerable from evidence.",
                    "missing_information": [],
                    "ambiguity_level": "low",
                },
                {"provider": "test"},
            )
        ),
    )

    result = await evaluate_answerability(
        "Who are you?",
        [{"source_id": "x-1", "text": "Deployment guide and API overview."}],
    )
    assert result["answerability"] == "direct"
    assert result["answerable"] is True


@pytest.mark.asyncio
async def test_contract_overrides_can_upgrade_insufficient_to_derivable(monkeypatch):
    monkeypatch.setattr(
        "modules.answerability.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answerability": "insufficient",
                    "confidence": 0.3,
                    "reasoning": "Model was conservative.",
                    "missing_information": ["more context"],
                    "ambiguity_level": "medium",
                },
                {"provider": "test"},
            )
        ),
    )

    result = await evaluate_answerability(
        "How should I talk to this twin?",
        [
            {"source_id": "s1", "text": "Communication style rules: direct, concise, pragmatic."},
            {"source_id": "s2", "text": "Decision rubric: recommendation, assumptions, risks, next steps."},
        ],
    )
    assert result["answerability"] == "derivable"
    assert result["answerable"] is True
    assert result["missing_information"] == []
