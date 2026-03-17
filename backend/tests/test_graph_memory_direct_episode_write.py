import pytest

from modules.graph_circuit_breaker import reset_all_breakers
from modules.graph_extraction_cache import reset_cache
from modules.graph_memory_config import reset_config
from modules.graph_memory_core import GraphMemoryCore
from modules.graph_outbox import reset_outbox


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    monkeypatch.setenv("GRAPH_MEMORY_ENABLED", "true")
    monkeypatch.setenv("GRAPH_MEMORY_READ_ENABLED", "true")
    monkeypatch.setenv("GRAPH_MEMORY_WRITE_ENABLED", "true")
    reset_config()
    reset_all_breakers()
    reset_outbox()
    reset_cache()
    yield
    reset_config()
    reset_all_breakers()
    reset_outbox()
    reset_cache()


class _FakeRecord:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


class _FakeResult:
    def __init__(self, records):
        self._records = [_FakeRecord(record) for record in records]

    async def single(self):
        return self._records[0] if self._records else None

    def __aiter__(self):
        self._iter = iter(self._records)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeSession:
    def __init__(self, recorder, records):
        self._recorder = recorder
        self._records = records

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, cypher, **params):
        self._recorder.append((cypher, params))
        return _FakeResult(self._records)


class _FakeDriver:
    def __init__(self, recorder, records):
        self._recorder = recorder
        self._records = records

    def session(self, **kwargs):
        self._recorder.append(("session", kwargs))
        return _FakeSession(self._recorder, self._records)


@pytest.mark.asyncio
async def test_sync_create_episode_uses_direct_neo4j_write(monkeypatch):
    recorder = []
    fake_driver = _FakeDriver(recorder, [{"episode_id": "episode-123"}])

    monkeypatch.setattr("modules.graph_memory_core._NEO4J_AVAILABLE", True)
    monkeypatch.setattr("modules.graph_memory_core._get_pooled_driver", lambda *args, **kwargs: fake_driver)

    def _fail_graphiti(self):
        raise AssertionError("Graphiti fallback should not be used when direct write succeeds")

    monkeypatch.setattr(GraphMemoryCore, "_get_graphiti", _fail_graphiti)

    client = GraphMemoryCore("tenant-a", "twin-a", "corr-a")
    episode_id = await client.create_episode(
        name="Direct Write",
        body="Direct episode content",
        source_type="test",
        source_ref="ref-1",
        async_write=False,
    )

    assert episode_id == "episode-123"
    write_calls = [entry for entry in recorder if isinstance(entry[0], str) and "MERGE (e:Episode" in entry[0]]
    assert write_calls, "Expected a direct Episode MERGE query"
    _, params = write_calls[0]
    assert params["group_id"] == "tenant-a__twin-a"
    assert params["source_ref"] == "ref-1"
    assert params["body"] == "Direct episode content"


@pytest.mark.asyncio
async def test_search_recent_wildcard_returns_episode_rows(monkeypatch):
    recorder = []
    fake_driver = _FakeDriver(
        recorder,
        [
            {"content": "Episode alpha", "name": "Alpha"},
            {"content": "Episode beta", "name": "Beta"},
        ],
    )

    monkeypatch.setattr("modules.graph_memory_core._NEO4J_AVAILABLE", True)
    monkeypatch.setattr("modules.graph_memory_core._get_pooled_driver", lambda *args, **kwargs: fake_driver)

    client = GraphMemoryCore("tenant-b", "twin-b", "corr-b")
    results = await client.search("*", num_results=5)

    assert results == [
        {"content": "Episode alpha", "name": "Alpha"},
        {"content": "Episode beta", "name": "Beta"},
    ]
    search_calls = [entry for entry in recorder if isinstance(entry[0], str) and "MATCH (e:Episode)" in entry[0]]
    assert search_calls, "Expected an episode search query"
    _, params = search_calls[0]
    assert params["gid"] == "tenant-b__twin-b"
    assert params["lim"] == 5
