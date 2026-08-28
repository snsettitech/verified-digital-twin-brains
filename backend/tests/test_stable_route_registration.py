import importlib
import sys

from fastapi.testclient import TestClient


def _import_main_fresh():
    sys.modules.pop("main", None)
    importlib.invalidate_caches()
    return importlib.import_module("main")


def test_stable_routes_remain_registered_when_legacy_flags_disabled(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("PINECONE_API_KEY", "test-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("ENABLE_REALTIME_INGESTION", "false")
    monkeypatch.setenv("ENABLE_ADVISOR_RETRIEVAL", "false")

    main_module = _import_main_fresh()
    client = TestClient(main_module.app)

    health_response = client.get("/ingestion/realtime/health")
    assert health_response.status_code == 200
    assert health_response.json()["enabled"] is True

    config_response = client.get("/ingestion/realtime/config")
    assert config_response.status_code == 200
    assert config_response.json()["enabled"] is True

    query_response = client.post("/retrieval/query", json={})
    assert query_response.status_code != 404

    across_twins_response = client.post("/retrieval/query-across-twins", json={})
    assert across_twins_response.status_code != 404
