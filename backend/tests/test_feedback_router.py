from unittest.mock import patch
import types
import sys

import pytest
from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import get_current_user


client = TestClient(app)

def _owner_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


@pytest.fixture(autouse=True)
def _auth_override():
    app.dependency_overrides[get_current_user] = _owner_user
    yield
    app.dependency_overrides = {}


def test_feedback_requires_langfuse_or_local_twin_context():
    fake_langfuse = types.SimpleNamespace(get_client=lambda: None)
    with patch.dict(sys.modules, {"langfuse": fake_langfuse}), patch(
        "routers.feedback.record_feedback_training_event", return_value=None
    ), patch(
        "routers.feedback.verify_twin_ownership", return_value=True
    ):
        resp = client.post(
            "/feedback/trace-1",
            json={"score": 1, "reason": "helpful"},
        )
        assert resp.status_code == 503
        assert "Provide twin_id/conversation_id" in resp.json()["detail"]


def test_feedback_stores_locally_when_twin_provided():
    fake_langfuse = types.SimpleNamespace(get_client=lambda: None)
    with patch.dict(sys.modules, {"langfuse": fake_langfuse}), patch(
        "routers.feedback.record_feedback_training_event",
        return_value={"id": "evt-1"},
    ) as mocked_store, patch(
        "routers.feedback.verify_twin_ownership", return_value=True
    ), patch(
        "routers.feedback.verify_conversation_ownership", return_value=True
    ):
        resp = client.post(
            "/feedback/trace-2",
            json={
                "score": -1,
                "reason": "incorrect",
                "comment": "Wrong pricing detail",
                "twin_id": "twin-1",
                "conversation_id": "conv-1",
                "intent_label": "factual_with_evidence",
                "module_ids": ["procedural.factual.cite_or_disclose_uncertainty"],
                "interaction_context": "public_share",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "stored locally" in body["message"]
        mocked_store.assert_called_once()


def test_feedback_auto_enqueues_feedback_learning_job():
    fake_langfuse = types.SimpleNamespace(get_client=lambda: None)
    with patch.dict(sys.modules, {"langfuse": fake_langfuse}), patch(
        "routers.feedback.record_feedback_training_event",
        return_value={"id": "evt-2"},
    ), patch(
        "routers.feedback.verify_twin_ownership", return_value=True
    ), patch(
        "routers.feedback.enqueue_feedback_learning_job",
        return_value={"enqueued": True, "job_id": "job-123"},
    ) as mocked_enqueue:
        resp = client.post(
            "/feedback/trace-3",
            json={
                "score": 1,
                "reason": "helpful",
                "twin_id": "twin-42",
                "intent_label": "meta_or_system",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        mocked_enqueue.assert_called_once()
        kwargs = mocked_enqueue.call_args.kwargs
        assert kwargs["twin_id"] == "twin-42"
        assert kwargs["trigger"] == "feedback_event"


def test_feedback_requires_authenticated_user():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": None, "role": "visitor"}
    try:
        resp = client.post(
            "/feedback/trace-unauth",
            json={"score": 1, "reason": "helpful"},
        )
        assert resp.status_code == 401 or resp.status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = _owner_user
