from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_removed_dead_backend_flag_plumbing_is_absent() -> None:
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/routers/chat.py")
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/README.md")
    assert "ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE" not in _read("backend/modules/agent.py")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read(".env.example")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read("backend/.env.example")


def test_removed_dead_frontend_flag_plumbing_is_absent() -> None:
    assert not (ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()
    assert "FeatureFlagProvider" not in _read("frontend/app/layout.tsx")

    runtime_flags = _read("frontend/lib/features/runtimeFlags.ts")
    assert "sourceLabeling" not in runtime_flags
    assert "officeHoursMode" not in runtime_flags
    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in _read("frontend/.env.example")
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in _read("frontend/.env.example")


def test_removed_graphrag_flag_surface_is_absent() -> None:
    assert not (ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md")
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ARCHITECTURE_INGESTION_RETRIEVAL.md")
