import main

from modules.deep_research_config import DeepResearchConfig


def _has_route(path: str, method: str) -> bool:
    for route in main.app.routes:
        route_path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if route_path == path and method.upper() in methods:
            return True
    return False


def test_vc_routes_flag_plumbing_removed():
    assert not hasattr(main, "VC_ROUTES_ENABLED")
    assert _has_route("/specializations", "GET")
    assert not _has_route("/api/vc/artifact/upload/{twin_id}", "POST")


def test_deep_research_config_no_deprecated_rollout_fields():
    config = DeepResearchConfig.from_env()

    assert not hasattr(config, "global_disable")
    assert not hasattr(config, "phase_8_claims_disabled")
    assert not hasattr(config, "phase_9_web_verification_disabled")
    assert not hasattr(config, "phase_10_claim_finalization_disabled")
    assert not hasattr(config, "phase_11_human_adjudication_disabled")
    assert not hasattr(config, "phase_12_runtime_publication_disabled")
