import importlib
import os

from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-key")
os.environ.setdefault("PINECONE_INDEX_NAME", "test-index")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

import main as main_module


def _reload_main():
    return importlib.reload(main_module)


def _iter_routes(routes):
    for route in routes:
        route_path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if route_path and methods:
            yield route_path, methods

        original_router = getattr(route, "original_router", None)
        nested_routes = getattr(original_router, "routes", None)
        if nested_routes:
            yield from _iter_routes(nested_routes)


def _has_route(app, path: str, method: str) -> bool:
    for route_path, methods in _iter_routes(app.router.routes):
        if route_path == path and method.upper() in methods:
            return True
    return False


def test_realtime_ingestion_routes_ignore_legacy_disable_flag(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("ENABLE_REALTIME_INGESTION", "false")
        reloaded_main = _reload_main()
        client = TestClient(reloaded_main.app)

        response = client.get("/ingestion/realtime/config")
        assert response.status_code == 200
        assert response.json()["enabled"] is True

    _reload_main()


def test_advisor_retrieval_routes_ignore_legacy_disable_flag(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("ENABLE_ADVISOR_RETRIEVAL", "false")
        reloaded_main = _reload_main()
        assert _has_route(reloaded_main.app, "/retrieval/health", "GET")
        assert _has_route(reloaded_main.app, "/retrieval/query", "POST")

    _reload_main()


def test_deep_research_routes_ignore_legacy_disable_flag(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("DEEP_RESEARCH_ENABLED", "false")
        reloaded_main = _reload_main()
        assert _has_route(reloaded_main.app, "/twins/{twin_id}/crawls", "GET")
        assert _has_route(reloaded_main.app, "/deep-research/runs", "POST")

    _reload_main()
