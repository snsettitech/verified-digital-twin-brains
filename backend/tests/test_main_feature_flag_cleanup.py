import importlib
import io
import sys
from contextlib import redirect_stdout


def _load_main(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("DEV_MODE", "false")
    sys.modules.pop("main", None)
    return importlib.import_module("main")


def test_main_feature_flag_summary_excludes_dead_vc_flag(monkeypatch):
    main = _load_main(monkeypatch)

    stream = io.StringIO()
    with redirect_stdout(stream):
        main.print_feature_flag_summary()

    summary = stream.getvalue()

    assert "VC Routes" not in summary
    assert "Realtime Ingestion" in summary
    assert "Deep Research" in summary


def test_main_routes_keep_shared_specializations_without_vc_router(monkeypatch):
    main = _load_main(monkeypatch)

    paths = {route.path for route in main.app.router.routes}

    assert "/config/specialization" in paths
    assert "/config/specializations" in paths
    assert "/twins/{twin_id}/specialization" in paths
    assert not any(path.startswith("/api/vc") for path in paths)
