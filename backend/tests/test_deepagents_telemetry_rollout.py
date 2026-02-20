import os
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX_NAME", "test-index")
os.environ.setdefault("SUPABASE_KEY", "test-key")

from main import app
from modules.auth_guard import get_current_user
from modules.deepagents_executor import execute_deepagents_plan
from modules.deepagents_router import build_deepagents_plan


client = TestClient(app)


def _parse_sse_blocks(raw_text: str):
    blocks = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            blocks.append(json.loads(line))
        except Exception:
            continue
    return blocks


def _owner_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


@pytest.mark.asyncio
async def test_deepagents_allowlist_blocks_when_enabled(monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "true")
    monkeypatch.setenv("DEEPAGENTS_REQUIRE_APPROVAL", "true")
    monkeypatch.setenv("DEEPAGENTS_ALLOWLIST_TWIN_IDS", "twin-allowlisted")
    monkeypatch.delenv("DEEPAGENTS_ALLOWLIST_TENANT_IDS", raising=False)

    plan = build_deepagents_plan("send email to jane@example.com subject: hi body: hello")
    result = await execute_deepagents_plan(
        twin_id="twin-blocked",
        plan=plan,
        actor_user_id="owner-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
        interaction_context="owner_chat",
    )

    assert result["status"] == "forbidden"
    assert result["http_status"] == 403
    assert result["error"]["code"] == "DEEPAGENTS_NOT_ALLOWLISTED"


def test_owner_metadata_emits_deepagents_telemetry_fields():
    app.dependency_overrides[get_current_user] = _owner_user
    gate_mock = AsyncMock(
        return_value={
            "decision": "ANSWER",
            "requires_owner": False,
            "reason": "test",
            "owner_memory": [],
            "owner_memory_refs": [],
            "owner_memory_context": "",
        }
    )

    async def _fake_stream(*_args, **_kwargs):
        msg = AIMessage(content="Action plan is ready and waiting for approval.")
        msg.additional_kwargs = {
            "intent_label": "action_or_tool_execution",
            "module_ids": [],
            "routing_decision": {"intent": "write", "action": "answer"},
            "planning_output": {
                "answerability": {"answerability": "direct"},
                "execution_lane": {
                    "status": "needs_approval",
                    "needs_approval": True,
                    "action_type": "draft_email",
                    "action_id": "draft-123",
                },
                "telemetry": {
                    "deepagents_route_rate": 1,
                    "deepagents_forbidden_context_rate": 0,
                    "deepagents_missing_params_rate": 0,
                    "deepagents_needs_approval_rate": 1,
                    "deepagents_executed_rate": 0,
                    "public_action_query_guarded_rate": 0,
                    "selection_recovery_failure_rate": 0,
                },
            },
        }
        yield {"agent": {"messages": [msg]}}

    try:
        with patch("routers.chat.verify_twin_ownership"), patch(
            "routers.chat.ensure_twin_active"
        ), patch(
            "routers.chat.get_user_group", new=AsyncMock(return_value=None)
        ), patch(
            "routers.chat.get_default_group", new=AsyncMock(return_value={"id": "group-1"})
        ), patch(
            "routers.chat._fetch_conversation_record",
            return_value={
                "id": "conv-1",
                "twin_id": "twin-1",
                "group_id": "group-1",
                "interaction_context": "owner_chat",
                "training_session_id": None,
            },
        ), patch(
            "routers.chat.get_messages", return_value=[]
        ), patch(
            "routers.chat.log_interaction"
        ), patch(
            "routers.chat.run_identity_gate", gate_mock
        ), patch(
            "routers.chat.run_agent_stream", _fake_stream
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ):
            resp = client.post(
                "/chat/twin-1",
                json={"query": "send email to jane@example.com", "conversation_id": "conv-1"},
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            assert metadata is not None
            counters = metadata.get("turn_counters")
            assert isinstance(counters, dict)
            assert counters["deepagents_route_rate"] == 1
            assert counters["deepagents_needs_approval_rate"] == 1
            assert "deepagents_forbidden_context_rate" in counters
            assert "deepagents_missing_params_rate" in counters
            assert "deepagents_executed_rate" in counters
            assert "public_action_query_guarded_rate" in counters
            assert "selection_recovery_failure_rate" in counters
    finally:
        app.dependency_overrides = {}
