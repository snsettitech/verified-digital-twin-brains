import pytest
import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock

# Add backend to path for imports
sys.path.append(os.path.join(os.getcwd(), "backend"))

from modules.agent import router_node, evidence_gate_node, TwinState
from langchain_core.messages import HumanMessage, AIMessage

@pytest.fixture
def base_state():
    return {
        "messages": [],
        "twin_id": "test-twin",
        "dialogue_mode": None,
        "requires_evidence": False,
        "requires_teaching": False,
        "target_owner_scope": False,
        "planning_output": None,
        "citations": [],
        "confidence_score": 1.0,
        "sub_queries": [],
        "reasoning_history": [],
        "retrieved_context": {"results": []}
    }

@pytest.mark.asyncio
async def test_router_node_intent_classification(base_state):
    # Mock invoke_json to avoid real model calls
    with unittest.mock.patch("modules.agent.invoke_json") as mock_invoke_json:
        mock_invoke_json.return_value = (
            {
                "mode": "SMALLTALK",
                "is_person_specific": False,
                "requires_evidence": False,
                "reasoning": "Greeting",
            },
            {},
        )

        base_state["messages"] = [HumanMessage(content="Hello!")]
        result = await router_node(base_state)

        assert result["dialogue_mode"] == "SMALLTALK"
        assert result["requires_evidence"] is False
        assert "Router: Mode=SMALLTALK" in result["reasoning_history"][-1]

@pytest.mark.asyncio
async def test_evidence_gate_pass(base_state):
    base_state["dialogue_mode"] = "QA_FACT"
    base_state["target_owner_scope"] = False
    base_state["retrieved_context"] = {"results": [{"text": "Some evidence"}]}
    base_state["messages"] = [HumanMessage(content="Fact query")]
    
    result = await evidence_gate_node(base_state)
    
    assert result["dialogue_mode"] == "QA_FACT"
    assert result["requires_teaching"] is False
    assert any(
        token in result["reasoning_history"][-1]
        for token in ["Gate: PASS", "Gate: SOFT"]
    )

@pytest.mark.asyncio
async def test_evidence_gate_fail_to_teaching(base_state):
    base_state["dialogue_mode"] = "QA_FACT"
    base_state["target_owner_scope"] = True # Person specific
    base_state["retrieved_context"] = {"results": []} # No evidence
    base_state["messages"] = [HumanMessage(content="What is your secret?")]
    
    result = await evidence_gate_node(base_state)
    
    assert result["dialogue_mode"] == "TEACHING"
    assert result["requires_teaching"] is True
    assert "Gate: FAIL -> TEACHING" in result["reasoning_history"][-1]

@pytest.mark.asyncio
async def test_evidence_gate_with_llm_verifier_fail(base_state):
    base_state["dialogue_mode"] = "QA_FACT"
    base_state["target_owner_scope"] = True
    base_state["retrieved_context"] = {"results": [{"text": "Irrelevant info"}]}
    base_state["messages"] = [HumanMessage(content="What is your favorite book?")]
    
    # Mock verifier to fail (invoke_json used by evidence gate)
    with unittest.mock.patch("modules.agent.invoke_json") as mock_invoke_json:
        mock_invoke_json.return_value = ({"is_sufficient": False, "reason": "No book found"}, {})

        result = await evidence_gate_node(base_state)

        assert result["dialogue_mode"] == "TEACHING"
        assert result["requires_teaching"] is True
        assert "Verifier: No book found" in result["reasoning_history"][-1]

if __name__ == "__main__":
    # For quick manual run
    asyncio.run(test_evidence_gate_fail_to_teaching(base_state()))
    print("Test passed manually.")
