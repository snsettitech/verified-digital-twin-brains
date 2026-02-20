from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import deepagents_node, router_node
from routers.chat import _extract_deepagents_metadata


@pytest.mark.asyncio
async def test_e2e_action_request_routes_to_lane_and_returns_needs_approval(monkeypatch):
    monkeypatch.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: True)
    monkeypatch.setattr(
        "modules.agent.execute_deepagents_plan",
        AsyncMock(
            return_value={
                "status": "needs_approval",
                "action_id": "draft-123",
                "action_type": "draft_email",
            }
        ),
    )

    base_state = {
        "messages": [HumanMessage(content="send email to jane@example.com subject: Intro body: hello")],
        "interaction_context": "owner_chat",
        "twin_id": "twin-actions",
    }
    routed = await router_node(base_state)
    assert routed["execution_lane"] is True
    assert routed["requires_evidence"] is False
    assert routed["intent_label"] == "action_or_tool_execution"

    lane_state = {
        **base_state,
        **routed,
        "routing_decision": routed.get("routing_decision"),
        "actor_user_id": "owner-1",
        "tenant_id": "tenant-1",
    }
    out = await deepagents_node(lane_state)
    assert out["routing_decision"]["action"] == "answer"
    assert out["planning_output"]["teaching_questions"] == []
    lane = out["planning_output"]["execution_lane"]
    assert lane["status"] == "needs_approval"
    assert lane["action_id"] == "draft-123"
    assert lane["action_type"] == "draft_email"


def test_deepagents_metadata_contract_is_minimal_and_stable():
    planning_output = {
        "execution_lane": {
            "status": "needs_approval",
            "needs_approval": True,
            "action_type": "draft_email",
            "action_id": "draft-123",
            "execution_id": None,
            "error_code": None,
            "inputs": {"to": "secret@example.com"},
            "raw_plan": {"steps": ["sensitive"]},
        }
    }
    payload = _extract_deepagents_metadata(planning_output)
    assert payload["status"] == "needs_approval"
    assert payload["action_type"] == "draft_email"
    assert payload["action_id"] == "draft-123"
    assert "inputs" not in payload
    assert "raw_plan" not in payload
