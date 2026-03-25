import importlib
import sys


def _has_route(path: str, method: str, app=None) -> bool:
    if app is None:
        from main import app as current_app
    else:
        current_app = app

    for route in current_app.routes:
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


def test_always_on_feature_routes_exist_even_with_legacy_opt_out_env(monkeypatch):
    monkeypatch.setenv("ENABLE_REALTIME_INGESTION", "false")
    monkeypatch.setenv("ENABLE_ADVISOR_RETRIEVAL", "false")
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("PINECONE_API_KEY", "test")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test")
    monkeypatch.setenv("JWT_SECRET", "test")

    sys.modules.pop("main", None)
    importlib.invalidate_caches()
    app = importlib.import_module("main").app

    assert _has_route("/ingestion/realtime/health", "GET", app)
    assert _has_route("/ingestion/realtime/config", "GET", app)
    assert _has_route("/retrieval/query", "POST", app)
    assert _has_route("/retrieval/health", "GET", app)
