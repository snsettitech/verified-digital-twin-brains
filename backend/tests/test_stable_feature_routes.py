import importlib
import os
import sys

from fastapi.testclient import TestClient

_MINIMAL_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "service-key",
    "OPENAI_API_KEY": "test-openai-key",
    "PINECONE_API_KEY": "test-pinecone-key",
    "PINECONE_INDEX_NAME": "test-index",
    "JWT_SECRET": "test-jwt-secret",
}


def _load_app_with_env(overrides: dict[str, str]):
    requested_env = {**_MINIMAL_ENV, **overrides}
    original = {name: os.environ.get(name) for name in requested_env}
    main = None

    try:
        for name, value in requested_env.items():
            os.environ[name] = value
        main = importlib.import_module("main")
        reloaded = importlib.reload(main)
        return reloaded.app
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if main is not None:
            sys.modules.pop("main", None)


def test_realtime_ingestion_routes_ignore_obsolete_disable_flag():
    app = _load_app_with_env({"ENABLE_REALTIME_INGESTION": "false"})
    client = TestClient(app)

    health = client.get("/ingestion/realtime/health")
    config = client.get("/ingestion/realtime/config")

    assert health.status_code == 200
    assert config.status_code == 200
    assert health.json()["enabled"] is True
    assert config.json()["enabled"] is True


def test_advisor_retrieval_routes_ignore_obsolete_disable_flag():
    app = _load_app_with_env({"ENABLE_ADVISOR_RETRIEVAL": "false"})
    client = TestClient(app)

    health = client.get("/retrieval/health")

    assert health.status_code in {200, 503}
