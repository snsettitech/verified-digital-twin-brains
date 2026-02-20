from routers.chat import _build_debug_snapshot


def test_debug_snapshot_contains_required_fields():
    contexts = [
        {
            "text": "Owner identity and credibility details.",
            "source_id": "src-1",
            "score": 0.81,
            "vector_score": 0.77,
            "lexical_score": 0.64,
            "chunk_type": "section",
            "block_type": "answer_text",
        },
        {
            "text": "Questionnaire prompt list.",
            "source_id": "src-2",
            "score": 0.31,
            "vector_score": 0.28,
            "lexical_score": 0.22,
            "chunk_type": "section",
            "block_type": "prompt_question",
        },
    ]
    planning_output = {"answerability": {"answerability": "derivable"}}
    routing_decision = {"action": "answer"}

    snapshot = _build_debug_snapshot(
        query="Tell me about yourself",
        requires_evidence=True,
        planning_output=planning_output,
        routing_decision=routing_decision,
        contexts=contexts,
    )

    assert snapshot["query_class"] == "identity"
    assert snapshot["requires_evidence"] is True
    assert snapshot["quote_intent"] is False
    assert snapshot["answerability_state"] == "derivable"
    assert snapshot["planner_action"] == "answer"
    assert "retrieval_stats" in snapshot
    assert snapshot["retrieval_stats"]["chunk_count"] == 2
    assert "selected_evidence_block_types" in snapshot
    assert "answer_text" in snapshot["selected_evidence_block_types"]


def test_debug_snapshot_marks_quote_intent():
    snapshot = _build_debug_snapshot(
        query="Quote the exact line about identity",
        requires_evidence=True,
        planning_output={},
        routing_decision={},
        contexts=[],
    )
    assert snapshot["quote_intent"] is True
