from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import get_current_user


client = TestClient(app)


def _owner_user():
    return {
        "user_id": "owner-1",
        "tenant_id": "tenant-1",
        "role": "owner",
    }


def test_start_training_session_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.training_sessions.verify_twin_ownership"), patch(
            "routers.training_sessions.ensure_twin_active"
        ), patch(
            "routers.training_sessions.start_training_session",
            return_value={
                "id": "ts-1",
                "twin_id": "twin-1",
                "owner_id": "owner-1",
                "status": "active",
            },
        ):
            resp = client.post(
                "/twins/twin-1/training-sessions/start",
                json={"metadata": {"source": "test"}},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "active"
            assert body["session"]["id"] == "ts-1"
    finally:
        app.dependency_overrides = {}


def test_stop_training_session_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.training_sessions.verify_twin_ownership"), patch(
            "routers.training_sessions.ensure_twin_active"
        ), patch(
            "routers.training_sessions.stop_training_session",
            return_value={
                "id": "ts-1",
                "twin_id": "twin-1",
                "owner_id": "owner-1",
                "status": "stopped",
            },
        ):
            resp = client.post("/twins/twin-1/training-sessions/ts-1/stop")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "stopped"
            assert body["session"]["status"] == "stopped"
    finally:
        app.dependency_overrides = {}

