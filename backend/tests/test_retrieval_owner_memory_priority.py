import pytest

from modules import retrieval


@pytest.mark.asyncio
async def test_owner_memory_precedence_short_circuits_verified_and_vectors(monkeypatch):
    async def fake_default_group(_twin_id: str):
        return {"id": "group-1"}

    called = {"verified": False}

    async def fake_verified(*_args, **_kwargs):
        called["verified"] = True
        return None

    monkeypatch.setattr(retrieval, "get_default_group", fake_default_group)
    monkeypatch.setattr(
        retrieval,
        "_match_owner_memory",
        lambda query, twin_id: {
            "id": "mem-1",
            "value": "I prefer concise answers with explicit citations.",
            "memory_type": "preference",
            "topic_normalized": "answer style",
            "confidence": 1.0,
            "status": "verified",
            "_score": 0.95,
        },
    )
    monkeypatch.setattr(retrieval, "match_verified_qna", fake_verified)

    result = await retrieval.retrieve_context_with_verified_first(
        query="What is your preferred answer style?",
        twin_id="twin-1",
    )

    assert len(result) == 1
    assert result[0]["is_owner_memory"] is True
    assert result[0]["owner_memory_match"] is True
    assert called["verified"] is False


@pytest.mark.asyncio
async def test_verified_fallback_when_no_owner_memory(monkeypatch):
    async def fake_default_group(_twin_id: str):
        return {"id": "group-1"}

    async def fake_verified(*_args, **_kwargs):
        return {
            "id": "vq-1",
            "question": "What is your stance on AI safety?",
            "answer": "I favor pragmatic guardrails with measurable safety checks.",
            "similarity_score": 0.91,
            "citations": [],
        }

    monkeypatch.setattr(retrieval, "get_default_group", fake_default_group)
    monkeypatch.setattr(retrieval, "_match_owner_memory", lambda query, twin_id: None)
    monkeypatch.setattr(retrieval, "match_verified_qna", fake_verified)

    result = await retrieval.retrieve_context_with_verified_first(
        query="What is your stance on AI safety?",
        twin_id="twin-1",
    )

    assert len(result) == 1
    assert result[0]["is_verified"] is True
    assert result[0]["verified_qna_match"] is True

