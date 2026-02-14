import pytest
from langchain_core.messages import HumanMessage

from modules.agent import evidence_gate_node


@pytest.mark.asyncio
async def test_generic_query_without_evidence_stays_conversational():
    state = {
        "messages": [HumanMessage(content="do you know antler")],
        "dialogue_mode": "QA_FACT",
        "target_owner_scope": False,
        "requires_evidence": True,
        "retrieved_context": {"results": []},
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }

    result = await evidence_gate_node(state)

    assert result["requires_teaching"] is False
    assert result["dialogue_mode"] == "QA_FACT"


@pytest.mark.asyncio
async def test_owner_specific_query_without_evidence_requires_teaching():
    state = {
        "messages": [HumanMessage(content="what is my stance on antler")],
        "dialogue_mode": "STANCE_GLOBAL",
        "target_owner_scope": True,
        "requires_evidence": True,
        "retrieved_context": {"results": []},
        "interaction_context": "owner_chat",
        "reasoning_history": [],
    }

    result = await evidence_gate_node(state)

    assert result["requires_teaching"] is True
    assert result["dialogue_mode"] == "TEACHING"
