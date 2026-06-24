from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_dead_backend_flag_names_removed_from_live_files():
    file_expectations = {
        "backend/routers/chat.py": ["RUNTIME_SUPPORT_POLICY_ENABLED"],
        "backend/modules/agent.py": ["ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE"],
        ".env.example": ["RUNTIME_CONFIDENCE_GATE_ENABLED"],
        "backend/.env.example": ["RUNTIME_CONFIDENCE_GATE_ENABLED"],
        "backend/README.md": ["RUNTIME_SUPPORT_POLICY_ENABLED"],
        "docs/ARCHITECTURE_INGESTION_RETRIEVAL.md": ["GRAPH_RAG_ENABLED"],
        "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md": ["GRAPH_RAG_ENABLED"],
    }

    for relative_path, removed_flags in file_expectations.items():
        contents = _read(relative_path)
        for removed_flag in removed_flags:
            assert removed_flag not in contents, (
                f"{removed_flag} should be removed from {relative_path}"
            )


def test_dead_graphrag_feature_flag_test_file_removed():
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()


def test_orphan_frontend_feature_flag_layer_removed():
    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()

    layout_contents = _read("frontend/app/layout.tsx")
    assert "FeatureFlagProvider" not in layout_contents

    runtime_flag_contents = _read("frontend/lib/features/runtimeFlags.ts")
    assert "sourceLabeling" not in runtime_flag_contents
    assert "officeHoursMode" not in runtime_flag_contents
