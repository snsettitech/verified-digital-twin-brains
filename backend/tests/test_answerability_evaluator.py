from unittest.mock import AsyncMock

import pytest

from modules.answerability import (
    build_targeted_clarification_questions,
    evaluate_answerability,
)


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


@pytest.mark.asyncio
async def test_identity_query_uses_identity_metadata_when_text_is_sparse(monkeypatch):
    monkeypatch.setattr(
        "modules.answerability.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answerability": "insufficient",
                    "confidence": 0.25,
                    "reasoning": "Model was conservative.",
                    "missing_information": ["identity of you"],
                    "ambiguity_level": "medium",
                },
                {"provider": "test"},
            )
        ),
    )

    result = await evaluate_answerability(
        "Tell me about yourself",
        [
            {
                "source_id": "id-2",
                "text": "Operators who need fast decisions, not theory.",
                "section_title": "Owner identity and credibility",
                "doc_name": "Identity.docx",
                "block_type": "answer_text",
                "is_answer_text": True,
            }
        ],
    )
    assert result["answerability"] == "direct"
    assert result["answerable"] is True
    assert result["missing_information"] == []


def test_clarification_filters_noisy_section_candidates():
    questions = build_targeted_clarification_questions(
        "Tell me about yourself",
        ["the twin's identity bio and core expertise"],
        evidence_chunks=[
            {
                "source_id": "s1",
                "section_title": "mean",
                "section_path": "E) > mean",
                "text": "Who are you (short bio used in the twin)?",
                "block_type": "prompt_question",
                "is_answer_text": False,
            }
        ],
        limit=3,
    )
    assert questions
    joined = " ".join(questions).lower()
    assert "mean" not in joined
    assert "e) > mean" not in joined


def test_non_identity_clarification_ignores_prompt_section_labels():
    questions = build_targeted_clarification_questions(
        "What do you see in the founders?",
        ['personal background from "mean" or "E) > mean"'],
        evidence_chunks=[
            {
                "source_id": "s1",
                "section_title": "mean",
                "section_path": "E) > mean",
                "text": "Who are you (short bio used in the twin)?",
                "block_type": "prompt_question",
                "is_answer_text": False,
            },
            {
                "source_id": "s2",
                "section_title": "E) > mean",
                "section_path": "Sham/mean",
                "text": "What do you optimize for?",
                "block_type": "prompt_question",
                "is_answer_text": False,
            },
        ],
        limit=3,
    )
    assert questions
    joined = " ".join(questions).lower()
    assert "mean" not in joined
    assert "e) > mean" not in joined
    assert "are you asking about" not in joined


@pytest.mark.asyncio
async def test_founder_query_derivable_from_profile_evidence(monkeypatch):
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))

    result = await evaluate_answerability(
        "What do you see in the founders?",
        [
            {
                "source_id": "kb-1",
                "text": "Decision rubric: prioritize founder clarity, execution discipline, and speed of learning.",
                "section_title": "Decision rubric",
                "block_type": "answer_text",
                "is_answer_text": True,
            },
            {
                "source_id": "kb-2",
                "text": "Communication style rules: direct feedback and practical next steps.",
                "section_title": "Communication style rules",
                "block_type": "answer_text",
                "is_answer_text": True,
            },
        ],
    )
    assert result["answerability"] in {"direct", "derivable"}
    assert result["answerable"] is True
    assert result["missing_information"] == []
