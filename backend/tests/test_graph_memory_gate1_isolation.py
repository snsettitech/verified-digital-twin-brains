"""
Gate 1: Isolation Proof

Validates that data written under tenantA:twinA group_id cannot be read
via tenantB:twinB using Graphiti retrieval behavior.
"""

import pytest
import asyncio
import time
import uuid

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import reset_config, get_graph_memory_config
from modules.graph_circuit_breaker import reset_all_breakers
from modules.graph_outbox import reset_outbox
from modules.graph_extraction_cache import reset_cache


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset all singletons before each test."""
    monkeypatch.setenv("GRAPH_MEMORY_ENABLED", "true")
    monkeypatch.setenv("GRAPH_MEMORY_READ_ENABLED", "true")
    monkeypatch.setenv("GRAPH_MEMORY_WRITE_ENABLED", "true")
    reset_config()
    reset_all_breakers()
    reset_outbox()
    reset_cache()


@pytest.fixture
def require_neo4j():
    """Skip tests if Neo4j is not actually connectable."""
    config = get_graph_memory_config()
    if not config.neo4j_uri or not config.neo4j_password:
        pytest.skip("Neo4j not configured")
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user or "neo4j", config.neo4j_password),
        )
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
    except Exception:
        pytest.skip("Neo4j not reachable")


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_neo4j")
async def test_cross_tenant_isolation_via_graphiti():
    """
    Verify Graphiti group_id isolation works end-to-end.
    
    This test validates isolation through Graphiti's retrieval API,
    not assumptions about Neo4j labels.
    """
    tenant_a_id = str(uuid.uuid4())
    tenant_b_id = str(uuid.uuid4())
    twin_a_id = str(uuid.uuid4())
    twin_b_id = str(uuid.uuid4())
    
    client_a = GraphMemoryCore(tenant_a_id, twin_a_id, "gate1-test")
    client_b = GraphMemoryCore(tenant_b_id, twin_b_id, "gate1-test")
    
    # Generate unique content
    secret_phrase = f"secret-tenant-a-{time.time()}-{uuid.uuid4().hex}"
    
    try:
        # Write data as tenant A (synchronous for immediate verification)
        episode_id = await client_a.create_episode(
            name="Secret Episode",
            body=f"This is {secret_phrase} data for tenant A only",
            source_type="test",
            source_ref="gate1-isolation-test",
            async_write=False
        )
        
        assert episode_id is not None, "Failed to create episode as tenant A"
        
        # Wait for Graphiti indexing
        await asyncio.sleep(2)
        
        # Try to read as tenant B using Graphiti search
        results_b = await client_b.search(secret_phrase, num_results=5)
        
        # Try to read as tenant A
        results_a = await client_a.search(secret_phrase, num_results=5)
        
        # Assertions
        assert len(results_b) == 0, (
            f"ISOLATION BREACH: Tenant B found {len(results_b)} results. "
            f"Data: {results_b[:2]}"
        )
        
        assert len(results_a) > 0, (
            f"Tenant A cannot read own data. Expected results, got none."
        )
        
        # Verify the content matches
        found_content = False
        for result in results_a:
            content = result.get("episode_body", result.get("content", ""))
            if secret_phrase in content:
                found_content = True
                break
        
        assert found_content, "Tenant A found results but not the expected content"
        
    finally:
        # Cleanup - delete both graphs
        await client_a.delete_twin_graph()
        await client_b.delete_twin_graph()


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_neo4j")
async def test_same_tenant_different_twin_isolation():
    """
    Verify that twinA and twinB under same tenant are isolated.
    """
    tenant_id = str(uuid.uuid4())
    twin_a_id = str(uuid.uuid4())
    twin_b_id = str(uuid.uuid4())
    
    client_a = GraphMemoryCore(tenant_id, twin_a_id, "gate1-test")
    client_b = GraphMemoryCore(tenant_id, twin_b_id, "gate1-test")
    
    secret_phrase = f"secret-twin-a-{time.time()}-{uuid.uuid4().hex}"
    
    try:
        # Write as twin A
        await client_a.create_episode(
            name="Twin A Episode",
            body=f"This is {secret_phrase}",
            source_type="test",
            source_ref="gate1-same-tenant-test",
            async_write=False
        )
        
        await asyncio.sleep(2)
        
        # Try to read as twin B (same tenant)
        results_b = await client_b.search(secret_phrase, num_results=5)
        results_a = await client_a.search(secret_phrase, num_results=5)
        
        # Twins should be isolated even in same tenant
        assert len(results_b) == 0, (
            f"Twin isolation failed: Twin B found {len(results_b)} results"
        )
        assert len(results_a) > 0, "Twin A cannot read own data"
        
    finally:
        await client_a.delete_twin_graph()
        await client_b.delete_twin_graph()


@pytest.mark.asyncio
async def test_group_id_format():
    """
    Verify group_id format is {tenant_id}__{twin_id}
    """
    tenant_id = str(uuid.uuid4())
    twin_id = str(uuid.uuid4())
    
    client = GraphMemoryCore(tenant_id, twin_id, "gate1-test")
    
    expected_group_id = f"{tenant_id}__{twin_id}"
    assert client.group_id == expected_group_id, (
        f"Group ID mismatch: expected {expected_group_id}, got {client.group_id}"
    )
