from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_unused_feature_flag_provider_removed():
    provider_path = REPO_ROOT / "frontend" / "lib" / "features" / "FeatureFlags.tsx"
    assert not provider_path.exists()

    layout_path = REPO_ROOT / "frontend" / "app" / "layout.tsx"
    layout_text = layout_path.read_text(encoding="utf-8")
    assert "FeatureFlagProvider" not in layout_text


def test_orphan_runtime_flag_keys_removed_but_live_gates_remain():
    runtime_flags_path = REPO_ROOT / "frontend" / "lib" / "features" / "runtimeFlags.ts"
    runtime_flags_text = runtime_flags_path.read_text(encoding="utf-8")

    assert "sourceLabeling" not in runtime_flags_text
    assert "officeHoursMode" not in runtime_flags_text
    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in runtime_flags_text
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in runtime_flags_text

    for live_flag in (
        "dashboardChat",
        "memoryCenter",
        "privacyControls",
        "publishControls",
        "contextPanel",
    ):
        assert live_flag in runtime_flags_text


def test_frontend_env_example_only_lists_live_runtime_flags():
    env_example_path = REPO_ROOT / "frontend" / ".env.example"
    env_example_text = env_example_path.read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in env_example_text
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in env_example_text

    for live_env_flag in (
        "NEXT_PUBLIC_FF_DASHBOARD_CHAT",
        "NEXT_PUBLIC_FF_MEMORY_CENTER",
        "NEXT_PUBLIC_FF_PRIVACY_CONTROLS",
        "NEXT_PUBLIC_FF_PUBLISH_CONTROLS",
        "NEXT_PUBLIC_FF_CONTEXT_PANEL",
    ):
        assert live_env_flag in env_example_text


def test_live_runtime_flags_still_gate_navigation_and_pages():
    navigation_config_path = REPO_ROOT / "frontend" / "lib" / "navigation" / "config.ts"
    navigation_config_text = navigation_config_path.read_text(encoding="utf-8")

    for active_nav_gate in (
        "featureFlag: 'dashboardChat'",
        "featureFlag: 'memoryCenter'",
        "featureFlag: 'privacyControls'",
        "featureFlag: 'publishControls'",
    ):
        assert active_nav_gate in navigation_config_text

    sidebar_path = REPO_ROOT / "frontend" / "components" / "Sidebar.tsx"
    sidebar_text = sidebar_path.read_text(encoding="utf-8")
    assert "isRuntimeFeatureEnabled" in sidebar_text

    chat_page_text = (
        REPO_ROOT / "frontend" / "app" / "dashboard" / "chat" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "isRuntimeFeatureEnabled('dashboardChat')" in chat_page_text
    assert "isRuntimeFeatureEnabled('contextPanel')" in chat_page_text

    memory_page_text = (
        REPO_ROOT / "frontend" / "app" / "dashboard" / "memory" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "isRuntimeFeatureEnabled('memoryCenter')" in memory_page_text

    privacy_page_text = (
        REPO_ROOT / "frontend" / "app" / "dashboard" / "privacy" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "isRuntimeFeatureEnabled('privacyControls')" in privacy_page_text

    publish_controls_page_text = (
        REPO_ROOT / "frontend" / "app" / "dashboard" / "publish-controls" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "isRuntimeFeatureEnabled('publishControls')" in publish_controls_page_text
