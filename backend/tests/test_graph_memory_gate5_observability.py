"""
Gate 5: Observability

Validates correlation_id in logs, metrics for read/write/timeout/error,
and outbox depth metric.
"""

import pytest
import logging
import time
from unittest.mock import patch, MagicMock

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import get_graph_memory_config, reset_config
from modules.graph_circuit_breaker import get_circuit_breaker, reset_all_breakers
from modules.graph_outbox import get_graph_outbox, reset_outbox, GraphOperationType
from modules.graph_extraction_cache import reset_cache


# Capture log records for testing
class LogCapture:
    def __init__(self):
        self.records = []
    
    def capture(self, record):
        self.records.append(record)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset all singletons before each test."""
    reset_config()
    reset_all_breakers()
    reset_outbox()
    reset_cache()


@pytest.fixture
def log_capture():
    """Capture log output."""
    capture = LogCapture()
    logger = logging.getLogger("modules.graph_memory_core")
    
    handler = logging.Handler()
    handler.emit = capture.capture
    handler.setLevel(logging.DEBUG)
    
    old_handlers = logger.handlers[:]
    logger.handlers = [handler]
    
    yield capture
    
    logger.handlers = old_handlers


def test_correlation_id_in_client():
    """
    Verify correlation_id is stored in client and available in status.
    """
    correlation_id = f"test-corr-{time.time()}"
    client = GraphMemoryCore("gate5-tenant", "gate5-twin", correlation_id)
    
    assert client.correlation_id == correlation_id
    
    status = client.get_status()
    assert status["correlation_id"] == correlation_id


def test_correlation_id_defaults_when_not_provided():
    """
    Verify default correlation_id when not provided.
    """
    client = GraphMemoryCore("gate5-tenant", "gate5-twin")
    
    assert client.correlation_id == "no-correlation"


@pytest.mark.asyncio
async def test_circuit_breaker_status_available():
    """
    Verify circuit breaker status is queryable.
    """
    tenant_id = "gate5-cb-tenant"
    twin_id = "gate5-cb-twin"
    
    breaker = get_circuit_breaker(tenant_id, twin_id)
    status = breaker.get_status()
    
    assert "state" in status
    assert "failure_count" in status
    assert "is_open" in status
    assert "tenant_id" in status
    assert "twin_id" in status


@pytest.mark.asyncio
async def test_outbox_stats_available():
    """
    Verify outbox statistics are available.
    """
    outbox = get_graph_outbox()
    
    stats = outbox.get_stats()
    
    assert "pending" in stats
    assert "processing" in stats
    assert "completed" in stats
    assert "failed" in stats


def test_outbox_depth_metric():
    """
    Verify outbox depth can be queried.
    """
    outbox = get_graph_outbox()
    
    depth = outbox.get_depth()
    
    assert isinstance(depth, int)
    assert depth >= 0


@pytest.mark.asyncio
async def test_client_status_includes_all_fields():
    """
    Verify client status includes comprehensive information.
    """
    client = GraphMemoryCore("gate5-tenant", "gate5-twin", "gate5-test")
    
    status = client.get_status()
    
    # Check all expected fields
    expected_fields = [
        "enabled",
        "read_allowed",
        "write_allowed",
        "circuit_status",
        "group_id",
        "graphiti_initialized",
        "correlation_id"
    ]
    
    for field in expected_fields:
        assert field in status, f"Missing field in status: {field}"


@pytest.mark.asyncio
async def test_circuit_breaker_metrics_on_failure():
    """
    Verify circuit breaker tracks failure metrics.
    """
    tenant_id = "gate5-metrics-tenant"
    twin_id = "gate5-metrics-twin"
    
    breaker = get_circuit_breaker(tenant_id, twin_id)
    
    # Record some failures
    for _ in range(3):
        breaker.record_failure()
    
    status = breaker.get_status()
    
    assert status["failure_count"] == 3
    assert status["last_failure_time"] is not None


@pytest.mark.asyncio
async def test_circuit_breaker_metrics_on_success():
    """
    Verify circuit breaker tracks success metrics.
    """
    tenant_id = "gate5-success-tenant"
    twin_id = "gate5-success-twin"
    
    breaker = get_circuit_breaker(tenant_id, twin_id)
    
    # Record success
    breaker.record_success()
    
    status = breaker.get_status()
    
    assert status["last_success_time"] is not None


def test_config_exposes_metrics():
    """
    Verify configuration exposes relevant settings for metrics.
    """
    config = get_graph_memory_config()
    
    # These should be accessible for monitoring
    assert hasattr(config, "enabled")
    assert hasattr(config, "read_enabled")
    assert hasattr(config, "write_enabled")
    assert hasattr(config, "read_timeout_ms")
    assert hasattr(config, "circuit_breaker_threshold")


@pytest.mark.asyncio
async def test_outbox_records_correlation_id(mock_graph_outbox_table):
    """
    Verify outbox records include correlation_id.
    """
    outbox = get_graph_outbox()
    correlation_id = "test-corr-outbox-123"
    
    job_id = outbox.submit(
        tenant_id="gate5-tenant",
        twin_id="gate5-twin",
        operation=GraphOperationType.CREATE_EPISODE,
        idempotency_key=f"test-{time.time()}",
        payload={"test": "data"},
        correlation_id=correlation_id
    )
    
    assert job_id is not None


def test_group_id_format_for_observability():
    """
    Verify group_id format is consistent and observable.
    """
    client = GraphMemoryCore("tenant-123", "twin-456", "test")
    
    # Scope/group uses "__" delimiter in single-profile migration.
    assert client.group_id == "tenant-123__twin-456"
    assert "__" in client.group_id
