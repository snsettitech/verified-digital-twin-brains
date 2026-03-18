from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adk_core.schemas.api import ChatTurnResponse
from adk_core.schemas.artifacts import (
    ResearchArtifact,
    ResearchClaim,
    ResearchQuoteCandidate,
    ResearchSource,
    ResearchTimelineItem,
)
from routers import chat, deep_research, personas


def _build_app(router) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _sample_research_artifact() -> ResearchArtifact:
    return ResearchArtifact(
        subject_identity={"canonical_name": "Ada Lovelace"},
        source_registry=[
            ResearchSource(
                source_id="src-1",
                url="https://example.com/ada",
                title="Ada Profile",
                extracted_text="Ada discussed computation and analytical engines.",
            )
        ],
        extracted_claims=[
            ResearchClaim(
                claim_id="claim-1",
                text="Ada worked on analytical engine notes.",
                source_ids=["src-1"],
            )
        ],
        timeline=[
            ResearchTimelineItem(
                date_or_range="1843",
                event="Published analytical engine notes.",
                source_ids=["src-1"],
            )
        ],
        verified_quote_candidates=[
            ResearchQuoteCandidate(
                quote="The analytical engine weaves algebraic patterns.",
                source_id="src-1",
                confidence=0.92,
            )
        ],
        synthesis_summary="Ada speaks with technical precision and historical breadth.",
        compile_metadata={"source": "test"},
    )


def test_owner_chat_turn_uses_v2_contract(monkeypatch):
    calls = {}

    async def fake_run_chat_turn(**kwargs):
        calls.update(kwargs)
        return ChatTurnResponse(
            conversation_id="conv-1",
            message="I think through first principles.",
            citations=["src-1"],
            persona_version="adk-v1",
            surface=kwargs["surface"],
        )

    monkeypatch.setattr(chat, "run_chat_turn", fake_run_chat_turn)
    monkeypatch.setattr(chat, "verify_twin_ownership", lambda twin_id, user: True)
    monkeypatch.setattr(chat, "ensure_twin_active", lambda twin_id: True)

    app = _build_app(chat.router)
    app.dependency_overrides[chat.require_tenant] = lambda: {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
    }
    client = TestClient(app)

    response = client.post(
        "/v2/chat/owner/twin-1",
        json={"message": "  Tell   me about your thinking  "},
    )

    assert response.status_code == 200
    assert response.json()["surface"] == "owner"
    assert calls["surface"] == "owner"
    assert calls["tenant_id"] == "tenant-1"
    assert calls["message"] == "Tell me about your thinking"


