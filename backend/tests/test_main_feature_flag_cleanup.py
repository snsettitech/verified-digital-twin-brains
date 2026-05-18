import importlib
import sys

from fastapi.testclient import TestClient


def _load_main_with_legacy_flags(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "test")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("PINECONE_API_KEY", "test")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test")
    monkeypatch.setenv("JWT_SECRET", "test")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("DEEP_RESEARCH_ENABLED", "false")
    monkeypatch.setenv("ENABLE_REALTIME_INGESTION", "false")
    monkeypatch.setenv("ENABLE_ADVISOR_RETRIEVAL", "false")
    monkeypatch.setenv("ENABLE_VC_ROUTES", "false")

    sys.modules.pop("main", None)
    importlib.invalidate_caches()
    return importlib.import_module("main")


def test_legacy_disable_flags_do_not_remove_launched_routes(monkeypatch):
    main = _load_main_with_legacy_flags(monkeypatch)

    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()))))
        for route in main.app.routes
    }

    assert any(path == "/ingestion/realtime/health" for path, _methods in routes)
    assert any(path == "/retrieval/query" for path, _methods in routes)
    assert not any(path.startswith("/api/vc") for path, _methods in routes)


def test_realtime_compat_endpoints_ignore_removed_flag_env(monkeypatch):
    main = _load_main_with_legacy_flags(monkeypatch)
    client = TestClient(main.app)

    health = client.get("/ingestion/realtime/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "feature": "realtime_ingestion",
        "enabled": True,
        "mode": "compat",
    }

    config = client.get("/ingestion/realtime/config")
    assert config.status_code == 200
    assert config.json() == {
        "enabled": True,
        "compat_router": True,
        "route_registered": True,
    }
