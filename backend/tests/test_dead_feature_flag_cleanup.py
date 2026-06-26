from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_backend_dead_feature_flags_are_removed_from_live_surfaces() -> None:
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/routers/chat.py")
    assert "runtime_support_policy" not in _read("backend/routers/chat.py")
    assert "ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE" not in _read("backend/modules/agent.py")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read(".env.example")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read("backend/.env.example")
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/README.md")
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md")
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ARCHITECTURE_INGESTION_RETRIEVAL.md")
    assert "GraphRAG switch" not in _read("docs/audit/CHAT_RETRIEVAL_FORENSIC_PROOF_20260214.md")
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()


def test_frontend_dead_feature_flag_plumbing_is_removed() -> None:
    assert "FeatureFlagProvider" not in _read("frontend/app/layout.tsx")
    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()

    runtime_flags = _read("frontend/lib/features/runtimeFlags.ts")
    assert "sourceLabeling" not in runtime_flags
    assert "officeHoursMode" not in runtime_flags

    frontend_env = _read("frontend/.env.example")
    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in frontend_env
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in frontend_env
