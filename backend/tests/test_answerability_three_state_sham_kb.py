from unittest.mock import AsyncMock

import pytest

from modules.answerability import _render_evidence_for_prompt, evaluate_answerability


SHAM_KNOWLEDGE_BASE = [
    {
        "source_id": "sham-geo",
        "section_path": "Company Profile/Geography",
        "text": "Geography coverage: United States, India, and Germany.",
    },
    {
        "source_id": "sham-usage-1",
        "section_path": "How It Works/Usage Overview",
        "text": "Usage overview: use onboarding, configuration, and review steps.",
    },
    {
        "source_id": "sham-usage-2",
        "section_path": "How It Works/Operations",
        "text": "Twin operation starts by connecting data sources and setting guardrails.",
    },
]


@pytest.mark.asyncio
async def test_sham_kb_geography_is_direct(monkeypatch):
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))

    result = await evaluate_answerability("What geography?", SHAM_KNOWLEDGE_BASE)

    assert result["answerability"] == "direct"
    assert result["missing_information"] == []


@pytest.mark.asyncio
async def test_sham_kb_how_to_use_twin_is_derivable(monkeypatch):
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))

    result = await evaluate_answerability("How to use the twin?", SHAM_KNOWLEDGE_BASE)

    assert result["answerability"] == "derivable"
    assert result["missing_information"] == []


@pytest.mark.asyncio
async def test_sham_kb_api_endpoint_is_insufficient(monkeypatch):
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))

    result = await evaluate_answerability("What API endpoint?", SHAM_KNOWLEDGE_BASE)

    assert result["answerability"] == "insufficient"
    assert result["missing_information"]


def test_sham_kb_rendered_evidence_preserves_non_unknown_sections():
    rendered = _render_evidence_for_prompt(SHAM_KNOWLEDGE_BASE)
    assert "section=unknown" not in rendered.lower()
