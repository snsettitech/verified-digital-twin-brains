import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_main_with_legacy_disable_flags(monkeypatch):
    required_env = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "test-supabase-key",
        "OPENAI_API_KEY": "test-openai-key",
        "PINECONE_API_KEY": "test-pinecone-key",
        "PINECONE_INDEX_NAME": "test-index",
        "DEV_MODE": "false",
        "ENABLE_ENHANCED_INGESTION": "false",
        "ENABLE_VC_ROUTES": "false",
        "DEEP_RESEARCH_ENABLED": "false",
        "ENABLE_REALTIME_INGESTION": "false",
        "ENABLE_ADVISOR_RETRIEVAL": "false",
    }
    for key, value in required_env.items():
        monkeypatch.setenv(key, value)

    sys.modules.pop("main", None)
    importlib.invalidate_caches()
    return importlib.import_module("main")


def test_realtime_ingestion_routes_ignore_removed_disable_flag(monkeypatch):
    main = _load_main_with_legacy_disable_flags(monkeypatch)
    client = TestClient(main.app)

    response = client.get("/ingestion/realtime/health")

    assert response.status_code == 200
    assert response.json()["enabled"] is True


def test_advisor_retrieval_routes_ignore_removed_disable_flag(monkeypatch):
    main = _load_main_with_legacy_disable_flags(monkeypatch)

    route_paths = {
        path
        for route in main.app.router.routes
        if (path := getattr(route, "path", None)) is not None
    }

    assert "/retrieval/health" in route_paths
