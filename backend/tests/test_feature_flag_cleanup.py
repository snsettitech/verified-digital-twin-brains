import importlib

from fastapi.testclient import TestClient
from modules.deep_research_config import DeepResearchConfig


def test_stable_routes_remain_registered_when_legacy_disable_envs_are_false(monkeypatch):
    monkeypatch.setenv("ENABLE_REALTIME_INGESTION", "false")
    monkeypatch.setenv("ENABLE_ADVISOR_RETRIEVAL", "false")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")

    import main

    main = importlib.reload(main)
    client = TestClient(main.app)

    assert client.get("/ingestion/realtime/health").status_code != 404
    assert client.get("/retrieval/health").status_code != 404


def test_deep_research_config_omits_deprecated_disable_fields():
    deprecated_fields = {
        "global_disable",
        "phase_8_claims_disabled",
        "phase_9_web_verification_disabled",
        "phase_10_claim_finalization_disabled",
        "phase_11_human_adjudication_disabled",
        "phase_12_runtime_publication_disabled",
    }

    assert deprecated_fields.isdisjoint(DeepResearchConfig.model_fields)
