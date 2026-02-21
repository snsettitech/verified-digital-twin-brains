"""
Comprehensive tests for the Conversational Query Rewriter.

Run with: pytest tests/test_query_rewriter.py -v
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

from modules.query_rewriter import (
    ConversationalQueryRewriter,
    QueryRewriteResult,
    rewrite_conversational_query,
    QUERY_REWRITING_ENABLED,
)


# Fixtures
@pytest.fixture
def rewriter():
    """Create a fresh rewriter instance for each test."""
    return ConversationalQueryRewriter()


@pytest.fixture
def sample_conversation():
    """Sample conversation history for testing."""
    return [
        {"role": "user", "content": "What is our Q3 revenue?"},
        {"role": "assistant", "content": "Q3 revenue was $5.2M, up 15% year over year."},
    ]


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock = Mock()
    mock.choices = [
        Mock(
            message=Mock(
                content='{"standalone_query": "What was the Q4 revenue?", "intent": "follow_up", "entities": {"primary": "revenue", "timeframe": "Q4"}, "confidence": 0.92, "reasoning": "Carried over revenue entity"}'
            )
        )
    ]
    return mock


# Test Group 1: Basic Functionality
class TestBasicFunctionality:
    """Test basic rewriter functionality."""
    
    @pytest.mark.asyncio
    async def test_follow_up_query_rewrite(self, rewriter, sample_conversation):
        """Test rewriting a follow-up query."""
        result = await rewriter.rewrite("What about Q4?", sample_conversation)
        
        assert isinstance(result, QueryRewriteResult)
        assert result.original_query == "What about Q4?"
        assert result.rewrite_applied is True
        assert result.requires_history is True
        assert "revenue" in result.standalone_query.lower() or "Q4" in result.standalone_query
    
    @pytest.mark.asyncio
    async def test_standalone_query_skipped(self, rewriter):
        """Test that standalone queries are not rewritten."""
        query = "What is the company's mission statement?"
        result = await rewriter.rewrite(query, [])
        
        assert result.original_query == query
        assert result.standalone_query == query
        assert result.rewrite_applied is False
        assert result.requires_history is False
    
    @pytest.mark.asyncio
    async def test_pronoun_resolution_it(self, rewriter):
        """Test resolving 'it' pronoun."""
        history = [
            {"role": "user", "content": "Tell me about the product launch."},
            {"role": "assistant", "content": "The product launch is scheduled for March."},
        ]
        
        # Rule-based should resolve 'it'
        hint = rewriter._resolve_pronouns_rule_based("When is it happening?", history)
        assert "launch" in hint.lower() or "March" in hint
    
    @pytest.mark.asyncio
    async def test_pronoun_resolution_that(self, rewriter):
        """Test resolving 'that' pronoun."""
        history = [
            {"role": "user", "content": "What's the pricing?"},
            {"role": "assistant", "content": "Our pricing starts at $99/month."},
        ]
        
        hint = rewriter._resolve_pronouns_rule_based("Is that competitive?", history)
        # Should include pricing context
        assert "pricing" in hint.lower() or hint != "Is that competitive?"


# Test Group 2: Entity Extraction
class TestEntityExtraction:
    """Test entity extraction from conversation history."""
    
    def test_extract_monetary_amounts(self, rewriter):
        """Test extraction of monetary amounts."""
        history = [
            {"role": "assistant", "content": "Revenue was $5.2M and profit was $1.2 million."}
        ]
        
        entities = rewriter._extract_entities_from_history(history)
        assert any("$5.2M" in e or "5.2M" in e for e in entities)
    
    def test_extract_percentages(self, rewriter):
        """Test extraction of percentages."""
        history = [
            {"role": "assistant", "content": "Growth was 15% and margin improved by 3.5%."}
        ]
        
        entities = rewriter._extract_entities_from_history(history)
        assert any("15%" in e for e in entities)
    
    def test_extract_time_periods(self, rewriter):
        """Test extraction of time periods."""
        history = [
            {"role": "assistant", "content": "Q3 2024 results exceeded Q2 expectations."}
        ]
        
        entities = rewriter._extract_entities_from_history(history)
        # Should extract Q3, Q2, or 2024
        assert any("Q3" in e or "Q2" in e or "2024" in e for e in entities)
    
    def test_extract_quoted_terms(self, rewriter):
        """Test extraction of quoted terms."""
        history = [
            {"role": "assistant", "content": 'The project is called "Project Phoenix"."}
        ]
        
        entities = rewriter._extract_entities_from_history(history)
        assert any("Project Phoenix" in e for e in entities)
    
    def test_filter_common_words(self, rewriter):
        """Test that common words are filtered out."""
        history = [
            {"role": "assistant", "content": "The And For Are But Not You All Can"}
        ]
        
        entities = rewriter._extract_entities_from_history(history)
        # Should not extract common words
        common = {"the", "and", "for", "are", "but", "not", "you", "all", "can"}
        assert not any(e.lower() in common for e in entities)


# Test Group 3: Standalone Query Detection
class TestStandaloneQueryDetection:
    """Test detection of standalone vs. conversational queries."""
    
    def test_standalone_no_pronouns(self, rewriter):
        """Test standalone query without pronouns."""
        assert rewriter._is_standalone_query("What is the company's mission?") is True
    
    def test_standalone_with_pronouns(self, rewriter):
        """Test non-standalone query with pronouns."""
        assert rewriter._is_standalone_query("What is it?") is False
        assert rewriter._is_standalone_query("Tell me about that.") is False
    
    def test_standalone_vague_terms(self, rewriter):
        """Test detection of vague starting terms."""
        assert rewriter._is_standalone_query("What about the pricing?") is False
        assert rewriter._is_standalone_query("How about Q4?") is False
    
    def test_standalone_too_short(self, rewriter):
        """Test that very short queries are not standalone."""
        assert rewriter._is_standalone_query("Why?") is False
        assert rewriter._is_standalone_query("How?") is False


# Test Group 4: Confidence and Fallback
class TestConfidenceAndFallback:
    """Test confidence scoring and fallback behavior."""
    
    @pytest.mark.asyncio
    async def test_low_confidence_fallback(self, rewriter):
        """Test that low confidence rewrites fall back to original."""
        # Force low confidence threshold
        rewriter.min_confidence = 0.99
        
        history = [{"role": "user", "content": "Something vague"}]
        result = await rewriter.rewrite("What about that?", history)
        
        # Should fallback to original
        assert result.standalone_query == "What about that?"
        assert result.rewrite_applied is False
    
    @pytest.mark.asyncio
    async def test_high_confidence_applied(self, rewriter):
        """Test that high confidence rewrites are applied."""
        # Mock LLM to return high confidence
        mock_result = QueryRewriteResult(
            standalone_query="What was the Q4 revenue?",
            original_query="What about Q4?",
            intent="follow_up",
            rewrite_applied=True,
            rewrite_confidence=0.95,
        )
        
        with patch.object(rewriter, '_rewrite_with_llm', return_value=mock_result):
            result = await rewriter.rewrite("What about Q4?", [
                {"role": "user", "content": "What's Q3 revenue?"},
                {"role": "assistant", "content": "Q3 was $5M."},
            ])
            
            assert result.rewrite_applied is True
            assert result.rewrite_confidence >= rewriter.min_confidence


# Test Group 5: Error Handling
class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_history(self, rewriter):
        """Test behavior with empty history."""
        result = await rewriter.rewrite("What is the mission?", [])
        
        # Should be standalone
        assert result.rewrite_applied is False
        assert result.requires_history is False
    
    @pytest.mark.asyncio
    async def test_empty_query(self, rewriter):
        """Test behavior with empty query."""
        result = await rewriter.rewrite("", [])
        
        assert result.original_query == ""
        assert result.standalone_query == ""
    
    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, rewriter):
        """Test fallback when LLM fails."""
        with patch.object(rewriter, '_get_llm_client', side_effect=Exception("LLM down")):
            result = await rewriter.rewrite("What about Q4?", [
                {"role": "user", "content": "Q3 was $5M."},
            ])
            
            # Should fallback to rule-based
            assert result.original_query == "What about Q4?"
            assert result.rewrite_confidence < 0.7  # Low confidence for fallback
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, rewriter):
        """Test handling of timeout."""
        with patch.object(rewriter, '_rewrite_with_llm', side_effect=asyncio.TimeoutError()):
            result = await rewriter.rewrite("What about Q4?", [
                {"role": "user", "content": "Q3 was $5M."},
            ])
            
            # Should return original
            assert result.standalone_query == "What about Q4?"


# Test Group 6: Intent Classification
class TestIntentClassification:
    """Test intent classification."""
    
    @pytest.mark.asyncio
    async def test_factual_lookup_intent(self, rewriter):
        """Test factual lookup intent."""
        result = await rewriter.rewrite("What is the revenue?", [])
        
        # Should be factual or standalone
        assert result.intent in ["factual_lookup", "standalone", "unknown"]
    
    @pytest.mark.asyncio
    async def test_follow_up_intent(self, rewriter, sample_conversation):
        """Test follow-up intent detection."""
        result = await rewriter.rewrite("What about Q4?", sample_conversation)
        
        # Should detect follow-up
        assert result.intent in ["follow_up", "temporal_analysis", "unknown"]


# Test Group 7: Integration with Agent
class TestAgentIntegration:
    """Test integration with agent module."""
    
    def test_extract_conversation_history(self):
        """Test extraction of conversation history from LangChain messages."""
        from modules.agent import _extract_conversation_history
        
        messages = [
            HumanMessage(content="First question?"),
            AIMessage(content="First answer."),
            HumanMessage(content="Second question?"),
            AIMessage(content="Second answer."),
            HumanMessage(content="Current question?"),  # Should be excluded
        ]
        
        history = _extract_conversation_history(messages, max_turns=2)
        
        # Should have 4 entries (2 turns x 2 roles)
        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "First question?"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "First answer."
    
    def test_extract_conversation_history_empty(self):
        """Test extraction with empty messages."""
        from modules.agent import _extract_conversation_history
        
        history = _extract_conversation_history([], max_turns=5)
        assert history == []
    
    @pytest.mark.asyncio
    async def test_rewrite_query_with_context(self):
        """Test the agent's rewrite helper function."""
        from modules.agent import _rewrite_query_with_context
        
        messages = [
            HumanMessage(content="What is Q3 revenue?"),
            AIMessage(content="Q3 was $5M."),
            HumanMessage(content="What about Q4?"),  # Current query
        ]
        
        effective_query, rewrite_result = await _rewrite_query_with_context(
            user_query="What about Q4?",
            messages=messages,
            twin_id="test_twin",
        )
        
        # If rewriting is disabled, should return original
        if not QUERY_REWRITING_ENABLED:
            assert effective_query == "What about Q4?"
            assert rewrite_result is None


