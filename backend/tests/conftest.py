# backend/tests/conftest.py
"""Pytest configuration for backend tests.

Adds the backend directory to Python path so tests can import modules.
Registers custom pytest markers.
"""

import sys
import os
import pytest
from types import SimpleNamespace
from typing import Set

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure feature flags and dev mode are consistent for tests
os.environ.setdefault("ENABLE_ENHANCED_INGESTION", "true")
os.environ.setdefault("DEV_MODE", "false")

# Ensure langfuse decorator doesn't break FastAPI signatures in tests
def _noop_observe(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

sys.modules.setdefault("langfuse", SimpleNamespace(observe=_noop_observe, get_client=lambda: None))

_STRICT_GATE_ENABLED = os.getenv("REGRESSION_GATE_STRICT", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_STRICT_GATE_REQUIRED_FILES: Set[str] = {
    "test_founder_clarifier_replay_e2e.py",
    "test_e2e_loop_replay.py",
    "test_e2e_action_lane_replay.py",
    "test_public_action_query_is_disabled.py",
}
_strict_gate_seen_files: Set[str] = set()
_strict_gate_failed_nodeids: list[str] = []


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access (skipped in CI)"
    )


def pytest_collection_modifyitems(session, config, items):
    if not _STRICT_GATE_ENABLED:
        return
    collected_files = {os.path.basename(str(item.fspath)) for item in items}
    missing = sorted(_STRICT_GATE_REQUIRED_FILES - collected_files)
    if missing:
        raise pytest.UsageError(
            "REGRESSION_GATE_STRICT=true requires replay suites to be collected. Missing: "
            + ", ".join(missing)
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if not _STRICT_GATE_ENABLED:
        return
    report = outcome.get_result()
    if report.when != "call":
        return
    filename = os.path.basename(str(item.fspath))
    if filename not in _STRICT_GATE_REQUIRED_FILES:
        return
    _strict_gate_seen_files.add(filename)
    if report.failed:
        _strict_gate_failed_nodeids.append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if not _STRICT_GATE_ENABLED:
        return

    missing_runs = sorted(_STRICT_GATE_REQUIRED_FILES - _strict_gate_seen_files)
    if missing_runs or _strict_gate_failed_nodeids:
        terminal = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal:
            terminal.write_sep("=", "REGRESSION_GATE_STRICT FAILED")
            if missing_runs:
                terminal.write_line(
                    "Required replay suites did not run: " + ", ".join(missing_runs)
                )
            if _strict_gate_failed_nodeids:
                terminal.write_line(
                    "Replay failures: " + ", ".join(_strict_gate_failed_nodeids)
                )
        session.exitstatus = 1
