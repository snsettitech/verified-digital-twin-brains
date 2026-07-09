from __future__ import annotations

import importlib
import sys


def _import_main_with_legacy_deep_research_flags_disabled(monkeypatch):
    required_env = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "OPENAI_API_KEY": "test-openai-key",
        "PINECONE_API_KEY": "test-pinecone-key",
        "PINECONE_INDEX_NAME": "test-index",
        "JWT_SECRET": "test-jwt-secret",
        "DEV_MODE": "false",
        "DEEP_RESEARCH_ENABLED": "false",
        "NAME_ONLY_DEEP_RESEARCH_ENABLED": "false",
    }
    for key, value in required_env.items():
        monkeypatch.setenv(key, value)

    sys.modules.pop("main", None)
    return importlib.import_module("main")


def test_core_deep_research_routes_stay_registered_when_legacy_flag_is_false(monkeypatch):
    main = _import_main_with_legacy_deep_research_flags_disabled(monkeypatch)

    paths = {route.path for route in main.app.router.routes}

    assert "/twins/{twin_id}/crawls" in paths
    assert "/twins/{twin_id}/research/{research_run_id}/continue-claims" in paths
    assert "/deep-research/runs" in paths


def test_deep_research_config_no_longer_exposes_global_disable_field():
    from modules.deep_research_config import DeepResearchConfig

    assert "global_disable" not in DeepResearchConfig.model_fields
