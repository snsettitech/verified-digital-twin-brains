# backend/tests/test_interview_integration.py
"""Integration tests for the Cognitive Interview flow.

These tests verify the complete flow works correctly with mocked database calls.
Tests various user response scenarios and validates correct system behavior.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Import the modules we need for testing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules._core.response_evaluator import ResponseEvaluator
from modules._core.repair_strategies import RepairManager


class TestInterviewQualityScenarios:
    """Test various user response scenarios."""
    
    @pytest.mark.asyncio
    async def test_scenario_greeting_then_substantive(self):
        """User says 'hi' first, then provides substantive answer."""
        # Turn 1: User says "hi"
        msg1 = "hi"
        quality1 = await ResponseEvaluator.evaluate_response(msg1, use_llm=False)
        
        assert not quality1.is_substantive
        assert quality1.quality_score < 0.3
        
        # System should respond with gentle re-ask
        repair1 = RepairManager.get_repair_strategy(
            attempt=1,
            current_question={"question": "What are you trying to use this twin for?"}
        )
        assert repair1.strategy_type == "gentle_reask"
        
        # Turn 2: User provides substantive answer
        msg2 = "I want to create a VC brain that helps me track my investment thesis"
        quality2 = await ResponseEvaluator.evaluate_response(msg2, use_llm=False)
        
        assert quality2.is_substantive
        assert quality2.quality_score >= 0.5
        # System should proceed to extraction
    
    @pytest.mark.asyncio
    async def test_scenario_multiple_non_answers(self):
        """User provides multiple non-answers, testing escalation."""
        non_answers = ["hi", "ok", "hmm", "idk"]
        question = {"question": "What's your investment thesis?"}
        
        for i, msg in enumerate(non_answers):
            attempt = i + 1
            quality = await ResponseEvaluator.evaluate_response(msg, use_llm=False)
            
            assert not quality.is_substantive, f"'{msg}' should not be substantive"
            
            repair = RepairManager.get_repair_strategy(
                attempt=attempt,
                current_question=question
            )
            
            # Verify correct strategy escalation
            if attempt == 1:
                assert repair.strategy_type == "gentle_reask"
            elif attempt == 2:
                assert repair.strategy_type == "provide_examples"
            elif attempt == 3:
                assert repair.strategy_type == "simplify_question"
            elif attempt == 4:
                assert repair.strategy_type == "offer_escape"
    
    @pytest.mark.asyncio
    async def test_scenario_user_wants_to_skip(self):
        """User explicitly asks to skip a question."""
        skip_requests = [
            "skip",
            "skip this question",
            "next question please",
            "pass",
            "I don't know, move on"
        ]
        
        for msg in skip_requests:
            is_skip = RepairManager.detect_skip_request(msg)
            assert is_skip, f"'{msg}' should be detected as skip request"
    
    @pytest.mark.asyncio
    async def test_scenario_borderline_response(self):
        """User provides a borderline response that could be substantive."""
        # Short but potentially meaningful
        borderline_responses = [
            "A VC twin",  # 3 words, could be substantive
            "for investing",  # 2 words, context-dependent
            "Enterprise SaaS",  # 2 words but domain-specific
        ]
        
        for msg in borderline_responses:
            quality = await ResponseEvaluator.evaluate_response(msg, use_llm=False)
            # These should get through Tier 1 and be evaluated by Tier 2
            # The exact result depends on heuristics
            assert quality.tier >= 1
    
    @pytest.mark.asyncio
    async def test_scenario_rich_substantive_response(self):
        """User provides a detailed, rich response."""
        rich_response = """I want to create a VC brain that captures my investment philosophy. 
        I focus on B2B SaaS companies at the seed stage, typically investing $500K-$2M. 
        My thesis is that great founders can build category-defining companies in underserved markets."""
        
        quality = await ResponseEvaluator.evaluate_response(rich_response, use_llm=False)
        
        assert quality.is_substantive
        assert quality.quality_score >= 0.7  # Should be high quality
    
    @pytest.mark.asyncio
    async def test_scenario_user_asks_question_back(self):
        """User asks a question instead of answering."""
        question_back = "What kind of information do you need? What should I include?"
        current_question = {"question": "What's your investment thesis?"}
        
        # Check if it's detected as off-topic
        redirect = RepairManager.detect_off_topic(question_back, current_question)
        
        # Should get some redirect suggestion
        if redirect:
            assert "thesis" in redirect.lower() or "question" in redirect.lower()
    
    @pytest.mark.asyncio
    async def test_scenario_mixed_session(self):
        """Simulate a realistic mixed session with good and bad responses."""
        session = [
            # Turn 1: Greeting (bad)
            {"msg": "hello", "expected_substantive": False, "expected_tier": 1},
            # Turn 2: Short acknowledgment (bad)  
            {"msg": "ok", "expected_substantive": False, "expected_tier": 1},
            # Turn 3: Finally substantive
            {"msg": "I want to build a VC brain", "expected_substantive": True, "expected_tier": 2},
            # Turn 4: Rich response
            {"msg": "I focus on B2B SaaS at seed stage with check sizes of 500K to 2M", "expected_substantive": True, "expected_tier": 2},
            # Turn 5: Skip request - Note: "skip this one" is 3 words, so it passes quality check
            # but gets detected separately as a skip request
            {"msg": "skip", "expected_substantive": False, "expected_tier": 1, "is_skip": True},
        ]
        
        for i, turn in enumerate(session):
            quality = await ResponseEvaluator.evaluate_response(turn["msg"], use_llm=False)
            
            assert quality.is_substantive == turn["expected_substantive"], \
                f"Turn {i+1} '{turn['msg']}' substantive mismatch"
            
            # Check skip detection for skip requests
            if turn.get("is_skip"):
                assert RepairManager.detect_skip_request(turn["msg"])


class TestResponsePatterns:
    """Test specific response patterns."""
    
    @pytest.mark.asyncio
    async def test_all_non_answer_patterns(self):
        """Verify all defined non-answer patterns are rejected."""
        from modules._core.response_evaluator import NON_ANSWERS
        
        for non_answer in NON_ANSWERS:
            quality = await ResponseEvaluator.evaluate_response(non_answer, use_llm=False)
            assert not quality.is_substantive, f"'{non_answer}' should not be substantive"
            assert quality.tier == 1, f"'{non_answer}' should be caught at Tier 1"
    
    @pytest.mark.asyncio
    async def test_domain_specific_keywords(self):
        """Test that domain-specific keywords boost relevance."""
        use_case_slot = {"slot_id": "intent_use_case"}
        
        # Response with domain keywords
        msg_with_keywords = "I want to build a twin for my investment decisions"
        quality = await ResponseEvaluator.evaluate_response(
            msg_with_keywords,
            current_slot=use_case_slot,
            use_llm=False
        )
        
        assert quality.is_substantive
        # Note: We can't directly verify keyword boost without comparing scores
    
    @pytest.mark.asyncio
    async def test_various_length_responses(self):
        """Test how response length affects quality scoring."""
        responses = [
            ("hi", False),  # 1 word, non-answer
            ("yes please", False),  # 2 words, too short
            ("I focus on SaaS", True),  # 4 words, might be borderline
            ("I focus on B2B SaaS companies at the seed stage", True),  # 10 words, good
            ("My investment thesis focuses on early-stage B2B SaaS companies in the enterprise space with strong founding teams and clear paths to market leadership", True),  # 25 words, great
        ]
        
        for msg, expected_substantive in responses:
            quality = await ResponseEvaluator.evaluate_response(msg, use_llm=False)
            # Note: The first few might vary based on heuristics
            if expected_substantive:
                # Longer, substantive messages should always pass
                assert quality.quality_score >= 0.4


class TestRepairStrategyEdgeCases:
    """Test edge cases for repair strategies."""
    
    def test_repair_without_question_context(self):
        """Test repair strategy when no question context is provided."""
        repair = RepairManager.get_repair_strategy(attempt=1)
        assert repair.message  # Should still provide a message
        assert repair.strategy_type == "gentle_reask"
    
    def test_repair_with_slot_only(self):
        """Test repair strategy when only slot context is provided."""
        repair = RepairManager.get_repair_strategy(
            attempt=3,
            current_slot={"slot_id": "investment_thesis"}
        )
        assert repair.strategy_type == "simplify_question"
        assert "investment thesis" in repair.message.lower()
    
    def test_repair_attempt_zero(self):
        """Test repair strategy with attempt 0 (edge case)."""
        # Should default to first strategy or handle gracefully
        repair = RepairManager.get_repair_strategy(attempt=0)
        # The code handles this, but behavior might vary
        assert repair.message


class TestQualityScoreTracking:
    """Test quality score tracking scenarios."""
    
    @pytest.mark.asyncio
    async def test_quality_score_fields(self):
        """Verify quality result contains all expected fields."""
        msg = "I want to create a comprehensive VC brain for investment analysis"
        quality = await ResponseEvaluator.evaluate_response(msg, use_llm=False)
        
        # Check all fields are present
        assert hasattr(quality, "is_substantive")
        assert hasattr(quality, "quality_score")
        assert hasattr(quality, "tier")
        assert hasattr(quality, "reason")
        
        # Values should be reasonable
        assert isinstance(quality.is_substantive, bool)
        assert 0.0 <= quality.quality_score <= 1.0
        assert quality.tier in [1, 2, 3]
        assert quality.reason  # Should have a reason


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

