from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_runtime_support_policy_flag_removed_from_live_surfaces():
    removed_flag = "RUNTIME_SUPPORT_POLICY_ENABLED"
    live_files = [
        "backend/routers/chat.py",
        "backend/README.md",
    ]

    for relative_path in live_files:
        assert removed_flag not in _read(relative_path), relative_path


def test_graphrag_flag_removed_from_active_docs_and_tests():
    removed_flag = "GRAPH_RAG_ENABLED"
    active_docs = [
        "docs/ARCHITECTURE_INGESTION_RETRIEVAL.md",
        "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md",
    ]

    for relative_path in active_docs:
        assert removed_flag not in _read(relative_path), relative_path

    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()
