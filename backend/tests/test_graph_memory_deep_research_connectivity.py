import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from modules.graph_outbox_worker import _dispatch
from modules.name_deep_research_service import NameDeepResearchService


class _FakeTwinsQuery:
    def __init__(self, row):
        self._row = row

    def select(self, _value):
        return self

    def eq(self, _field, _value):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=[self._row])


class _FakeDB:
    def __init__(self, row):
        self._row = row

    def table(self, table_name):
        if table_name != "twins":
            raise AssertionError(f"Unexpected table access in test: {table_name}")
        return _FakeTwinsQuery(self._row)


class _FakeOutbox:
    def __init__(self):
        self.calls = []

    def submit(self, **kwargs):
        self.calls.append(kwargs)
        return f"job-{len(self.calls)}"


@pytest.mark.asyncio
async def test_deep_research_enqueue_uses_single_profile_scope(monkeypatch):
    monkeypatch.setenv("GRAPH_MEMORY_ENABLED", "true")
    monkeypatch.setenv("GRAPH_MEMORY_WRITE_ENABLED", "true")

    from modules.graph_memory_config import reset_config

    reset_config()

    fake_db = _FakeDB(
        {
            "tenant_id": "97c6e919-64f8-45f5-8ebf-8455e9b1627e",
            "creator_id": "tenant_97c6e919-64f8-45f5-8ebf-8455e9b1627e",
        }
    )
    service = NameDeepResearchService(db_client=fake_db, firecrawl_client=object(), openai_client=object())
    fake_outbox = _FakeOutbox()

    result_doc = {
        "bio": {"short": "Short bio", "medium": "Medium bio"},
        "claims": [{"text": "Works on AI safety", "status": "verified", "confidence": 0.9}],
    }

    with patch("modules.graph_outbox.get_graph_outbox", return_value=fake_outbox):
        await service._enqueue_graph_memory_jobs(
            run_id="run-123",
            tenant_id="97c6e919-64f8-45f5-8ebf-8455e9b1627e",
            twin_id="f035ab5e-c431-4376-9100-67c49ee078cb",
            result_doc=result_doc,
        )

    assert len(fake_outbox.calls) == 3
    expected_scope = "97c6e919-64f8-45f5-8ebf-8455e9b1627e__tenant_97c6e919-64f8-45f5-8ebf-8455e9b1627e"
    for call in fake_outbox.calls:
        assert call["scope_id"] == expected_scope
        assert call["tenant_id"] == "97c6e919-64f8-45f5-8ebf-8455e9b1627e"
        assert call["twin_id"] == "f035ab5e-c431-4376-9100-67c49ee078cb"


@pytest.mark.asyncio
async def test_graph_outbox_dispatch_create_claims_refreshes_snapshot():
    job = {
        "id": "job-abc",
        "operation": "create_claims",
        "tenant_id": "97c6e919-64f8-45f5-8ebf-8455e9b1627e",
        "twin_id": "f035ab5e-c431-4376-9100-67c49ee078cb",
        "correlation_id": "corr-1",
        "payload": {
            "scope_id": "97c6e919-64f8-45f5-8ebf-8455e9b1627e__tenant_97c6e919-64f8-45f5-8ebf-8455e9b1627e",
            "source_type": "name_deep_research",
            "source_ref": "run-xyz",
            "text": "Sainath builds enterprise AI systems and leads product strategy.",
        },
    }

    with patch("modules.graph_outbox_worker._persist_claims", new=AsyncMock(return_value=2)) as mock_persist:
        with patch("modules.graph_outbox_worker._refresh_snapshot", new=AsyncMock(return_value=True)) as mock_refresh:
            ok = await _dispatch(job)

    assert ok is True
    assert mock_persist.await_count == 1
    assert mock_refresh.await_count == 1

