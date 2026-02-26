"""
Tests for Runtime Confidence Gate

Run: pytest backend/tests/test_runtime_confidence_gate.py -v
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from modules.runtime_confidence_gate import (
    RuntimeConfidenceGate,
    GateDecision,
    ConfidenceGateResult,
    check_answer_confidence,
    get_fallback_message,
)


class TestRuntimeConfidenceGate:
    """Test confidence gate functionality."""
    
    @pytest.fixture
    def gate(self):
        return RuntimeConfidenceGate("test-twin")
    
    @pytest.mark.asyncio
    async def test_allow_high_answerability(self, gate):
        """Test that high answerability allows answer."""
        with patch.object(gate, '_get_policy', return_value={
            "confidence_threshold_answer": 0.5,
            "fallback_behavior": "i_dont_know"
        }):
            with patch.object(gate, '_get_global_score', return_value={
                "answerability_score": 80
            }):
                with patch.object(gate, '_count_open_contradictions', return_value=0):
                    result = await gate.check("test query")
        
        assert result.decision == GateDecision.ALLOW
        assert result.answerability_score == 80
    
    @pytest.mark.asyncio
    async def test_block_low_answerability(self, gate):
        """Test that low answerability blocks answer."""
        with patch.object(gate, '_get_policy', return_value={
            "confidence_threshold_answer": 0.6,
            "fallback_behavior": "i_dont_know"
        }):
            with patch.object(gate, '_get_global_score', return_value={
                "answerability_score": 40
            }):
                with patch.object(gate, '_count_open_contradictions', return_value=0):
                    result = await gate.check("test query")
        
        assert result.decision == GateDecision.BLOCK
        assert result.fallback_message is not None
    
    @pytest.mark.asyncio
    async def test_partial_with_contradictions(self, gate):
        """Test that open contradictions result in partial decision."""
        with patch.object(gate, '_get_policy', return_value={
            "confidence_threshold_answer": 0.5,
            "fallback_behavior": "i_dont_know"
        }):
            with patch.object(gate, '_get_global_score', return_value={
                "answerability_score": 70
            }):
                with patch.object(gate, '_count_open_contradictions', return_value=2):
                    result = await gate.check("test query")
        
        assert result.decision == GateDecision.PARTIAL
        assert result.open_contradictions == 2
    
    @pytest.mark.asyncio
    async def test_topic_specific_score(self, gate):
        """Test topic-specific answerability scoring."""
        with patch.object(gate, '_get_policy', return_value={
            "confidence_threshold_answer": 0.5,
        }):
            with patch.object(gate, '_get_topic_score', return_value={
                "answerability_score": 90
            }) as mock_topic:
                with patch.object(gate, '_count_open_contradictions', return_value=0):
                    result = await gate.check("test query", query_topic="expertise")
        
        mock_topic.assert_called_once()
        assert result.decision == GateDecision.ALLOW
    
    def test_format_response_block(self, gate):
        """Test response formatting for blocked answers."""
        result = ConfidenceGateResult(
            decision=GateDecision.BLOCK,
            fallback_message="I don't know enough about this."
        )
        
        response = gate.format_response_with_confidence("original", result)
        
        assert response == "I don't know enough about this."
        assert "original" not in response
    
    def test_format_response_partial(self, gate):
        """Test response formatting for partial confidence."""
        result = ConfidenceGateResult(
            decision=GateDecision.PARTIAL,
            answerability_score=65,
            open_contradictions=1
        )
        
        response = gate.format_response_with_confidence("original answer", result)
        
        assert "original answer" in response
        assert "confidence" in response.lower() or "Note" in response
    
    def test_format_response_allow(self, gate):
        """Test response formatting for allowed answers."""
        result = ConfidenceGateResult(
            decision=GateDecision.ALLOW,
            answerability_score=85
        )
        
        response = gate.format_response_with_confidence("original answer", result)
        
        assert response == "original answer"


class TestFallbackMessages:
    """Test fallback message generation."""
    
    def test_i_dont_know_fallback(self):
        msg = get_fallback_message("i_dont_know")
        assert "don't have" in msg.lower() or "don't know" in msg.lower()
    
    def test_clarify_fallback(self):
        msg = get_fallback_message("clarify")
        assert "clarify" in msg.lower() or "context" in msg.lower()
    
    def test_escalate_fallback(self):
        msg = get_fallback_message("escalate")
        assert "research" in msg.lower() or "review" in msg.lower()
    
    def test_custom_template(self):
        custom = "Custom fallback message"
        msg = get_fallback_message("i_dont_know", custom_template=custom)
        assert msg == custom


class TestIntegration:
    """Integration-style tests."""
    
    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test the convenience function."""
        with patch('modules.runtime_confidence_gate.RuntimeConfidenceGate') as MockGate:
            mock_instance = Mock()
            mock_instance.check = AsyncMock(return_value=Mock(
                decision=GateDecision.ALLOW,
                answerability_score=75
            ))
            MockGate.return_value = mock_instance
            
            result = await check_answer_confidence("twin-1", "query")
        
        assert result.decision == GateDecision.ALLOW


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