def test_widget_chat_stream_emits_sse_events(monkeypatch):
    async def fake_stream_chat_turn(**kwargs):
        del kwargs
        yield {"type": "session_started", "conversation_id": "conv-1"}
        yield {"type": "assistant_final", "message": "Shipping matters."}
        yield {"type": "citations", "citations": ["src-1"]}
        yield {"type": "done"}

    monkeypatch.setattr(chat, "stream_chat_turn", fake_stream_chat_turn)
    monkeypatch.setattr(chat, "_widget_access_or_404", lambda twin_id: None)
    monkeypatch.setattr(chat, "ensure_twin_active", lambda twin_id: True)

    app = _build_app(chat.router)
    client = TestClient(app)

    response = client.post("/v2/chat/widget/twin-1/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert "event: session_started" in response.text
    assert "event: assistant_final" in response.text
    assert "event: citations" in response.text
    assert "event: done" in response.text


def test_public_chat_turn_routes_to_public_surface(monkeypatch):
    calls = {}

    async def fake_run_chat_turn(**kwargs):
        calls.update(kwargs)
        return ChatTurnResponse(
            conversation_id="conv-2",
            message="I would approach it methodically.",
            citations=[],
            persona_version="adk-v2",
            surface=kwargs["surface"],
        )

    monkeypatch.setattr(chat, "run_chat_turn", fake_run_chat_turn)
    monkeypatch.setattr(chat, "_public_access_or_404", lambda twin_id, token: None)
    monkeypatch.setattr(chat, "ensure_twin_active", lambda twin_id: True)

    app = _build_app(chat.router)
    client = TestClient(app)

    response = client.post(
        "/v2/chat/public/twin-9/token-123",
        json={"message": "What matters most to you?"},
    )

    assert response.status_code == 200
    assert response.json()["surface"] == "public"
    assert calls["surface"] == "public"
    assert calls["share_token"] == "token-123"


def test_create_research_run_uses_v2_shape(monkeypatch):
    class FakeService:
        async def create_run(self, **kwargs):
            return {
                "id": "run-1",
                "twin_id": kwargs.get("twin_id"),
                "subject_name": kwargs["name"],
                "status": "queued",
                "created_at": "2026-03-18T00:00:00Z",
                "updated_at": "2026-03-18T00:00:00Z",
            }

    monkeypatch.setattr(deep_research, "get_name_deep_research_service", lambda: FakeService())
    monkeypatch.setattr(deep_research, "verify_twin_ownership", lambda twin_id, user: True)

    app = _build_app(deep_research.router)
    app.dependency_overrides[deep_research.require_tenant] = lambda: {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
    }
    client = TestClient(app)

    response = client.post(
        "/v2/research/runs",
        json={"subject_name": "  Ada   Lovelace  ", "twin_id": "twin-1", "hints": {"company": "Analytical Engine"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-1"
    assert payload["subject_name"] == "Ada Lovelace"
    assert payload["status"] == "queued"


def test_compile_research_run_returns_persona_payload(monkeypatch):
    artifact = _sample_research_artifact()

    class FakeService:
        def parse_artifact(self, payload):
            assert payload["synthesis_summary"] == artifact.synthesis_summary
            return artifact

    monkeypatch.setattr(deep_research, "verify_twin_ownership", lambda twin_id, user: True)
    monkeypatch.setattr(deep_research, "get_name_deep_research_service", lambda: FakeService())
    monkeypatch.setattr(
        deep_research,
        "get_research_repository",
        lambda: SimpleNamespace(
            get_artifact=lambda run_id, tenant_id: {
                "artifact_json": artifact.model_dump(mode="json")
            }
        ),
    )
    async def fake_run_compiler_pipeline(**kwargs):
        del kwargs
        return {
            "artifact_id": "persona-1",
            "version": "adk-20260318",
            "status": "active",
            "quote_count": 1,
        }

    monkeypatch.setattr(deep_research, "run_compiler_pipeline", fake_run_compiler_pipeline)
    monkeypatch.setattr(
        deep_research,
        "get_persona_repository",
        lambda: SimpleNamespace(
            get_active_artifact=lambda twin_id, tenant_id: {
                "artifact_json": {"version": "adk-20260318", "subject_name": "Ada Lovelace"}
            }
        ),
    )

    app = _build_app(deep_research.router)
    app.dependency_overrides[deep_research.require_tenant] = lambda: {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
    }
    client = TestClient(app)

    response = client.post(
        "/v2/research/runs/run-1/compile",
        json={"twin_id": "twin-1", "publish": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_id"] == "persona-1"
    assert payload["persona"]["version"] == "adk-20260318"


def test_persona_route_returns_active_artifact(monkeypatch):
    monkeypatch.setattr(personas, "verify_twin_ownership", lambda twin_id, user: True)
    monkeypatch.setattr(
        personas,
        "get_persona_repository",
        lambda: SimpleNamespace(
            get_active_artifact=lambda twin_id, tenant_id: {
                "artifact_json": {"version": "adk-v3", "subject_name": "Ada Lovelace"}
            }
        ),
    )

    app = _build_app(personas.router)
    app.dependency_overrides[personas.require_tenant] = lambda: {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
    }
    client = TestClient(app)

    response = client.get("/v2/personas/twin-1")

    assert response.status_code == 200
    assert response.json()["version"] == "adk-v3"
