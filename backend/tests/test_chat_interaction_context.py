import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from main import app
from modules.auth_guard import get_current_user


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


async def _fake_agent_stream(*_args, **_kwargs):
    msg = AIMessage(content="ok")
    msg.additional_kwargs = {
        "intent_label": "meta_or_system",
        "module_ids": ["procedural.style.smalltalk"],
        "persona_spec_version": "9.9.9",
    }
    yield {"agent": {"messages": [msg]}}


def _owner_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


def _visitor_user():
    return {"user_id": None, "tenant_id": None, "role": "visitor", "twin_id": "twin-1"}


def test_owner_chat_ignores_client_mode_spoof():
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
            "routers.chat.run_agent_stream", _fake_agent_stream
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ):
            resp = client.post(
                "/chat/twin-1",
                json={
                    "query": "hello",
                    "conversation_id": "conv-1",
                    "mode": "public",
                },
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            assert metadata is not None
            assert metadata["interaction_context"] == "owner_chat"
            assert metadata["origin_endpoint"] == "chat"
            assert metadata["intent_label"] == "meta_or_system"
            assert metadata["module_ids"] == ["procedural.style.smalltalk"]
            assert metadata["persona_spec_version"] == "9.9.9"
            assert "deterministic_gate_passed" in metadata
            assert "structure_policy_score" in metadata
            assert "voice_score" in metadata
            assert "draft_persona_score" in metadata
            assert "final_persona_score" in metadata
            assert "rewrite_applied" in metadata
            assert gate_mock.await_args.kwargs["mode"] == "owner"
    finally:
        app.dependency_overrides = {}


def test_owner_training_context_with_active_session():
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
                "interaction_context": "owner_training",
                "training_session_id": "ts-1",
            },
        ), patch(
            "routers.chat.get_messages", return_value=[]
        ), patch(
            "routers.chat.log_interaction"
        ), patch(
            "routers.chat.run_identity_gate", gate_mock
        ), patch(
            "routers.chat.run_agent_stream", _fake_agent_stream
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ), patch(
            "modules.interaction_context.get_training_session",
            return_value={"id": "ts-1", "status": "active", "owner_id": "owner-1"},
        ):
            resp = client.post(
                "/chat/twin-1",
                json={
                    "query": "train this response style",
                    "conversation_id": "conv-1",
                    "training_session_id": "ts-1",
                    "mode": "public",
                },
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            assert metadata is not None
            assert metadata["interaction_context"] == "owner_training"
            assert metadata["training_session_id"] == "ts-1"
            assert gate_mock.await_args.kwargs["mode"] == "owner"
    finally:
        app.dependency_overrides = {}


def test_visitor_cannot_spoof_owner_training():
    app.dependency_overrides[get_current_user] = _visitor_user
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
                "interaction_context": "public_widget",
                "training_session_id": None,
            },
        ), patch(
            "routers.chat.get_messages", return_value=[]
        ), patch(
            "routers.chat.log_interaction"
        ), patch(
            "routers.chat.run_identity_gate", gate_mock
        ), patch(
            "routers.chat.run_agent_stream", _fake_agent_stream
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ), patch(
            "modules.interaction_context.get_training_session",
            return_value={"id": "ts-1", "status": "active", "owner_id": "owner-1"},
        ):
            resp = client.post(
                "/chat/twin-1",
                json={
                    "query": "try spoof",
                    "conversation_id": "conv-1",
                    "training_session_id": "ts-1",
                },
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            assert metadata is not None
            assert metadata["interaction_context"] == "public_widget"
            assert gate_mock.await_args.kwargs["mode"] == "public"
    finally:
        app.dependency_overrides = {}


def test_public_share_clarify_uses_public_context_and_mode():
    gate_mock = AsyncMock(
        return_value={
            "decision": "CLARIFY",
            "question": "Can you clarify?",
            "options": [{"label": "A"}, {"label": "B"}],
            "memory_write_proposal": {"topic": "x", "memory_type": "stance"},
        }
    )
    with patch("routers.chat.ensure_twin_active"), patch(
        "modules.share_links.validate_share_token", return_value=True
    ), patch(
        "modules.share_links.get_public_group_for_twin", return_value={"id": "group-public"}
    ), patch(
        "modules.rate_limiting.check_rate_limit", return_value=(True, {})
    ), patch(
        "modules.actions_engine.EventEmitter.emit", return_value=None
    ), patch(
        "routers.chat.run_identity_gate", gate_mock
    ), patch(
        "routers.chat.create_clarification_thread", return_value={"id": "clar-1"}
    ) as clarif_mock:
        resp = client.post(
            "/public/chat/twin-1/token-abcdef12",
            json={"message": "what do you think?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["interaction_context"] == "public_share"
        assert body["share_link_id"] == "token-ab"
        assert clarif_mock.call_args.kwargs["mode"] == "public"
        assert clarif_mock.call_args.kwargs["requested_by"] == "public"


def test_public_share_answer_includes_persona_audit_fields():
    gate_mock = AsyncMock(
        return_value={
            "decision": "ANSWER",
            "owner_memory_context": "",
            "owner_memory_refs": [],
            "owner_memory": [],
        }
    )

    async def fake_public_agent_stream(*_args, **_kwargs):
        msg = AIMessage(content="public answer")
        msg.additional_kwargs = {
            "intent_label": "meta_or_system",
            "module_ids": ["procedural.style.smalltalk"],
            "persona_spec_version": "3.0.0",
        }
        yield {"agent": {"messages": [msg]}}

    with patch("routers.chat.ensure_twin_active"), patch(
        "modules.share_links.validate_share_token", return_value=True
    ), patch(
        "modules.share_links.get_public_group_for_twin", return_value={"id": "group-public"}
    ), patch(
        "modules.rate_limiting.check_rate_limit", return_value=(True, {})
    ), patch(
        "modules.actions_engine.EventEmitter.emit", return_value=None
    ), patch(
        "routers.chat.run_identity_gate", gate_mock
    ), patch(
        "routers.chat.run_agent_stream", fake_public_agent_stream
    ):
        resp = client.post(
            "/public/chat/twin-1/token-abcdef12",
            json={"message": "hello"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "answer"
        assert body["intent_label"] == "meta_or_system"
        assert body["module_ids"] == ["procedural.style.smalltalk"]
        assert "deterministic_gate_passed" in body
        assert "rewrite_applied" in body


def test_context_mismatch_forces_new_conversation():
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
            "routers.chat.create_conversation",
            return_value={"id": "conv-2"},
        ), patch(
            "routers.chat.get_messages", return_value=[]
        ), patch(
            "routers.chat.log_interaction"
        ), patch(
            "routers.chat.run_identity_gate", gate_mock
        ), patch(
            "routers.chat.run_agent_stream", _fake_agent_stream
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ), patch(
            "modules.interaction_context.get_training_session",
            return_value={"id": "ts-1", "status": "active", "owner_id": "owner-1"},
        ):
            resp = client.post(
                "/chat/twin-1",
                json={
                    "query": "train this response style",
                    "conversation_id": "conv-1",
                    "training_session_id": "ts-1",
                },
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            assert metadata is not None
            assert metadata["interaction_context"] == "owner_training"
            assert metadata["conversation_id"] == "conv-2"
            assert metadata["forced_new_conversation"] is True
            assert metadata["previous_conversation_id"] == "conv-1"
            assert "context_mismatch" in (metadata["context_reset_reason"] or "")
    finally:
        app.dependency_overrides = {}
