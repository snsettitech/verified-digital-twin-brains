import pytest

from modules import identity_gate
from modules.identity_gate import classify_query


def test_classify_query_goals_requires_owner():
    result = classify_query("What are my goals this year?")
    assert result["requires_owner"] is True
    assert result["memory_type"] == "belief"


def test_classify_query_generic_want_to_does_not_require_owner():
    result = classify_query("I want to ask you about antler")
    assert result["requires_owner"] is False
    assert result["memory_type"] is None


@pytest.mark.asyncio
async def test_identity_gate_falls_back_to_intent_profile(monkeypatch):
    monkeypatch.setattr(identity_gate, "find_owner_memory_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        identity_gate,
        "_load_intent_profile",
        lambda twin_id: {
            "use_case": "Help founders understand my investment philosophy.",
            "audience": "Early-stage founders and operators.",
            "boundaries": "No legal, tax, or medical advice."
        }
    )

    result = await identity_gate.run_identity_gate(
        query="What is your intent for this twin?",
        history=[],
        twin_id="twin-test",
        tenant_id=None,
        group_id=None,
        mode="owner"
    )

    assert result["decision"] == "ANSWER"
    assert result["reason"] == "intent_profile_fallback"
    assert "investment philosophy" in result["owner_memory_context"]


@pytest.mark.asyncio
async def test_identity_gate_public_mode_requests_owner_clarification(monkeypatch):
    monkeypatch.setattr(identity_gate, "find_owner_memory_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(identity_gate, "PUBLIC_CLARIFICATION_QUEUE_ENABLED", True)
    monkeypatch.setattr(identity_gate, "AUTO_APPROVE_OWNER_MEMORY", False)
    monkeypatch.setattr(
        identity_gate,
        "_load_intent_profile",
        lambda twin_id: {
            "use_case": "Help founders understand my investment philosophy.",
            "audience": "Early-stage founders and operators.",
            "boundaries": "No legal, tax, or medical advice."
        }
    )

    result = await identity_gate.run_identity_gate(
        query="What is your intent for this twin?",
        history=[],
        twin_id="twin-test",
        tenant_id=None,
        group_id=None,
        mode="public"
    )

    assert result["decision"] == "CLARIFY"
    assert result["reason"] == "missing_or_conflicting_public"
    assert result["gate_mode"] == "public"


@pytest.mark.asyncio
async def test_identity_gate_owner_chat_can_disable_clarify(monkeypatch):
    monkeypatch.setattr(identity_gate, "find_owner_memory_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(identity_gate, "_load_intent_profile", lambda twin_id: {})

    result = await identity_gate.run_identity_gate(
        query="What is your stance on AI safety?",
        history=[],
        twin_id="twin-test",
        tenant_id=None,
        group_id=None,
        mode="owner",
        allow_clarify=False,
    )

    assert result["decision"] == "ANSWER"
    assert result["reason"] == "clarification_disabled"
