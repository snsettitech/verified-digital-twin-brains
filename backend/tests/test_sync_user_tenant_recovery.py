import pytest
from fastapi import Response


class _Query:
    def __init__(self, table_name, state):
        self._table_name = table_name
        self._state = state
        self._filters = {}

    def select(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def eq(self, field, value):  # noqa: ANN001
        self._filters[field] = value
        return self

    def order(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def limit(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def upsert(self, payload):  # noqa: ANN001
        self._state["upsert_calls"].append((self._table_name, payload))
        return self

    def execute(self):
        if self._table_name == "users":
            user_id = self._filters.get("id")
            if user_id is not None:
                row = self._state["users_by_id"].get(user_id)
                return type("Resp", (), {"data": [row] if row else []})()
            return type("Resp", (), {"data": []})()

        if self._table_name == "twins":
            tenant_id = self._filters.get("tenant_id")
            twins = self._state["twins_by_tenant"].get(tenant_id, [])
            return type("Resp", (), {"data": twins})()

        return type("Resp", (), {"data": []})()


class _Supabase:
    def __init__(self, state):
        self._state = state

    def table(self, name):  # noqa: ANN001
        return _Query(name, self._state)


class _Request:
    def __init__(self):
        self.headers = {}


@pytest.mark.asyncio
async def test_sync_user_reuses_recovered_tenant_instead_of_new_creation(monkeypatch):
    from routers import auth as auth_router

    state = {
        "users_by_id": {},
        "twins_by_tenant": {"tenant-existing": [{"id": "twin-1"}]},
        "upsert_calls": [],
    }
    monkeypatch.setattr(auth_router, "supabase", _Supabase(state))
    monkeypatch.setattr(auth_router, "resolve_tenant_id", lambda *_args, **_kwargs: "tenant-existing")

    user = {
        "user_id": "new-user-id",
        "email": "owner@example.com",
        "user_metadata": {"full_name": "Owner"},
    }

    result = await auth_router.sync_user(_Request(), Response(), user=user)

    assert result.user.tenant_id == "tenant-existing"
    assert result.needs_onboarding is False
    assert ("users", {"id": "new-user-id", "email": "owner@example.com", "tenant_id": "tenant-existing"}) in state["upsert_calls"]
