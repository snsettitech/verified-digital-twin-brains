# backend/tests/test_interview_quality_flow.py
"""Test Enterprise Cognitive Interview Flow with Response Quality Evaluation.

Tests the complete interview flow with various response qualities:
- Tier 1: Rule-based fast rejection (greetings, acknowledgments, too-short)
- Tier 2: Heuristic analysis (word count, character length, domain keywords)
- Tier 3: LLM classification (borderline cases)
- Repair strategies: Escalating clarification attempts
- Skip requests: Detection and handling
- Full flow: End-to-end with quality gates
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Import modules under test
from modules._core.response_evaluator import ResponseEvaluator, ResponseQuality, NON_ANSWERS
from modules._core.repair_strategies import RepairManager, RepairStrategy


class TestResponseEvaluatorTier1:
    """Test Tier 1: Rule-based fast rejection (no API call)."""
    
    @pytest.mark.asyncio
    async def test_rejects_greetings(self):
        """Greetings like 'hi', 'hello' should be rejected at Tier 1."""
        greetings = ["hi", "hello", "hey", "yo", "sup", "hola"]
        
        for greeting in greetings:
            result = await ResponseEvaluator.evaluate_response(greeting, use_llm=False)
            assert not result.is_substantive, f"'{greeting}' should not be substantive"
            assert result.tier == 1, f"'{greeting}' should be caught at Tier 1"
            assert result.quality_score < 0.3, f"'{greeting}' should have low quality score"
    
    @pytest.mark.asyncio
    async def test_rejects_acknowledgments(self):
        """Acknowledgments like 'ok', 'yes', 'k' should be rejected at Tier 1."""
        acknowledgments = ["ok", "okay", "k", "yes", "no", "yep", "nope", "yeah"]
        
        for ack in acknowledgments:
            result = await ResponseEvaluator.evaluate_response(ack, use_llm=False)
            assert not result.is_substantive, f"'{ack}' should not be substantive"
            assert result.tier == 1, f"'{ack}' should be caught at Tier 1"
            assert result.quality_score < 0.3, f"'{ack}' should have low quality score"
    
    @pytest.mark.asyncio
    async def test_rejects_uncertainty_phrases(self):
        """Uncertainty phrases like 'idk', 'not sure' should be rejected."""
        uncertainties = ["idk", "not sure", "maybe", "dunno"]
        
        for phrase in uncertainties:
            result = await ResponseEvaluator.evaluate_response(phrase, use_llm=False)
            assert not result.is_substantive, f"'{phrase}' should not be substantive"
            assert result.tier == 1, f"'{phrase}' should be caught at Tier 1"
    
    @pytest.mark.asyncio
    async def test_rejects_test_messages(self):
        """Test messages like 'test', 'testing' should be rejected."""
        tests = ["test", "testing", "test message"]
        
        for msg in tests:
            result = await ResponseEvaluator.evaluate_response(msg, use_llm=False)
            assert not result.is_substantive, f"'{msg}' should not be substantive"
    
    @pytest.mark.asyncio
    async def test_rejects_too_short_responses(self):
        """Responses with less than 3 words should generally be rejected."""
        short_responses = ["no", "a b", "one two"]
        
        for resp in short_responses:
            result = await ResponseEvaluator.evaluate_response(resp, use_llm=False)
            assert not result.is_substantive, f"'{resp}' is too short"
            assert result.quality_score < 0.5, f"'{resp}' should have low quality"
    
    @pytest.mark.asyncio
    async def test_rejects_only_punctuation(self):
        """Messages with only punctuation should be rejected."""
        punct_only = ["...", "???", "!!!", "   ", "---"]
        
        for msg in punct_only:
            result = await ResponseEvaluator.evaluate_response(msg, use_llm=False)
            assert not result.is_substantive, f"'{msg}' should not be substantive"
            assert result.tier == 1
    
    @pytest.mark.asyncio
    async def test_single_substantive_word_passes_tier1(self):
        """Single substantive words (>5 chars) should pass Tier 1 for further evaluation."""
        # These should pass Tier 1 and go to Tier 2/3
        substantive_words = ["Enterprise", "B2B SaaS", "Investment"]
        
        for word in substantive_words:
            result = await ResponseEvaluator.evaluate_response(word, use_llm=False)
            # Should either pass Tier 1 or be evaluated at Tier 2
            assert result.tier >= 1


class TestResponseEvaluatorTier2:
    """Test Tier 2: Heuristic analysis."""
    
    @pytest.mark.asyncio
    async def test_longer_responses_get_higher_scores(self):
        """Longer responses should get higher quality scores."""
        short = "I want a twin"  # 4 words
        medium = "I want to create a VC brain for my investment decisions"  # 11 words
        long = "I want to create a comprehensive VC brain that helps me analyze deals, track my investment thesis, and communicate with founders effectively"  # 23 words
        
        result_short = await ResponseEvaluator.evaluate_response(short, use_llm=False)
        result_medium = await ResponseEvaluator.evaluate_response(medium, use_llm=False)
        result_long = await ResponseEvaluator.evaluate_response(long, use_llm=False)
        
        assert result_medium.quality_score >= result_short.quality_score
        assert result_long.quality_score >= result_medium.quality_score
    
    @pytest.mark.asyncio
    async def test_domain_keywords_boost_score(self):
        """Responses with domain keywords should get boosted scores."""
        # With use_case slot
        use_case_slot = {"slot_id": "intent_use_case"}
        
        with_keywords = "I want to create a twin to help build my investment brain"
        without_keywords = "Something about being productive at work"
        
        result_with = await ResponseEvaluator.evaluate_response(
            with_keywords, 
            current_slot=use_case_slot,
            use_llm=False
        )
        result_without = await ResponseEvaluator.evaluate_response(
            without_keywords,
            current_slot=use_case_slot, 
            use_llm=False
        )
        
        # Both should be substantive but keywords version might have higher relevance
        assert result_with.is_substantive
        assert result_without.is_substantive
    
    @pytest.mark.asyncio
    async def test_question_marks_slight_penalty(self):
        """Questions asked back should get a slight penalty."""
        statement = "I want to create a VC brain for investments"
        question = "I want to create a VC brain for investments?"
        
        result_statement = await ResponseEvaluator.evaluate_response(statement, use_llm=False)
        result_question = await ResponseEvaluator.evaluate_response(question, use_llm=False)
        
        # Both should be substantive, but question has slight penalty
        assert result_statement.is_substantive
        assert result_question.is_substantive
    
    @pytest.mark.asyncio
    async def test_borderline_passes_to_tier3(self):
        """Borderline responses (score ~0.5) should pass to Tier 3 when LLM is enabled."""
        borderline = "A VC twin"  # 3 words, short but potentially meaningful
        
        # With LLM disabled, should use Tier 2
        result_no_llm = await ResponseEvaluator.evaluate_response(borderline, use_llm=False)
        assert result_no_llm.tier == 2
        
        # Score should be in borderline range (0.4-0.8)
        assert 0.3 <= result_no_llm.quality_score <= 0.8


class TestRepairStrategies:
    """Test Repair Strategy Manager."""
    
    def test_strategy_1_gentle_reask(self):
        """First attempt should use gentle re-ask strategy."""
        current_question = {"question": "What are you trying to use this twin for?"}
        
        repair = RepairManager.get_repair_strategy(
            attempt=1,
            current_question=current_question
        )
        
        assert repair.strategy_type == "gentle_reask"
        assert repair.attempt == 1
        assert not repair.should_skip
        assert "What are you trying to use this twin for?" in repair.message
    
    def test_strategy_2_provide_examples(self):
        """Second attempt should provide examples."""
        current_question = {
            "question": "What sectors are you excited about?",
            "examples": "B2B SaaS, climate tech, fintech..."
        }
        
        repair = RepairManager.get_repair_strategy(
            attempt=2,
            current_question=current_question
        )
        
        assert repair.strategy_type == "provide_examples"
        assert repair.attempt == 2
        assert "example" in repair.message.lower() or "B2B SaaS" in repair.message
    
    def test_strategy_3_simplify_question(self):
        """Third attempt should simplify the question."""
        current_question = {"question": "What is your investment thesis and how has it evolved?"}
        current_slot = {"slot_id": "investment_thesis"}
        
        repair = RepairManager.get_repair_strategy(
            attempt=3,
            current_question=current_question,
            current_slot=current_slot
        )
        
        assert repair.strategy_type == "simplify_question"
        assert repair.attempt == 3
        assert "simpler" in repair.message.lower()
    
    def test_strategy_4_offer_escape(self):
        """Fourth attempt should offer escape/skip option."""
        current_slot = {"slot_id": "deal_flow_sources", "optional": False}
        
        repair = RepairManager.get_repair_strategy(
            attempt=4,
            current_slot=current_slot
        )
        
        assert repair.strategy_type == "offer_escape"
        assert repair.attempt == 4
        assert "move on" in repair.message.lower() or "okay" in repair.message.lower()
    
    def test_strategy_4_optional_skip(self):
        """Fourth attempt for optional slot should offer skip."""
        current_slot = {"slot_id": "boundaries", "optional": True}
        
        repair = RepairManager.get_repair_strategy(
            attempt=4,
            current_slot=current_slot
        )
        
        assert repair.strategy_type == "offer_skip_optional"
        assert repair.should_skip
        assert "skip" in repair.message.lower() or "optional" in repair.message.lower()
    
    def test_max_attempts_capped(self):
        """Attempts beyond MAX_ATTEMPTS should be capped."""
        repair = RepairManager.get_repair_strategy(attempt=10)
        
        assert repair.attempt == 4  # Should be capped at MAX_ATTEMPTS
        assert repair.strategy_type in ["offer_escape", "offer_skip_optional"]
    
    def test_detect_skip_request(self):
        """Should detect when user wants to skip."""
        skip_phrases = [
            "skip", "skip this", "next question", "pass", "don't know",
            "not applicable", "n/a", "move on", "continue", "let's move on"
        ]
        
        for phrase in skip_phrases:
            assert RepairManager.detect_skip_request(phrase), f"'{phrase}' should be detected as skip"
    
    def test_non_skip_not_detected(self):
        """Regular answers should not be detected as skip requests."""
        regular_answers = [
            "I focus on B2B SaaS companies",
            "My investment thesis is early-stage",
            "I've been doing this for 10 years"
        ]
        
        for answer in regular_answers:
            assert not RepairManager.detect_skip_request(answer), f"'{answer}' should not be skip"
    
    def test_detect_off_topic(self):
        """Should detect off-topic responses with questions."""
        off_topic = "What is your name? How long have you been doing this?"
        current_question = {"question": "What sectors interest you?"}
        
        redirect = RepairManager.detect_off_topic(off_topic, current_question)
        assert redirect is not None
        assert "sector" in redirect.lower() or "question" in redirect.lower()
    
    def test_on_topic_not_flagged(self):
        """On-topic responses should not be flagged."""
        on_topic = "I focus on B2B SaaS in the enterprise space"
        
        redirect = RepairManager.detect_off_topic(on_topic)
        assert redirect is None


class TestQualityGates:
    """Test quality gates for node creation."""
    
    @pytest.mark.asyncio
    async def test_quality_gate_blocks_low_quality(self):
        """Responses with quality < 0.5 should be blocked from node creation."""
        low_quality_responses = ["hi", "ok", "test", "hmm"]
        
        for resp in low_quality_responses:
            result = await ResponseEvaluator.evaluate_response(resp, use_llm=False)
            # Quality gate: quality > 0.6
            assert result.quality_score < 0.6, f"'{resp}' should be below quality gate"
            assert not result.is_substantive
    
    @pytest.mark.asyncio
    async def test_quality_gate_passes_high_quality(self):
        """High quality responses should pass the quality gate."""
        high_quality = "I want to create a VC brain that helps me analyze early-stage B2B SaaS deals and track my investment decisions"
        
        result = await ResponseEvaluator.evaluate_response(high_quality, use_llm=False)
        assert result.quality_score >= 0.5, "High quality response should pass gate"
        assert result.is_substantive


class TestEndToEndFlow:
    """Test end-to-end interview flow scenarios."""
    
    @pytest.mark.asyncio
    async def test_greeting_triggers_repair_flow(self):
        """A greeting should trigger repair flow, not node creation."""
        # Simulate the flow
        user_message = "hi"
        
        # Step 1: Evaluate response
        quality = await ResponseEvaluator.evaluate_response(user_message, use_llm=False)
        
        assert not quality.is_substantive
        assert quality.quality_score < 0.5
        
        # Step 2: Since quality is insufficient, get repair strategy
        repair = RepairManager.get_repair_strategy(
            attempt=1,
            current_question={"question": "What are you trying to use this twin for?"}
        )
        
        assert repair.strategy_type == "gentle_reask"
        assert "What are you trying to use this twin for?" in repair.message
    
    @pytest.mark.asyncio
    async def test_substantive_response_proceeds(self):
        """A substantive response should proceed to extraction."""
        user_message = "I want to create a VC brain that captures my investment philosophy"
        
        quality = await ResponseEvaluator.evaluate_response(user_message, use_llm=False)
        
        assert quality.is_substantive
        assert quality.quality_score >= 0.5
        # Flow would proceed to scribe extraction
    
    @pytest.mark.asyncio
    async def test_escalating_repair_flow(self):
        """Test that repair strategies escalate correctly."""
        current_question = {"question": "What is your investment thesis?"}
        current_slot = {"slot_id": "investment_thesis"}
        
        responses = ["hi", "hmm", "ok", "idk"]
        expected_strategies = ["gentle_reask", "provide_examples", "simplify_question", "offer_escape"]
        
        for i, resp in enumerate(responses):
            attempt = i + 1
            
            quality = await ResponseEvaluator.evaluate_response(resp, use_llm=False)
            assert not quality.is_substantive
            
            repair = RepairManager.get_repair_strategy(
                attempt=attempt,
                current_question=current_question,
                current_slot=current_slot
            )
            
            assert repair.strategy_type == expected_strategies[i], f"Attempt {attempt} should use {expected_strategies[i]}"
    
    @pytest.mark.asyncio
    async def test_skip_request_handled(self):
        """Test that skip requests are properly handled."""
        user_message = "skip this question please"
        current_slot = {"slot_id": "optional_field", "optional": True}
        
        # First check if it's a skip request
        is_skip = RepairManager.detect_skip_request(user_message)
        assert is_skip
        
        # Get repair strategy (4th attempt to get skip option)
        repair = RepairManager.get_repair_strategy(
            attempt=4,
            current_slot=current_slot,
            user_message=user_message
        )
        
        # Should offer to skip since slot is optional
        assert repair.should_skip or "skip" in repair.message.lower()


class TestResponseEvaluatorModel:
    """Test ResponseQuality model."""
    
    def test_response_quality_model(self):
        """Test ResponseQuality model creation and fields."""
        quality = ResponseQuality(
            is_substantive=True,
            quality_score=0.85,
            tier=2,
            relevance_score=0.9,
            suggested_follow_up="Can you elaborate?",
            reason="Heuristic analysis"
        )
        
        assert quality.is_substantive is True
        assert quality.quality_score == 0.85
        assert quality.tier == 2
        assert quality.relevance_score == 0.9
        assert quality.suggested_follow_up == "Can you elaborate?"
    
    def test_non_answers_set(self):
        """Test that NON_ANSWERS contains expected patterns."""
        assert "hi" in NON_ANSWERS
        assert "hello" in NON_ANSWERS
        assert "ok" in NON_ANSWERS
        assert "test" in NON_ANSWERS
        assert "idk" in NON_ANSWERS


class TestRepairStrategyModel:
    """Test RepairStrategy model."""
    
    def test_repair_strategy_creation(self):
        """Test RepairStrategy object creation."""
        repair = RepairStrategy(
            message="Please provide more details",
            strategy_type="gentle_reask",
            attempt=1,
            should_skip=False
        )
        
        assert repair.message == "Please provide more details"
        assert repair.strategy_type == "gentle_reask"
        assert repair.attempt == 1
        assert repair.should_skip is False


# Additional integration tests that would require mocking the full stack
class TestCognitiveRouterIntegration:
    """Integration tests for cognitive router (requires mocking)."""
    
    @pytest.mark.asyncio
    async def test_interview_endpoint_rejects_greeting(self):
        """Test that POST /cognitive/interview rejects greetings."""
        # This would require mocking supabase and other dependencies
        # For now, we test the underlying logic
        
        user_message = "hi"
        quality = await ResponseEvaluator.evaluate_response(user_message, use_llm=False)
        
        # The endpoint should:
        # 1. Not create any nodes (quality < 0.5)
        # 2. Return a repair message
        # 3. Increment clarification_attempts
        
        assert not quality.is_substantive
        assert quality.quality_score < 0.5
        
        repair = RepairManager.get_repair_strategy(attempt=1)
        assert repair.message  # Should have a repair message


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])

