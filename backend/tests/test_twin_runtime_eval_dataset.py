import json
from pathlib import Path


def test_twin_runtime_eval_dataset_schema():
    dataset_path = Path(__file__).resolve().parents[1] / "eval" / "twin_runtime_eval_cases.json"
    rows = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    assert len(rows) >= 10

    required = {"id", "query", "expected_intent", "expected_action", "requires_citations"}
    for row in rows:
        assert required.issubset(set(row.keys()))
        assert isinstance(row["id"], str) and row["id"].strip()
        assert isinstance(row["query"], str) and row["query"].strip()
        assert isinstance(row["expected_intent"], str) and row["expected_intent"].strip()
        assert row["expected_action"] in {"answer", "clarify", "refuse", "escalate"}
        assert isinstance(row["requires_citations"], bool)

