from unittest.mock import patch

from modules.persona_feedback_learning import (
    record_feedback_training_event,
    run_feedback_learning_cycle,
)


def test_record_feedback_training_event_requires_twin_id():
    result = record_feedback_training_event(
        trace_id="trace-1",
        score=1.0,
        reason="helpful",
        comment="Good answer",
        twin_id=None,
        tenant_id=None,
        conversation_id=None,
        message_id=None,
        intent_label="advice_or_stance",
        module_ids=["procedural.style.concise_direct"],
        interaction_context="public_share",
        created_by=None,
    )
    assert result is None


def test_feedback_learning_cycle_publishes_when_gate_passes():
    with patch(
        "modules.persona_feedback_learning._start_learning_run",
        return_value={"id": "run-1"},
    ), patch(
        "modules.persona_feedback_learning._fetch_unprocessed_events",
        return_value=[{"id": "evt-1", "event_type": "thumb_down", "reason": "incorrect", "score": -1, "payload": {"intent_label": "factual_with_evidence"}}],
    ), patch(
        "modules.persona_feedback_learning._fetch_recent_judge_results",
        return_value=[{"intent_label": "factual_with_evidence", "module_ids": ["procedural.factual.cite_or_disclose_uncertainty"], "rewrite_applied": True, "final_persona_score": 0.82, "violated_clause_ids": ["POL_A"]}],
    ), patch(
        "modules.persona_feedback_learning._fetch_modules",
        return_value=[{"id": "mod-1", "module_id": "procedural.factual.cite_or_disclose_uncertainty", "intent_label": "factual_with_evidence", "status": "draft", "confidence": 0.72, "module_data": {}}],
    ), patch(
        "modules.persona_feedback_learning._update_modules_with_signals",
        return_value={"updates": [{"module_id": "procedural.factual.cite_or_disclose_uncertainty"}], "modules_updated": 1, "avg_confidence_delta": 0.041},
    ), patch(
        "modules.persona_feedback_learning._mark_events_processed",
        return_value=1,
    ), patch(
        "modules.persona_feedback_learning.run_persona_regression",
        return_value={"gate": {"passed": True}, "output_path": "proof.json"},
    ), patch(
        "modules.persona_feedback_learning._latest_draft_spec_version",
        return_value="2.1.0",
    ), patch(
        "modules.persona_feedback_learning.publish_persona_spec",
        return_value={"version": "2.1.0", "status": "active"},
    ), patch(
        "modules.persona_feedback_learning._finalize_learning_run",
        return_value={"id": "run-1", "status": "completed"},
    ):
        summary = run_feedback_learning_cycle(
            twin_id="twin-1",
            tenant_id="tenant-1",
            created_by="owner-1",
            auto_publish=True,
            run_regression_gate=True,
        )
        assert summary["status"] == "completed"
        assert summary["publish_decision"] == "published"
        assert summary["publish_candidate_version"] == "2.1.0"
        assert summary["modules_updated"] == 1


def test_feedback_learning_cycle_holds_when_gate_fails():
    with patch(
        "modules.persona_feedback_learning._start_learning_run",
        return_value={"id": "run-2"},
    ), patch(
        "modules.persona_feedback_learning._fetch_unprocessed_events",
        return_value=[],
    ), patch(
        "modules.persona_feedback_learning._fetch_recent_judge_results",
        return_value=[],
    ), patch(
        "modules.persona_feedback_learning._fetch_modules",
        return_value=[],
    ), patch(
        "modules.persona_feedback_learning._update_modules_with_signals",
        return_value={"updates": [], "modules_updated": 0, "avg_confidence_delta": 0.0},
    ), patch(
        "modules.persona_feedback_learning._mark_events_processed",
        return_value=0,
    ), patch(
        "modules.persona_feedback_learning.run_persona_regression",
        return_value={"gate": {"passed": False}, "output_path": "proof.json"},
    ), patch(
        "modules.persona_feedback_learning._finalize_learning_run",
        return_value={"id": "run-2", "status": "completed"},
    ):
        summary = run_feedback_learning_cycle(
            twin_id="twin-2",
            tenant_id="tenant-2",
            created_by="owner-2",
            auto_publish=True,
            run_regression_gate=True,
        )
        assert summary["status"] == "completed"
        assert summary["publish_decision"] == "held"
        assert summary["modules_updated"] == 0
