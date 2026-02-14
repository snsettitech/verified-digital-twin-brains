import pytest
from langchain_core.messages import HumanMessage

from modules.agent import router_node


@pytest.mark.asyncio
async def test_router_owner_generic_query_disables_evidence(monkeypatch):
    async def fake_invoke_json(*args, **kwargs):
        return (
            {
                "mode": "QA_FACT",
                "is_person_specific": True,
                "requires_evidence": True,
                "reasoning": "mock",
            },
            {"provider": "test"},
        )

    monkeypatch.setattr("modules.agent.invoke_json", fake_invoke_json)

    state = {
        "messages": [HumanMessage(content="What metrics should I track weekly?")],
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }
    out = await router_node(state)
    assert out["dialogue_mode"] == "QA_FACT"
    assert out["target_owner_scope"] is False
    assert out["requires_evidence"] is False


@pytest.mark.asyncio
async def test_router_explicit_source_request_keeps_evidence(monkeypatch):
    async def fake_invoke_json(*args, **kwargs):
        return (
            {
                "mode": "QA_FACT",
                "is_person_specific": False,
                "requires_evidence": False,
                "reasoning": "mock",
            },
            {"provider": "test"},
        )

    monkeypatch.setattr("modules.agent.invoke_json", fake_invoke_json)

    state = {
        "messages": [HumanMessage(content="Answer based on my sources about GTM")],
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }
    out = await router_node(state)
    assert out["requires_evidence"] is True


@pytest.mark.asyncio
async def test_router_respects_model_person_specific_when_not_generic_coaching(monkeypatch):
    async def fake_invoke_json(*args, **kwargs):
        return (
            {
                "mode": "QA_FACT",
                "is_person_specific": True,
                "requires_evidence": True,
                "reasoning": "mock",
            },
            {"provider": "test"},
        )

    monkeypatch.setattr("modules.agent.invoke_json", fake_invoke_json)

    state = {
        "messages": [HumanMessage(content="What did I say about specialist agents?")],
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }
    out = await router_node(state)
    assert out["target_owner_scope"] is True
    assert out["requires_evidence"] is True


@pytest.mark.asyncio
async def test_router_week1_guidance_is_treated_as_generic_coaching(monkeypatch):
    async def fake_invoke_json(*args, **kwargs):
        return (
            {
                "mode": "QA_FACT",
                "is_person_specific": True,
                "requires_evidence": True,
                "reasoning": "mock",
            },
            {"provider": "test"},
        )

    monkeypatch.setattr("modules.agent.invoke_json", fake_invoke_json)

    state = {
        "messages": [HumanMessage(content="What should I do in week 1 for GTM?")],
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }
    out = await router_node(state)
    assert out["target_owner_scope"] is False
    assert out["requires_evidence"] is False
