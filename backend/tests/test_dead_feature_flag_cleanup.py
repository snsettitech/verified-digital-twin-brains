from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_removed_backend_feature_flags_are_absent_from_active_surfaces() -> None:
    file_expectations = {
        ".env.example": ["RUNTIME_CONFIDENCE_GATE_ENABLED"],
        "backend/.env.example": ["RUNTIME_CONFIDENCE_GATE_ENABLED"],
        "backend/README.md": ["RUNTIME_SUPPORT_POLICY_ENABLED"],
        "backend/routers/chat.py": ["RUNTIME_SUPPORT_POLICY_ENABLED"],
        "backend/modules/agent.py": ["ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE"],
        "docs/ARCHITECTURE_INGESTION_RETRIEVAL.md": ["GRAPH_RAG_ENABLED"],
        "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md": ["GRAPH_RAG_ENABLED"],
        "AGENTS.md": ["ENABLE_DELPHI_RETRIEVAL"],
    }

    for rel_path, removed_literals in file_expectations.items():
        contents = _read(rel_path)
        for literal in removed_literals:
            assert literal not in contents, f"{literal} still present in {rel_path}"


def test_removed_frontend_flag_plumbing_is_absent() -> None:
    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()

    file_expectations = {
        "frontend/app/layout.tsx": ["FeatureFlagProvider"],
        "frontend/lib/features/runtimeFlags.ts": [
            "sourceLabeling",
            "officeHoursMode",
            "NEXT_PUBLIC_FF_SOURCE_LABELING",
            "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE",
        ],
        "frontend/.env.example": [
            "NEXT_PUBLIC_FF_SOURCE_LABELING",
            "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE",
        ],
    }

    for rel_path, removed_literals in file_expectations.items():
        contents = _read(rel_path)
        for literal in removed_literals:
            assert literal not in contents, f"{literal} still present in {rel_path}"


def test_graphrag_cleanup_keeps_active_coverage_and_drops_flag_only_test() -> None:
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()
    assert (REPO_ROOT / "backend/tests/test_graphrag_retrieval.py").exists()
    assert (REPO_ROOT / "backend/tests/test_graphrag_isolation.py").exists()
