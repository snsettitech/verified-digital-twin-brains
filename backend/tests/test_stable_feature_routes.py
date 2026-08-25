import importlib

from fastapi.testclient import TestClient


def _load_app_with_env(monkeypatch, **env_overrides):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
    monkeypatch.setenv("DEV_MODE", "false")

    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    import main

    return importlib.reload(main).app


def test_realtime_config_ignores_legacy_disable_flag(monkeypatch):
    app = _load_app_with_env(monkeypatch, ENABLE_REALTIME_INGESTION="false")
    client = TestClient(app)

    response = client.get("/ingestion/realtime/config")

    assert response.status_code == 200
    assert response.json() == {"enabled": True, "compat_router": True}


def test_realtime_health_ignores_legacy_disable_flag(monkeypatch):
    app = _load_app_with_env(monkeypatch, ENABLE_REALTIME_INGESTION="false")
    client = TestClient(app)

    response = client.get("/ingestion/realtime/health")

    assert response.status_code == 200
    assert response.json()["enabled"] is True


def test_advisor_health_route_ignores_legacy_disable_flag(monkeypatch):
    app = _load_app_with_env(monkeypatch, ENABLE_ADVISOR_RETRIEVAL="false")
    import routers.retrieval_advisor as retrieval_advisor_module

    class _FakeIndex:
        def describe_index_stats(self):
            return object()

    class _FakeAdvisorClient:
        def __init__(self):
            self.index = _FakeIndex()

    monkeypatch.setattr(
        retrieval_advisor_module,
        "get_advisor_client",
        lambda: _FakeAdvisorClient(),
    )

    client = TestClient(app)
    response = client.get("/retrieval/health")

    assert "/retrieval/health" in app.openapi()["paths"]
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_advisor_health_sanitizes_failure_details(monkeypatch):
    app = _load_app_with_env(monkeypatch, ENABLE_ADVISOR_RETRIEVAL="false")
    import routers.retrieval_advisor as retrieval_advisor_module

    monkeypatch.setattr(
        retrieval_advisor_module,
        "get_advisor_client",
        lambda: (_ for _ in ()).throw(RuntimeError("sensitive backend detail")),
    )

    client = TestClient(app)
    response = client.get("/retrieval/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service unhealthy"}
