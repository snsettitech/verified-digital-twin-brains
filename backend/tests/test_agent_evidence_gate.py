import pytest
from langchain_core.messages import HumanMessage

from modules.agent import evidence_gate_node


@pytest.mark.asyncio
async def test_evidence_gate_pass_through_with_context():
    state = {
        "dialogue_mode": "QA_FACT",
        "requires_evidence": True,
        "messages": [HumanMessage(content="What does the doc say?")],
        "retrieved_context": {"results": [{"text": "Some evidence", "source_id": "s1"}]},
        "reasoning_history": [],
    }

    out = await evidence_gate_node(state)
    assert out["dialogue_mode"] == "QA_FACT"
    assert out["requires_teaching"] is False


@pytest.mark.asyncio
async def test_evidence_gate_pass_through_without_context():
    state = {
        "dialogue_mode": "QA_FACT",
        "requires_evidence": True,
        "messages": [HumanMessage(content="Unknown question")],
        "retrieved_context": {"results": []},
        "reasoning_history": [],
    }

    out = await evidence_gate_node(state)
    assert out["dialogue_mode"] == "QA_FACT"
    assert out["requires_teaching"] is False
