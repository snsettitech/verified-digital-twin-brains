import importlib
import os
from contextlib import contextmanager

from fastapi.testclient import TestClient


def _has_route(app, path: str, method: str) -> bool:
    for route in app.routes:
        route_path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if route_path == path and method.upper() in methods:
            return True
    return False


@contextmanager
def _reloaded_main(**env_overrides):
    required_env = {
        "SUPABASE_URL": "https://example.supabase.co",
        "OPENAI_API_KEY": "test-openai-key",
        "PINECONE_API_KEY": "test-pinecone-key",
        "PINECONE_INDEX_NAME": "test-index",
        "SUPABASE_SERVICE_KEY": "test-supabase-service-key",
    }
    merged_overrides = {**required_env, **env_overrides}
    previous = {key: os.environ.get(key) for key in merged_overrides}

    for key, value in merged_overrides.items():
        os.environ[key] = value

    import main as main_module

    try:
        yield importlib.reload(main_module)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_realtime_ingestion_routes_ignore_removed_flag_env():
    with _reloaded_main(ENABLE_REALTIME_INGESTION="false") as main_module:
        assert _has_route(main_module.app, "/ingestion/realtime/health", "GET")

        client = TestClient(main_module.app)
        response = client.get("/ingestion/realtime/health")

        assert response.status_code == 200
        assert response.json()["enabled"] is True


def test_retrieval_advisor_routes_ignore_removed_flag_env():
    with _reloaded_main(ENABLE_ADVISOR_RETRIEVAL="false") as main_module:
        assert _has_route(main_module.app, "/retrieval/query", "POST")
        assert _has_route(main_module.app, "/retrieval/query-across", "POST")
        assert _has_route(main_module.app, "/retrieval/delete", "POST")
