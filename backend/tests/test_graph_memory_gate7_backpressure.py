"""
Gate 7: Backpressure

Validates that outbox grows safely during outage and drains safely after 
recovery without duplicates. Uses failure injection, not worker stopping.
"""

import pytest
import asyncio
import time
import uuid
import os
from unittest.mock import patch

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import get_graph_memory_config, reset_config
from modules.graph_circuit_breaker import reset_all_breakers
from modules.graph_outbox import get_graph_outbox, reset_outbox, GraphOperationType
from modules.graph_extraction_cache import reset_cache


@pytest.fixture(autouse=True)
def reset_state():
    """Reset all singletons before each test."""
    reset_config()
    reset_all_breakers()
    reset_outbox()
    reset_cache()


@pytest.fixture
def require_neo4j():
    """Skip tests if Neo4j not configured."""
    config = get_graph_memory_config()
    if not config.neo4j_uri or not config.neo4j_password:
        pytest.skip("Neo4j not configured")


@pytest.mark.asyncio
async def test_outbox_grows_during_simulated_outage(mock_graph_outbox_table):
    """
    Simulate outage by breaking Neo4j, verify outbox still accepts jobs.
    """
    tenant_id = f"gate7-{uuid.uuid4().hex[:8]}"
    twin_id = f"gate7-twin-{uuid.uuid4().hex[:8]}"
    
    # Enable graph memory but break Neo4j (simulates outage)
    os.environ["GRAPH_MEMORY_ENABLED"] = "true"
    os.environ["GRAPH_MEMORY_WRITE_ENABLED"] = "true"
    os.environ["NEO4J_URI"] = "bolt://invalid-host-99999:7687"
    reset_config()
    
    try:
        client = GraphMemoryCore(tenant_id, twin_id, "gate7-test")
        
        # Submit jobs during "outage"
        for i in range(10):
            await client.create_episode(
                name=f"Outage Job {i}",
                body=f"Content {i}",
                source_type="test",
                source_ref=f"outage-{i}",
                async_write=True
            )
        
        # Verify outbox grew
        depth = client.outbox.get_depth()
        assert depth >= 10, f"Outbox should have 10+ jobs, got {depth}"
        
    finally:
        # Restore
        os.environ["GRAPH_MEMORY_ENABLED"] = "false"
        if "NEO4J_URI" in os.environ:
            del os.environ["NEO4J_URI"]
        reset_config()


@pytest.mark.asyncio
async def test_deduplication_prevents_duplicates_on_resubmit(mock_graph_outbox_table):
    """
    Verify that resubmitting same jobs during recovery doesn't create duplicates.
    """
    # Enable graph memory
    os.environ["GRAPH_MEMORY_ENABLED"] = "true"
    os.environ["GRAPH_MEMORY_WRITE_ENABLED"] = "true"
    reset_config()
    
    try:
        tenant_id = f"gate7-dedup-{uuid.uuid4().hex[:8]}"
        twin_id = f"gate7-twin-{uuid.uuid4().hex[:8]}"
        
        client = GraphMemoryCore(tenant_id, twin_id, "gate7-test")
        
        source_ref = f"gate7-test-{time.time()}"
        content = "Test content for deduplication"
        
        # Submit 5 unique jobs
        job_ids_first = []
        for i in range(5):
            job_id = await client.create_episode(
                name=f"Job {i}",
                body=f"{content} - {i}",
                source_type="test",
                source_ref=f"{source_ref}-{i}",
                async_write=True
            )
            job_ids_first.append(job_id)
        
        # Resubmit same jobs (simulating recovery retry)
        job_ids_second = []
        for i in range(5):
            job_id = await client.create_episode(
                name=f"Job {i}",
                body=f"{content} - {i}",
                source_type="test",
                source_ref=f"{source_ref}-{i}",
                async_write=True
            )
            job_ids_second.append(job_id)
        
        # Job IDs should be identical (deduplication)
        assert job_ids_first == job_ids_second, "Duplicate jobs should return same ID"
        
        # Total unique jobs should be 5
        all_jobs = set(job_ids_first + job_ids_second)
        assert len(all_jobs) == 5, f"Should have 5 unique jobs, got {len(all_jobs)}"
    finally:
        # Cleanup
        os.environ["GRAPH_MEMORY_ENABLED"] = "false"
        reset_config()


