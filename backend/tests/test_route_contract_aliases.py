def _has_route(path: str, method: str) -> bool:
    from main import app

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
