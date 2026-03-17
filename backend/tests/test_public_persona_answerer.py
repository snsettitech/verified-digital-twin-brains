import pytest

from modules.public_persona_answerer import maybe_answer_public_persona_query


@pytest.mark.asyncio
async def test_public_persona_finalizer_accepts_openai_fallback(monkeypatch):
    monkeypatch.setattr(
        "modules.public_persona_answerer._load_public_twin_settings",
        lambda _twin_id: {
            "name": "Narendra Modi",
            "public_profile": {
                "occupation": "Prime Minister of India at Government of India",
                "bio": "Narendra Modi has served as Prime Minister of India since 2014.",
                "contributions": ["Joined Bharatiya Janata Party (BJP)."],
            },
        },
    )
    monkeypatch.setattr("modules.public_persona_answerer._load_public_profile_pack", lambda _twin_id: None)

    async def _fake_invoke_json(*_args, **_kwargs):
        return (
            {
                "answerable": True,
                "answer": "I have served as Prime Minister of India since 2014.",
                "citations": [],
                "answerability_state": "direct",
            },
            {},
        )

    async def _fake_invoke_text(*_args, **_kwargs):
        return (
            "I serve as Prime Minister of India and lead the Government of India.",
            {"provider": "openai", "model": "gpt-4.1"},
        )

    monkeypatch.setattr("modules.public_persona_answerer.inference_router.invoke_json", _fake_invoke_json)
    monkeypatch.setattr("modules.public_persona_answerer.inference_router.invoke_text", _fake_invoke_text)

    result = await maybe_answer_public_persona_query(
        "twin-1",
        "What public role is Narendra Modi associated with?",
        query_policy={"query_class": "factual"},
    )

    assert result is not None
    assert result.response == "I serve as Prime Minister of India and lead the Government of India."
    assert result.provider_used == "openai"
