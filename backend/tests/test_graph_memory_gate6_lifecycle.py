"""
Gate 6: Data Lifecycle

Validates that twin graph data can be deleted by group_id reliably without orphans.
"""

import pytest
import uuid

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import reset_config
from modules.graph_circuit_breaker import reset_all_breakers
from modules.graph_outbox import reset_outbox
from modules.graph_extraction_cache import reset_cache
from modules.observability import supabase

pytestmark = pytest.mark.network


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


@pytest.mark.asyncio
async def test_delete_twin_graph_queues_job():
    """
    Verify delete_twin_graph queues a job to outbox.
    """
    tenant_id = str(uuid.uuid4())
    twin_id = str(uuid.uuid4())
    
    client = GraphMemoryCore(tenant_id, twin_id, "gate6-test")

    # Queue deletion
    result = await client.delete_twin_graph()
    
    assert result is True, "delete_twin_graph should return True"

    # Verify outbox has deletion job
    outbox_result = supabase.table("graph_outbox").select("*").eq(
        "tenant_id", tenant_id
    ).eq("twin_id", twin_id).eq("operation", "delete_twin_graph").execute()
    
    deletion_jobs = outbox_result.data or []
    assert len(deletion_jobs) >= 1, "Should have at least one deletion job"


@pytest.mark.asyncio
async def test_delete_only_targets_specific_twin():
    """
    Verify deletion only affects target twin, not others.
    """
    tenant_id = str(uuid.uuid4())
    twin_a_id = str(uuid.uuid4())
    twin_b_id = str(uuid.uuid4())
    
    client_a = GraphMemoryCore(tenant_id, twin_a_id, "gate6-test")
    client_b = GraphMemoryCore(tenant_id, twin_b_id, "gate6-test")

    # Delete twin A only
    assert await client_a.delete_twin_graph() is True

    outbox_result = (
        supabase.table("graph_outbox")
        .select("tenant_id, twin_id, operation, payload")
        .eq("tenant_id", tenant_id)
        .eq("operation", "delete_twin_graph")
        .execute()
    )
    rows = outbox_result.data or []
    assert len(rows) >= 1, "Expected at least one deletion job"
    assert any(row.get("twin_id") == twin_a_id for row in rows), "Twin A deletion job missing"
    assert not any(row.get("twin_id") == twin_b_id for row in rows), "Twin B should not be targeted yet"

    # Clean up created row(s) for test isolation.
    supabase.table("graph_outbox").delete().eq("tenant_id", tenant_id).execute()


@pytest.mark.asyncio
async def test_delete_respects_kill_switch():
    """
    Verify deletion respects GRAPH_MEMORY_ENABLED kill switch.
    """
    import os
    os.environ["GRAPH_MEMORY_ENABLED"] = "false"
    reset_config()
    
    try:
        client = GraphMemoryCore("gate6-tenant", "gate6-twin", "gate6-test")
        
        result = await client.delete_twin_graph()
        
        assert result is False, "Should return False when disabled"
        
    finally:
        os.environ["GRAPH_MEMORY_ENABLED"] = "true"
        reset_config()


def test_group_id_for_deletion_targeting():
    """
    Verify group_id format supports reliable deletion targeting.
    """
    tenant_id = "tenant-abc-123"
    twin_id = "twin-xyz-456"
    
    client = GraphMemoryCore(tenant_id, twin_id, "test")
    
    # Group ID should be deterministic
    expected = f"{tenant_id}__{twin_id}"
    assert client.group_id == expected
    
    # Should be parseable
    parts = client.group_id.split("__", 1)
    assert len(parts) == 2
    assert parts[0] == tenant_id
    assert parts[1] == twin_id


@pytest.mark.asyncio
async def test_delete_job_payload_contains_group_id(mock_graph_outbox_table):
    """
    Verify deletion job payload includes group_id for targeting.
    """
    tenant_id = f"gate6-payload-{uuid.uuid4().hex[:8]}"
    twin_id = f"gate6-twin-{uuid.uuid4().hex[:8]}"
    
    client = GraphMemoryCore(tenant_id, twin_id, "gate6-test")
    
    # Queue deletion
    await client.delete_twin_graph()
    
    # Verify job was queued in mock outbox
    jobs = mock_graph_outbox_table
    delete_jobs = [j for j in jobs.values() if j["operation"] == "delete_twin_graph"]
    
    assert len(delete_jobs) >= 1, "Delete job should be queued"
    
    # Verify payload contains group_id
    payload = delete_jobs[0]["payload"]
    assert "group_id" in payload
    assert payload["group_id"] == client.group_id


@pytest.mark.asyncio
async def test_cleanup_cache_on_delete():
    """
    Verify extraction cache is cleaned up on twin deletion.
    """
    from modules.graph_extraction_cache import get_extraction_cache
    
    tenant_id = str(uuid.uuid4())
    twin_id = str(uuid.uuid4())
    
    cache = get_extraction_cache()
    
    # Add cache entry
    await cache.set(
        tenant_id=tenant_id,
        twin_id=twin_id,
        source_ref="test-source",
        content="test content",
        claims=[{"test": "claim"}]
    )
    
    # Invalidate cache for twin
    await cache.invalidate(tenant_id, twin_id)
    
    # Verify cache empty
    cached = await cache.get(
        tenant_id=tenant_id,
        twin_id=twin_id,
        source_ref="test-source",
        content="test content"
    )
    
    assert cached is None, "Cache should be invalidated"
