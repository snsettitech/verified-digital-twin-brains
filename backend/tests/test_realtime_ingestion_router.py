from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import verify_owner


client = TestClient(app)


def _owner_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


def test_start_realtime_session_success():
    app.dependency_overrides[verify_owner] = _owner_user
    try:
        with patch("routers.ingestion_realtime.verify_twin_ownership"), patch(
            "routers.ingestion_realtime.ensure_twin_active"
        ), patch(
            "routers.ingestion_realtime.start_realtime_session",
            return_value={
                "id": "session-1",
                "twin_id": "twin-1",
                "tenant_id": "tenant-1",
                "owner_id": "owner-1",
                "status": "active",
                "source_id": "source-1",
            },
        ):
            resp = client.post(
                "/ingest/realtime/sessions/twin-1/start",
                json={"title": "Realtime Test"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "active"
            assert body["session"]["id"] == "session-1"
            assert body["session"]["source_id"] == "source-1"
    finally:
        app.dependency_overrides = {}


def test_append_realtime_event_success():
    app.dependency_overrides[verify_owner] = _owner_user
    try:
        with patch("routers.ingestion_realtime.verify_twin_ownership"), patch(
            "routers.ingestion_realtime.ensure_twin_active"
        ), patch(
            "routers.ingestion_realtime.get_realtime_session",
            return_value={
                "id": "session-1",
                "twin_id": "twin-1",
                "tenant_id": "tenant-1",
                "owner_id": "owner-1",
                "status": "active",
                "source_id": "source-1",
                "appended_chars": 10,
                "indexed_chars": 0,
            },
        ), patch(
            "routers.ingestion_realtime.append_realtime_event",
            return_value={
                "status": "appended",
                "session": {"id": "session-1"},
                "event": {"sequence_no": 1},
                "should_index": True,
            },
        ), patch(
            "routers.ingestion_realtime.enqueue_realtime_processing_job",
            return_value={"enqueued": True, "job_id": "job-1"},
        ):
            resp = client.post(
                "/ingest/realtime/sessions/session-1/append",
                json={"sequence_no": 1, "text_chunk": "hello"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "appended"
            assert body["append"]["event"]["sequence_no"] == 1
            assert body["queued_job"]["enqueued"] is True
            assert body["queued_job"]["job_id"] == "job-1"
    finally:
        app.dependency_overrides = {}


def test_commit_realtime_session_success():
    app.dependency_overrides[verify_owner] = _owner_user
    try:
        with patch("routers.ingestion_realtime.verify_twin_ownership"), patch(
            "routers.ingestion_realtime.ensure_twin_active"
        ), patch(
            "routers.ingestion_realtime.get_realtime_session",
            return_value={
                "id": "session-1",
                "twin_id": "twin-1",
                "tenant_id": "tenant-1",
                "owner_id": "owner-1",
                "status": "active",
                "source_id": "source-1",
            },
        ), patch(
            "routers.ingestion_realtime.commit_realtime_session",
            new=AsyncMock(
                return_value={
                    "session": {"id": "session-1", "status": "committed"},
                    "processing": {"processed": True, "chunks": 3},
                }
            ),
        ):
            resp = client.post(
                "/ingest/realtime/sessions/session-1/commit",
                json={"metadata": {"test": True}, "process_async": False},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "committed"
            assert body["session"]["status"] == "committed"
            assert body["processing"]["processed"] is True
    finally:
        app.dependency_overrides = {}


def test_commit_realtime_session_async_enqueues_job():
    app.dependency_overrides[verify_owner] = _owner_user
    try:
        with patch("routers.ingestion_realtime.verify_twin_ownership"), patch(
            "routers.ingestion_realtime.ensure_twin_active"
        ), patch(
            "routers.ingestion_realtime.get_realtime_session",
            return_value={
                "id": "session-1",
                "twin_id": "twin-1",
                "tenant_id": "tenant-1",
                "owner_id": "owner-1",
                "status": "active",
                "source_id": "source-1",
            },
        ), patch(
            "routers.ingestion_realtime.mark_realtime_session_committed",
            return_value={"id": "session-1", "status": "committed"},
        ), patch(
            "routers.ingestion_realtime.enqueue_realtime_processing_job",
            return_value={"enqueued": True, "job_id": "job-2"},
        ):
            resp = client.post(
                "/ingest/realtime/sessions/session-1/commit",
                json={"metadata": {"test": True}, "process_async": True},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "committed_queued"
            assert body["session"]["status"] == "committed"
            assert body["queued_job"]["job_id"] == "job-2"
    finally:
        app.dependency_overrides = {}


def test_commit_realtime_session_async_falls_back_when_queue_fails():
    app.dependency_overrides[verify_owner] = _owner_user
    try:
        with patch("routers.ingestion_realtime.verify_twin_ownership"), patch(
            "routers.ingestion_realtime.ensure_twin_active"
        ), patch(
            "routers.ingestion_realtime.get_realtime_session",
            return_value={
                "id": "session-1",
                "twin_id": "twin-1",
                "tenant_id": "tenant-1",
                "owner_id": "owner-1",
                "status": "active",
                "source_id": "source-1",
            },
        ), patch(
            "routers.ingestion_realtime.mark_realtime_session_committed",
            return_value={"id": "session-1", "status": "committed"},
        ), patch(
            "routers.ingestion_realtime.enqueue_realtime_processing_job",
            side_effect=Exception("queue unavailable"),
        ), patch(
            "routers.ingestion_realtime.process_realtime_session",
            new=AsyncMock(return_value={"processed": True, "chunks": 2}),
        ):
            resp = client.post(
                "/ingest/realtime/sessions/session-1/commit",
                json={"metadata": {"test": True}, "process_async": True},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "committed_processed_fallback"
            assert body["processing"]["processed"] is True
            assert "queue_error" in body
    finally:
        app.dependency_overrides = {}
