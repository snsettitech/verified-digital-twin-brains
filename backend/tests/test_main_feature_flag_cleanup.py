import importlib
import sys


REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "OPENAI_API_KEY": "test-openai-key",
    "PINECONE_API_KEY": "test-pinecone-key",
    "PINECONE_INDEX_NAME": "test-index",
    "JWT_SECRET": "test-jwt-secret",
    "DEV_MODE": "false",
}

SPECIALIZATION_ROUTE_PATHS = {
    "/config/specialization",
    "/config/specializations",
    "/twins/{twin_id}/specialization",
}


def _load_main_module(monkeypatch, enable_vc_routes: bool):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("ENABLE_VC_ROUTES", "true" if enable_vc_routes else "false")
    sys.modules.pop("main", None)
    importlib.invalidate_caches()

    return importlib.import_module("main")


def _route_paths(module) -> set[str]:
    return {getattr(route, "path", "") for route in module.app.routes}


def test_vc_flag_does_not_change_specialization_routes(monkeypatch):
    disabled_module = _load_main_module(monkeypatch, enable_vc_routes=False)
    disabled_paths = _route_paths(disabled_module)

    enabled_module = _load_main_module(monkeypatch, enable_vc_routes=True)
    enabled_paths = _route_paths(enabled_module)

    assert SPECIALIZATION_ROUTE_PATHS.issubset(disabled_paths)
    assert SPECIALIZATION_ROUTE_PATHS.issubset(enabled_paths)
    assert disabled_paths == enabled_paths
    assert not any(path.startswith("/api/vc") for path in disabled_paths)
    assert not any(path.startswith("/api/vc") for path in enabled_paths)


def test_feature_flag_summary_omits_removed_vc_flag(monkeypatch, capsys):
    module = _load_main_module(monkeypatch, enable_vc_routes=True)

    capsys.readouterr()
    module.print_feature_flag_summary()
    summary = capsys.readouterr().out

    assert "Realtime Ingestion" in summary
    assert "Enhanced Ingestion" in summary
    assert "advisor retrieval" in summary
    assert "VC Routes" not in summary
