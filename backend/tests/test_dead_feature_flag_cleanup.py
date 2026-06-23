from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_dead_backend_feature_flag_plumbing_removed():
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/routers/chat.py")
    assert "ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE" not in _read("backend/modules/agent.py")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read(".env.example")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read("backend/.env.example")


def test_dead_frontend_feature_flag_plumbing_removed():
    assert "FeatureFlagProvider" not in _read("frontend/app/layout.tsx")
    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()
    assert "sourceLabeling" not in _read("frontend/lib/features/runtimeFlags.ts")
    assert "officeHoursMode" not in _read("frontend/lib/features/runtimeFlags.ts")
    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in _read("frontend/.env.example")
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in _read("frontend/.env.example")


def test_dead_graphrag_flag_surfaces_removed():
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ARCHITECTURE_INGESTION_RETRIEVAL.md")
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md")
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/README.md")
