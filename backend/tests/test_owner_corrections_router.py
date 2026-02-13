from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import verify_owner


client = TestClient(app)


def _owner_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


def test_owner_correction_creates_memory_and_verified_qna():
    app.dependency_overrides[verify_owner] = _owner_user
    try:
        with patch("routers.owner_memory.verify_twin_ownership"), patch(
            "routers.owner_memory.create_owner_memory",
            return_value={"id": "mem-1"},
        ), patch(
            "routers.owner_memory.create_verified_qna",
            new=AsyncMock(return_value="vq-1"),
        ), patch(
            "routers.owner_memory.create_memory_event",
            new=AsyncMock(return_value={"id": "evt-1"}),
        ):
            resp = client.post(
                "/twins/twin-1/owner-corrections",
                json={
                    "question": "What is your hiring philosophy?",
                    "corrected_answer": "I hire for ownership and learning velocity.",
                    "memory_type": "belief",
                    "create_verified_qna_entry": True,
                },
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["status"] == "applied"
            assert payload["owner_memory_id"] == "mem-1"
            assert payload["verified_qna_id"] == "vq-1"
    finally:
        app.dependency_overrides = {}

