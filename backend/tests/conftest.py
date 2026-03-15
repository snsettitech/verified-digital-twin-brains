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
os.environ.setdefault("DEEP_RESEARCH_ENABLED", "true")

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
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test requiring external services"
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
    _ = exitstatus
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


# =============================================================================
# Graph Memory Test Fixtures
# =============================================================================

class MockGraphOutbox:
    """Mock outbox for testing without database."""
    
    def __init__(self):
        self._jobs = {}
        self._idempotency = {}
    
    def submit(
        self,
        tenant_id,
        twin_id,
        operation,
        idempotency_key,
        payload,
        priority=0,
        correlation_id=None,
        scope_id=None,
        creator_id=None,
    ):
        """Mock submit that stores in memory."""
        import uuid
        import time
        
        # Scope-isolated idempotency (matches production behavior)
        dedupe_key = f"{scope_id or twin_id}:{idempotency_key}"
        if dedupe_key in self._idempotency:
            return self._idempotency[dedupe_key]
        
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "tenant_id": tenant_id,
            "twin_id": twin_id,
            "scope_id": scope_id,
            "creator_id": creator_id,
            "operation": operation.value if hasattr(operation, 'value') else str(operation),
            "idempotency_key": idempotency_key,
            "payload": payload,
            "status": "pending",
            "priority": priority,
            "attempt_count": 0,
            "correlation_id": correlation_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        self._jobs[job_id] = job
        self._idempotency[dedupe_key] = job_id
        return job_id
    
    def get_depth(self, scope_id=None) -> int:
        """Get pending job count."""
        return sum(
            1
            for j in self._jobs.values()
            if j.get("status") == "pending" and (scope_id is None or j.get("scope_id") == scope_id)
        )
    
    def get_stats(self, scope_id=None):
        """Get job statistics."""
        stats = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        for job in self._jobs.values():
            if scope_id is not None and job.get("scope_id") != scope_id:
                continue
            status = job.get("status", "pending")
            if status in stats:
                stats[status] += 1
        return stats
    
    def get_pending_jobs(self, limit=100, scope_id=None):
        """Get pending jobs."""
        return [
            j
            for j in self._jobs.values()
            if j.get("status") == "pending" and (scope_id is None or j.get("scope_id") == scope_id)
        ][:limit]
    
    def clear(self):
        """Clear all jobs."""
        self._jobs.clear()
        self._idempotency.clear()


@pytest.fixture(scope="function")
def mock_graph_outbox_table(monkeypatch):
    """
    Mock the graph_outbox table for tests that don't need real database.
    Returns a mock outbox that stores jobs in memory.
    """
    import modules.graph_outbox as outbox_module
    
    # Create mock instance
    mock_outbox = MockGraphOutbox()
    
    # Replace the singleton getter
    monkeypatch.setattr(outbox_module, "_outbox_instance", mock_outbox)
    monkeypatch.setattr(outbox_module, "get_graph_outbox", lambda: mock_outbox)
    
    yield mock_outbox._jobs
    
    # Cleanup
    mock_outbox.clear()
    outbox_module.reset_outbox()


@pytest.fixture(scope="function")
def mock_graphiti_client(monkeypatch):
    """
    Mock Graphiti client for tests that don't need real Neo4j.
    Returns a mock client with configurable behavior.
    """
    from unittest.mock import MagicMock
    import uuid
    
    class MockGraphiti:
        def __init__(self, **kwargs):
            self._episodes = {}
            self._initialized = True
            self.init_kwargs = kwargs
        
        def add_episode(self, name, episode_body, source_description, **kwargs):
            episode_id = str(uuid.uuid4())
            self._episodes[episode_id] = {
                "uuid": episode_id,
                "name": name,
                "body": episode_body,
                "source": source_description
            }
            return {"uuid": episode_id}
        
        def search(self, query, num_results=10):
            # Return empty list by default, tests can override
            return []
        
        def delete_by_group_id(self, group_id):
            deleted = 0
            to_delete = [k for k, v in self._episodes.items() if v.get("group_id") == group_id]
            for k in to_delete:
                del self._episodes[k]
                deleted += 1
            return deleted
    
    import modules.graph_memory_core as core_module
    
    def mock_get_graphiti(self):
        if not hasattr(self, '_mock_graphiti'):
            self._mock_graphiti = MockGraphiti()
        return self._mock_graphiti
    
    monkeypatch.setattr(core_module.GraphMemoryCore, "_get_graphiti", mock_get_graphiti)
    
    yield MockGraphiti


@pytest.fixture(scope="function")
def enable_graph_memory(monkeypatch):
    """Enable graph memory for tests."""
    monkeypatch.setenv("GRAPH_MEMORY_ENABLED", "true")
    monkeypatch.setenv("GRAPH_MEMORY_READ_ENABLED", "true")
    monkeypatch.setenv("GRAPH_MEMORY_WRITE_ENABLED", "true")
    monkeypatch.setenv("NEO4J_URI", "bolt://mock:7687")
    monkeypatch.setenv("NEO4J_PASSWORD", "mock-password")
    
    # Force config reload
    import modules.graph_memory_config as config_module
    config_module._config_instance = None
    
    yield
    
    # Cleanup
    config_module._config_instance = None
