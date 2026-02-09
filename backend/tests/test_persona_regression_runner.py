from pathlib import Path

from eval.persona_regression_runner import run_persona_regression


def test_phase6_persona_regression_runner_passes_with_default_dataset(tmp_path):
    output = tmp_path / "phase6_regression.json"
    summary = run_persona_regression(
        dataset_path="backend/eval/persona_regression_dataset.json",
        output_path=str(output),
        min_pass_rate=0.95,
        min_adversarial_pass_rate=0.95,
        min_channel_isolation_pass_rate=1.0,
    )

    assert summary["total_cases"] >= 100
    assert summary["pass_rate"] >= 0.95
    assert summary["adversarial_pass_rate"] >= 0.95
    assert summary["channel_isolation"]["pass_rate"] == 1.0
    assert summary["gate"]["passed"] is True
    assert output.exists()
