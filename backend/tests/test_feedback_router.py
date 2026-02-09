from unittest.mock import patch
import types
import sys

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_feedback_requires_langfuse_or_local_twin_context():
    fake_langfuse = types.SimpleNamespace(get_client=lambda: None)
    with patch.dict(sys.modules, {"langfuse": fake_langfuse}), patch(
        "routers.feedback.record_feedback_training_event", return_value=None
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
    ) as mocked_store:
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
