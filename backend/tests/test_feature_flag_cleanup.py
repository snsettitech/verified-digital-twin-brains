import importlib
import sys

from fastapi.testclient import TestClient


def _set_required_startup_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "index-name")


def _reload_main():
    if "main" in sys.modules:
        return importlib.reload(sys.modules["main"])
    return importlib.import_module("main")

def test_realtime_ingestion_routes_remain_available_when_legacy_flag_disabled(monkeypatch):
    _set_required_startup_env(monkeypatch)
    monkeypatch.setenv("ENABLE_REALTIME_INGESTION", "false")
    main = _reload_main()
    client = TestClient(main.app)

    health_response = client.get("/ingestion/realtime/health")
    assert health_response.status_code == 200
    assert health_response.json()["enabled"] is True

    response = client.get("/ingestion/realtime/config")
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "compat_router": True}


def test_advisor_retrieval_routes_remain_available_when_legacy_flag_disabled(monkeypatch):
    _set_required_startup_env(monkeypatch)
    monkeypatch.setenv("ENABLE_ADVISOR_RETRIEVAL", "false")
    main = _reload_main()
    response = TestClient(main.app).get("/retrieval/health")

    assert response.status_code == 503
    assert "Service unhealthy" in response.json()["detail"]
