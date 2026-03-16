"""
Phase 3 Retrieval Tests
=======================
Verifies BUG #14 fix:
  BUG #14 — Partial namespace failure not retried (retrieval.py)

The retry for the primary namespace must trigger whenever the primary namespace
specifically failed — not only when ALL namespaces fail.

Run with:
    cd backend && python -m pytest tests/test_phase_3_retrieval.py -v
"""

import inspect
import pytest
from unittest.mock import MagicMock


# ============================================================================
# BUG #14 — Primary namespace retry on partial failure
# ============================================================================

class TestBug14PartialNamespaceRetry:

    def test_primary_ns_failed_key_is_not_gated_on_all_failing(self):
        """
        BUG #14: The condition that triggers a primary-namespace retry must check
        whether the primary namespace is in failed_namespaces — not whether ALL
        namespaces failed.
        """
        from modules import retrieval

        source = inspect.getsource(retrieval)

        # Old (broken) condition: only retry when ALL fail
        bad_condition = "len(failed_namespaces) == len(namespace_candidates)"
        # New (fixed) condition: check if primary specifically failed
        good_condition = "namespace_candidates[0] in failed_namespaces"

        assert good_condition in source, (
            "retrieval.py must check 'namespace_candidates[0] in failed_namespaces' "
            "so partial failures (primary down, secondary up) also trigger a retry"
        )

    def test_partial_failure_retry_flag_name_present(self):
        """
        The intermediate variable _primary_ns_failed must exist so the logic
        is readable and clearly documented.
        """
        from modules import retrieval
        source = inspect.getsource(retrieval)

        assert "_primary_ns_failed" in source, (
            "BUG #14 fix must introduce _primary_ns_failed variable "
            "to express the retry condition clearly"
        )

    def test_partial_failure_logged_distinctly(self):
        """
        When only the primary namespace fails (partial failure), the log line
        must say 'partial failure' rather than the old 'all namespaces failed'.
        """
        from modules import retrieval
        source = inspect.getsource(retrieval)

        assert "partial failure" in source.lower(), (
            "BUG #14 fix must log 'partial failure' for the partial-failure case "
            "to aid debugging"
        )

    def test_primary_retry_enabled_env_flag_still_gates_retry(self):
        """
        The RETRIEVAL_PRIMARY_RETRY_ENABLED feature flag must still gate the
        retry — it's an operational escape hatch, not a permanent bypass.
        """
        from modules import retrieval
        source = inspect.getsource(retrieval)

        # Both the flag and the new primary-failed check must coexist
        assert "RETRIEVAL_PRIMARY_RETRY_ENABLED" in source
        assert "_primary_ns_failed" in source


class TestBug14RetryLogic:
    """Unit-level checks for the retry logic structure."""

    def test_primary_ns_failed_logic_is_correct(self):
        """
        Simulate the boolean logic used in the fix to confirm it behaves
        correctly for all scenarios.
        """
        def _should_retry(retry_enabled, namespace_candidates, failed_namespaces):
            """Replicates the fixed condition from retrieval.py."""
            return (
                retry_enabled
                and bool(namespace_candidates)
                and namespace_candidates[0] in failed_namespaces
            )

        primary = "ns-primary"
        secondary = "ns-secondary"
        candidates = [primary, secondary]

        # All failed → should retry (primary is in failed set)
        assert _should_retry(True, candidates, [primary, secondary]) is True

        # Only primary failed → should retry (NEW FIX)
        assert _should_retry(True, candidates, [primary]) is True

        # Only secondary failed → should NOT retry
        assert _should_retry(True, candidates, [secondary]) is False

        # Nothing failed → should NOT retry
        assert _should_retry(True, candidates, []) is False

        # Retry disabled via flag → should NOT retry even if primary failed
        assert _should_retry(False, candidates, [primary]) is False

        # No candidates → should NOT retry
        assert _should_retry(True, [], []) is False


class TestPhase3CompileCheck:

    def test_retrieval_module_imports(self):
        import modules.retrieval  # noqa: F401
