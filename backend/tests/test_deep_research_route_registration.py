import importlib
import sys


def _load_main(monkeypatch, *, deep_research_enabled: str, name_only_enabled: str):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("DEEP_RESEARCH_ENABLED", deep_research_enabled)
    monkeypatch.setenv("NAME_ONLY_DEEP_RESEARCH_ENABLED", name_only_enabled)

    sys.modules.pop("main", None)
    importlib.invalidate_caches()
    return importlib.import_module("main")


def _route_paths(app) -> set[str]:
    paths: set[str] = set()
    for route in app.router.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)

        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            for child_route in getattr(original_router, "routes", []):
                child_path = getattr(child_route, "path", None)
                if child_path:
                    paths.add(child_path)

    return paths


def test_core_deep_research_routes_remain_registered_when_legacy_flag_false(monkeypatch):
    main = _load_main(
        monkeypatch,
        deep_research_enabled="false",
        name_only_enabled="true",
    )

    routes = _route_paths(main.app)

    assert "/twins/{twin_id}/crawls" in routes
    assert "/twins/{twin_id}/research/{research_run_id}/continue-claims" in routes
    assert "/deep-research/runs" in routes


def test_name_only_routes_still_register_when_name_only_flag_false(monkeypatch):
    main = _load_main(
        monkeypatch,
        deep_research_enabled="false",
        name_only_enabled="false",
    )

    routes = _route_paths(main.app)

    assert "/twins/{twin_id}/crawls" in routes
    assert "/twins/{twin_id}/research/{research_run_id}/continue-claims" in routes
    assert "/deep-research/runs" in routes
