from unittest.mock import patch

from modules.deep_research_config import DeepResearchConfig


REMOVED_LEGACY_FIELDS = {
    "global_disable",
    "phase_8_claims_disabled",
    "phase_9_web_verification_disabled",
    "phase_10_claim_finalization_disabled",
    "phase_11_human_adjudication_disabled",
    "phase_12_runtime_publication_disabled",
}

LEGACY_DISABLE_ENV_KEYS = {
    "DEEP_RESEARCH_ENABLED",
    "DEEP_RESEARCH_GLOBAL_DISABLE",
    "DR_PHASE_8_CLAIMS_DISABLED",
    "DR_PHASE_9_WEB_VERIFICATION_DISABLED",
    "DR_PHASE_10_CLAIM_FINALIZATION_DISABLED",
    "DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED",
    "DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED",
}


class TestDeepResearchConfigCleanup:
    @patch("os.getenv")
    def test_legacy_disable_fields_removed_from_config_model(self, mock_getenv):
        """Legacy Deep Research disable flags should be gone from the public config."""

        def mock_env(key, default=None):
            if key in LEGACY_DISABLE_ENV_KEYS:
                return "true"
            return default

        mock_getenv.side_effect = mock_env

        config = DeepResearchConfig.from_env()

        assert config.is_enabled() is True
        assert config.phase_12_suppress_unresolved_by_default is True
        assert config.phase_12_auto_publish is False

        field_names = set(DeepResearchConfig.model_fields)
        assert REMOVED_LEGACY_FIELDS.isdisjoint(field_names)

        for field_name in REMOVED_LEGACY_FIELDS:
            assert not hasattr(config, field_name)
