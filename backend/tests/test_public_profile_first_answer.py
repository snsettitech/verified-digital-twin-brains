import pytest

from routers.chat import _maybe_answer_from_public_profile


@pytest.mark.asyncio
async def test_public_profile_first_answer_handles_background_question(monkeypatch):
    monkeypatch.setattr(
        "routers.chat._load_public_twin_settings",
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
                "confidence": 0.77,
            },
            {},
        )

    monkeypatch.setattr("routers.chat.inference_router.invoke_json", _fake_invoke_json)

    result = await _maybe_answer_from_public_profile(
        "twin-1",
        "how you got into politics?",
        {"query_class": "factual"},
    )

    assert result is not None
    assert "bharatiya janata party" in result["response"].lower()
    assert result["confidence"] >= 0.62
