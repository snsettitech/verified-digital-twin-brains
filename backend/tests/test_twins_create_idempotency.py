import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock


class _TwinsSelectQuery:
    def __init__(self, table):
        self._table = table

    def select(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def eq(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def order(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def limit(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def execute(self):
        idx = self._table.select_calls
        self._table.select_calls += 1
        if idx < len(self._table.select_responses):
            data = self._table.select_responses[idx]
        else:
            data = []
        return SimpleNamespace(data=data)


class _TwinsInsertQuery:
    def __init__(self, table, payload):
        self._table = table
        self._payload = payload

    def execute(self):
        self._table.insert_calls += 1
        self._table.insert_payloads.append(self._payload)
        if self._table.insert_error is not None:
            raise self._table.insert_error

        twin = {
            "id": "twin-new",
            **self._payload,
        }
        return SimpleNamespace(data=[twin])


class _TwinsTable:
    def __init__(self, select_responses=None, insert_error=None):
        self.select_responses = select_responses or []
        self.insert_error = insert_error
        self.select_calls = 0
        self.insert_calls = 0
        self.insert_payloads = []

    def select(self, *_args, **_kwargs):  # noqa: ANN001
        return _TwinsSelectQuery(self)

    def insert(self, payload):  # noqa: ANN001
        return _TwinsInsertQuery(self, payload)


class _Supabase:
    def __init__(self, twins_table):
        self._twins_table = twins_table

    def table(self, name):  # noqa: ANN001
        if name != "twins":
            raise AssertionError(f"Unexpected table: {name}")
        return self._twins_table


@pytest.mark.asyncio
async def test_create_twin_reuses_existing_active_twin(monkeypatch):
    from routers import twins as twins_router

    existing = {
        "id": "twin-existing",
        "name": "Sai Twin",
        "tenant_id": "tenant-1",
        "settings": {},
    }
    twins_table = _TwinsTable(select_responses=[[existing]])

    monkeypatch.setattr(twins_router, "supabase", _Supabase(twins_table))
    monkeypatch.setattr(twins_router, "resolve_tenant_id", lambda *_args, **_kwargs: "tenant-1")
    monkeypatch.setattr(twins_router, "create_group", AsyncMock())

    req = twins_router.TwinCreateRequest(name="Sai Twin")
    result = await twins_router.create_twin(
        request=req,
        user={"user_id": "user-1", "email": "user@example.com"},
    )

    assert result["id"] == "twin-existing"
    assert twins_table.insert_calls == 0


@pytest.mark.asyncio
async def test_create_twin_returns_existing_when_insert_hits_duplicate_race(monkeypatch):
    from routers import twins as twins_router

    existing = {
        "id": "twin-existing-after-race",
        "name": "Sai Twin",
        "tenant_id": "tenant-1",
        "settings": {},
    }
    twins_table = _TwinsTable(
        select_responses=[[], [existing]],
        insert_error=RuntimeError("duplicate key value violates unique constraint"),
    )

    monkeypatch.setattr(twins_router, "supabase", _Supabase(twins_table))
    monkeypatch.setattr(twins_router, "resolve_tenant_id", lambda *_args, **_kwargs: "tenant-1")
    monkeypatch.setattr(twins_router, "create_group", AsyncMock())

    req = twins_router.TwinCreateRequest(name="Sai Twin")
    result = await twins_router.create_twin(
        request=req,
        user={"user_id": "user-1", "email": "user@example.com"},
    )

    assert result["id"] == "twin-existing-after-race"
    assert twins_table.insert_calls == 1

