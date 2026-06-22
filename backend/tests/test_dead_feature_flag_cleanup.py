from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


def test_dead_backend_feature_flag_literals_are_removed_from_live_surfaces():
    files_and_literals = {
        ".env.example": ["RUNTIME_CONFIDENCE_GATE_ENABLED"],
        "backend/.env.example": ["RUNTIME_CONFIDENCE_GATE_ENABLED"],
        "backend/README.md": ["RUNTIME_SUPPORT_POLICY_ENABLED"],
        "backend/routers/chat.py": ["RUNTIME_SUPPORT_POLICY_ENABLED"],
        "backend/modules/agent.py": ["ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE"],
        "docs/ARCHITECTURE_INGESTION_RETRIEVAL.md": ["GRAPH_RAG_ENABLED"],
        "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md": ["GRAPH_RAG_ENABLED"],
    }

    for relative_path, literals in files_and_literals.items():
        content = _read(relative_path)
        for literal in literals:
            assert literal not in content, f"{literal} should be removed from {relative_path}"


def test_phantom_graphrag_flag_test_is_deleted():
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()


def test_dead_frontend_feature_flag_plumbing_is_removed():
    files_and_literals = {
        "frontend/app/layout.tsx": ["FeatureFlagProvider"],
        "frontend/lib/features/runtimeFlags.ts": ["sourceLabeling", "officeHoursMode"],
        "frontend/.env.example": [
            "NEXT_PUBLIC_FF_SOURCE_LABELING",
            "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE",
        ],
    }

    for relative_path, literals in files_and_literals.items():
        content = _read(relative_path)
        for literal in literals:
            assert literal not in content, f"{literal} should be removed from {relative_path}"

    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()
