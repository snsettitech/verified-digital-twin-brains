"""
Persona Feedback Learning Job Orchestration

Handles automatic enqueueing and worker execution for feedback-learning cycles.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from modules.job_queue import enqueue_job
from modules.jobs import JobType, append_log, complete_job, create_job, fail_job, start_job
from modules.observability import supabase
from modules.persona_feedback_learning import run_feedback_learning_cycle


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _env_min_events(default: int = 5) -> int:
    return max(1, _to_int(os.getenv("FEEDBACK_LEARNING_MIN_EVENTS", default), default))


def _env_cooldown_minutes(default: int = 30) -> int:
    return max(1, _to_int(os.getenv("FEEDBACK_LEARNING_COOLDOWN_MINUTES", default), default))


def _env_auto_publish(default: bool = False) -> bool:
    return _to_bool(os.getenv("FEEDBACK_LEARNING_AUTO_PUBLISH"), default)


def _env_run_regression_gate(default: bool = True) -> bool:
    return _to_bool(os.getenv("FEEDBACK_LEARNING_RUN_REGRESSION_GATE"), default)


def _job_exists_inflight(twin_id: str) -> bool:
    try:
        res = (
            supabase.table("jobs")
            .select("id,status")
            .eq("twin_id", twin_id)
            .eq("job_type", JobType.FEEDBACK_LEARNING.value)
            .in_("status", ["queued", "processing"])
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        print(f"[FeedbackLearningJob] inflight check failed: {e}")
        return False


def _pending_event_count(twin_id: str) -> int:
    try:
        res = (
            supabase.table("persona_training_events")
            .select("id", count="exact")
            .eq("twin_id", twin_id)
            .eq("processed", False)
            .execute()
        )
        return int(res.count or 0)
    except Exception as e:
        print(f"[FeedbackLearningJob] pending event count failed: {e}")
        return 0


def _recent_learning_run_within_cooldown(twin_id: str, cooldown_minutes: int) -> bool:
    try:
        res = (
            supabase.table("persona_feedback_learning_runs")
            .select("created_at")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            return False
        created_at_raw = res.data[0].get("created_at")
        if not created_at_raw:
            return False
        created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
        return created_at >= (_now_utc() - timedelta(minutes=cooldown_minutes))
    except Exception as e:
        print(f"[FeedbackLearningJob] cooldown check failed: {e}")
        return False


def enqueue_feedback_learning_job(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    created_by: Optional[str],
    min_events: Optional[int] = None,
    trigger: str = "feedback_event",
    force: bool = False,
    auto_publish: Optional[bool] = None,
    run_regression_gate: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Enqueue a feedback-learning job when due.
    """
    if not twin_id:
        return {"enqueued": False, "reason": "missing_twin_id"}

    if _job_exists_inflight(twin_id):
        return {"enqueued": False, "reason": "job_already_inflight"}

    required_events = max(1, int(min_events or _env_min_events()))
    pending = _pending_event_count(twin_id)
    if not force and pending < required_events:
        return {
            "enqueued": False,
            "reason": "insufficient_events",
            "pending_events": pending,
            "required_events": required_events,
        }

    cooldown = _env_cooldown_minutes()
    if not force and _recent_learning_run_within_cooldown(twin_id, cooldown):
        return {"enqueued": False, "reason": "cooldown_active", "cooldown_minutes": cooldown}

    resolved_auto_publish = _env_auto_publish(default=False) if auto_publish is None else bool(auto_publish)
    resolved_run_regression = (
        _env_run_regression_gate(default=True) if run_regression_gate is None else bool(run_regression_gate)
    )

    metadata = {
        "trigger": trigger,
        "tenant_id": tenant_id,
        "created_by": created_by,
        "min_events": required_events,
        "pending_events_at_enqueue": pending,
        "auto_publish": resolved_auto_publish,
        "run_regression_gate": resolved_run_regression,
    }

    try:
        job = create_job(
            job_type=JobType.FEEDBACK_LEARNING,
            twin_id=twin_id,
            source_id=None,
            priority=1,
            metadata=metadata,
        )
        enqueue_job(job.id, JobType.FEEDBACK_LEARNING.value, priority=1, metadata=metadata)
        return {
            "enqueued": True,
            "job_id": job.id,
            "pending_events": pending,
            "required_events": required_events,
        }
    except Exception as e:
        return {"enqueued": False, "reason": f"enqueue_failed:{e}"}


