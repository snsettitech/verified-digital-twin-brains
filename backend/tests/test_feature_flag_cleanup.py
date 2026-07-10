from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_MAIN = REPO_ROOT / "backend" / "main.py"
BACKEND_ENV_EXAMPLE = REPO_ROOT / "backend" / ".env.example"
INGESTION_REALTIME = REPO_ROOT / "backend" / "routers" / "ingestion_realtime.py"
FRONTEND_LAYOUT = REPO_ROOT / "frontend" / "app" / "layout.tsx"
FRONTEND_FEATURE_FLAGS = REPO_ROOT / "frontend" / "lib" / "features" / "FeatureFlags.tsx"
FRONTEND_RUNTIME_FLAGS = REPO_ROOT / "frontend" / "lib" / "features" / "runtimeFlags.ts"

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-key")
os.environ.setdefault("PINECONE_INDEX_NAME", "test-index")

from main import app


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontend_sources() -> list[Path]:
    return [
        path
        for path in (REPO_ROOT / "frontend").rglob("*")
        if path.suffix in {".ts", ".tsx"} and path.is_file()
    ]


def test_stable_backend_routes_do_not_keep_rollout_flags():
    client = TestClient(app)
    realtime_response = client.get("/ingestion/realtime/health")
    retrieval_response = client.post("/retrieval/query", json={})

    assert realtime_response.status_code == 200
    assert retrieval_response.status_code == 401

    main_text = _read(BACKEND_MAIN)
    env_text = _read(BACKEND_ENV_EXAMPLE)
    realtime_text = _read(INGESTION_REALTIME)

    assert "ENABLE_REALTIME_INGESTION" not in main_text
    assert "ENABLE_ADVISOR_RETRIEVAL" not in main_text
    assert "ENABLE_REALTIME_INGESTION" not in env_text
    assert "ENABLE_ADVISOR_RETRIEVAL" not in env_text
    assert "ENABLE_REALTIME_INGESTION" not in realtime_text


def test_backend_does_not_keep_vc_flag_without_router():
    main_text = _read(BACKEND_MAIN)
    has_vc_flag = "ENABLE_VC_ROUTES" in main_text or "VC_ROUTES_ENABLED" in main_text
    has_vc_router = any((REPO_ROOT / "backend").rglob("vc_routes.py"))

    assert not has_vc_flag or has_vc_router


def test_runtime_flags_align_with_live_frontend_consumers():
    runtime_text = _read(FRONTEND_RUNTIME_FLAGS)
    declared_flags = set(
        re.findall(r"^\s{2}([a-zA-Z][a-zA-Z0-9_]*)\s*:\s*toBool\(", runtime_text, flags=re.MULTILINE)
    )

    used_flags: set[str] = set()
    usage_patterns = [
        re.compile(r"isRuntimeFeatureEnabled\('([^']+)'\)"),
        re.compile(r'featureFlag:\s*\'([^\']+)\''),
    ]
    for path in _frontend_sources():
        if path == FRONTEND_RUNTIME_FLAGS:
            continue
        text = _read(path)
        for pattern in usage_patterns:
            used_flags.update(pattern.findall(text))

    assert declared_flags == used_flags


def test_layout_does_not_mount_unused_feature_flag_provider():
    layout_text = _read(FRONTEND_LAYOUT)
    provider_consumers = [
        path
        for path in _frontend_sources()
        if path not in {FRONTEND_FEATURE_FLAGS, FRONTEND_LAYOUT}
        and (
            "useFeatureFlags" in _read(path)
            or "useFeatureFlag" in _read(path)
            or "FeatureFlagProvider" in _read(path)
        )
    ]

    assert provider_consumers or "FeatureFlagProvider" not in layout_text
