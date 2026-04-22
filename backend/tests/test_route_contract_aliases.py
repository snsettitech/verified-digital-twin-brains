import importlib
import os
import sys


_MAIN_IMPORT_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "OPENAI_API_KEY": "test-openai-key",
    "PINECONE_API_KEY": "test-pinecone-key",
    "PINECONE_INDEX_NAME": "test-index",
    "JWT_SECRET": "test-jwt-secret",
}


def _load_main_with_env(**env_overrides):
    env_keys = set(_MAIN_IMPORT_ENV) | set(env_overrides)
    previous_env = {key: os.environ.get(key) for key in env_keys}

    try:
        os.environ.update(_MAIN_IMPORT_ENV)
        os.environ.update(env_overrides)
        sys.modules.pop("main", None)
        return importlib.import_module("main")
    finally:
        sys.modules.pop("main", None)
        for key, previous_value in previous_env.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value


def _has_route(path: str, method: str, **env_overrides) -> bool:
    app = _load_main_with_env(**env_overrides).app

    for route in app.routes:
        route_path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if route_path == path and method.upper() in methods:
            return True
    return False


def test_governance_sources_twin_alias_route_exists():
    assert _has_route("/twins/{twin_id}/sources", "GET")
    assert _has_route("/sources/{twin_id}", "GET")


def test_invitation_acceptance_routes_exist():
    assert _has_route("/auth/invitation/{token}", "GET")
    assert _has_route("/auth/accept-invitation", "POST")


def test_cognitive_profile_approve_route_exists():
    assert _has_route("/cognitive/profiles/{twin_id}/approve", "POST")


def test_access_groups_compat_routes_exist():
    assert _has_route("/access-groups", "GET")
    assert _has_route("/access-groups", "POST")
    assert _has_route("/access-groups/{group_id}", "GET")
    assert _has_route("/access-groups/{group_id}", "DELETE")
    assert _has_route("/access-groups/{group_id}/members", "GET")
    assert _has_route("/access-groups/{group_id}/permissions", "GET")
    assert _has_route("/access-groups/{group_id}/permissions", "POST")
    assert _has_route("/access-groups/{group_id}/permissions/{content_type}/{content_id}", "DELETE")
    assert _has_route("/access-groups/{group_id}/limits", "GET")
    assert _has_route("/access-groups/{group_id}/limits", "POST")
    assert _has_route("/access-groups/{group_id}/overrides", "GET")
    assert _has_route("/access-groups/{group_id}/overrides", "POST")
    assert _has_route("/twins/{twin_id}/group-memberships", "POST")
    assert _has_route("/group-memberships/{membership_id}", "DELETE")


def test_link_compile_compat_routes_exist():
    assert _has_route("/persona/link-compile/twins/{twin_id}/claims/{claim_id}/verify", "POST")
    assert _has_route("/twins/{twin_id}/transition/{target_state}", "POST")


def test_public_marketplace_route_exists():
    assert _has_route("/public/marketplace", "GET")


def test_deep_research_routes_exist_when_legacy_global_flag_is_false():
    main = _load_main_with_env(
        DEEP_RESEARCH_ENABLED="false",
        NAME_ONLY_DEEP_RESEARCH_ENABLED="false",
    )

    paths = {route.path for route in main.app.routes}

    assert not hasattr(main, "DEEP_RESEARCH_ENABLED")
    assert "/deep-research/runs" in paths
    assert "/twins/{twin_id}/crawls" in paths
    assert "/twins/{twin_id}/research/{research_run_id}/claims-status" in paths
