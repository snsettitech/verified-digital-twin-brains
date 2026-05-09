import importlib
import sys


def _import_main(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("DEV_MODE", "false")
    sys.modules.pop("main", None)
    return importlib.import_module("main")


def test_feature_flag_summary_omits_dead_vc_flag(monkeypatch, capsys):
    main = _import_main(monkeypatch)

    main.print_feature_flag_summary()
    output = capsys.readouterr().out

    assert "VC Routes" not in output


def test_specializations_routes_still_register_without_vc_gate(monkeypatch):
    main = _import_main(monkeypatch)
    route_paths = {route.path for route in main.app.routes}

    assert "/specializations" in route_paths
    assert "/api/vc/artifact/upload/{twin_id}" not in route_paths
