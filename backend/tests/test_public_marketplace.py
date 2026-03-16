from modules.share_links import (
    build_public_share_path,
    is_marketplace_public_twin_record,
    is_publicly_accessible_twin_record,
)


def test_marketplace_public_rule_requires_public_ready_not_deleted():
    twin = {
        "status": "persona_built",
        "is_active": False,
        "settings": {"public_profile": {"display_name": "Test Persona"}},
    }

    assert is_marketplace_public_twin_record(twin) is True

    twin["settings"]["deleted_at"] = "2026-03-16T00:00:00Z"
    assert is_marketplace_public_twin_record(twin) is False


def test_public_access_rule_allows_marketplace_persona_without_legacy_toggle():
    twin = {
        "status": "active",
        "is_active": True,
        "settings": {
            "widget_settings": {"public_share_enabled": False},
        },
    }

    assert is_publicly_accessible_twin_record(twin) is True


def test_build_public_share_path_prefers_handle_before_token():
    path = build_public_share_path(
        "twin-123",
        {
            "handle": "jane-doe",
            "widget_settings": {"share_token": "token-123"},
        },
    )

    assert path == "/share/jane-doe"
