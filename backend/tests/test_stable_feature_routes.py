import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_MAIN_PATH = Path(__file__).resolve().parents[1] / "main.py"


def _load_isolated_app(*, enable_realtime_ingestion: str, enable_advisor_retrieval: str, monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("ENABLE_REALTIME_INGESTION", enable_realtime_ingestion)
        env.setenv("ENABLE_ADVISOR_RETRIEVAL", enable_advisor_retrieval)
        env.setenv("SUPABASE_URL", "https://example.supabase.co")
        env.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
        env.setenv("OPENAI_API_KEY", "test-openai-key")
        env.setenv("PINECONE_API_KEY", "test-pinecone-key")
        env.setenv("PINECONE_INDEX_NAME", "test-index")
        env.setenv("JWT_SECRET", "test-jwt-secret")

        module_name = f"stable_feature_main_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, BACKEND_MAIN_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module.app


def _documented_paths(app) -> dict:
    client = TestClient(app)
    response = client.get("/openapi.json")
    response.raise_for_status()
    return response.json()["paths"]


def test_realtime_ingestion_routes_remain_registered_when_legacy_flag_false(monkeypatch):
    app = _load_isolated_app(
        enable_realtime_ingestion="false",
        enable_advisor_retrieval="true",
        monkeypatch=monkeypatch,
    )
    documented_paths = _documented_paths(app)
    client = TestClient(app)

    assert "/ingestion/realtime/health" in documented_paths
    assert "/ingestion/realtime/config" in documented_paths

    health_response = client.get("/ingestion/realtime/health")
    config_response = client.get("/ingestion/realtime/config")

    assert health_response.status_code == 200
    assert config_response.status_code == 200
    assert health_response.json()["enabled"] is True
    assert config_response.json()["enabled"] is True


def test_advisor_retrieval_routes_remain_registered_when_legacy_flag_false(monkeypatch):
    app = _load_isolated_app(
        enable_realtime_ingestion="true",
        enable_advisor_retrieval="false",
        monkeypatch=monkeypatch,
    )
    documented_paths = _documented_paths(app)

    assert "/retrieval/query" in documented_paths
    assert "/retrieval/health" in documented_paths
