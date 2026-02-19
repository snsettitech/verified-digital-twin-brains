import pytest
from langchain_core.messages import HumanMessage

from modules.agent import router_node


@pytest.mark.asyncio
async def test_router_always_requires_evidence(monkeypatch):
    monkeypatch.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: True)

    state = {
        "twin_id": "twin-1",
        "messages": [HumanMessage(content="Who are you?")],
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }
    out = await router_node(state)

    assert out["dialogue_mode"] == "QA_FACT"
    assert out["requires_evidence"] is True
    assert len(out["sub_queries"]) == 1
    assert "who are you?" in out["sub_queries"][0].lower()


@pytest.mark.asyncio
async def test_router_returns_generalized_routing_decision(monkeypatch):
    monkeypatch.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: False)

    state = {
        "twin_id": "twin-2",
        "messages": [HumanMessage(content="Should we use containers or serverless?")],
        "interaction_context": "public_share",
        "reasoning_history": [],
    }
    out = await router_node(state)

    decision = out["routing_decision"]
    assert isinstance(decision, dict)
    assert decision["action"] == "answer"
    assert decision["clarifying_questions"] == []
    assert decision["required_inputs_missing"] == []
    assert out["workflow_intent"] == decision["intent"]


@pytest.mark.asyncio
async def test_router_smalltalk_bypasses_retrieval(monkeypatch):
    monkeypatch.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: True)

    state = {
        "twin_id": "twin-3",
        "messages": [HumanMessage(content="hi")],
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }
    out = await router_node(state)

    assert out["dialogue_mode"] == "SMALLTALK"
    assert out["requires_evidence"] is False
    assert out["sub_queries"] == []
    assert out["routing_decision"]["action"] == "answer"


@pytest.mark.asyncio
async def test_router_resolves_second_person_to_twin_persona(monkeypatch):
    monkeypatch.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: True)

    state = {
        "twin_id": "twin-4",
        "messages": [HumanMessage(content="Who are you?")],
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }
    out = await router_node(state)

    assert out["dialogue_mode"] == "QA_FACT"
    assert out["requires_evidence"] is True
    assert len(out["sub_queries"]) == 1
    assert "twin persona identity" in out["sub_queries"][0].lower()
