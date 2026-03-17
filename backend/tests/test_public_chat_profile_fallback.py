import pytest

from modules.public_persona_answerer import maybe_build_public_persona_fallback


@pytest.mark.asyncio
async def test_public_profile_seed_fallback_answers_biographical_question(monkeypatch):
    monkeypatch.setattr(
        "modules.public_persona_answerer._load_public_twin_settings",
        lambda _twin_id: {
            "name": "Narendra Modi",
            "public_profile": {
                "role": "Prime Minister of India",
                "organization": "Government of India",
                "headline": "Heads the Government of India",
                "bio": (
                    "Narendra Modi is an Indian politician from the Bharatiya Janata Party "
                    "who has led the country as Prime Minister since 2014."
                ),
                "contributions": [
                    "Joined Bharatiya Janata Party (BJP)",
                    "Served as Chief Minister of Gujarat",
                ],
                "work_experience": [
                    {
                        "role": "Chief Minister",
                        "company": "Gujarat",
                        "description": "He served as Chief Minister of Gujarat from 2001 to 2014.",
                    }
                ],
            },
        },
    )

    async def _fake_invoke_json(*_args, **_kwargs):
        return (
            {
                "answer_points": [
                    "I got into politics through the Bharatiya Janata Party and then built a longer public career in Gujarat before becoming prime minister."
                ],
                "citations": [],
                "answerability_state": "derivable",
            },
            {},
        )

    async def _fake_invoke_text(*_args, **_kwargs):
        return (
            "I got into politics through the Bharatiya Janata Party and then built a longer public career in Gujarat before becoming prime minister.",
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        )

    monkeypatch.setattr("modules.public_persona_answerer.inference_router.invoke_json", _fake_invoke_json)
    monkeypatch.setattr("modules.public_persona_answerer.inference_router.invoke_text", _fake_invoke_text)

    result = await maybe_build_public_persona_fallback("twin-1", "how you got into politics?")

    assert result is not None
    assert "bharatiya janata party" in result.response.lower()
    assert result.answerability_state == "derivable"
    assert result.source_tier == "canonical"
    assert result.provider_used == "gemini"