# Test Group 8: Performance
class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_rewriting_latency(self, rewriter, sample_conversation):
        """Test that rewriting completes within acceptable time."""
        import time
        
        start = time.time()
        result = await rewriter.rewrite("What about Q4?", sample_conversation)
        elapsed_ms = (time.time() - start) * 1000
        
        # Should complete within 5 seconds (generous timeout)
        assert elapsed_ms < 5000
        assert result.latency_ms > 0
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, rewriter):
        """Test that caching works if enabled."""
        # This test is for when caching is implemented
        query = "What about Q4?"
        history = [
            {"role": "user", "content": "Q3 was $5M."},
        ]
        
        # First call
        result1 = await rewriter.rewrite(query, history)
        
        # Second call with same input should use cache
        # (if caching is implemented)
        result2 = await rewriter.rewrite(query, history)
        
        # Results should be consistent
        assert result1.standalone_query == result2.standalone_query


# Test Group 9: Multi-Strategy Rewriting
class TestMultiStrategy:
    """Test multi-strategy rewriting (DMQR-RAG approach)."""
    
    @pytest.mark.asyncio
    async def test_multi_strategy_output(self, rewriter):
        """Test that multi-strategy produces multiple rewrites."""
        history = [
            {"role": "user", "content": "Tell me about the product."},
        ]
        
        results = await rewriter.rewrite_multi_strategy(
            "What are the features?",
            history,
        )
        
        # Should return multiple results
        assert len(results) >= 2
        assert all(isinstance(r, QueryRewriteResult) for r in results)
    
    def test_extract_keywords(self, rewriter):
        """Test keyword extraction for minimal strategy."""
        query = "What is the best product feature?"
        keywords = rewriter._extract_keywords(query)
        
        # Should remove stopwords
        assert "the" not in keywords.lower()
        assert "is" not in keywords.lower()
        assert "best product feature" in keywords.lower()


