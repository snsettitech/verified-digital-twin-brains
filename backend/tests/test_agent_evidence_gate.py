import pytest
from langchain_core.messages import HumanMessage

from modules.agent import evidence_gate_node


@pytest.mark.asyncio
async def test_evidence_gate_owner_chat_verifier_fail_clears_context(monkeypatch):
    async def fake_invoke_json(*args, **kwargs):
        return {"is_sufficient": False, "reason": "irrelevant context"}, {"provider": "test"}

    monkeypatch.setattr("modules.agent.invoke_json", fake_invoke_json)

    state = {
        "dialogue_mode": "QA_FACT",
        "target_owner_scope": True,
        "requires_evidence": True,
        "interaction_context": "owner_chat",
        "messages": [HumanMessage(content="What do I think about X?")],
        "retrieved_context": {"results": [{"text": "unrelated", "source_id": "s1"}]},
        "reasoning_history": [],
    }

    out = await evidence_gate_node(state)
    assert out["dialogue_mode"] == "QA_FACT"
    assert out["requires_teaching"] is False
    assert out["retrieved_context"] == {"results": []}


@pytest.mark.asyncio
async def test_evidence_gate_owner_training_verifier_fail_keeps_teaching(monkeypatch):
    async def fake_invoke_json(*args, **kwargs):
        return {"is_sufficient": False, "reason": "irrelevant context"}, {"provider": "test"}

    monkeypatch.setattr("modules.agent.invoke_json", fake_invoke_json)

    state = {
        "dialogue_mode": "TEACHING",
        "target_owner_scope": True,
        "requires_evidence": True,
        "interaction_context": "owner_training",
        "messages": [HumanMessage(content="Teach this")],
        "retrieved_context": {"results": [{"text": "unrelated", "source_id": "s1"}]},
        "reasoning_history": [],
    }

    out = await evidence_gate_node(state)
    assert out["dialogue_mode"] == "TEACHING"
    assert out["requires_teaching"] is True
