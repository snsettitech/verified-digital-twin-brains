"""
Persona Convergence Gate

Evaluates whether aggressive persona training cycles converged to
production thresholds for multiple consecutive cycles.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from pydantic import BaseModel, Field

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


class ConvergenceThresholds(BaseModel):
    persona_recognizability_min: float = 0.80
    post_rewrite_compliance_min: float = 0.88
    citation_validity_min: float = 0.95
    clarification_correctness_min: float = 0.85
    invalid_policy_transitions_max: int = 0
    rewrite_rate_max: float = 0.30
    latency_delta_max: float = 0.25
    public_context_training_writes_max: int = 0
    unpublished_leakage_max: int = 0


class CycleMetrics(BaseModel):
    cycle: int
    persona_recognizability: float
    post_rewrite_compliance: float
    citation_validity: float
    clarification_correctness: float
    invalid_policy_transitions: int
    rewrite_rate: float
    latency_delta: float
    public_context_training_writes: int
    unpublished_leakage: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


def evaluate_cycle(metrics: CycleMetrics, thresholds: ConvergenceThresholds) -> Dict[str, Any]:
    checks = {
        "persona_recognizability": metrics.persona_recognizability >= thresholds.persona_recognizability_min,
        "post_rewrite_compliance": metrics.post_rewrite_compliance >= thresholds.post_rewrite_compliance_min,
        "citation_validity": metrics.citation_validity >= thresholds.citation_validity_min,
        "clarification_correctness": metrics.clarification_correctness >= thresholds.clarification_correctness_min,
        "invalid_policy_transitions": metrics.invalid_policy_transitions <= thresholds.invalid_policy_transitions_max,
        "rewrite_rate": metrics.rewrite_rate <= thresholds.rewrite_rate_max,
        "latency_delta": metrics.latency_delta <= thresholds.latency_delta_max,
        "public_context_training_writes": metrics.public_context_training_writes
        <= thresholds.public_context_training_writes_max,
        "unpublished_leakage": metrics.unpublished_leakage <= thresholds.unpublished_leakage_max,
    }
    passed = all(checks.values())
    failed_checks = [name for name, ok in checks.items() if not ok]
    return {
        "cycle": metrics.cycle,
        "passed": passed,
        "checks": checks,
        "failed_checks": failed_checks,
        "metrics": metrics.model_dump(),
    }


def evaluate_convergence(
    *,
    cycles: Sequence[CycleMetrics],
    thresholds: ConvergenceThresholds,
    required_consecutive: int = 3,
) -> Dict[str, Any]:
    if required_consecutive < 1:
        raise ValueError("required_consecutive must be >= 1")

    evaluations = [evaluate_cycle(cycle, thresholds) for cycle in cycles]
    tail_streak = 0
    for item in reversed(evaluations):
        if item["passed"]:
            tail_streak += 1
            continue
        break

    # Longest streak helps debug training behavior over time.
    longest_streak = 0
    current = 0
    for item in evaluations:
        if item["passed"]:
            current += 1
            longest_streak = max(longest_streak, current)
        else:
            current = 0

    converged = tail_streak >= required_consecutive
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "required_consecutive": required_consecutive,
        "total_cycles": len(evaluations),
        "tail_streak": tail_streak,
        "longest_streak": longest_streak,
        "converged": converged,
        "thresholds": thresholds.model_dump(),
        "cycles": evaluations,
    }


def _load_cycles(path: str) -> List[CycleMetrics]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("cycles", [])
    if not isinstance(raw, list):
        raise ValueError("Input must be a list of cycle objects or an object with a 'cycles' list")
    return [CycleMetrics.model_validate(item) for item in raw]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persona convergence gate")
    parser.add_argument("--input", required=True, type=str, help="JSON file with cycle metrics")
    parser.add_argument("--output", type=str, default=None, help="Optional output path")
    parser.add_argument("--required-consecutive", type=int, default=3)
    parser.add_argument("--persona-recognizability-min", type=float, default=0.80)
    parser.add_argument("--post-rewrite-compliance-min", type=float, default=0.88)
    parser.add_argument("--citation-validity-min", type=float, default=0.95)
    parser.add_argument("--clarification-correctness-min", type=float, default=0.85)
    parser.add_argument("--invalid-policy-transitions-max", type=int, default=0)
    parser.add_argument("--rewrite-rate-max", type=float, default=0.30)
    parser.add_argument("--latency-delta-max", type=float, default=0.25)
    parser.add_argument("--public-context-training-writes-max", type=int, default=0)
    parser.add_argument("--unpublished-leakage-max", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    thresholds = ConvergenceThresholds(
        persona_recognizability_min=args.persona_recognizability_min,
        post_rewrite_compliance_min=args.post_rewrite_compliance_min,
        citation_validity_min=args.citation_validity_min,
        clarification_correctness_min=args.clarification_correctness_min,
        invalid_policy_transitions_max=args.invalid_policy_transitions_max,
        rewrite_rate_max=args.rewrite_rate_max,
        latency_delta_max=args.latency_delta_max,
        public_context_training_writes_max=args.public_context_training_writes_max,
        unpublished_leakage_max=args.unpublished_leakage_max,
    )
    cycles = _load_cycles(args.input)
    summary = evaluate_convergence(
        cycles=cycles,
        thresholds=thresholds,
        required_consecutive=args.required_consecutive,
    )

    output = json.dumps(summary, indent=2)
    print(output)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
    return 0 if summary["converged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

