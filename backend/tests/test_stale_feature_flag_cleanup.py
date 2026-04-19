import importlib
import sys

from modules.deep_research_config import DeepResearchConfig


def _load_main(monkeypatch, *, deep_research_enabled: str | None = None):
    if deep_research_enabled is None:
        monkeypatch.delenv("DEEP_RESEARCH_ENABLED", raising=False)
    else:
        monkeypatch.setenv("DEEP_RESEARCH_ENABLED", deep_research_enabled)

    sys.modules.pop("main", None)
    return importlib.import_module("main")


def _has_route(app_module, path: str, method: str) -> bool:
    for route in app_module.app.routes:
        route_path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if route_path == path and method.upper() in methods:
            return True
    return False


def test_vc_routes_flag_plumbing_removed(monkeypatch):
    main = _load_main(monkeypatch)

    assert not hasattr(main, "VC_ROUTES_ENABLED")
    assert _has_route(main, "/specializations", "GET")
    assert not _has_route(main, "/api/vc/artifact/upload/{twin_id}", "POST")


def test_deep_research_routes_ignore_removed_global_gate(monkeypatch):
    main = _load_main(monkeypatch, deep_research_enabled="false")

    assert not hasattr(main, "DEEP_RESEARCH_ENABLED")
    assert _has_route(main, "/deep-research/runs", "POST")
    assert _has_route(main, "/twins/{twin_id}/crawls", "POST")
    assert _has_route(main, "/twins/{twin_id}/research/{research_run_id}/continue-claims", "POST")


def test_deep_research_config_no_deprecated_rollout_fields():
    config = DeepResearchConfig.from_env()

    assert not hasattr(config, "global_disable")
    assert not hasattr(config, "phase_8_claims_disabled")
    assert not hasattr(config, "phase_9_web_verification_disabled")
    assert not hasattr(config, "phase_10_claim_finalization_disabled")
    assert not hasattr(config, "phase_11_human_adjudication_disabled")
    assert not hasattr(config, "phase_12_runtime_publication_disabled")
