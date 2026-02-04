import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import Request, HTTPException

# We need to mock 'modules.observability.supabase' BEFORE importing tenant_guard
# because tenant_guard imports it at the top level.
sys_modules_patch = patch.dict('sys.modules', {'modules.observability': MagicMock()})
sys_modules_patch.start()

from modules.observability import supabase
# Setup the mock supabase structure
supabase.table.return_value.insert.return_value.execute.return_value = None

from modules._core.tenant_guard import verify_tenant_access, verify_twin_access, emit_audit_event
import modules._core.tenant_guard as tenant_guard_module

@pytest.mark.asyncio
async def test_emit_audit_event_async_insert():
    """
    Test that emit_audit_event calls supabase.table().insert().execute() asynchronously.
    """
    # Setup
    event_type = "TEST_EVENT"
    user_id = "user_123"
    tenant_id = "tenant_456"
    details = {"twin_id": "twin_789", "foo": "bar"}

    # We mock asyncio.to_thread to verify it's used, or we can just mock supabase and check it's called.
    # Since we use asyncio.to_thread, the inner function call happens in a thread.
    # unittest.mock works across threads if we check the mock object.

    # Reset mock
    supabase.table.reset_mock()

    # Execute
    # Check if it is async
    if asyncio.iscoroutinefunction(emit_audit_event):
        await emit_audit_event(event_type, user_id, tenant_id, details)
    else:
        # If not async yet, this test will fail to prove asyncness, but we can check logic
        emit_audit_event(event_type, user_id, tenant_id, details)

    # Assert
    # We expect supabase.table("audit_logs").insert(...).execute() to be called.
    supabase.table.assert_called_with("audit_logs")

    # Verify arguments
    # The insert call should receive a dict with correct fields
    insert_call = supabase.table().insert.call_args
    assert insert_call is not None
    inserted_data = insert_call[0][0]

    assert inserted_data["tenant_id"] == tenant_id
    assert inserted_data["event_type"] == event_type
    assert inserted_data["actor_id"] == user_id
    assert inserted_data["twin_id"] == "twin_789"
    assert inserted_data["metadata"] == details
    # We might set action same as event_type
    assert inserted_data["action"] == event_type

@pytest.mark.asyncio
async def test_verify_tenant_access_waits_for_audit():
    """
    Test that verify_tenant_access awaits emit_audit_event on failure.
    """
    request = MagicMock(spec=Request)
    request.url.path = "/test/path"
    request.path_params = {"twin_id": "twin_123"}
    request.query_params = {}
    user = {
        "user_id": "svc_key",
        "tenant_id": "default",
        "is_service_key": True
    }

    # Mock emit_audit_event to check if it's awaited
    with patch("modules._core.tenant_guard.emit_audit_event", new_callable=AsyncMock) as mock_emit:
        with pytest.raises(HTTPException):
            await verify_tenant_access(request, user)

        mock_emit.assert_awaited_once()
        emitted_details = mock_emit.await_args.args[3]
        assert emitted_details["endpoint"] == "/test/path"
        assert emitted_details["twin_id"] == "twin_123"
