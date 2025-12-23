# backend/tests/test_tenant_guard.py
"""Unit tests for tenant isolation enforcement in tenant_guard.py.

Tests cover:
1. Tenant isolation violation (user tries to access another tenant's data).
2. Twin ownership violation (twin_id belongs to a different tenant).
3. Service-key bypass prevention (is_service_key=True is blocked).
4. Missing tenant_id in request.
5. Access group denial (user lacks required group).
6. Success case (all checks pass, audit event emitted).
"""
import pytest
from unittest.mock import patch, MagicMock
from modules._core import tenant_guard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user_default():
    """A standard user belonging to default_tenant."""
    return {
        "user_id": "user_1",
        "tenant_id": "default_tenant",
        "access_groups": ["user"],
        "is_service_key": False,
    }


@pytest.fixture
def mock_user_other_tenant():
    """A user belonging to a different tenant."""
    return {
        "user_id": "user_2",
        "tenant_id": "other_tenant",
        "access_groups": ["user"],
        "is_service_key": False,
    }


@pytest.fixture
def mock_service_key_user():
    """A service-key context (should be blocked)."""
    return {
        "user_id": "svc_key",
        "tenant_id": "default_tenant",
        "access_groups": ["admin"],
        "is_service_key": True,
    }


# ---------------------------------------------------------------------------
# Test: Tenant isolation violation
# ---------------------------------------------------------------------------

def test_tenant_isolation_violation(mock_user_other_tenant):
    with patch.object(tenant_guard, "get_current_user", return_value=mock_user_other_tenant):
        @tenant_guard.require_tenant
        def dummy_action(tenant_id: str):
            return "ok"

        with pytest.raises(PermissionError, match="Tenant isolation violation"):
            dummy_action(tenant_id="default_tenant")


# ---------------------------------------------------------------------------
# Test: Twin ownership violation
# ---------------------------------------------------------------------------

def test_twin_ownership_violation(mock_user_default):
    def fake_get_twin_tenant(twin_id: str):
        # This twin belongs to 'other_tenant', not 'default_tenant'
        return "other_tenant"

    with patch.object(tenant_guard, "get_current_user", return_value=mock_user_default):
        with patch.object(tenant_guard, "get_twin_tenant", side_effect=fake_get_twin_tenant):
            @tenant_guard.require_tenant
            def dummy_action(tenant_id: str, twin_id: str):
                return "ok"

            with pytest.raises(PermissionError, match="Twin does not belong to the requested tenant"):
                dummy_action(tenant_id="default_tenant", twin_id="twin_123")


# ---------------------------------------------------------------------------
# Test: Service-key bypass blocked
# ---------------------------------------------------------------------------

def test_service_key_bypass_blocked(mock_service_key_user):
    with patch.object(tenant_guard, "get_current_user", return_value=mock_service_key_user):
        @tenant_guard.require_tenant
        def dummy_action(tenant_id: str):
            return "ok"

        with pytest.raises(PermissionError, match="Service-key bypass is not allowed"):
            dummy_action(tenant_id="default_tenant")


# ---------------------------------------------------------------------------
# Test: Missing tenant_id
# ---------------------------------------------------------------------------

def test_missing_tenant_id(mock_user_default):
    with patch.object(tenant_guard, "get_current_user", return_value=mock_user_default):
        @tenant_guard.require_tenant
        def dummy_action():
            return "ok"

        with pytest.raises(PermissionError, match="Tenant ID missing from request"):
            dummy_action()


# ---------------------------------------------------------------------------
# Test: Access group denied
# ---------------------------------------------------------------------------

def test_access_group_denied(mock_user_default):
    with patch.object(tenant_guard, "get_current_user", return_value=mock_user_default):
        def dummy_action(tenant_id: str):
            return "ok"

        dummy_action.required_group = "admin"  # user only has 'user' group
        wrapped = tenant_guard.require_tenant(dummy_action)

        with pytest.raises(PermissionError, match="User lacks required group: admin"):
            wrapped(tenant_id="default_tenant")


# ---------------------------------------------------------------------------
# Test: Success case
# ---------------------------------------------------------------------------

def test_success_case(mock_user_default):
    with patch.object(tenant_guard, "get_current_user", return_value=mock_user_default):
        with patch.object(tenant_guard, "get_twin_tenant", return_value="default_tenant"):
            with patch.object(tenant_guard, "emit_audit_event") as mock_audit:
                @tenant_guard.require_tenant
                def dummy_action(tenant_id: str, twin_id: str):
                    return "ok"

                result = dummy_action(tenant_id="default_tenant", twin_id="twin_1")
                assert result == "ok"
                # Verify audit event was emitted for success
                mock_audit.assert_called()
                call_args = mock_audit.call_args_list[-1]
                assert call_args[0][0] == "GUARDED_ACTION_SUCCESS"
