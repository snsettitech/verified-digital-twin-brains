import importlib
import sys


REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "test-key",
    "OPENAI_API_KEY": "test-key",
    "PINECONE_API_KEY": "test-key",
    "PINECONE_INDEX_NAME": "test-index",
    "JWT_SECRET": "test-jwt-secret",
    "DEV_MODE": "false",
}


def _load_main(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop("main", None)
    import main

    return importlib.reload(main)


def test_main_no_vc_feature_flag_symbol(monkeypatch):
    main = _load_main(monkeypatch)

    assert not hasattr(main, "VC_ROUTES_ENABLED")


def test_legacy_vc_env_var_no_longer_changes_route_surface(monkeypatch):
    monkeypatch.setenv("ENABLE_VC_ROUTES", "true")
    main = _load_main(monkeypatch)

    route_paths = {getattr(route, "path", "") for route in main.app.routes}

    assert "/config/specialization" in route_paths
    assert "/config/specializations" in route_paths
    assert "/twins/{twin_id}/specialization" in route_paths
    assert not any(path.startswith("/api/vc") for path in route_paths)
