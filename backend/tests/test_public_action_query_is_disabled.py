from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from modules.schemas import PublicChatRequest
from modules.deepagents_router import build_deepagents_plan
from modules.deepagents_executor import execute_deepagents_plan
from routers import chat as chat_router


@pytest.mark.asyncio
async def test_deepagents_forbidden_for_public_or_anonymous_context(monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "true")
    monkeypatch.setenv("DEEPAGENTS_REQUIRE_APPROVAL", "true")

    plan = build_deepagents_plan("send email to jane@example.com subject: hi body: hello")
    result = await execute_deepagents_plan(
        twin_id="twin-public",
        plan=plan,
        actor_user_id=None,
        tenant_id=None,
        conversation_id="conv-1",
        interaction_context="public_share",
    )

    assert result["status"] == "forbidden"
    assert result["http_status"] == 403
    assert result["error"]["code"] == "DEEPAGENTS_FORBIDDEN_CONTEXT"

    widget_result = await execute_deepagents_plan(
        twin_id="twin-public",
        plan=plan,
        actor_user_id=None,
        tenant_id=None,
        conversation_id="conv-1",
        interaction_context="public_widget",
    )
    assert widget_result["status"] == "forbidden"
    assert widget_result["http_status"] == 403


@pytest.mark.asyncio
async def test_public_action_like_query_returns_sanitized_response_without_action_execution(monkeypatch):
    monkeypatch.setattr("modules.share_links.validate_share_token", lambda _token, _twin_id: True)
    monkeypatch.setattr(
        "modules.share_links.get_public_group_for_twin",
        lambda _twin_id: {"id": "group-public"},
    )
    monkeypatch.setattr("routers.chat.ensure_twin_active", lambda _twin_id: True)
    monkeypatch.setattr("modules.rate_limiting.check_rate_limit", lambda *args, **kwargs: (True, {}))
    monkeypatch.setattr(
        "routers.chat._run_identity_gate_passthrough",
        AsyncMock(
            return_value={
                "decision": "ANSWER",
                "owner_memory_context": "",
                "owner_memory_refs": [],
                "owner_memory": [],
            }
        ),
    )
    monkeypatch.setattr(
        "routers.chat._load_public_publish_controls",
        lambda _twin_id: {
            "published_identity_topics": set(),
            "published_policy_topics": set(),
            "published_source_ids": set(),
        },
    )
    monkeypatch.setattr("routers.chat._persist_runtime_audit", lambda **kwargs: None)

    def _fail_if_event_emitted(*_args, **_kwargs):
        raise AssertionError("Public action-like query must not emit automation events.")

    monkeypatch.setattr("modules.actions_engine.EventEmitter.emit", _fail_if_event_emitted)

    async def _fake_agent_stream(*_args, **_kwargs):
        msg = AIMessage(content="Action execution is unavailable in public or anonymous contexts.")
        msg.additional_kwargs = {
            "dialogue_mode": "ANSWER",
            "intent_label": "action_or_tool_execution",
            "workflow_intent": "write",
            "module_ids": ["mod-sensitive"],
            "routing_decision": {"intent": "write", "action": "answer", "internal": "secret"},
            "render_strategy": "source_faithful",
            "planning_output": {
                "execution_lane": {
                    "status": "forbidden",
                    "action_type": "draft_email",
                    "needs_approval": False,
                    "action_id": "draft-123",
                    "error_code": "DEEPAGENTS_FORBIDDEN_CONTEXT",
                }
            },
        }
        yield {"agent": {"messages": [msg]}}

    monkeypatch.setattr("routers.chat.run_agent_stream", _fake_agent_stream)

    req = PublicChatRequest(
        message="send email to founder@example.com subject: hello body: hi",
        conversation_history=None,
    )
    raw_req = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    payload = await chat_router.public_chat_endpoint(
        twin_id="twin-public",
        token="token-abc12345",
        request=req,
        req_raw=raw_req,
        x_langfuse_trace_id=None,
    )

    assert payload["status"] == "answer"
    assert "unavailable" in payload["response"].lower()
    assert payload["owner_memory_refs"] == []
    assert payload["owner_memory_topics"] == []
    assert payload["routing_decision"] == {}
    assert payload["debug_snapshot"] == {}
    assert payload["online_eval"]["skipped_reason"] == "public_action_query_guarded"
