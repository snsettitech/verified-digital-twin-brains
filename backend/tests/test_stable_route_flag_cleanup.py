import importlib.util
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = BACKEND_DIR.parent
MAIN_PATH = BACKEND_DIR / "main.py"

REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "OPENAI_API_KEY": "test-openai-key",
    "PINECONE_API_KEY": "test-pinecone-key",
    "PINECONE_INDEX_NAME": "test-index",
    "JWT_SECRET": "test-jwt-secret",
    "DEV_MODE": "false",
}


def _load_main_module(monkeypatch, **env_overrides):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    module_name = f"test_main_cleanup_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MAIN_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _has_route(app, path: str, method: str) -> bool:
    path_item = app.openapi()["paths"].get(path)
    return path_item is not None and method.lower() in path_item


def test_launched_routes_ignore_legacy_disable_envs(monkeypatch):
    module = _load_main_module(
        monkeypatch,
        ENABLE_REALTIME_INGESTION="false",
        ENABLE_ADVISOR_RETRIEVAL="false",
    )

    assert _has_route(module.app, "/ingestion/realtime/health", "GET")
    assert _has_route(module.app, "/ingestion/realtime/config", "GET")
    assert _has_route(module.app, "/retrieval/query", "POST")


def test_realtime_compat_diagnostics_report_always_on_surface(monkeypatch):
    module = _load_main_module(monkeypatch, ENABLE_REALTIME_INGESTION="false")
    client = TestClient(module.app)

    health_response = client.get("/ingestion/realtime/health")
    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "feature": "realtime_ingestion",
        "enabled": True,
        "mode": "compat",
        "route_registered": True,
    }

    config_response = client.get("/ingestion/realtime/config")
    assert config_response.status_code == 200
    assert config_response.json() == {
        "enabled": True,
        "compat_router": True,
        "route_registered": True,
    }


def test_active_operator_docs_drop_removed_flag_names():
    active_paths = [
        BACKEND_DIR / ".env.example",
        WORKSPACE_DIR / "AGENTS.md",
        WORKSPACE_DIR / "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md",
        WORKSPACE_DIR / "docs/ops/ONE_USER_PILOT_CHECKLIST.md",
    ]

    for path in active_paths:
        text = path.read_text()
        assert "ENABLE_REALTIME_INGESTION" not in text, f"{path} still mentions removed realtime flag"
        assert "ENABLE_ADVISOR_RETRIEVAL" not in text, f"{path} still mentions removed advisor flag"


def test_main_imports_realtime_router_as_stable_surface():
    text = (BACKEND_DIR / "main.py").read_text()
    assert "ingestion_realtime," in text
    assert "ingestion_realtime = None" not in text
