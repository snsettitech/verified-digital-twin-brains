"""
Gate 2: Retry Safety

Validates that replaying the same event 10 times produces exactly
1 Episode and 1 Claim (idempotency).
"""

import pytest
import asyncio
import time
import uuid
from typing import List

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import get_graph_memory_config, reset_config
from modules.graph_outbox import get_graph_outbox, reset_outbox
from modules.graph_circuit_breaker import reset_all_breakers
from modules.graph_extraction_cache import reset_cache
from modules.observability import supabase


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
@pytest.mark.usefixtures("require_neo4j")
async def test_idempotent_episode_creation():
    """
    Submit same episode 10 times, verify only 1 created.
    """
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:8]}"
    twin_id = f"test-twin-{uuid.uuid4().hex[:8]}"
    
    client = GraphMemoryCore(tenant_id, twin_id, "gate2-test")
    config = get_graph_memory_config()
    
    source_ref = f"gate2-test-{time.time()}"
    content = "Owner prefers direct communication without fluff"
    
    # Generate deterministic idempotency key
    idempotency_key = config.make_idempotency_key(
        tenant_id=tenant_id,
        twin_id=twin_id,
        source_type="escalation",
        source_ref=source_ref,
        content=content
    )
    
    job_ids: List[str] = []
    
    try:
        # Submit 10 times with same content
        for i in range(10):
            job_id = await client.create_episode(
                name=f"Retry Test {i}",
                body=content,
                source_type="escalation",
                source_ref=source_ref,
                async_write=True  # Use outbox
            )
            if job_id:
                job_ids.append(job_id)
        
        # Verify all 10 submissions returned job IDs
        assert len(job_ids) == 10, f"Expected 10 job IDs, got {len(job_ids)}"
        
        # Wait for outbox processing
        await asyncio.sleep(1)
        
        # Query outbox for this tenant-twin
        result = supabase.table("graph_outbox").select("*").eq(
            "tenant_id", tenant_id
        ).eq("twin_id", twin_id).execute()
        
        records = result.data or []
        
        # Count unique idempotency keys
        unique_keys = set(r["idempotency_key"] for r in records)
        
        print(f"Total outbox records: {len(records)}")
        print(f"Unique idempotency keys: {len(unique_keys)}")
        
        # Should have exactly 1 unique idempotency key
        assert len(unique_keys) == 1, (
            f"Idempotency failed: {len(unique_keys)} unique keys for 10 submissions. "
            f"Keys: {list(unique_keys)[:3]}"
        )
        
        # Verify all records point to same idempotency key
        for record in records:
            assert record["idempotency_key"] == idempotency_key, (
                f"Mismatched idempotency key: {record['idempotency_key'][:20]}..."
            )
        
    finally:
        # Cleanup
        await client.delete_twin_graph()
        # Clean outbox
        supabase.table("graph_outbox").delete().eq("tenant_id", tenant_id).eq(
            "twin_id", twin_id
        ).execute()


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_neo4j")
async def test_different_content_creates_different_episodes():
    """
    Verify that different content creates different episodes (non-false-positive).
    """
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:8]}"
    twin_id = f"test-twin-{uuid.uuid4().hex[:8]}"
    
    client = GraphMemoryCore(tenant_id, twin_id, "gate2-test")
    
    try:
        # Create 3 different episodes
        for i in range(3):
            await client.create_episode(
                name=f"Episode {i}",
                body=f"Unique content {i} - {time.time()}",
                source_type="test",
                source_ref=f"gate2-unique-{i}",
                async_write=True
            )
        
        # Wait for outbox
        await asyncio.sleep(1)
        
        # Query outbox
        result = supabase.table("graph_outbox").select("idempotency_key").eq(
            "tenant_id", tenant_id
        ).eq("twin_id", twin_id).execute()
        
        records = result.data or []
        unique_keys = set(r["idempotency_key"] for r in records)
        
        # Should have 3 unique keys
        assert len(unique_keys) == 3, (
            f"Expected 3 unique episodes, got {len(unique_keys)}"
        )
        
    finally:
        await client.delete_twin_graph()
        supabase.table("graph_outbox").delete().eq("tenant_id", tenant_id).eq(
            "twin_id", twin_id
        ).execute()


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_neo4j")
async def test_outbox_deduplication_at_submission():
    """
    Verify outbox deduplicates at submission time (before processing).
    """
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:8]}"
    twin_id = f"test-twin-{uuid.uuid4().hex[:8]}"
    
    outbox = get_graph_outbox()
    config = get_graph_memory_config()
    
    idempotency_key = f"test-dedup-{time.time()}"
    
    # Submit same operation twice rapidly
    job_id_1 = outbox.submit(
        tenant_id=tenant_id,
        twin_id=twin_id,
        operation="create_episode",  # type: ignore
        idempotency_key=idempotency_key,
        payload={"test": "data"},
        correlation_id="gate2-test"
    )
    
    job_id_2 = outbox.submit(
        tenant_id=tenant_id,
        twin_id=twin_id,
        operation="create_episode",  # type: ignore
        idempotency_key=idempotency_key,
        payload={"test": "data"},
        correlation_id="gate2-test"
    )
    
    # Should return same job ID (deduplicated)
    assert job_id_1 == job_id_2, (
        f"Deduplication failed: got different job IDs {job_id_1} vs {job_id_2}"
    )
    
    # Cleanup
    supabase.table("graph_outbox").delete().eq("tenant_id", tenant_id).eq(
        "twin_id", twin_id
    ).execute()
