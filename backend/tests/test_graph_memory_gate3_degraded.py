"""
Gate 3: Degraded Mode Proof

Validates that when Neo4j is down, Graphiti fails, extractor fails, or 
Pinecone is slow, chat endpoints still return successfully using fallback.
"""

import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock

from modules.graph_memory_core import GraphMemoryCore, GraphMemoryUnavailable
from modules.graph_memory_config import get_graph_memory_config, reset_config
from modules.graph_circuit_breaker import get_circuit_breaker, reset_all_breakers
from modules.graph_outbox import reset_outbox
from modules.graph_extraction_cache import reset_cache


@pytest.fixture(autouse=True)
def reset_state():
    """Reset all singletons before each test."""
    reset_config()
    reset_all_breakers()
    reset_outbox()
    reset_cache()


@pytest.fixture
def test_client():
    """Create a test client."""
    return GraphMemoryCore("gate3-tenant", "gate3-twin", "gate3-test")


@pytest.mark.asyncio
async def test_neo4j_connection_failure_fallback(mock_graph_outbox_table, mock_graphiti_client):
    """
    Simulate Neo4j connection failure - operations should fallback to outbox
    or return empty results without raising exceptions.
    """
    # Enable graph memory first
    os.environ["GRAPH_MEMORY_ENABLED"] = "true"
    os.environ["GRAPH_MEMORY_WRITE_ENABLED"] = "true"
    
    # Temporarily break Neo4j connection
    original_uri = os.environ.get("NEO4J_URI")
    os.environ["NEO4J_URI"] = "bolt://invalid-host-99999:7687"
    reset_config()
    
    try:
        client = GraphMemoryCore("gate3-tenant", "gate3-twin", "gate3-test")
        
        # Create episode should queue to outbox (not fail)
        job_id = await client.create_episode(
            name="Test Episode",
            body="Test content",
            source_type="test",
            source_ref="gate3-test",
            async_write=True
        )
        
        # Should return job ID (outbox submission succeeds even if Neo4j down)
        assert job_id is not None, "Outbox submission should succeed"
        
        # Search should return empty (not raise)
        results = await client.search("test query")
        assert isinstance(results, list), "Search should return list"
        assert len(results) == 0, "Search should return empty when Neo4j down"
        
    finally:
        # Restore
        if original_uri:
            os.environ["NEO4J_URI"] = original_uri
        else:
            if "NEO4J_URI" in os.environ:
                del os.environ["NEO4J_URI"]
        # Reset to default disabled state
        os.environ["GRAPH_MEMORY_ENABLED"] = "false"
        reset_config()


@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failure(mock_graph_outbox_table):
    """
    Verify circuit breaker opens after threshold failures.
    """
    # Enable graph memory
    os.environ["GRAPH_MEMORY_ENABLED"] = "true"
    os.environ["GRAPH_MEMORY_WRITE_ENABLED"] = "true"
    reset_config()
    
    tenant_id = f"gate3-cb-tenant"
    twin_id = f"gate3-cb-twin"
    
    breaker = get_circuit_breaker(tenant_id, twin_id)
    config = get_graph_memory_config()
    
    # Record failures up to threshold
    threshold = config.circuit_breaker_threshold
    
    for i in range(threshold + 2):
        should_open = breaker.record_failure()
        if i >= threshold - 1:
            assert should_open or breaker.is_open(), (
                f"Circuit should open after {threshold} failures"
            )
    
    # Circuit should be open
    assert breaker.is_open(), "Circuit breaker should be open"
    
    # Create client with open circuit
    client = GraphMemoryCore(tenant_id, twin_id, "gate3-test")
    
    # Operations should be skipped or queued
    job_id = await client.create_episode(
        name="Test",
        body="Test",
        source_type="test",
        source_ref="gate3-cb-test",
        async_write=True
    )
    
    # Should still queue to outbox for later retry
    assert job_id is not None, "Should queue to outbox even with open circuit"
    
    # Cleanup
    os.environ["GRAPH_MEMORY_ENABLED"] = "false"
    reset_config()


@pytest.mark.asyncio
async def test_graphiti_initialization_failure_graceful(mock_graph_outbox_table):
    """
    Test graceful handling when Graphiti cannot initialize.
    """
    # Enable graph memory
    os.environ["GRAPH_MEMORY_ENABLED"] = "true"
    os.environ["GRAPH_MEMORY_WRITE_ENABLED"] = "true"
    reset_config()
    
    try:
        # Mock Graphiti as unavailable
        with patch.object(GraphMemoryCore, 'check_graphiti_available', return_value=False):
            client = GraphMemoryCore("gate3-tenant", "gate3-twin", "gate3-test")
            
            # Operations should not fail
            job_id = await client.create_episode(
                name="Test",
                body="Test",
                source_type="test",
                source_ref="gate3-test",
                async_write=True
            )
            
            assert job_id is not None
            
            results = await client.search("test")
            assert results == []
    finally:
        # Cleanup
        os.environ["GRAPH_MEMORY_ENABLED"] = "false"
        reset_config()


@pytest.mark.asyncio
async def test_timeout_does_not_crash(test_client):
    """
    Verify timeout exceptions are caught and handled gracefully.
    """
    # Mock the internal _execute_with_timeout to simulate timeout
    async def mock_execute_with_timeout(name, coro, timeout_ms=None):
        raise GraphMemoryUnavailable("Timeout: search")
    
    with patch.object(test_client, '_execute_with_timeout', mock_execute_with_timeout):
        # Should not raise, should return empty or fallback
        results = await test_client.search("test query")
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_kill_switch_disables_reads():
    """
    Verify GRAPH_MEMORY_READ_ENABLED=false disables reads.
    """
    os.environ["GRAPH_MEMORY_READ_ENABLED"] = "false"
    reset_config()
    
    try:
        client = GraphMemoryCore("gate3-tenant", "gate3-twin", "gate3-test")
        
        # Read should be disabled
        assert not client.config.is_read_allowed()
        
        # Search should return empty immediately
        results = await client.search("test")
        assert results == []
        
    finally:
        os.environ["GRAPH_MEMORY_READ_ENABLED"] = "true"
        reset_config()


@pytest.mark.asyncio
async def test_kill_switch_disables_writes(mock_graph_outbox_table):
    """
    Verify GRAPH_MEMORY_WRITE_ENABLED=false disables writes.
    """
    os.environ["GRAPH_MEMORY_WRITE_ENABLED"] = "false"
    reset_config()
    
    try:
        client = GraphMemoryCore("gate3-tenant", "gate3-twin", "gate3-test")
        
        # Write should be disabled
        assert not client.config.is_write_allowed()
        
        # Episode creation should return None
        result = await client.create_episode(
            name="Test",
            body="Test",
            source_type="test",
            source_ref="gate3-test",
            async_write=True
        )
        assert result is None
        
    finally:
        os.environ["GRAPH_MEMORY_WRITE_ENABLED"] = "true"
        reset_config()


@pytest.mark.asyncio
async def test_master_kill_switch():
    """
    Verify GRAPH_MEMORY_ENABLED=false disables everything.
    """
    os.environ["GRAPH_MEMORY_ENABLED"] = "false"
    reset_config()
    
    try:
        client = GraphMemoryCore("gate3-tenant", "gate3-twin", "gate3-test")
        
        # Everything should be disabled
        assert not client.config.enabled
        assert not client.config.is_read_allowed()
        assert not client.config.is_write_allowed()
        
        # All operations should return None/empty
        assert client._get_graphiti() is None
        
    finally:
        os.environ["GRAPH_MEMORY_ENABLED"] = "true"
        reset_config()
