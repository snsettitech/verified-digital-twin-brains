import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from main import app
from modules.auth_guard import get_current_user
from modules.response_policy import UNCERTAINTY_RESPONSE


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
            assert gate_mock.await_count == 0
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


def test_public_share_clarify_is_suppressed_and_routes_to_agent():
    gate_mock = AsyncMock(
        return_value={
            "decision": "CLARIFY",
            "question": "Can you clarify?",
            "options": [{"label": "A"}, {"label": "B"}],
            "memory_write_proposal": {"topic": "x", "memory_type": "stance"},
        }
    )

    async def fake_public_agent_stream(*_args, **_kwargs):
        msg = AIMessage(content="Grounded response")
        msg.additional_kwargs = {
            "dialogue_mode": "QA_FACT",
            "intent_label": "factual_with_evidence",
            "module_ids": [],
            "routing_decision": {"action": "answer", "intent": "answer"},
            "planning_output": {"answerability": {"answerability": "direct"}},
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
            json={"message": "what do you think?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "answer"
        assert body["interaction_context"] == "public_share"
        assert body["share_link_id"] == "token-ab"
        assert gate_mock.await_args.kwargs["mode"] == "public"


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


def test_owner_chat_accepts_node_update_stream_shape():
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

    async def _fake_node_update_stream(*_args, **_kwargs):
        yield {"retrieve": {"citations": ["src-node-1"], "confidence_score": 0.73}}
        msg = AIMessage(content="node-shape answer")
        msg.additional_kwargs = {
            "intent_label": "factual_with_evidence",
            "module_ids": ["procedural.decision.cite_first"],
            "persona_spec_version": "4.2.0",
        }
        yield {"realizer": {"messages": [msg]}}

    audit_mock = AsyncMock(
        return_value=(
            "node-shape answer",
            "factual_with_evidence",
            ["procedural.decision.cite_first"],
        )
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
            "routers.chat.run_agent_stream", _fake_node_update_stream
        ), patch(
            "routers.chat._apply_persona_audit", audit_mock
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ):
            resp = client.post(
                "/chat/twin-1",
                json={"query": "give me proof", "conversation_id": "conv-1"},
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            content = next((b for b in blocks if b.get("type") == "content"), None)
            assert metadata is not None
            assert content is not None
            assert metadata["citations"] == ["src-node-1"]
            assert metadata["intent_label"] == "factual_with_evidence"
            assert metadata["module_ids"] == ["procedural.decision.cite_first"]
            assert content["content"] == "node-shape answer"
    finally:
        app.dependency_overrides = {}


def test_owner_chat_source_faithful_skips_persona_audit_rewrite():
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

    async def _fake_source_faithful_stream(*_args, **_kwargs):
        yield {"retrieve": {"citations": ["src-faithful-1"], "confidence_score": 0.91}}
        msg = AIMessage(content="Use managed containers first for faster MVP iteration.")
        msg.additional_kwargs = {
            "intent_label": "factual_with_evidence",
            "module_ids": ["procedural.decision.cite_first"],
            "persona_spec_version": "4.2.0",
            "render_strategy": "source_faithful",
            "planning_output": {"render_strategy": "source_faithful"},
        }
        yield {"realizer": {"messages": [msg]}}

    audit_mock = AsyncMock(
        return_value=(
            "This should not be used",
            "factual_with_evidence",
            ["procedural.decision.cite_first"],
        )
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
            "routers.chat.run_agent_stream", _fake_source_faithful_stream
        ), patch(
            "routers.chat._apply_persona_audit", audit_mock
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ):
            resp = client.post(
                "/chat/twin-1",
                json={"query": "What should we use for MVP infra?", "conversation_id": "conv-1"},
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            content = next((b for b in blocks if b.get("type") == "content"), None)
            assert metadata is not None
            assert content is not None
            assert metadata["render_strategy"] == "source_faithful"
            assert content["content"] == "Use managed containers first for faster MVP iteration."
            audit_mock.assert_not_awaited()
    finally:
        app.dependency_overrides = {}


def test_owner_chat_grounding_verifier_downgrades_strict_unsupported_answer():
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
        yield {
            "retrieve": {
                "citations": ["src-unsupported-1"],
                "confidence_score": 0.87,
                "retrieved_context": {
                    "results": [
                        {
                            "source_id": "src-unsupported-1",
                            "text": "The owner prefers asynchronous standups and weekly retrospectives.",
                        }
                    ]
                },
            }
        }
        msg = AIMessage(content="The owner launched a mobile gaming studio in 2012.")
        msg.additional_kwargs = {
            "intent_label": "owner_position_request",
            "module_ids": ["procedural.decision.cite_first"],
            "persona_spec_version": "4.2.0",
        }
        yield {"realizer": {"messages": [msg]}}

    audit_mock = AsyncMock(
        return_value=(
            "The owner launched a mobile gaming studio in 2012.",
            "owner_position_request",
            ["procedural.decision.cite_first"],
        )
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
            "routers.chat.run_agent_stream", _fake_stream
        ), patch(
            "routers.chat._apply_persona_audit", audit_mock
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ):
            resp = client.post(
                "/chat/twin-1",
                json={"query": "Based on my sources, what is my remote work preference?", "conversation_id": "conv-1"},
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            content = next((b for b in blocks if b.get("type") == "content"), None)
            assert metadata is not None
            assert content is not None
            assert metadata["grounding_verifier"]["supported"] is False
            assert metadata["grounding_verifier"]["support_ratio"] < 0.78
            assert content["content"].startswith(UNCERTAINTY_RESPONSE)
    finally:
        app.dependency_overrides = {}


def test_owner_chat_requires_evidence_does_not_force_hard_downgrade_for_non_strict_query():
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
        yield {
            "retrieve": {
                "citations": ["src-general-1"],
                "confidence_score": 0.84,
                "retrieved_context": {
                    "results": [
                        {
                            "source_id": "src-general-1",
                            "text": "For MVPs, managed containers are usually easier to debug and deploy consistently.",
                        }
                    ]
                },
            }
        }
        msg = AIMessage(
            content=(
                "Use managed containers first for MVP speed and reliability. "
                "This approach is always cheaper than serverless in every scenario."
            )
        )
        msg.additional_kwargs = {
            "dialogue_mode": "QA_FACT",
            "intent_label": "advice_or_stance",
            "requires_evidence": True,
            "target_owner_scope": False,
            "module_ids": ["procedural.decision.cite_first"],
        }
        yield {"realizer": {"messages": [msg]}}

    policy_mock = AsyncMock(
        return_value=(
            "Use managed containers first for MVP speed and reliability. This approach is always cheaper than serverless in every scenario.",
            {
                "enabled": True,
                "ran": False,
                "skipped_reason": "test-bypass",
                "context_chars": 0,
                "overall_score": None,
                "needs_review": None,
                "flags": [],
                "action": "none",
            },
        )
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
            "routers.chat.run_agent_stream", _fake_stream
        ), patch(
            "routers.chat._apply_online_eval_policy", policy_mock
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ):
            resp = client.post(
                "/chat/twin-1",
                json={"query": "Should we use containers or serverless for our MVP?", "conversation_id": "conv-1"},
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            content = next((b for b in blocks if b.get("type") == "content"), None)
            assert metadata is not None
            assert content is not None
            assert metadata["grounding_verifier"]["supported"] is False
            assert metadata.get("grounding_verifier_enforced") is False
            assert not content["content"].startswith(UNCERTAINTY_RESPONSE)
    finally:
        app.dependency_overrides = {}


def test_owner_chat_smalltalk_does_not_force_uncertainty_without_citations():
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

    async def _fake_smalltalk_stream(*_args, **_kwargs):
        msg = AIMessage(content="Hey! Great to chat with you.")
        msg.additional_kwargs = {
            "intent_label": "meta_or_system",
            "module_ids": ["procedural.style.smalltalk"],
            "persona_spec_version": "9.9.9",
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
            "routers.chat.run_agent_stream", _fake_smalltalk_stream
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ):
            resp = client.post(
                "/chat/twin-1",
                json={"query": "hi", "conversation_id": "conv-1"},
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            content = next((b for b in blocks if b.get("type") == "content"), None)
            assert content is not None
            assert content["content"] == "Hey! Great to chat with you."
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_online_eval_policy_low_score_falls_back_to_source_faithful(monkeypatch):
    import routers.chat as chat_router

    captured = {}

    class _FakeEvalResult:
        def __init__(self):
            self.trace_id = "trace-1"
            self.overall_score = 0.21
            self.needs_review = True
            self.flags = ["low_faithfulness"]

    class _FakePipeline:
        async def evaluate_response(self, **kwargs):
            captured.update(kwargs)
            return _FakeEvalResult()

    monkeypatch.setattr(chat_router, "ONLINE_EVAL_POLICY_ENABLED", True)
    monkeypatch.setattr(chat_router, "ONLINE_EVAL_POLICY_MIN_OVERALL_SCORE", 0.72)
    monkeypatch.setattr(chat_router, "ONLINE_EVAL_POLICY_STRICT_ONLY", False)
    monkeypatch.setattr(chat_router, "_online_eval_capable", lambda: True)
    monkeypatch.setattr(
        "modules.evaluation_pipeline.get_evaluation_pipeline",
        lambda threshold=0.7: _FakePipeline(),
    )

    rewritten, policy = await chat_router._apply_online_eval_policy(
        query="Should we use containers or serverless for our MVP?",
        response="Use what feels right for now.",
        fallback_message="I don't know.",
        contexts=[
            {
                "source_id": "src-1",
                "text": "Recommendation: Start with containers on a managed platform for predictable deployments.",
            },
            {
                "source_id": "src-1",
                "text": "Why: Serverless cold starts and timeout debugging can slow MVP iteration.",
            },
        ],
        citations=["src-1"],
        trace_id="trace-1",
        strict_grounding=False,
        source_faithful=False,
    )

    assert policy["ran"] is True
    assert policy["action"] == "fallback_source_faithful"
    assert "Recommendation:" in rewritten
    assert "containers" in rewritten.lower()
    assert "serverless" in rewritten.lower()
    assert "source=src-1" in (captured.get("context") or "")


def test_owner_chat_async_eval_uses_retrieved_chunk_text_context():
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
        yield {
            "retrieve": {
                "citations": ["src-eval-1"],
                "confidence_score": 0.88,
                "retrieved_context": {
                    "results": [
                        {
                            "source_id": "src-eval-1",
                            "text": "Retrieved chunk about containers and serverless tradeoffs.",
                        }
                    ]
                },
            }
        }
        msg = AIMessage(content="Use containers first for MVP speed.")
        msg.additional_kwargs = {
            "intent_label": "advice_or_stance",
            "module_ids": ["procedural.decision.cite_first"],
        }
        yield {"realizer": {"messages": [msg]}}

    policy_mock = AsyncMock(
        return_value=(
            "Use containers first for MVP speed.",
            {
                "enabled": True,
                "ran": False,
                "skipped_reason": "test-bypass",
                "context_chars": 0,
                "overall_score": None,
                "needs_review": None,
                "flags": [],
                "action": "none",
            },
        )
    )

    eval_call = {}

    def _capture_eval(**kwargs):
        eval_call.update(kwargs)

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
            "routers.chat._apply_online_eval_policy", policy_mock
        ), patch(
            "modules.graph_context.get_graph_stats", return_value={"has_graph": False, "node_count": 0}
        ), patch(
            "modules.evaluation_pipeline.evaluate_response_async", side_effect=_capture_eval
        ):
            resp = client.post(
                "/chat/twin-1",
                json={"query": "Should we use containers or serverless?", "conversation_id": "conv-1"},
            )
            assert resp.status_code == 200
            blocks = _parse_sse_blocks(resp.text)
            metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
            assert metadata is not None
            assert metadata["online_eval"]["skipped_reason"] == "test-bypass"

            assert "Retrieved chunk about containers and serverless tradeoffs." in (eval_call.get("context") or "")
            assert eval_call.get("context") != "src-eval-1"
            assert isinstance(eval_call.get("citations"), list)
            assert isinstance(eval_call["citations"][0], dict)
    finally:
        app.dependency_overrides = {}
