import pytest

from modules.twin_service import create_twin_for_name_research


class _Result:
    def __init__(self, data=None):
        self.data = data or []


class _FakeTwinsTable:
    def __init__(self, missing_column: str):
        self._missing_column = missing_column
        self._mode = None
        self._insert_attempts = 0
        self.insert_payloads = []

    def select(self, *_args, **_kwargs):
        self._mode = "select"
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self._mode = "insert"
        self.insert_payloads.append(dict(payload))
        return self

    def execute(self):
        if self._mode == "select":
            return _Result(data=[])

        if self._mode == "insert":
            self._insert_attempts += 1
            if self._insert_attempts == 1:
                raise Exception(
                    {
                        "message": (
                            f"Could not find the '{self._missing_column}' column "
                            "of 'twins' in the schema cache"
                        ),
                        "code": "PGRST204",
                    }
                )
            return _Result(data=[{"id": "twin_123"}])

        return _Result(data=[])


class _FakeDB:
    def __init__(self, missing_column: str):
        self.twins = _FakeTwinsTable(missing_column=missing_column)

    def table(self, name: str):
        if name != "twins":
            raise AssertionError(f"Unexpected table: {name}")
        return self.twins


class _CreationModeConstraintTwinsTable:
    def __init__(self):
        self._mode = None
        self._insert_attempts = 0
        self.insert_payloads = []

    def select(self, *_args, **_kwargs):
        self._mode = "select"
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self._mode = "insert"
        self.insert_payloads.append(dict(payload))
        return self

    def execute(self):
        if self._mode == "select":
            return _Result(data=[])
        if self._mode == "insert":
            self._insert_attempts += 1
            if self._insert_attempts == 1:
                raise Exception(
                    {
                        "message": 'new row for relation "twins" violates check constraint "twins_creation_mode_check"',
                        "code": "23514",
                    }
                )
            return _Result(data=[{"id": "twin_456"}])
        return _Result(data=[])


class _CreationModeConstraintDB:
    def __init__(self):
        self.twins = _CreationModeConstraintTwinsTable()

    def table(self, name: str):
        if name != "twins":
            raise AssertionError(f"Unexpected table: {name}")
        return self.twins


@pytest.mark.parametrize("missing_column", ["is_active", "status", "creation_mode"])
@pytest.mark.asyncio
async def test_create_twin_for_name_research_retries_without_missing_legacy_columns(
    monkeypatch, missing_column: str
):
    async def _fake_create_group(**_kwargs):
        return {"id": "group_1"}

    monkeypatch.setattr("modules.access_groups.create_group", _fake_create_group)

    fake_db = _FakeDB(missing_column=missing_column)

    twin_id = await create_twin_for_name_research(
        db=fake_db,
        tenant_id="tenant_1",
        user_id="user_1",
        name="Test Person",
        hints={"location": None, "company": None, "website": None},
    )

    assert twin_id == "twin_123"
    assert len(fake_db.twins.insert_payloads) >= 2
    first_payload = fake_db.twins.insert_payloads[0]
    retried_payload = fake_db.twins.insert_payloads[-1]
    assert missing_column in first_payload
    assert missing_column not in retried_payload


@pytest.mark.asyncio
async def test_create_twin_for_name_research_falls_back_when_creation_mode_check_rejects_name_first(
    monkeypatch,
):
    async def _fake_create_group(**_kwargs):
        return {"id": "group_1"}

    monkeypatch.setattr("modules.access_groups.create_group", _fake_create_group)

    fake_db = _CreationModeConstraintDB()

    twin_id = await create_twin_for_name_research(
        db=fake_db,
        tenant_id="tenant_1",
        user_id="user_1",
        name="Test Person",
        hints={"location": None, "company": None, "website": None},
    )

    assert twin_id == "twin_456"
    assert len(fake_db.twins.insert_payloads) == 2
    assert fake_db.twins.insert_payloads[0]["creation_mode"] == "name_first"
    assert fake_db.twins.insert_payloads[1]["creation_mode"] == "link_first"
