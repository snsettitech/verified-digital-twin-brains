import pytest

from routers.chat import _rewrite_public_background_fastpath


@pytest.mark.asyncio
async def test_public_background_rewrite_uses_first_person(monkeypatch):
    async def _fake_invoke_json(*_args, **_kwargs):
        return (
            {
                "answer": (
                    "I came into national politics through the Bharatiya Janata Party and built my public career in Gujarat "
                    "before becoming prime minister in 2014."
                )
            },
            {},
        )

    monkeypatch.setattr("routers.chat.inference_router.invoke_json", _fake_invoke_json)

    answer = await _rewrite_public_background_fastpath(
        display_name="Narendra Modi",
        seed_rows=[
            {"text": "Joined Bharatiya Janata Party (BJP)."},
            {"text": "He served as Chief Minister of Gujarat from 2001 to 2014."},
            {"text": "Narendra Modi has been Prime Minister of India since 26 May 2014."},
        ],
    )

    assert answer.startswith("I ")
    assert "bharatiya janata party" in answer.lower()
