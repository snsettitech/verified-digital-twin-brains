import importlib
import sys

from fastapi.testclient import TestClient


_REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "OPENAI_API_KEY": "test-openai-key",
    "PINECONE_API_KEY": "test-pinecone-key",
    "PINECONE_INDEX_NAME": "test-index",
    "JWT_SECRET": "test-jwt-secret",
    "DEV_MODE": "false",
}


def _load_main(monkeypatch, **overrides):
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    for module_name in ("main", "routers.ingestion_realtime"):
        sys.modules.pop(module_name, None)

    importlib.invalidate_caches()
    return importlib.import_module("main")


def _paths(app) -> set[str]:
    return {getattr(route, "path", "") for route in app.router.routes}


def test_stable_routes_stay_registered_when_legacy_disable_flags_are_false(monkeypatch):
    main = _load_main(
        monkeypatch,
        ENABLE_REALTIME_INGESTION="false",
        ENABLE_ADVISOR_RETRIEVAL="false",
        ENABLE_VC_ROUTES="true",
    )

    paths = _paths(main.app)

    assert "/ingestion/realtime/health" in paths
    assert "/ingestion/realtime/config" in paths
    assert "/retrieval/query" in paths
    assert "/config/specialization" in paths
    assert "/config/specializations" in paths
    assert "/twins/{twin_id}/specialization" in paths
    assert not any(path.startswith("/api/vc") for path in paths)


def test_realtime_compat_endpoints_report_always_registered(monkeypatch):
    main = _load_main(monkeypatch, ENABLE_REALTIME_INGESTION="false")
    client = TestClient(main.app)

    health = client.get("/ingestion/realtime/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "feature": "realtime_ingestion",
        "enabled": True,
        "mode": "compat",
        "route_registered": True,
    }

    config = client.get("/ingestion/realtime/config")
    assert config.status_code == 200
    assert config.json() == {
        "enabled": True,
        "compat_router": True,
        "route_registered": True,
    }
