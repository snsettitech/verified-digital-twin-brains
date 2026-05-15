import importlib
import sys


REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "service-key",
    "OPENAI_API_KEY": "openai-key",
    "PINECONE_API_KEY": "pinecone-key",
    "PINECONE_INDEX_NAME": "pinecone-index",
    "JWT_SECRET": "jwt-secret",
    "DEV_MODE": "false",
}


def _load_main(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("ENABLE_REALTIME_INGESTION", "false")
    monkeypatch.setenv("ENABLE_ADVISOR_RETRIEVAL", "false")
    monkeypatch.setenv("ENABLE_VC_ROUTES", "true")

    sys.modules.pop("main", None)
    import main

    return importlib.reload(main)


def _route_paths(app) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_launched_routes_ignore_legacy_disable_flags(monkeypatch):
    main = _load_main(monkeypatch)
    paths = _route_paths(main.app)

    assert "/ingestion/realtime/health" in paths
    assert "/ingestion/realtime/config" in paths
    assert "/retrieval/query" in paths


def test_vc_routes_remain_absent_without_live_router(monkeypatch):
    main = _load_main(monkeypatch)
    paths = _route_paths(main.app)

    assert not any(path.startswith("/api/vc") for path in paths)
