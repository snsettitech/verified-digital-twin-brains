import pytest

from modules.public_persona_answerer import maybe_answer_public_persona_query


@pytest.mark.asyncio
async def test_public_profile_first_answer_handles_background_question(monkeypatch):
    monkeypatch.setattr(
        "modules.public_persona_answerer._load_public_twin_settings",
        lambda _twin_id: {
            "name": "Narendra Modi",
            "public_profile": {
                "occupation": "Prime Minister of India at Government of India",
                "headline": "Heads the Government of India",
                "bio": (
                    "Narendra Modi is an Indian politician from the Bharatiya Janata Party "
                    "who has served as Prime Minister of India since 2014."
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
                "answerable": True,
                "answer": (
                    "I got into politics through the Bharatiya Janata Party and built my public career in Gujarat "
                    "before becoming prime minister."
                ),
                "citations": [],
                "answerability_state": "derivable",
            },
            {},
        )

    async def _fake_invoke_text(*_args, **_kwargs):
        return (
            "I got into politics through the Bharatiya Janata Party and built my public career in Gujarat before becoming prime minister.",
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        )

    monkeypatch.setattr("modules.public_persona_answerer.inference_router.invoke_json", _fake_invoke_json)
    monkeypatch.setattr("modules.public_persona_answerer.inference_router.invoke_text", _fake_invoke_text)
    monkeypatch.setattr("modules.public_persona_answerer._load_public_profile_pack", lambda _twin_id: None)

    result = await maybe_answer_public_persona_query(
        "twin-1",
        "how you got into politics?",
        query_policy={"query_class": "factual"},
    )

    assert result is not None
    assert "bharatiya janata party" in result.response.lower()
    assert result.answerability_state == "derivable"
    assert result.source_tier == "canonical"
    assert result.provider_used == "gemini"
