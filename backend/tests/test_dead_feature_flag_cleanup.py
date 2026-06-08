from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("flag_name", "paths"),
    [
        (
            "RUNTIME_SUPPORT_POLICY_ENABLED",
            [
                "backend/routers/chat.py",
                "backend/README.md",
            ],
        ),
        (
            "GRAPH_RAG_ENABLED",
            [
                "docs/ARCHITECTURE_INGESTION_RETRIEVAL.md",
                "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md",
            ],
        ),
    ],
)
def test_removed_feature_flags_are_absent_from_live_surfaces(flag_name: str, paths: list[str]):
    for relative_path in paths:
        assert flag_name not in _read(relative_path), (
            f"{flag_name} is still present in {relative_path}"
        )


def test_stale_graphrag_feature_flag_test_is_deleted():
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()
