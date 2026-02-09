from eval.persona_channel_isolation import (
    DEFAULT_CHANNEL_CHECK_IDS,
    run_channel_isolation_checks,
)


def test_channel_isolation_checks_all_pass():
    summary = run_channel_isolation_checks(declared_checks=DEFAULT_CHANNEL_CHECK_IDS)

    assert summary["total"] == len(DEFAULT_CHANNEL_CHECK_IDS)
    assert summary["passed"] == summary["total"]
    assert summary["pass_rate"] == 1.0
    assert summary["missing_declared_checks"] == []
    assert summary["undeclared_executed_checks"] == []

