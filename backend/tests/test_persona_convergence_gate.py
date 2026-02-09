from eval.persona_convergence_gate import (
    ConvergenceThresholds,
    CycleMetrics,
    evaluate_convergence,
)


def test_convergence_requires_tail_streak():
    thresholds = ConvergenceThresholds()
    cycles = [
        CycleMetrics(
            cycle=1,
            persona_recognizability=0.72,
            post_rewrite_compliance=0.90,
            citation_validity=0.96,
            clarification_correctness=0.87,
            invalid_policy_transitions=0,
            rewrite_rate=0.41,
            latency_delta=0.31,
            public_context_training_writes=0,
            unpublished_leakage=0,
        ),
        CycleMetrics(
            cycle=2,
            persona_recognizability=0.86,
            post_rewrite_compliance=0.92,
            citation_validity=0.98,
            clarification_correctness=0.90,
            invalid_policy_transitions=0,
            rewrite_rate=0.26,
            latency_delta=0.19,
            public_context_training_writes=0,
            unpublished_leakage=0,
        ),
        CycleMetrics(
            cycle=3,
            persona_recognizability=0.88,
            post_rewrite_compliance=0.94,
            citation_validity=0.98,
            clarification_correctness=0.90,
            invalid_policy_transitions=0,
            rewrite_rate=0.22,
            latency_delta=0.17,
            public_context_training_writes=0,
            unpublished_leakage=0,
        ),
        CycleMetrics(
            cycle=4,
            persona_recognizability=0.89,
            post_rewrite_compliance=0.95,
            citation_validity=0.99,
            clarification_correctness=0.91,
            invalid_policy_transitions=0,
            rewrite_rate=0.19,
            latency_delta=0.16,
            public_context_training_writes=0,
            unpublished_leakage=0,
        ),
    ]

    summary = evaluate_convergence(
        cycles=cycles,
        thresholds=thresholds,
        required_consecutive=3,
    )

    assert summary["converged"] is True
    assert summary["tail_streak"] == 3
    assert summary["total_cycles"] == 4

