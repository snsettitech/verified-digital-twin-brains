import pytest


class _SelectQuery:
    def __init__(self, data):
        self._data = data

    def eq(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def single(self):
        return self

    def execute(self):
        return type("Resp", (), {"data": self._data})()


class _UpdateQuery:
    def __init__(self, sink, payload):
        self._sink = sink
        self._payload = payload

    def eq(self, *_args, **_kwargs):  # noqa: ANN001
        return self

    def execute(self):
        self._sink["updated"] = self._payload
        return type("Resp", (), {"data": [self._payload]})()


class _Table:
    def __init__(self, name, sink):
        self._name = name
        self._sink = sink

    def select(self, *_args, **_kwargs):  # noqa: ANN001
        if self._name == "interview_sessions":
            return _SelectQuery({"twin_id": "twin-1"})
        return _SelectQuery({})

    def update(self, payload):  # noqa: ANN001
        return _UpdateQuery(self._sink, payload)


class _Supabase:
    def __init__(self, sink):
        self._sink = sink

    def table(self, name):  # noqa: ANN001
        return _Table(name, self._sink)


class _FakeZep:
    async def upsert_memory(self, _user_id, _memory):  # noqa: ANN001
        return {"status": "created"}


@pytest.mark.asyncio
async def test_finalize_reports_proposal_failures(monkeypatch):
    from routers import interview
    import modules.zep_memory as zep_memory

    sink = {}
    monkeypatch.setattr(interview, "AUTO_APPROVE_OWNER_MEMORY", True)
    monkeypatch.setattr(interview, "supabase", _Supabase(sink))
    monkeypatch.setattr(zep_memory, "get_zep_client", lambda: _FakeZep())

    async def _extract(_transcript, session_id):  # noqa: ANN001
        return [
            interview.ExtractedMemory(
                type="goal",
                value="I prioritize founder clarity.",
                evidence="I push for specifics.",
                confidence=0.9,
                timestamp="2026-02-08T00:00:00Z",
                session_id=session_id,
                source="interview_mode",
            ),
            interview.ExtractedMemory(
                type="preference",
                value="I like concise updates.",
                evidence="Keep it short.",
                confidence=0.4,
                timestamp="2026-02-08T00:00:01Z",
                session_id=session_id,
                source="interview_mode",
            ),
        ]

    monkeypatch.setattr(interview, "_extract_memories_from_transcript", _extract)
    monkeypatch.setattr(interview, "create_owner_memory", lambda **_kwargs: None)

    req = interview.FinalizeSessionRequest(
        transcript=[interview.TranscriptTurn(role="user", content="test", timestamp="2026-02-08T00:00:00Z")],
        duration_seconds=12,
        metadata={"from_test": True},
    )
    res = await interview.finalize_interview_session(
        "session-1",
        req,
        user={"user_id": "user-1", "tenant_id": "tenant-1"},
    )

    assert res.proposed_count == 0
    assert res.proposed_failed_count == 1
    assert any("low-confidence" in note for note in res.notes)
    assert any("could not be saved as verified memories" in note for note in res.notes)
    assert sink["updated"]["metadata"]["proposed_failed_count"] == 1
