from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _route_paths(routes: Iterable[object]) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        route_path = getattr(route, "path", None)
        if isinstance(route_path, str):
            paths.add(route_path)
        nested_routes = getattr(route, "routes", None)
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            nested_routes = getattr(original_router, "routes", nested_routes)
        if nested_routes:
            paths.update(_route_paths(nested_routes))
    return paths


def test_legacy_vc_flag_surface_is_removed_from_entrypoints() -> None:
    main_source = _read_repo_file("backend/main.py")
    env_source = _read_repo_file("backend/.env.example")

    assert "ENABLE_VC_ROUTES" not in main_source
    assert "VC_ROUTES_ENABLED" not in main_source
    assert "ENABLE_VC_ROUTES" not in env_source


def test_specialization_routes_remain_registered_without_vc_gate(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "test")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("PINECONE_API_KEY", "test")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test")
    monkeypatch.setenv("JWT_SECRET", "test")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("ENABLE_VC_ROUTES", "true")

    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    paths = _route_paths(main.app.routes)

    assert "/config/specialization" in paths
    assert "/config/specializations" in paths
    assert "/twins/{twin_id}/specialization" in paths
    assert not any(path.startswith("/api/vc") for path in paths)


def test_graphrag_flag_surface_is_removed_from_live_assets() -> None:
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()
    assert "GRAPH_RAG_ENABLED" not in _read_repo_file("docs/ARCHITECTURE_INGESTION_RETRIEVAL.md")
    assert "GRAPH_RAG_ENABLED" not in _read_repo_file("docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md")
    assert "vc_routes.py" not in _read_repo_file("docs/architecture/system-overview.md")


def test_runtime_support_policy_flag_surface_is_removed() -> None:
    chat_source = _read_repo_file("backend/routers/chat.py")
    readme_source = _read_repo_file("backend/README.md")

    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in chat_source
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in readme_source


def test_frontend_orphan_flag_plumbing_is_removed() -> None:
    layout_source = _read_repo_file("frontend/app/layout.tsx")
    runtime_flags_source = _read_repo_file("frontend/lib/features/runtimeFlags.ts")

    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()
    assert "FeatureFlagProvider" not in layout_source
    assert "sourceLabeling" not in runtime_flags_source
    assert "officeHoursMode" not in runtime_flags_source
    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in _read_repo_file("frontend/.env.example")
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in _read_repo_file("frontend/.env.example")


def test_live_graph_and_chat_paths_still_use_active_controls() -> None:
    agent_source = inspect.getsource(importlib.import_module("modules.agent"))
    chat_source = _read_repo_file("backend/routers/chat.py")

    assert "GRAPH_MEMORY_ENABLED" in agent_source
    assert "_apply_runtime_support_policy_if_enabled" in chat_source
