import contextlib
import importlib
import io
import os
import sys


_REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "OPENAI_API_KEY": "test-openai-key",
    "PINECONE_API_KEY": "test-pinecone-key",
    "PINECONE_INDEX_NAME": "test-index",
    "JWT_SECRET": "test-jwt-secret",
}


def _load_main():
    for key, value in _REQUIRED_ENV.items():
        os.environ.setdefault(key, value)

    sys.modules.pop("main", None)
    importlib.invalidate_caches()

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        module = importlib.import_module("main")
    return module


def test_feature_flag_summary_omits_dead_vc_flag():
    main = _load_main()

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        main.print_feature_flag_summary()

    assert "VC Routes" not in stdout.getvalue()


def test_specialization_routes_remain_mounted_without_vc_router():
    main = _load_main()
    paths = {getattr(route, "path", "") for route in main.app.routes}

    assert "/specializations" in paths
    assert "/config/specialization" in paths
    assert "/config/specializations" in paths
    assert "/twins/{twin_id}/specialization" in paths
    assert not any(path.startswith("/api/vc") for path in paths)