# Test Group 10: Edge Cases
class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    @pytest.mark.asyncio
    async def test_very_long_query(self, rewriter):
        """Test handling of very long queries."""
        long_query = "What about " + "Q4 " * 100 + "?"
        result = await rewriter.rewrite(long_query, [])
        
        assert result.original_query == long_query
    
    @pytest.mark.asyncio
    async def test_unicode_characters(self, rewriter):
        """Test handling of unicode characters."""
        query = "What about the €5M investment?"
        result = await rewriter.rewrite(query, [])
        
        assert "€" in result.original_query or "5M" in result.original_query
    
    @pytest.mark.asyncio
    async def test_special_characters(self, rewriter):
        """Test handling of special characters."""
        query = "What about Q4 & Q3 (2024)?"
        result = await rewriter.rewrite(query, [])
        
        assert result.original_query == query
    
    @pytest.mark.asyncio
    async def test_multiple_pronouns(self, rewriter):
        """Test query with multiple pronouns."""
        history = [
            {"role": "assistant", "content": "The product launch is in March. The team is ready."},
        ]
        
        result = await rewriter.rewrite("When is it and are they ready?", history)
        
        # Should attempt to resolve at least one pronoun
        assert result.rewrite_applied is True or result.standalone_query != "When is it and are they ready?"


# Integration test with mocked LLM
@pytest.mark.asyncio
async def test_full_integration_with_mock(mock_openai_response):
    """Test full integration with mocked LLM."""
    rewriter = ConversationalQueryRewriter()
    
    # Mock the LLM client
    mock_client = Mock()
    mock_client.chat.completions.create = Mock(return_value=mock_openai_response)
    
    with patch.object(rewriter, '_get_llm_client', return_value=mock_client):
        result = await rewriter.rewrite("What about Q4?", [
            {"role": "user", "content": "What's Q3 revenue?"},
            {"role": "assistant", "content": "Q3 was $5M."},
        ])
        
        assert result.standalone_query == "What was the Q4 revenue?"
        assert result.intent == "follow_up"
        assert result.rewrite_confidence == 0.92
        assert result.rewrite_applied is True


# Convenience function test
@pytest.mark.asyncio
async def test_convenience_function():
    """Test the convenience function."""
    result = await rewrite_conversational_query(
        "What about Q4?",
        [{"role": "assistant", "content": "Q3 was $5M."}],
    )
    
    assert isinstance(result, QueryRewriteResult)
    assert result.original_query == "What about Q4?"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
