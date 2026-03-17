import pytest

from routers.chat import _maybe_build_public_profile_seed_fallback


@pytest.mark.asyncio
async def test_public_profile_seed_fallback_answers_biographical_question(monkeypatch):
    monkeypatch.setattr(
        "routers.chat._load_public_twin_settings",
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
                "confidence": 0.74,
            },
            {},
        )

    monkeypatch.setattr("routers.chat.inference_router.invoke_json", _fake_invoke_json)

    result = await _maybe_build_public_profile_seed_fallback("twin-1", "how you got into politics?")

    assert result is not None
    assert "bharatiya janata party" in result["response"].lower()
    assert result["confidence"] >= 0.58
