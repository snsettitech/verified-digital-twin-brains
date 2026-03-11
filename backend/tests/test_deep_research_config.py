import pytest

from modules.deep_research_config import DeepResearchConfig, reset_config
from modules.research_orchestrator_state_fix import is_deep_research_enabled


@pytest.fixture(autouse=True)
def clear_cached_config():
    reset_config()
    yield
    reset_config()


def test_deep_research_config_stays_enabled():
    """Deep Research should remain always on in runtime config."""
    config = DeepResearchConfig.from_env()

    assert config.enabled is True
    assert config.is_enabled() is True


def test_name_only_flag_still_controls_name_only_flow(monkeypatch):
    """The name-only flow remains separately gateable."""
    monkeypatch.setenv("NAME_ONLY_DEEP_RESEARCH_ENABLED", "false")

    config = DeepResearchConfig.from_env()

    assert config.name_only_deep_research_enabled is False


def test_research_orchestrator_honors_explicit_metadata_disable():
    """Per-run metadata can still skip Deep Research."""
    run_data = {"checkpoint_data": {"metadata": {"deep_research_enabled": False}}}

    assert is_deep_research_enabled(run_data) is False


def test_research_orchestrator_defaults_to_deep_research():
    """Runs without an explicit opt-out should follow the active Deep Research path."""
    run_data = {"checkpoint_data": {"metadata": {}}}

    assert is_deep_research_enabled(run_data) is True
