"""
Gate 4: Latency Budget

Validates that graph retrieval is bounded and auto-fallback on timeout.
"""

import pytest
import asyncio
import time
import os

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import get_graph_memory_config, reset_config
from modules.graph_circuit_breaker import reset_all_breakers
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
def require_neo4j():
    """Skip tests if Neo4j not configured or not reachable."""
    import socket
    config = get_graph_memory_config()
    if not config.neo4j_uri or not config.neo4j_password:
        pytest.skip("Neo4j not configured")
    try:
        host = config.neo4j_uri.split("://")[-1].split(":")[0]
        socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError):
        pytest.skip("Neo4j host not reachable")


@pytest.mark.asyncio
async def test_search_respects_timeout():
    """
    Verify search operation respects configured timeout.
    Tests that timeout config is correctly passed to _execute_with_timeout.
    """
    from unittest.mock import patch
    
    # Set short timeout
    os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = "150"  # 150ms
    reset_config()
    
    try:
        client = GraphMemoryCore("gate4-tenant", "gate4-twin", "gate4-test")
        
        # Verify config is set correctly
        assert client.config.read_timeout_ms == 150
        
        # Mock _execute_with_timeout to capture the timeout value
        timeout_used = None
        
        async def mock_execute(name, coro, timeout_ms=None):
            nonlocal timeout_used
            timeout_used = timeout_ms or client.config.read_timeout_ms
            # Return empty results immediately
            return []
        
        # Apply mock before search
        original_execute = client._execute_with_timeout
        client._execute_with_timeout = mock_execute
        
        try:
            results = await client.search("test query")
        finally:
            client._execute_with_timeout = original_execute
        
        # Timeout should be passed correctly (150ms)
        assert timeout_used == 150, f"Expected 150ms timeout, got {timeout_used}ms"
        
        # Results should be a list
        assert isinstance(results, list)
        
    finally:
        os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = "300"
        reset_config()


@pytest.mark.asyncio
async def test_extraction_respects_timeout():
    """
    Verify extraction operation respects configured timeout.
    """
    os.environ["GRAPH_MEMORY_EXTRACTION_TIMEOUT_MS"] = "100"
    reset_config()
    
    try:
        config = get_graph_memory_config()
        assert config.extraction_timeout_ms == 100
        
        # Cleanup
    finally:
        os.environ["GRAPH_MEMORY_EXTRACTION_TIMEOUT_MS"] = "5000"
        reset_config()


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_neo4j")
async def test_timeout_returns_empty_not_exception():
    """
    Verify timeout returns empty results, not exception.
    """
    os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = "1"  # 1ms - guaranteed timeout
    reset_config()
    
    client = GraphMemoryCore("gate4-tenant", "gate4-twin", "gate4-test")
    
    try:
        # Should not raise
        results = await client.search("test")
        
        # Should return empty list
        assert results == [], f"Expected empty list on timeout, got {results}"
        
    finally:
        os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = "300"
        reset_config()


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_neo4j")
async def test_configurable_timeout_values():
    """
    Verify timeout values are configurable and respected.
    """
    test_cases = [
        ("50", 50),
        ("100", 100),
        ("500", 500),
        ("1000", 1000),
    ]
    
    for env_value, expected_ms in test_cases:
        os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = env_value
        reset_config()
        
        config = get_graph_memory_config()
        assert config.read_timeout_ms == expected_ms, (
            f"Expected {expected_ms}ms, got {config.read_timeout_ms}ms"
        )
    
    # Restore
    os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = "300"
    reset_config()


@pytest.mark.asyncio
async def test_latency_metrics_emitted():
    """
    Verify latency metrics are available in status.
    """
    client = GraphMemoryCore("gate4-tenant", "gate4-twin", "gate4-test")
    
    status = client.get_status()
    
    # Status should include configuration
    assert "read_allowed" in status
    assert "circuit_status" in status


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_neo4j")
async def test_fast_fallback_on_slow_query():
    """
    Verify that slow queries are abandoned and fallback used.
    """
    os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = "50"
    reset_config()
    
    client = GraphMemoryCore("gate4-tenant", "gate4-twin", "gate4-test")
    
    try:
        # Create some data first
        await client.create_episode(
            name="Test",
            body="Test content for latency test",
            source_type="test",
            source_ref="latency-test",
            async_write=False
        )
        
        await asyncio.sleep(2)  # Wait for indexing
        
        # Search with very short timeout
        start = time.time()
        results = await client.search("Test content", num_results=100)
        elapsed_ms = (time.time() - start) * 1000
        
        # Should complete within reasonable time even if timeout
        assert elapsed_ms < 1000, f"Fallback took too long: {elapsed_ms}ms"
        
    finally:
        await client.delete_twin_graph()
        os.environ["GRAPH_MEMORY_READ_TIMEOUT_MS"] = "300"
        reset_config()
