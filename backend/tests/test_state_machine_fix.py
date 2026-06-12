"""
Tests for State Machine Fix

Run: pytest backend/tests/test_state_machine_fix.py -v
"""

from unittest.mock import patch

import pytest
from modules.research_orchestrator_state_fix import (
    ResearchRunStatus,
    is_deep_research_enabled,
    get_valid_transitions,
    get_next_auto_status,
    is_terminal_status,
    should_skip_adjudication,
    get_adjudication_path,
)


class TestDeepResearchEnablement:
    """Test deep research enablement detection."""
    
    def test_explicitly_enabled(self):
        run_data = {
            "checkpoint_data": {
                "metadata": {"deep_research_enabled": True}
            }
        }
        assert is_deep_research_enabled(run_data) is True
    
    def test_explicitly_disabled(self):
        run_data = {
            "checkpoint_data": {
                "metadata": {"deep_research_enabled": False}
            }
        }
        assert is_deep_research_enabled(run_data) is False
    
    def test_default_enabled(self):
        run_data = {"checkpoint_data": {}}
        # Should default to enabled
        assert is_deep_research_enabled(run_data) is True

    def test_default_enabled_ignores_legacy_env_flags(self):
        from modules.deep_research_config import DeepResearchConfig

        with patch.dict(
            "os.environ",
            {
                "DEEP_RESEARCH_ENABLED": "false",
                "DEEP_RESEARCH_GLOBAL_DISABLE": "true",
            },
            clear=False,
        ):
            assert DeepResearchConfig.from_env().is_enabled() is True

    def test_deprecated_rollout_fields_removed_from_config_model(self):
        from modules.deep_research_config import DeepResearchConfig

        deprecated_fields = {
            "global_disable",
            "phase_8_claims_disabled",
            "phase_9_web_verification_disabled",
            "phase_10_claim_finalization_disabled",
            "phase_11_human_adjudication_disabled",
            "phase_12_runtime_publication_disabled",
        }

        assert deprecated_fields.isdisjoint(DeepResearchConfig.model_fields)


class TestStateTransitions:
    """Test state transition rules."""
    
    def test_planning_transitions(self):
        valid = get_valid_transitions(ResearchRunStatus.PLANNING)
        assert ResearchRunStatus.QUEUED in valid
        assert ResearchRunStatus.FAILED in valid
        assert ResearchRunStatus.COMPLETED not in valid
    
    def test_finalizing_transitions_no_deep_research(self):
        run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": False}}}
        valid = get_valid_transitions(ResearchRunStatus.FINALIZING, run_data)
        assert ResearchRunStatus.COMPLETED in valid
        assert ResearchRunStatus.CLAIMS_ENRICHMENT not in valid
    
    def test_finalizing_transitions_with_deep_research(self):
        run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": True}}}
        valid = get_valid_transitions(ResearchRunStatus.FINALIZING, run_data)
        # Can go to COMPLETED (which then continues) or directly
        assert ResearchRunStatus.COMPLETED in valid
    
    def test_completed_transitions(self):
        # Without run data, COMPLETED should have no transitions
        valid = get_valid_transitions(ResearchRunStatus.COMPLETED)
        assert len(valid) == 0  # Terminal
        
        # With deep research enabled, can continue
        run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": True}}}
        valid = get_valid_transitions(ResearchRunStatus.COMPLETED, run_data)
        assert ResearchRunStatus.CLAIMS_ENRICHMENT in valid


class TestAutoTransition:
    """Test automatic next status determination."""
    
    def test_finalizing_no_deep_research(self):
        run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": False}}}
        next_status = get_next_auto_status(ResearchRunStatus.FINALIZING, run_data)
        assert next_status == ResearchRunStatus.COMPLETED
    
    def test_finalizing_with_deep_research(self):
        run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": True}}}
        next_status = get_next_auto_status(ResearchRunStatus.FINALIZING, run_data)
        assert next_status == ResearchRunStatus.CLAIMS_ENRICHMENT
    
    def test_runtime_published(self):
        run_data = {"checkpoint_data": {}}
        next_status = get_next_auto_status(ResearchRunStatus.RUNTIME_PUBLISHED, run_data)
        assert next_status == ResearchRunStatus.COMPLETED


class TestTerminalStatus:
    """Test terminal status detection."""
    
    def test_failed_is_terminal(self):
        assert is_terminal_status(ResearchRunStatus.FAILED) is True
    
    def test_completed_no_deep_research(self):
        run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": False}}}
        assert is_terminal_status(ResearchRunStatus.COMPLETED, run_data) is True
    
    def test_completed_with_deep_research(self):
        run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": True}}}
        assert is_terminal_status(ResearchRunStatus.COMPLETED, run_data) is False
    
    def test_runtime_published_not_terminal(self):
        # RUNTIME_PUBLISHED can transition to COMPLETED
        assert is_terminal_status(ResearchRunStatus.RUNTIME_PUBLISHED) is False


class TestAdjudicationSkip:
    """Test adjudication skip logic."""
    
    def test_explicit_skip(self):
        run_data = {"checkpoint_data": {"metadata": {"skip_adjudication": True}}}
        assert should_skip_adjudication(run_data) is True
    
    def test_no_skip(self):
        run_data = {"checkpoint_data": {"metadata": {}}}
        assert should_skip_adjudication(run_data) is False
    
    def test_get_adjudication_path_with_skip(self):
        run_data = {"checkpoint_data": {"metadata": {"skip_adjudication": True}}}
        next_status = get_adjudication_path(ResearchRunStatus.CLAIMS_FINALIZED, run_data)
        assert next_status == ResearchRunStatus.RUNTIME_PUBLICATION
    
    def test_get_adjudication_path_no_skip(self):
        run_data = {"checkpoint_data": {"metadata": {}}}
        next_status = get_adjudication_path(ResearchRunStatus.CLAIMS_FINALIZED, run_data)
        assert next_status == ResearchRunStatus.ADJUDICATION


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
