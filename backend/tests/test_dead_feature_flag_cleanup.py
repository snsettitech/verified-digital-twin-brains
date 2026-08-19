from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_removed_dead_feature_flags_are_absent_from_live_code_and_docs():
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/routers/chat.py")
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in _read("backend/README.md")
    assert "ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE" not in _read("backend/modules/agent.py")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read(".env.example")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in _read("backend/.env.example")
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ARCHITECTURE_INGESTION_RETRIEVAL.md")
    assert "GRAPH_RAG_ENABLED" not in _read("docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md")


def test_obsolete_graphrag_flag_test_stays_deleted():
    assert not (BACKEND_ROOT / "tests" / "test_graphrag_feature_flag.py").exists()
