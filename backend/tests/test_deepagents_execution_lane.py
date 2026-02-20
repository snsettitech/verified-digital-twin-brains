from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import deepagents_node, router_node
from modules.deepagents_executor import execute_deepagents_plan
from modules.deepagents_router import build_deepagents_plan


@pytest.mark.asyncio
async def test_action_request_routes_to_execution_lane_without_doc_clarifier(monkeypatch):
    monkeypatch.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: True)
    monkeypatch.setattr(
        "modules.agent.execute_deepagents_plan",
        AsyncMock(return_value={"status": "needs_approval", "action_id": "draft-123"}),
    )

    base_state = {
        "messages": [HumanMessage(content="send email to jane@example.com subject: Intro body: Hello there")],
        "interaction_context": "owner_chat",
        "twin_id": "twin-1",
    }
    routed = await router_node(base_state)
    assert routed["execution_lane"] is True
    assert routed["requires_evidence"] is False
    assert routed["sub_queries"] == []

    lane_state = {
        **base_state,
        **routed,
        "routing_decision": routed.get("routing_decision"),
        "actor_user_id": "user-1",
        "tenant_id": "tenant-1",
    }
    planned = await deepagents_node(lane_state)
    assert planned["routing_decision"]["action"] == "answer"
    assert planned["planning_output"]["execution_lane"]["status"] == "needs_approval"
    assert planned["planning_output"]["teaching_questions"] == []


@pytest.mark.asyncio
async def test_missing_params_returns_single_targeted_clarification(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.execute_deepagents_plan",
        AsyncMock(return_value={"status": "missing_params", "missing_params": ["to", "subject", "body"]}),
    )
    state = {
        "messages": [HumanMessage(content="send email")],
        "interaction_context": "owner_chat",
        "twin_id": "twin-1",
        "routing_decision": {
            "intent": "write",
            "confidence": 0.4,
            "required_inputs_missing": [],
            "chosen_workflow": "write",
            "output_schema": "workflow.write.v1",
            "action": "answer",
            "clarifying_questions": [],
        },
        "deepagents_plan": build_deepagents_plan("send email"),
        "actor_user_id": "user-1",
        "tenant_id": "tenant-1",
    }
    out = await deepagents_node(state)
    assert out["routing_decision"]["action"] == "clarify"
    assert len(out["planning_output"]["teaching_questions"]) == 1
    question = out["planning_output"]["teaching_questions"][0].lower()
    assert "recipient" in question or "subject" in question
    assert "section" not in question


@pytest.mark.asyncio
async def test_approval_required_creates_draft_without_execution_and_records_audit(monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "true")
    monkeypatch.setenv("DEEPAGENTS_REQUIRE_APPROVAL", "true")
    monkeypatch.setenv("DEEPAGENTS_MAX_STEPS", "6")
    monkeypatch.setenv("DEEPAGENTS_TIMEOUT_SECONDS", "10")

    audit_calls = []
    execution_calls = []

    def _fake_create_draft(*_args, **_kwargs):
        return "draft-123"

    def _fake_execute_action(**kwargs):
        execution_calls.append(kwargs)
        return "exec-should-not-run"

    def _fake_audit(*args, **kwargs):
        audit_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr("modules.deepagents_executor.ActionDraftManager.create_draft", _fake_create_draft)
    monkeypatch.setattr("modules.deepagents_executor.ActionExecutor.execute_action", _fake_execute_action)
    monkeypatch.setattr("modules.deepagents_executor.AuditLogger.log", _fake_audit)

    plan = build_deepagents_plan(
        "send email to jane@example.com subject: Founder update body: Sharing this week's summary."
    )
    result = await execute_deepagents_plan(
        twin_id="twin-1",
        plan=plan,
        actor_user_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
    )

    assert result["status"] == "needs_approval"
    assert result["action_id"] == "draft-123"
    assert execution_calls == []
    assert audit_calls
    assert audit_calls[0]["kwargs"].get("action") == "DEEPAGENTS_PLAN_CREATED"


@pytest.mark.asyncio
async def test_approved_execution_runs_with_step_limit_and_returns_results(monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "true")
    monkeypatch.setenv("DEEPAGENTS_REQUIRE_APPROVAL", "false")
    monkeypatch.setenv("DEEPAGENTS_MAX_STEPS", "2")
    monkeypatch.setenv("DEEPAGENTS_TIMEOUT_SECONDS", "10")

    captured_inputs = {}
    audit_calls = []

    def _fake_execute_action(**kwargs):
        captured_inputs.update(kwargs.get("inputs") or {})
        return "exec-123"

    def _fake_get_execution_details(execution_id):
        return {"id": execution_id, "status": "success"}

    def _fake_audit(*args, **kwargs):
        audit_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr("modules.deepagents_executor.ActionExecutor.execute_action", _fake_execute_action)
    monkeypatch.setattr("modules.deepagents_executor.ActionExecutor.get_execution_details", _fake_get_execution_details)
    monkeypatch.setattr("modules.deepagents_executor.AuditLogger.log", _fake_audit)

    plan = build_deepagents_plan(
        "send email to jane@example.com subject: Founder update body: Sharing this week's summary."
    )
    result = await execute_deepagents_plan(
        twin_id="twin-1",
        plan=plan,
        actor_user_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
    )

    assert result["status"] == "executed"
    assert result["execution_id"] == "exec-123"
    assert isinstance(captured_inputs.get("_deepagents_steps"), list)
    assert len(captured_inputs.get("_deepagents_steps")) <= 2
    assert result["execution"]["status"] == "success"
    assert audit_calls
    assert audit_calls[0]["kwargs"].get("action") == "DEEPAGENTS_EXECUTED"


@pytest.mark.asyncio
async def test_deepagents_disabled_returns_deterministic_501_gated_result(monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "false")
    plan = build_deepagents_plan("schedule a meeting for title: Weekly sync")
    result = await execute_deepagents_plan(
        twin_id="twin-1",
        plan=plan,
        actor_user_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
    )
    assert result["status"] == "disabled"
    assert result["http_status"] == 501
    assert result["error"]["code"] == "DEEPAGENTS_DISABLED"
