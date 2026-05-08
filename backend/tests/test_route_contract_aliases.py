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


def test_vc_artifact_upload_route_is_absent():
    assert not _has_route("/api/vc/artifact/upload/{twin_id}", "POST")


def test_feature_flag_summary_no_longer_mentions_vc_routes(capsys):
    import main

    main.print_feature_flag_summary()
    captured = capsys.readouterr()
    assert "VC Routes" not in captured.out
