from eval.persona_aggressive_runner import run_persona_aggressive_evaluation


def test_aggressive_runner_converges_on_default_dataset(tmp_path):
    output = tmp_path / "persona_aggressive_summary.json"
    summary = run_persona_aggressive_evaluation(
        dataset_path="backend/eval/persona_roleplay_scenarios.json",
        output_path=str(output),
        max_cycles=6,
        required_consecutive=3,
        scenario_multiplier=1,
    )

    assert summary["total_cycles_executed"] >= 3
    assert summary["converged"] is True
    final_metrics = summary["final_cycle_metrics"]
    assert final_metrics["persona_recognizability"] >= 0.80
    assert final_metrics["post_rewrite_compliance"] >= 0.88
    assert final_metrics["citation_validity"] >= 0.95
    assert final_metrics["clarification_correctness"] >= 0.85
    assert final_metrics["rewrite_rate"] <= 0.30
    assert final_metrics["latency_delta"] <= 0.25
    assert final_metrics["public_context_training_writes"] == 0
    assert final_metrics["unpublished_leakage"] == 0
    assert output.exists()


def test_aggressive_runner_explicit_heuristic_mode(tmp_path):
    output = tmp_path / "persona_aggressive_summary_heuristic.json"
    summary = run_persona_aggressive_evaluation(
        dataset_path="backend/eval/persona_roleplay_scenarios.json",
        output_path=str(output),
        max_cycles=3,
        required_consecutive=1,
        scenario_multiplier=1,
        generator_mode="heuristic",
    )

    assert summary["generator_mode"] == "heuristic"
    assert summary["converged"] is True
    assert output.exists()
