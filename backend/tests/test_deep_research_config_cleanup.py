import os
from unittest.mock import patch

from modules.deep_research_config import DeepResearchConfig, reset_config
from modules.research_orchestrator_state_fix import is_deep_research_enabled


DEPRECATED_DEEP_RESEARCH_FIELDS = {
    "global_disable",
    "phase_8_claims_disabled",
    "phase_9_web_verification_disabled",
    "phase_10_claim_finalization_disabled",
    "phase_11_human_adjudication_disabled",
    "phase_12_runtime_publication_disabled",
}


def test_deep_research_config_model_omits_deprecated_rollout_flags():
    assert DEPRECATED_DEEP_RESEARCH_FIELDS.isdisjoint(DeepResearchConfig.model_fields)


def test_deep_research_defaults_stay_enabled_without_legacy_rollout_flags():
    reset_config()
    legacy_env = {
        "DEEP_RESEARCH_ENABLED": "false",
        "DEEP_RESEARCH_GLOBAL_DISABLE": "true",
        "DR_PHASE_8_CLAIMS_DISABLED": "true",
        "DR_PHASE_9_WEB_VERIFICATION_DISABLED": "true",
        "DR_PHASE_10_CLAIM_FINALIZATION_DISABLED": "true",
        "DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED": "true",
        "DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED": "true",
    }

    try:
        with patch.dict(os.environ, legacy_env, clear=False):
            config = DeepResearchConfig.from_env()
            assert config.is_enabled() is True
            assert is_deep_research_enabled({}) is True
    finally:
        reset_config()
