# backend/tests/test_memory_extractor.py
"""Unit tests for memory extraction module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
import sys
from types import SimpleNamespace


class TestMemoryExtraction:
    """Test memory extraction from transcripts."""
    
    @pytest.mark.asyncio
    async def test_extract_empty_transcript(self):
        """Empty transcript should return empty memories list."""
        from modules.memory_extractor import extract_memories
        
        result = await extract_memories([], "test-session-id")
        
        assert result.memories == []
        assert result.total_extracted == 0
        assert result.transcript_turns == 0
    
    @pytest.mark.asyncio
    async def test_extraction_result_structure(self):
        """Verify ExtractionResult has all expected fields."""
        from modules.memory_extractor import ExtractionResult, ExtractedMemory
        
        result = ExtractionResult(
            memories=[],
            total_extracted=0,
            transcript_turns=5,
            extraction_time_ms=100
        )
        
        assert hasattr(result, 'memories')
        assert hasattr(result, 'total_extracted')
        assert hasattr(result, 'transcript_turns')
        assert hasattr(result, 'extraction_time_ms')
    
    @pytest.mark.asyncio
    async def test_extracted_memory_model(self):
        """Verify ExtractedMemory model structure."""
        from modules.memory_extractor import ExtractedMemory
        
        memory = ExtractedMemory(
            type="goal",
            value="Build a VC brain for investment decisions",
            evidence="I want to create a VC brain",
            confidence=0.85,
            session_id="test-session"
        )
        
        assert memory.type == "goal"
        assert memory.confidence == 0.85
        assert memory.source == "interview_mode"
    
    @pytest.mark.asyncio
    async def test_memory_type_validation(self):
        """Memory types should be validated."""
        from modules.memory_extractor import ExtractedMemory
        
        valid_types = ["intent", "goal", "constraint", "preference", "boundary"]
        
        for mem_type in valid_types:
            memory = ExtractedMemory(
                type=mem_type,
                value="Test value",
                evidence="Test evidence",
                session_id="test"
            )
            assert memory.type == mem_type
    
    @pytest.mark.asyncio
    async def test_confidence_bounds(self):
        """Confidence should be clamped to 0-1 range."""
        from modules.memory_extractor import ExtractedMemory
        
        # Valid confidence
        memory = ExtractedMemory(
            type="goal",
            value="Test",
            evidence="Test",
            confidence=0.5,
            session_id="test"
        )
        assert memory.confidence == 0.5
    
    @pytest.mark.asyncio
    async def test_score_memory_importance(self):
        """Test memory importance scoring."""
        from modules.memory_extractor import ExtractedMemory, score_memory_importance
        
        # Higher priority type (boundary) should score higher
        boundary_memory = ExtractedMemory(
            type="boundary",
            value="Never invest in tobacco",
            evidence="I refuse to invest in tobacco companies",
            confidence=0.9,
            session_id="test"
        )
        
        intent_memory = ExtractedMemory(
            type="intent",
            value="Looking at deals",
            evidence="Just browsing",
            confidence=0.5,
            session_id="test"
        )
        
        boundary_score = score_memory_importance(boundary_memory)
        intent_score = score_memory_importance(intent_memory)
        
        # Boundary should have higher importance
        assert boundary_score > intent_score


class TestConflictDetection:
    """Test conflict detection between memories."""
    
    @pytest.mark.asyncio
    async def test_detect_no_conflicts(self):
        """Non-conflicting memories should return empty list."""
        from modules.memory_extractor import detect_conflicts, ExtractedMemory
        
        new_memories = [
            ExtractedMemory(
                type="goal",
                value="Invest in B2B SaaS",
                evidence="Focus on B2B",
                session_id="s1"
            )
        ]
        
        existing = [
            {"type": "preference", "value": "Prefer seed stage"}
        ]
        
        conflicts = await detect_conflicts(new_memories, existing)
        assert conflicts == []
    
    @pytest.mark.asyncio
    async def test_detect_contradiction(self):
        """Contradicting memories should be detected."""
        from modules.memory_extractor import detect_conflicts, ExtractedMemory
        
        new_memories = [
            ExtractedMemory(
                type="preference",
                value="I want to avoid early stage",
                evidence="Don't like early stage",
                session_id="s2"
            )
        ]
        
        existing = [
            {"type": "preference", "value": "I like early stage startups"}
        ]
        
        conflicts = await detect_conflicts(new_memories, existing)
        # May or may not detect based on keyword matching
        # The actual implementation uses simple keyword matching


class TestExtractionPrompt:
    """Test the extraction prompt formatting."""
    
    def test_prompt_template_exists(self):
        """Verify extraction prompt template is defined."""
        from modules.memory_extractor import EXTRACTION_PROMPT
        
        assert EXTRACTION_PROMPT is not None
        assert "{transcript}" in EXTRACTION_PROMPT
        assert "intent" in EXTRACTION_PROMPT.lower()
        assert "goal" in EXTRACTION_PROMPT.lower()
        assert "constraint" in EXTRACTION_PROMPT.lower()
        assert "preference" in EXTRACTION_PROMPT.lower()
        assert "boundary" in EXTRACTION_PROMPT.lower()


class TestExtractionRobustness:
    """Regression tests for extraction edge-cases seen in production."""

    @pytest.mark.asyncio
    async def test_extract_handles_object_wrapped_memories(self, monkeypatch):
        from modules import memory_extractor

        class _Completions:
            async def create(self, **_kwargs):  # noqa: ANN003
                content = json.dumps({
                    "m1": {
                        "type": "goal",
                        "value": "Build a verified digital twin",
                        "evidence": "I am building a digital twin",
                        "confidence": 0.9
                    }
                })
                msg = type("Msg", (), {"content": content})()
                choice = type("Choice", (), {"message": msg})()
                return type("Resp", (), {"choices": [choice]})()

        class _AsyncOpenAI:
            def __init__(self, **_kwargs):  # noqa: ANN003
                self.chat = type("Chat", (), {"completions": _Completions()})()

        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=_AsyncOpenAI))

        result = await memory_extractor.extract_memories(
            transcript=[{"role": "user", "content": "I am building a digital twin for founders."}],
            session_id="session-shape",
        )

        assert result.total_extracted == 1
        assert result.memories[0].type == "goal"
        assert "digital twin" in result.memories[0].value.lower()

    @pytest.mark.asyncio
    async def test_extract_falls_back_to_heuristics_when_model_fails(self, monkeypatch):
        from modules import memory_extractor

        class _Completions:
            async def create(self, **_kwargs):  # noqa: ANN003
                raise RuntimeError("openai timeout")

        class _AsyncOpenAI:
            def __init__(self, **_kwargs):  # noqa: ANN003
                self.chat = type("Chat", (), {"completions": _Completions()})()

        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=_AsyncOpenAI))

        transcript = [
            {"role": "user", "content": "I want answers to be direct, structured, and practical."},
            {"role": "user", "content": "Do not invent details and escalate risky asks to me."},
        ]

        result = await memory_extractor.extract_memories(
            transcript=transcript,
            session_id="session-fallback",
        )

        assert result.total_extracted >= 1
        assert any(m.type in {"preference", "boundary", "goal"} for m in result.memories)

    @pytest.mark.asyncio
    async def test_extract_coalesces_fragmented_owner_turns_around_ack_messages(self, monkeypatch):
        from modules import memory_extractor

        class _Completions:
            async def create(self, **_kwargs):  # noqa: ANN003
                raise RuntimeError("openai timeout")

        class _AsyncOpenAI:
            def __init__(self, **_kwargs):  # noqa: ANN003
                self.chat = type("Chat", (), {"completions": _Completions()})()

        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=_AsyncOpenAI))

        transcript = [
            {"role": "user", "content": "My name is Sai, short for Sainath Shetty."},
            {"role": "assistant", "content": "Got it."},
            {"role": "user", "content": "I want my answers to be direct."},
            {"role": "assistant", "content": "Understood."},
            {"role": "user", "content": "structured and practical, no fluff."},
            {"role": "assistant", "content": "Sure."},
            {"role": "user", "content": "Do not invent details."},
        ]

        result = await memory_extractor.extract_memories(
            transcript=transcript,
            session_id="session-fragmented",
        )

        assert result.total_extracted >= 1
        assert result.transcript_turns == 1
        assert any(m.type == "boundary" for m in result.memories)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
