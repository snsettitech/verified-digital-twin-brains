from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import require_admin, require_tenant


client = TestClient(app)


def _tenant_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


def _admin_user():
    return {"user_id": "admin-1", "tenant_id": "tenant-1", "role": "owner"}


def _query_mock(data):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.single.return_value = query
    query.lt.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=data)
    return query


def test_resolve_escalation_creates_verified_qna_primary_route():
    app.dependency_overrides[require_tenant] = _tenant_user
    try:
        esc_lookup = _query_mock({"id": "esc-1", "twin_id": "twin-1"})
        msg_lookup = _query_mock(
            {"conversation_id": "conv-1", "created_at": "2026-02-12T00:00:00Z"}
        )
        user_msg_lookup = _query_mock([{"content": "What is your investment thesis?"}])

        with patch("routers.escalations.require_twin_access"), patch(
            "routers.escalations.resolve_db_escalation",
            new=AsyncMock(return_value={"id": "esc-1", "message_id": "msg-1"}),
        ), patch(
            "routers.escalations.create_verified_qna",
            new=AsyncMock(return_value="vq-1"),
        ) as mocked_create_vqna, patch(
            "routers.escalations.AuditLogger.log"
        ) as mocked_audit, patch(
            "routers.escalations.supabase"
        ) as mocked_supabase:
            mocked_supabase.table.side_effect = [esc_lookup, msg_lookup, user_msg_lookup]

            response = client.post(
                "/twins/twin-1/escalations/esc-1/resolve",
                json={"owner_answer": "I prioritize founder-market fit and pace."},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"
            mocked_create_vqna.assert_awaited_once()
            kwargs = mocked_create_vqna.await_args.kwargs
            assert kwargs["twin_id"] == "twin-1"
            assert kwargs["question"] == "What is your investment thesis?"
            assert kwargs["answer"] == "I prioritize founder-market fit and pace."
            assert kwargs["owner_id"] == "owner-1"
            assert "group_id" in kwargs
            mocked_audit.assert_called_once()
    finally:
        app.dependency_overrides = {}


def test_resolve_escalation_creates_verified_qna_legacy_route():
    app.dependency_overrides[require_admin] = _admin_user
    try:
        esc_lookup = _query_mock({"id": "esc-2", "twin_id": "twin-2"})
        msg_lookup = _query_mock(
            {"conversation_id": "conv-2", "created_at": "2026-02-12T00:00:00Z"}
        )
        user_msg_lookup = _query_mock([{"content": "How do you evaluate GTM risk?"}])

        with patch("routers.escalations.require_twin_access"), patch(
            "routers.escalations.resolve_db_escalation",
            new=AsyncMock(return_value={"id": "esc-2", "message_id": "msg-2"}),
        ), patch(
            "routers.escalations.create_verified_qna",
            new=AsyncMock(return_value="vq-2"),
        ) as mocked_create_vqna, patch(
            "routers.escalations.AuditLogger.log"
        ) as mocked_audit, patch(
            "routers.escalations.supabase"
        ) as mocked_supabase:
            mocked_supabase.table.side_effect = [esc_lookup, msg_lookup, user_msg_lookup]

            response = client.post(
                "/escalations/esc-2/resolve",
                json={"owner_answer": "I require clear, repeatable customer pull signals."},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"
            mocked_create_vqna.assert_awaited_once()
            kwargs = mocked_create_vqna.await_args.kwargs
            assert kwargs["twin_id"] == "twin-2"
            assert kwargs["question"] == "How do you evaluate GTM risk?"
            assert kwargs["answer"] == "I require clear, repeatable customer pull signals."
            assert kwargs["owner_id"] == "admin-1"
            assert "group_id" in kwargs
            mocked_audit.assert_called_once()
    finally:
        app.dependency_overrides = {}
