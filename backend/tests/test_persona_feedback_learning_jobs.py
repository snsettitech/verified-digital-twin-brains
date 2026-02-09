from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from modules.persona_feedback_learning_jobs import (
    enqueue_feedback_learning_job,
    process_feedback_learning_job,
)


def test_enqueue_feedback_learning_job_enqueues_when_due():
    with patch(
        "modules.persona_feedback_learning_jobs._job_exists_inflight",
        return_value=False,
    ), patch(
        "modules.persona_feedback_learning_jobs._pending_event_count",
        return_value=12,
    ), patch(
        "modules.persona_feedback_learning_jobs._recent_learning_run_within_cooldown",
        return_value=False,
    ), patch(
        "modules.persona_feedback_learning_jobs.create_job",
        return_value=SimpleNamespace(id="job-fl-1"),
    ) as mocked_create, patch(
        "modules.persona_feedback_learning_jobs.enqueue_job",
    ) as mocked_enqueue:
        result = enqueue_feedback_learning_job(
            twin_id="twin-1",
            tenant_id="tenant-1",
            created_by="owner-1",
            min_events=5,
            trigger="feedback_event",
            force=False,
            auto_publish=False,
            run_regression_gate=True,
        )

    assert result["enqueued"] is True
    assert result["job_id"] == "job-fl-1"
    mocked_create.assert_called_once()
    mocked_enqueue.assert_called_once_with(
        "job-fl-1",
        "feedback_learning",
        priority=1,
        metadata=ANY,
    )


def test_enqueue_feedback_learning_job_skips_when_insufficient_events():
    with patch(
        "modules.persona_feedback_learning_jobs._job_exists_inflight",
        return_value=False,
    ), patch(
        "modules.persona_feedback_learning_jobs._pending_event_count",
        return_value=2,
    ):
        result = enqueue_feedback_learning_job(
            twin_id="twin-1",
            tenant_id=None,
            created_by=None,
            min_events=5,
        )

    assert result["enqueued"] is False
    assert result["reason"] == "insufficient_events"
    assert result["pending_events"] == 2
    assert result["required_events"] == 5


@pytest.mark.asyncio
async def test_process_feedback_learning_job_happy_path():
    mock_supabase = MagicMock()
    (
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data
    ) = {
        "id": "job-fl-1",
        "twin_id": "twin-1",
        "metadata": {
            "tenant_id": "tenant-1",
            "created_by": "owner-1",
            "min_events": 5,
            "auto_publish": False,
            "run_regression_gate": True,
        },
    }

    with patch(
        "modules.persona_feedback_learning_jobs.supabase",
        mock_supabase,
    ), patch(
        "modules.persona_feedback_learning_jobs.start_job",
    ), patch(
        "modules.persona_feedback_learning_jobs.append_log",
    ), patch(
        "modules.persona_feedback_learning_jobs.complete_job",
    ) as mocked_complete, patch(
        "modules.persona_feedback_learning_jobs.run_feedback_learning_cycle",
        return_value={
            "status": "completed",
            "run_id": "run-1",
            "events_scanned": 7,
            "events_processed": 7,
            "modules_updated": 2,
            "publish_decision": "held",
            "gate_summary": {"gate": {"passed": True}},
        },
    ):
        ok = await process_feedback_learning_job("job-fl-1")

    assert ok is True
    mocked_complete.assert_called_once()
