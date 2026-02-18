from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import get_current_user


client = TestClient(app)


def _owner_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


def test_get_active_twin_spec_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.twin_runtime.verify_twin_ownership"), patch(
            "routers.twin_runtime.ensure_twin_active"
        ), patch(
            "routers.twin_runtime.get_active_persona_spec",
            return_value={
                "version": "1.2.3",
                "spec": {
                    "identity_voice": {},
                    "decision_policy": {},
                    "interaction_style": {},
                    "deterministic_rules": {},
                },
            },
        ):
            resp = client.get("/twins/twin-1/twin-spec/active")
            assert resp.status_code == 200
            body = resp.json()
            assert body["active"] is True
            assert body["source_persona_spec_version"] == "1.2.3"
            assert body["twin_spec"]["version"] == "1.2.3"
    finally:
        app.dependency_overrides = {}


def test_create_learning_input_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.twin_runtime.verify_twin_ownership"), patch(
            "routers.twin_runtime.ensure_twin_active"
        ), patch(
            "routers.twin_runtime.create_learning_input",
            return_value={"id": "li-1", "status": "pending", "input_type": "add_faq_answer"},
        ):
            resp = client.post(
                "/twins/twin-1/learning-inputs",
                json={
                    "input_type": "add_faq_answer",
                    "payload": {"question": "Q", "answer": "A"},
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "pending"
            assert body["learning_input"]["id"] == "li-1"
    finally:
        app.dependency_overrides = {}


def test_list_owner_review_queue_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.twin_runtime.verify_twin_ownership"), patch(
            "routers.twin_runtime.ensure_twin_active"
        ), patch(
            "routers.twin_runtime.list_owner_review_queue",
            return_value=[{"id": "rq-1", "status": "pending"}],
        ):
            resp = client.get("/twins/twin-1/owner-review-queue")
            assert resp.status_code == 200
            body = resp.json()
            assert body["count"] == 1
            assert body["items"][0]["id"] == "rq-1"
    finally:
        app.dependency_overrides = {}