def enqueue_due_feedback_learning_jobs(
    *,
    min_events: Optional[int] = None,
    limit_twins: int = 100,
    auto_publish: Optional[bool] = None,
    run_regression_gate: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Periodic scheduler sweep:
    - find twins with unprocessed feedback events
    - enqueue jobs for twins that meet threshold/cooldown requirements
    """
    required_events = max(1, int(min_events or _env_min_events()))
    try:
        res = (
            supabase.table("persona_training_events")
            .select("twin_id")
            .eq("processed", False)
            .limit(max(1000, limit_twins * required_events * 3))
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        return {"status": "failed", "error": f"load_events_failed:{e}"}

    counts: Dict[str, int] = {}
    for row in rows:
        twin_id = str(row.get("twin_id") or "").strip()
        if not twin_id:
            continue
        counts[twin_id] = counts.get(twin_id, 0) + 1

    candidates = [twin_id for twin_id, count in counts.items() if count >= required_events][:limit_twins]
    decisions: List[Dict[str, Any]] = []
    enqueued = 0

    for twin_id in candidates:
        outcome = enqueue_feedback_learning_job(
            twin_id=twin_id,
            tenant_id=None,
            created_by=None,
            min_events=required_events,
            trigger="scheduled_sweep",
            force=False,
            auto_publish=auto_publish,
            run_regression_gate=run_regression_gate,
        )
        decisions.append({"twin_id": twin_id, **outcome})
        if outcome.get("enqueued"):
            enqueued += 1

    return {
        "status": "completed",
        "required_events": required_events,
        "twins_considered": len(candidates),
        "jobs_enqueued": enqueued,
        "decisions": decisions,
    }


async def process_feedback_learning_job(job_id: str) -> bool:
    """
    Worker processor for feedback_learning jobs.
    """
    try:
        job_res = supabase.table("jobs").select("*").eq("id", job_id).single().execute()
        job = job_res.data or {}
    except Exception as e:
        print(f"[FeedbackLearningJob] job lookup failed for {job_id}: {e}")
        return False

    if not job:
        print(f"[FeedbackLearningJob] job {job_id} not found")
        return False

    metadata = dict(job.get("metadata") or {})
    twin_id = job.get("twin_id")
    tenant_id = metadata.get("tenant_id")
    created_by = metadata.get("created_by")
    min_events = _to_int(metadata.get("min_events"), _env_min_events())
    auto_publish = _to_bool(metadata.get("auto_publish"), False)
    run_regression_gate = _to_bool(metadata.get("run_regression_gate"), True)

    try:
        start_job(job_id)
    except Exception:
        pass

    append_log(
        job_id,
        f"Starting feedback-learning cycle for twin={twin_id}, min_events={min_events}",
    )

    try:
        summary = run_feedback_learning_cycle(
            twin_id=twin_id,
            tenant_id=tenant_id,
            created_by=created_by,
            min_events=min_events,
            event_limit=_to_int(metadata.get("event_limit"), 500),
            judge_limit=_to_int(metadata.get("judge_limit"), 500),
            max_confidence_delta=float(metadata.get("max_confidence_delta", 0.08)),
            activation_threshold=float(metadata.get("activation_threshold", 0.75)),
            archive_threshold=float(metadata.get("archive_threshold", 0.45)),
            auto_publish=auto_publish,
            run_regression_gate=run_regression_gate,
            regression_dataset_path=metadata.get("regression_dataset_path"),
        )
        if summary.get("status") != "completed":
            fail_job(job_id, f"Feedback learning failed: {summary}")
            append_log(job_id, f"Feedback learning failed: {summary}", log_level="error")
            return False

        gate = (summary.get("gate_summary") or {}).get("gate") or {}
        complete_job(
            job_id,
            metadata={
                "feedback_learning_run_id": summary.get("run_id"),
                "events_scanned": summary.get("events_scanned"),
                "events_processed": summary.get("events_processed"),
                "modules_updated": summary.get("modules_updated"),
                "publish_decision": summary.get("publish_decision"),
                "gate_passed": gate.get("passed"),
            },
        )
        append_log(
            job_id,
            "Feedback learning completed "
            f"(events={summary.get('events_scanned')}, updated={summary.get('modules_updated')}, "
            f"publish={summary.get('publish_decision')})",
        )
        return True
    except Exception as e:
        fail_job(job_id, f"Feedback learning processor crashed: {e}")
        append_log(job_id, f"Feedback learning processor crashed: {e}", log_level="error")
        return False
