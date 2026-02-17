from types import SimpleNamespace


def test_list_owner_memories_includes_verified_for_active(monkeypatch):
    from modules import owner_memory_store as oms

    class FakeQuery:
        def __init__(self):
            self.filters = []
        def select(self, *args, **kwargs):
            return self
        def eq(self, field, value):
            self.filters.append(("eq", field, value))
            return self
        def in_(self, field, values):
            self.filters.append(("in", field, tuple(values)))
            return self
        def order(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self
        def execute(self):
            return SimpleNamespace(data=[])

    class FakeSupabase:
        def __init__(self):
            self.last_query = None
        def table(self, name):
            self.last_query = FakeQuery()
            return self.last_query

    fake = FakeSupabase()
    monkeypatch.setattr(oms, "supabase", fake)
    monkeypatch.setattr(oms, "AUTO_APPROVE_OWNER_MEMORY", False)

    oms.list_owner_memories("twin-123", status="active")

    assert ("in", "status", ("active", "verified")) in fake.last_query.filters


def test_list_owner_memories_includes_proposed_when_auto_approve(monkeypatch):
    from modules import owner_memory_store as oms

    class FakeQuery:
        def __init__(self):
            self.filters = []
        def select(self, *args, **kwargs):
            return self
        def eq(self, field, value):
            self.filters.append(("eq", field, value))
            return self
        def in_(self, field, values):
            self.filters.append(("in", field, tuple(values)))
            return self
        def order(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self
        def execute(self):
            return SimpleNamespace(data=[])

    class FakeSupabase:
        def __init__(self):
            self.last_query = None
        def table(self, name):
            self.last_query = FakeQuery()
            return self.last_query

    fake = FakeSupabase()
    monkeypatch.setattr(oms, "supabase", fake)
    monkeypatch.setattr(oms, "AUTO_APPROVE_OWNER_MEMORY", True)

    oms.list_owner_memories("twin-123", status="active")

    assert ("in", "status", ("active", "verified", "proposed")) in fake.last_query.filters


def test_create_owner_memory_respects_provenance_source_type(monkeypatch):
    from modules import owner_memory_store as oms

    inserted = {}

    class FakeInsert:
        def __init__(self, data):
            self._data = data
        def execute(self):
            return SimpleNamespace(data=[self._data])

    class FakeTable:
        def insert(self, data):
            inserted.update(data)
            return FakeInsert(data)

    class FakeSupabase:
        def table(self, name):
            return FakeTable()

    monkeypatch.setattr(oms, "supabase", FakeSupabase())
    monkeypatch.setattr(oms, "get_embedding", lambda text: None)

    result = oms.create_owner_memory(
        twin_id="twin-123",
        tenant_id="tenant-123",
        topic_normalized="pricing",
        memory_type="stance",
        value="I prefer value-based pricing.",
        confidence=1.0,
        provenance={
            "source_type": "owner_clarification",
            "source_id": "clarif-1",
            "owner_id": "user-1"
        }
    )

    assert result is not None
    assert inserted["provenance"]["source_type"] == "owner_clarification"
    assert inserted["provenance"]["source_id"] == "clarif-1"


def test_list_owner_memory_history_filters_by_topic_and_type(monkeypatch):
    from modules import owner_memory_store as oms

    class FakeQuery:
        def __init__(self):
            self.filters = []
        def select(self, *args, **kwargs):
            return self
        def eq(self, field, value):
            self.filters.append(("eq", field, value))
            return self
        def order(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self
        def execute(self):
            return SimpleNamespace(data=[])

    class FakeSupabase:
        def __init__(self):
            self.last_query = None
        def table(self, name):
            self.last_query = FakeQuery()
            return self.last_query

    fake = FakeSupabase()
    monkeypatch.setattr(oms, "supabase", fake)

    oms.list_owner_memory_history("twin-123", topic_normalized="pricing", memory_type="belief")

    assert ("eq", "twin_id", "twin-123") in fake.last_query.filters
    assert ("eq", "topic_normalized", "pricing") in fake.last_query.filters
    assert ("eq", "memory_type", "belief") in fake.last_query.filters


def test_approve_owner_memory_promotes_proposed(monkeypatch):
    from modules import owner_memory_store as oms

    existing = {
        "id": "mem-1",
        "status": "proposed",
        "provenance": {"source_type": "interview", "source_id": "sess-1"},
    }
    updated_payload = {}

    class FakeExecute:
        def __init__(self, data):
            self.data = data

    class FakeUpdateQuery:
        def __init__(self, data):
            self._data = data
        def eq(self, field, value):
            assert field == "id"
            assert value == "mem-1"
            return self
        def execute(self):
            return FakeExecute([{"id": "mem-1", **self._data}])

    class FakeTable:
        def update(self, data):
            updated_payload.update(data)
            return FakeUpdateQuery(data)

    class FakeSupabase:
        def table(self, name):
            assert name == "owner_beliefs"
            return FakeTable()

    monkeypatch.setattr(oms, "get_owner_memory", lambda mem_id: existing if mem_id == "mem-1" else None)
    monkeypatch.setattr(oms, "supabase", FakeSupabase())

    result = oms.approve_owner_memory("mem-1", approver_id="user-1", expected_status="proposed")

    assert result is not None
    assert updated_payload["status"] == "verified"
    assert updated_payload["provenance"]["approved_by"] == "user-1"
    assert "approved_at" in updated_payload["provenance"]


def test_approve_owner_memory_is_idempotent_for_verified(monkeypatch):
    from modules import owner_memory_store as oms

    existing = {"id": "mem-1", "status": "verified"}
    monkeypatch.setattr(oms, "get_owner_memory", lambda mem_id: existing if mem_id == "mem-1" else None)

    result = oms.approve_owner_memory("mem-1", approver_id="user-1", expected_status="proposed")

    assert result == existing


def test_create_owner_memory_auto_approves_requested_proposed(monkeypatch):
    from modules import owner_memory_store as oms

    inserted = {}

    class FakeInsert:
        def __init__(self, data):
            self._data = data
        def execute(self):
            return SimpleNamespace(data=[self._data])

    class FakeTable:
        def insert(self, data):
            inserted.update(data)
            return FakeInsert(data)

    class FakeSupabase:
        def table(self, name):
            return FakeTable()

    monkeypatch.setattr(oms, "supabase", FakeSupabase())
    monkeypatch.setattr(oms, "get_embedding", lambda text: None)
    monkeypatch.setattr(oms, "AUTO_APPROVE_OWNER_MEMORY", True)

    result = oms.create_owner_memory(
        twin_id="twin-123",
        tenant_id="tenant-123",
        topic_normalized="pricing",
        memory_type="belief",
        value="Pricing should stay transparent.",
        confidence=0.9,
        provenance={"source_type": "interview", "source_id": "session-1"},
        status="proposed",
    )

    assert result is not None
    assert inserted["status"] == "verified"
    assert inserted["provenance"]["auto_approved"] is True
