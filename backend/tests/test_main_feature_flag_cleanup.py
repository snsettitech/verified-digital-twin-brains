import importlib
import os
import sys


def _reload_main():
    os.environ.setdefault("SUPABASE_URL", "test")
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("PINECONE_API_KEY", "test")
    os.environ.setdefault("PINECONE_INDEX_NAME", "test")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "test")
    os.environ.setdefault("JWT_SECRET", "test")
    sys.modules.pop("main", None)
    return importlib.import_module("main")


def test_feature_flag_summary_omits_removed_vc_flag(capsys):
    main = _reload_main()

    capsys.readouterr()
    main.print_feature_flag_summary()
    captured = capsys.readouterr().out

    assert "VC Routes" not in captured


def test_legacy_vc_flag_env_does_not_add_route_surface(monkeypatch):
    monkeypatch.setenv("ENABLE_VC_ROUTES", "true")

    main = _reload_main()
    paths = {route.path for route in main.app.router.routes}

    assert "/config/specialization" in paths
    assert "/config/specializations" in paths
    assert "/twins/{twin_id}/specialization" in paths
    assert not any(path.startswith("/api/vc") for path in paths)