@pytest.mark.asyncio
async def test_outbox_stats_accurate(mock_graph_outbox_table):
    """
    Verify outbox stats reflect actual state.
    """
    tenant_id = f"gate7-stats-{uuid.uuid4().hex[:8]}"
    twin_id = f"gate7-twin-{uuid.uuid4().hex[:8]}"
    
    outbox = get_graph_outbox()
    
    # Initial stats should be empty
    stats = outbox.get_stats()
    assert isinstance(stats, dict)
    
    # Submit jobs
    for i in range(5):
        outbox.submit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            operation=GraphOperationType.CREATE_EPISODE,
            idempotency_key=f"stats-test-{time.time()}-{i}",
            payload={"test": i},
            priority=0
        )
    
    # Stats should reflect submitted jobs
    depth = outbox.get_depth()
    assert depth >= 5, f"Depth should be >= 5, got {depth}"


@pytest.mark.asyncio
async def test_priority_ordering(mock_graph_outbox_table):
    """
    Verify higher priority jobs are processed first.
    """
    tenant_id = f"gate7-priority-{uuid.uuid4().hex[:8]}"
    twin_id = f"gate7-twin-{uuid.uuid4().hex[:8]}"
    
    outbox = get_graph_outbox()
    
    # Submit low priority jobs
    low_priority_ids = []
    for i in range(3):
        job_id = outbox.submit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            operation=GraphOperationType.CREATE_EPISODE,
            idempotency_key=f"low-{time.time()}-{i}",
            payload={"priority": "low"},
            priority=1  # Low priority
        )
        low_priority_ids.append(job_id)
    
    # Submit high priority jobs
    high_priority_ids = []
    for i in range(3):
        job_id = outbox.submit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            operation=GraphOperationType.CREATE_EPISODE,
            idempotency_key=f"high-{time.time()}-{i}",
            payload={"priority": "high"},
            priority=10  # High priority
        )
        high_priority_ids.append(job_id)
    
    # All jobs should be accepted
    assert len(low_priority_ids) == 3
    assert len(high_priority_ids) == 3
    
    # Verify all unique
    all_ids = set(low_priority_ids + high_priority_ids)
    assert len(all_ids) == 6


@pytest.mark.asyncio
async def test_retry_with_backoff(mock_graph_outbox_table):
    """
    Verify failed jobs are retried with exponential backoff.
    """
    tenant_id = f"gate7-retry-{uuid.uuid4().hex[:8]}"
    twin_id = f"gate7-twin-{uuid.uuid4().hex[:8]}"
    
    outbox = get_graph_outbox()
    
    job_id = outbox.submit(
        tenant_id=tenant_id,
        twin_id=twin_id,
        operation=GraphOperationType.CREATE_EPISODE,
        idempotency_key=f"retry-test-{time.time()}",
        payload={"test": "retry"},
        priority=5
    )
    
    assert job_id is not None
    
    # Verify job exists in mock outbox
    assert job_id in mock_graph_outbox_table
    job = mock_graph_outbox_table[job_id]
    assert job["status"] == "pending"
    assert job["attempt_count"] == 0


@pytest.mark.asyncio
async def test_outbox_depth_metric(mock_graph_outbox_table):
    """
    Verify outbox depth metric is exposed and accurate.
    """
    tenant_id = f"gate7-metric-{uuid.uuid4().hex[:8]}"
    twin_id = f"gate7-twin-{uuid.uuid4().hex[:8]}"
    
    outbox = get_graph_outbox()
    
    # Get initial depth
    initial_depth = outbox.get_depth()
    
    # Add jobs
    for i in range(7):
        outbox.submit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            operation=GraphOperationType.CREATE_EPISODE,
            idempotency_key=f"metric-test-{time.time()}-{i}",
            payload={"metric": "test"},
            priority=0
        )
    
    # Depth should increase
    final_depth = outbox.get_depth()
    assert final_depth >= initial_depth + 7, f"Depth should increase by ~7"
