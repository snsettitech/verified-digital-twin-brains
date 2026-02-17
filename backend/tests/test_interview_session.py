# backend/tests/test_interview_session.py
"""Integration tests for interview session endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException


# Mock user for authentication
MOCK_USER = {
    "user_id": "test-user-123",
    "tenant_id": "test-tenant-456",
    "email": "test@example.com"
}


class TestInterviewSessionCreation:
    """Test interview session creation endpoint."""
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication dependency."""
        with patch("routers.interview.get_current_user", return_value=MOCK_USER):
            yield
    
    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client."""
        with patch("routers.interview.supabase") as mock:
            mock.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[{"id": "twin-123"}])
            mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
            yield mock
    
    def test_create_session_request_model(self):
        """Test CreateSessionRequest model."""
        from routers.interview import CreateSessionRequest
        
        req = CreateSessionRequest()
        assert req.twin_id is None
        
        req_with_twin = CreateSessionRequest(twin_id="my-twin-id")
        assert req_with_twin.twin_id == "my-twin-id"
    
    def test_create_session_response_model(self):
        """Test CreateSessionResponse model structure."""
        from routers.interview import CreateSessionResponse
        
        response = CreateSessionResponse(
            session_id="session-123",
            context_bundle="Prior context here",
            system_prompt="You are an interviewer...",
            metadata={"twin_id": "twin-123"}
        )
        
        assert response.session_id == "session-123"
        assert "Prior context" in response.context_bundle
        assert "interviewer" in response.system_prompt


class TestInterviewSessionFinalization:
    """Test interview session finalization endpoint."""
    
    def test_finalize_request_model(self):
        """Test FinalizeSessionRequest model."""
        from routers.interview import FinalizeSessionRequest, TranscriptTurn
        
        req = FinalizeSessionRequest(
            transcript=[
                TranscriptTurn(role="user", content="I want a VC brain"),
                TranscriptTurn(role="assistant", content="Tell me more")
            ],
            duration_seconds=120
        )
        
        assert len(req.transcript) == 2
        assert req.duration_seconds == 120
    
    def test_extracted_memory_model(self):
        """Test ExtractedMemory response model."""
        from routers.interview import ExtractedMemory
        
        memory = ExtractedMemory(
            type="goal",
            value="Build a VC brain",
            evidence="I want to create...",
            confidence=0.85,
            timestamp="2024-01-15T12:00:00Z",
            session_id="session-123"
        )
        
        assert memory.type == "goal"
        assert memory.source == "interview_mode"


class TestRealtimeSessionEndpoint:
    """Test ephemeral Realtime session endpoint."""
    
    def test_realtime_request_model(self):
        """Test RealtimeSessionRequest model defaults."""
        from routers.interview import RealtimeSessionRequest
        
        req = RealtimeSessionRequest()
        
        assert req.model == "gpt-4o-realtime-preview-2024-12-17"
        assert req.voice == "alloy"
        assert req.system_prompt is None
    
    def test_realtime_response_model(self):
        """Test RealtimeSessionResponse model."""
        from routers.interview import RealtimeSessionResponse
        
        response = RealtimeSessionResponse(
            client_secret="ephemeral-key-abc123",
            session_id="rt-session-456",
            expires_at="2024-01-15T12:05:00Z"
        )
        
        assert response.client_secret == "ephemeral-key-abc123"
        assert response.session_id == "rt-session-456"


class TestContextRetrieval:
    """Test context bundle retrieval endpoint."""
    
    def test_context_response_model(self):
        """Test ContextBundleResponse model."""
        from routers.interview import ContextBundleResponse
        
        response = ContextBundleResponse(
            context_bundle="**Goals:**\n- Build VC brain",
            memory_count=5,
            priority_order=["boundary", "constraint", "goal", "preference", "intent"]
        )
        
        assert response.memory_count == 5
        assert response.priority_order[0] == "boundary"


class TestSystemPromptGeneration:
    """Test system prompt generation."""
    
    def test_build_system_prompt_empty_context(self):
        """System prompt with empty context should still be valid."""
        from routers.interview import _build_system_prompt
        
        prompt = _build_system_prompt("")
        
        assert "interview" in prompt.lower()
        assert "intent" in prompt.lower()
        assert "goals" in prompt.lower()
        # Should not include context section
        assert "WHAT YOU ALREADY KNOW" not in prompt
    
    def test_build_system_prompt_with_context(self):
        """System prompt with context should include context section."""
        from routers.interview import _build_system_prompt
        
        context = "User is interested in B2B SaaS investments"
        prompt = _build_system_prompt(context)
        
        assert "WHAT YOU ALREADY KNOW" in prompt
        assert "B2B SaaS" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


class _Resp:
    def __init__(self, data):
        self.data = data


class _CreateSessionTwinsQuery:
    def __init__(self, parent):
        self.parent = parent
        self.filters = {}
        self._single = False
        self._limit = None

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value):
        self._limit = value
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        if self._single:
            if self.parent.explicit_twin_exists:
                return _Resp({"id": self.filters.get("id", "explicit-twin")})
            return _Resp(None)
        rows = self.parent.fallback_twins
        if self._limit is not None:
            rows = rows[:self._limit]
        return _Resp(rows)


class _CreateSessionTwinsTable:
    def __init__(self, parent):
        self.parent = parent

    def select(self, *_args, **_kwargs):
        return _CreateSessionTwinsQuery(self.parent)


class _CreateSessionInsertQuery:
    def __init__(self, parent, payload):
        self.parent = parent
        self.payload = payload

    def execute(self):
        self.parent.inserted = self.payload
        return _Resp([self.payload])


class _CreateSessionInterviewTable:
    def __init__(self, parent):
        self.parent = parent

    def insert(self, payload):
        return _CreateSessionInsertQuery(self.parent, payload)


class _CreateSessionSupabase:
    def __init__(self, fallback_twins, explicit_twin_exists=True):
        self.fallback_twins = fallback_twins
        self.explicit_twin_exists = explicit_twin_exists
        self.inserted = None

    def table(self, name):
        if name == "twins":
            return _CreateSessionTwinsTable(self)
        if name == "interview_sessions":
            return _CreateSessionInterviewTable(self)
        raise AssertionError(f"Unexpected table: {name}")


class _FinalizeSessionQuery:
    def __init__(self, row):
        self.row = row

    def eq(self, *_args, **_kwargs):
        return self

    def single(self):
        return self

    def execute(self):
        return _Resp(self.row)


class _FinalizeSessionTable:
    def __init__(self, row):
        self.row = row

    def select(self, *_args, **_kwargs):
        return _FinalizeSessionQuery(self.row)

    def update(self, _payload):
        return _FinalizeSessionQuery(self.row)


class _FinalizeSupabase:
    def __init__(self, row):
        self.row = row

    def table(self, name):
        if name == "interview_sessions":
            return _FinalizeSessionTable(self.row)
        raise AssertionError(f"Unexpected table: {name}")


@pytest.mark.asyncio
async def test_create_session_requires_explicit_twin_when_multiple_twins(monkeypatch):
    from routers import interview

    mock_supabase = _CreateSessionSupabase(
        fallback_twins=[{"id": "twin-a"}, {"id": "twin-b"}],
        explicit_twin_exists=True,
    )
    monkeypatch.setattr(interview, "supabase", mock_supabase)
    monkeypatch.setattr(interview, "_get_user_context", AsyncMock(return_value=""))

    with pytest.raises(HTTPException) as exc:
        await interview.create_interview_session(
            interview.CreateSessionRequest(),
            user=MOCK_USER
        )
    assert exc.value.status_code == 422
    assert "Multiple twins found" in exc.value.detail


@pytest.mark.asyncio
async def test_create_session_uses_explicit_twin(monkeypatch):
    from routers import interview

    mock_supabase = _CreateSessionSupabase(
        fallback_twins=[{"id": "twin-a"}, {"id": "twin-b"}],
        explicit_twin_exists=True,
    )
    monkeypatch.setattr(interview, "supabase", mock_supabase)
    monkeypatch.setattr(interview, "_get_user_context", AsyncMock(return_value=""))

    response = await interview.create_interview_session(
        interview.CreateSessionRequest(twin_id="twin-b"),
        user=MOCK_USER
    )

    assert response.metadata["twin_id"] == "twin-b"
    assert mock_supabase.inserted["twin_id"] == "twin-b"


@pytest.mark.asyncio
async def test_finalize_rejects_other_users_session(monkeypatch):
    from routers import interview

    monkeypatch.setattr(
        interview,
        "supabase",
        _FinalizeSupabase(
            {
                "id": "session-1",
                "twin_id": "twin-1",
                "user_id": "another-user",
                "status": "active",
            }
        ),
    )

    req = interview.FinalizeSessionRequest(
        transcript=[interview.TranscriptTurn(role="user", content="hello", timestamp="2026-02-08T00:00:00Z")],
        duration_seconds=5,
    )

    with pytest.raises(HTTPException) as exc:
        await interview.finalize_interview_session(
            "session-1",
            req,
            user=MOCK_USER
        )

    assert exc.value.status_code == 403
    assert "Not authorized" in exc.value.detail


@pytest.mark.asyncio
async def test_get_user_context_falls_back_to_owner_memories(monkeypatch):
    from routers import interview
    import modules.zep_memory as zep_memory

    class _NoContextZep:
        async def get_user_context(self, *_args, **_kwargs):
            return ""

    def _list_owner_memories(_twin_id, status="active", limit=200):
        if status == "active":
            return [
                {
                    "memory_type": "belief",
                    "topic_normalized": "mission",
                    "value": "Build reliable digital twins.",
                    "confidence": 1.0,
                }
            ]
        if status == "proposed":
            return [
                {
                    "memory_type": "preference",
                    "topic_normalized": "communication style",
                    "value": "Prefer concise summaries.",
                    "confidence": 0.7,
                }
            ]
        return []

    monkeypatch.setattr(zep_memory, "get_zep_client", lambda: _NoContextZep())
    monkeypatch.setattr(interview, "list_owner_memories", _list_owner_memories)
    monkeypatch.setattr(interview, "AUTO_APPROVE_OWNER_MEMORY", False)

    context = await interview._get_user_context("user-1", "interview", twin_id="twin-1")
    assert "Approved owner memories" in context
    assert "Pending owner memory proposals" in context
    assert "Build reliable digital twins." in context
