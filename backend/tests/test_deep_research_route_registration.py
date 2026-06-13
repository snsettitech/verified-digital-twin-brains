import sys

from modules.deep_research_config import DeepResearchConfig


_STARTUP_ENV = {
    "SUPABASE_URL": "test",
    "SUPABASE_SERVICE_KEY": "test",
    "OPENAI_API_KEY": "test",
    "PINECONE_API_KEY": "test",
    "PINECONE_INDEX_NAME": "test",
    "JWT_SECRET": "test",
    "DEV_MODE": "false",
}


def _load_main(monkeypatch, **overrides):
    for key, value in _STARTUP_ENV.items():
        monkeypatch.setenv(key, value)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    sys.modules.pop("main", None)
    import main  # noqa: F401

    return sys.modules["main"]


def test_core_deep_research_routes_stay_registered_when_legacy_env_flags_are_false(monkeypatch):
    main = _load_main(
        monkeypatch,
        DEEP_RESEARCH_ENABLED="false",
        NAME_ONLY_DEEP_RESEARCH_ENABLED="false",
    )

    paths = {route.path for route in main.app.router.routes}

    assert "/twins/{twin_id}/crawls" in paths
    assert "/twins/{twin_id}/research/{research_run_id}/continue-claims" in paths
    assert "/deep-research/runs" in paths


def test_deep_research_config_no_longer_exposes_removed_rollout_fields():
    removed_fields = {
        "global_disable",
        "phase_8_claims_disabled",
        "phase_9_web_verification_disabled",
        "phase_10_claim_finalization_disabled",
        "phase_11_human_adjudication_disabled",
        "phase_12_runtime_publication_disabled",
    }

    assert removed_fields.isdisjoint(DeepResearchConfig.model_fields)
