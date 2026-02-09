"""
Feedback Learning Scheduler

Periodic sweep that enqueues feedback-learning jobs for twins with enough
unprocessed feedback events.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

# Ensure `modules.*` imports resolve when executed from repo root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from modules.persona_feedback_learning_jobs import enqueue_due_feedback_learning_jobs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_once(
    *,
    min_events: int,
    limit_twins: int,
    auto_publish: bool,
    run_regression_gate: bool,
) -> dict:
    summary = enqueue_due_feedback_learning_jobs(
        min_events=min_events,
        limit_twins=limit_twins,
        auto_publish=auto_publish,
        run_regression_gate=run_regression_gate,
    )
    print(json.dumps({"timestamp": _now(), "summary": summary}, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run feedback-learning enqueue sweeps.")
    parser.add_argument("--once", action="store_true", help="Run one sweep and exit.")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=900,
        help="Sweep interval in seconds for continuous mode (default: 900).",
    )
    parser.add_argument("--min-events", type=int, default=5, help="Minimum pending events per twin.")
    parser.add_argument("--limit-twins", type=int, default=100, help="Max twins per sweep.")
    parser.add_argument("--auto-publish", action="store_true", help="Allow auto-publish on passing gate.")
    parser.add_argument(
        "--skip-regression-gate",
        action="store_true",
        help="Disable regression gate for feedback-learning runs.",
    )
    args = parser.parse_args()

    run_regression_gate = not args.skip_regression_gate

    if args.once:
        _run_once(
            min_events=max(1, args.min_events),
            limit_twins=max(1, args.limit_twins),
            auto_publish=bool(args.auto_publish),
            run_regression_gate=bool(run_regression_gate),
        )
        return 0

    interval = max(5, args.interval_seconds)
    print(
        f"[FeedbackLearningScheduler] starting continuous mode "
        f"(interval={interval}s, min_events={max(1, args.min_events)}, limit_twins={max(1, args.limit_twins)})"
    )
    try:
        while True:
            _run_once(
                min_events=max(1, args.min_events),
                limit_twins=max(1, args.limit_twins),
                auto_publish=bool(args.auto_publish),
                run_regression_gate=bool(run_regression_gate),
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[FeedbackLearningScheduler] stopped by user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
