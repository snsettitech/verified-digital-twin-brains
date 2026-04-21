import importlib


def _load_main_with_placeholder_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "pinecone-index")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret")
    monkeypatch.setenv("DEEP_RESEARCH_ENABLED", "false")

    import main as main_module

    return importlib.reload(main_module)


def test_main_registers_deep_research_routes_without_legacy_master_flag(monkeypatch):
    main_module = _load_main_with_placeholder_env(monkeypatch)
    route_paths = {route.path for route in main_module.app.router.routes}

    assert not hasattr(main_module, "DEEP_RESEARCH_ENABLED")
    assert not hasattr(main_module, "VC_ROUTES_ENABLED")
    assert "/deep-research/runs" in route_paths
    assert "/twins/{twin_id}/crawls" in route_paths
    assert "/twins/{twin_id}/research/{research_run_id}/continue-claims" in route_paths
    assert all(not path.startswith("/api/vc") for path in route_paths)
