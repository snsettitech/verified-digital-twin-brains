# backend/tests/test_interview_session.py
"""Integration tests for interview session endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import json


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
