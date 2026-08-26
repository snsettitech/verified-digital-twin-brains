import importlib


REQUIRED_ENV_VARS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "test-key",
    "OPENAI_API_KEY": "test-key",
    "PINECONE_API_KEY": "test-key",
    "PINECONE_INDEX_NAME": "test-index",
    "SUPABASE_KEY": "test-key",
}


def _load_main_module(monkeypatch, **env_overrides):
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    import main

    return importlib.reload(main)


def _has_route(app, path: str, method: str) -> bool:
    for route in app.routes:
        nested_router = getattr(route, "original_router", None)
        if nested_router is not None:
            for nested_route in getattr(nested_router, "routes", []):
                nested_path = getattr(nested_route, "path", "")
                nested_methods = getattr(nested_route, "methods", set())
                if nested_path == path and method.upper() in nested_methods:
                    return True

        route_path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if route_path == path and method.upper() in methods:
            return True
    return False


def test_realtime_ingestion_routes_remain_available_when_legacy_flag_false(monkeypatch):
    main = _load_main_module(monkeypatch, ENABLE_REALTIME_INGESTION="false")

    assert _has_route(main.app, "/ingestion/realtime/health", "GET")
    assert _has_route(main.app, "/ingestion/realtime/config", "GET")


def test_advisor_retrieval_routes_remain_available_when_legacy_flag_false(monkeypatch):
    main = _load_main_module(monkeypatch, ENABLE_ADVISOR_RETRIEVAL="false")

    assert _has_route(main.app, "/retrieval/query", "POST")
    assert _has_route(main.app, "/retrieval/query-across-twins", "POST")
    assert _has_route(main.app, "/retrieval/health", "GET")
