import os
from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_app():
    os.environ.setdefault("SUPABASE_URL", "test")
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("PINECONE_API_KEY", "test")
    os.environ.setdefault("PINECONE_INDEX_NAME", "test")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "test")
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

    from main import app

    return app


def test_main_no_dead_vc_feature_flag_wiring():
    main_source = (_backend_root() / "main.py").read_text()

    assert "ENABLE_VC_ROUTES" not in main_source
    assert "VC_ROUTES_ENABLED" not in main_source


def test_specialization_routes_remain_without_vc_flag_gate():
    app = _load_app()
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/config/specialization" in route_paths
    assert "/config/specializations" in route_paths
    assert "/twins/{twin_id}/specialization" in route_paths
    assert not any(path.startswith("/api/vc") for path in route_paths)
