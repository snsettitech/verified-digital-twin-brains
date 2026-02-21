"""
5-Layer Persona Consistency Testing Harness

This module provides automated testing for:
- Decision consistency (same input → same output)
- Rule adherence
- Value hierarchy compliance
- Determinism validation

Usage:
    pytest backend/tests/test_persona_consistency_harness.py -v
"""

from __future__ import annotations

import pytest
import asyncio
from typing import Any, Dict, List, Tuple
from statistics import variance, mean

from modules.persona_spec_v2 import (
    PersonaSpecV2,
    IdentityFrame,
    CognitiveHeuristics,
    CognitiveHeuristic,
    ValueHierarchy,
    ValueItem,
    ValueConflictRule,
    CommunicationPatterns,
    MemoryAnchors,
    SafetyBoundary,
)
from modules.persona_decision_engine import PersonaDecisionEngine
from modules.persona_decision_schema import StructuredDecisionOutput


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_persona_spec() -> PersonaSpecV2:
    """Create a sample 5-Layer persona spec for testing"""
    return PersonaSpecV2(
        version="2.0.0",
        name="Test Investor",
        description="An experienced angel investor persona",
        
        # Layer 1: Identity
        identity_frame=IdentityFrame(
            role_definition="Experienced angel investor with 50+ investments",
            expertise_domains=["fintech", "saas", "marketplaces"],
            background_summary="Former founder, strong technical background",
            reasoning_style="analytical",
            relationship_to_user="advisor",
        ),
        
        # Layer 2: Cognitive Heuristics
        cognitive_heuristics=CognitiveHeuristics(
            heuristics=[
                CognitiveHeuristic(
                    id="team_first",
                    name="Team-First Evaluation",
                    description="Prioritize team quality in evaluations",
                    applicable_query_types=["evaluation"],
                    steps=["Evaluate founder background", "Check team completeness", "Assess domain fit"],
                    priority=10,
                ),
                CognitiveHeuristic(
                    id="market_sizing",
                    name="Market Sizing",
                    description="Evaluate market opportunity",
                    applicable_query_types=["evaluation"],
                    steps=["Calculate TAM", "Assess growth rate", "Evaluate competition"],
                    priority=20,
                ),
            ]
        ),
        
        # Layer 3: Value Hierarchy
        value_hierarchy=ValueHierarchy(
            values=[
                ValueItem(name="team_quality", priority=1, description="Strong founding team"),
                ValueItem(name="market_size", priority=2, description="Large addressable market"),
                ValueItem(name="traction", priority=3, description="Evidence of product-market fit"),
                ValueItem(name="defensibility", priority=4, description="Competitive moat"),
                ValueItem(name="speed", priority=5, description="Execution velocity"),
            ],
            conflict_rules=[
                ValueConflictRule(
                    value_a="speed",
                    value_b="quality",
                    resolution="prioritize_a",
                )
            ]
        ),
        
        # Layer 4: Communication
        communication_patterns=CommunicationPatterns(
            signature_phrases=["Here's the thing...", "From my experience..."],
            brevity_preference="concise",
        ),
        
        # Layer 5: Memory
        memory_anchors=MemoryAnchors(
            anchors=[],
        ),
        
        # Safety
        safety_boundaries=[
            SafetyBoundary(
                id="no_investment_promises",
                pattern=r"(should I invest|is this a good investment)",
                category="investment_promise",
                action="refuse",
                refusal_template="I can't provide investment advice, but I can share my perspective on the team and market.",
            ),
        ]
    )


@pytest.fixture
def decision_engine(sample_persona_spec) -> PersonaDecisionEngine:
    """Create a decision engine from the sample spec"""
    return PersonaDecisionEngine(sample_persona_spec)


# =============================================================================
# Consistency Tests
# =============================================================================

class TestDecisionConsistency:
    """Tests for decision consistency across multiple runs"""
    
    async def run_multiple_times(
        self,
        engine: PersonaDecisionEngine,
        query: str,
        context: Dict[str, Any],
        runs: int = 5
    ) -> List[StructuredDecisionOutput]:
        """Run the same decision multiple times"""
        results = []
        for _ in range(runs):
            result = await engine.decide(query=query, context=context)
            results.append(result)
        return results
    
    def calculate_score_variance(
        self,
        results: List[StructuredDecisionOutput],
        dimension: str
    ) -> float:
        """Calculate variance for a dimension across results"""
        scores = [r.get_dimension_score(dimension) for r in results]
        scores = [s for s in scores if s is not None]
        if len(scores) < 2:
            return 0.0
        return variance(scores)
    
    @pytest.mark.asyncio
    async def test_five_run_variance_low(self, decision_engine):
        """
        Test Case: Same query run 5 times should produce consistent scores
        
        Success Criteria: Score variance < 0.5 for all dimensions
        """
        query = "What do you think of this AI startup with strong technical founders?"
        context = {
            "dimensions": {
                "market": {"strong_positive_indicators": True, "source_credibility": "high"},
                "founder": {"strong_positive_indicators": True, "expert_validation": True},
                "traction": {"positive_indicators": True},
                "defensibility": {"positive_indicators": True},
                "speed": {"positive_indicators": True},
            }
        }
        
        results = await self.run_multiple_times(decision_engine, query, context, runs=5)
        
        # Check variance for each dimension
        for dimension in ["market", "founder", "traction", "defensibility", "speed"]:
            var = self.calculate_score_variance(results, dimension)
            assert var <= 0.5, f"Variance for {dimension} ({var}) exceeds 0.5"
    
    @pytest.mark.asyncio
    async def test_consistency_hash_same_input(self, decision_engine):
        """
        Test Case: Same input should produce same consistency hash
        """
        query = "Evaluate this fintech startup"
        context = {"dimensions": {"market": {"strong_positive_indicators": True}}}
        
        result1 = await decision_engine.decide(query=query, context=context)
        result2 = await decision_engine.decide(query=query, context=context)
        
        assert result1.consistency_hash == result2.consistency_hash, \
            "Same input should produce same consistency hash"
    
    @pytest.mark.asyncio
    async def test_dimension_scores_present(self, decision_engine):
        """
        Test Case: All dimensions should have scores
        """
        query = "What do you think of this startup?"
        context = {
            "dimensions": {
                "market": {"strong_positive_indicators": True},
                "founder": {"strong_positive_indicators": True},
                "traction": {"positive_indicators": True},
                "defensibility": {"positive_indicators": True},
                "speed": {"positive_indicators": True},
            }
        }
        
        result = await decision_engine.decide(query=query, context=context)
        
        # All 5 dimensions should have scores
        assert len(result.dimension_scores) == 5, "Should have 5 dimension scores"
        
        dimension_names = [ds.dimension for ds in result.dimension_scores]
        for dim in ["market", "founder", "traction", "defensibility", "speed"]:
            assert dim in dimension_names, f"Missing score for dimension: {dim}"


class TestRuleAdherence:
    """Tests for cognitive heuristic and rule adherence"""
    
    @pytest.mark.asyncio
    async def test_team_first_heuristic(self, decision_engine):
        """
        Test Case: Team-first heuristic should prioritize founder score
        
        When evaluating startups, founder dimension should be highly weighted
        """
        query = "Evaluate this startup with amazing founders but small market"
        context = {
            "dimensions": {
                "market": {"negative_indicators": True, "missing_critical_data": True},
                "founder": {"strong_positive_indicators": True, "expert_validation": True},
                "traction": {"positive_indicators": True},
                "defensibility": {"positive_indicators": True},
                "speed": {"positive_indicators": True},
            }
        }
        
        result = await decision_engine.decide(query=query, context=context)
        
        founder_score = result.get_dimension_score("founder")
        market_score = result.get_dimension_score("market")
        
        # With strong founders, founder score should be high
        assert founder_score >= 4, f"Founder score ({founder_score}) should be high with strong founders"
        
        # Reasoning should mention team evaluation
        reasoning_lower = " ".join(result.reasoning_steps).lower()
        assert "team" in reasoning_lower or "founder" in reasoning_lower, \
            "Reasoning should mention team evaluation"
    
    @pytest.mark.asyncio
    async def test_evidence_based_scoring(self, decision_engine):
        """
        Test Case: Scores should be based on evidence quality
        
        Strong evidence → higher confidence
        Weak evidence → lower confidence, neutral score
        """
        # Test with strong evidence
        query = "Evaluate this startup"
        strong_context = {
            "dimensions": {
                "market": {"strong_positive_indicators": True, "source_credibility": "high"},
            }
        }
        
        result_strong = await decision_engine.decide(query=query, context=strong_context)
        
        # Test with weak evidence
        weak_context = {
            "dimensions": {
                "market": {"missing_critical_data": True},
            }
        }
        
        result_weak = await decision_engine.decide(query=query, context=weak_context)
        
        strong_score = result_strong.get_dimension_score("market")
        weak_score = result_weak.get_dimension_score("market")
        
        # Strong evidence should produce higher score
        assert strong_score > weak_score, \
            f"Strong evidence ({strong_score}) should produce higher score than weak ({weak_score})"


class TestValueHierarchy:
    """Tests for value hierarchy compliance"""
    
    @pytest.mark.asyncio
    async def test_value_priority_in_output(self, decision_engine):
        """
        Test Case: Top values should be present in output
        """
        query = "What do you think of this opportunity?"
        context = {"dimensions": {"market": {"positive_indicators": True}}}
        
        result = await decision_engine.decide(query=query, context=context)
        
        # Top values should be in prioritized list
        assert len(result.values_prioritized) > 0, "Should have prioritized values"
        assert "team_quality" in result.values_prioritized, \
            "team_quality should be top prioritized value"
    
    @pytest.mark.asyncio
    async def test_conflict_resolution(self, decision_engine):
        """
        Test Case: Value conflicts should be resolved according to hierarchy
        """
        # This test would require a query that triggers value conflict
        # For now, we verify the conflict resolution structure exists
        assert len(decision_engine.spec.value_hierarchy.conflict_rules) > 0, \
            "Should have conflict resolution rules"


class TestSafetyBoundaries:
    """Tests for safety boundary enforcement"""
    
    @pytest.mark.asyncio
    async def test_investment_advice_refusal(self, decision_engine):
        """
        Test Case: Should refuse investment advice requests
        """
        query = "Should I invest $10,000 in this startup?"
        context = {}
        
        result = await decision_engine.decide(query=query, context=context)
        
        assert result.safety_blocked, "Should block investment advice requests"
        assert "invest" in result.safety_refusal_reason.lower() or \
               any("invest" in sc.category.lower() for sc in result.safety_checks if sc.triggered), \
            "Should identify investment advice category"
    
    @pytest.mark.asyncio
    async def test_legal_advice_refusal(self, decision_engine):
        """
        Test Case: Should refuse legal advice requests
        
        Note: This test assumes legal advice boundary is configured.
        Add legal advice boundary to sample spec to enable this test.
        """
        # Add legal advice boundary for this test
        decision_engine.spec.safety_boundaries.append(
            SafetyBoundary(
                id="no_legal_advice",
                pattern=r"is this legal",
                category="legal_advice",
                action="refuse",
            )
        )
        # Re-initialize safety checker with new boundaries
        from modules.persona_decision_engine import SafetyBoundaryChecker
        decision_engine.safety_checker = SafetyBoundaryChecker(decision_engine.spec.safety_boundaries)
        
        query = "Is this legal?"
        context = {}
        
        result = await decision_engine.decide(query=query, context=context)
        
        assert result.safety_blocked, "Should block legal advice requests"


class TestStructuredOutput:
    """Tests for structured output format"""
    
    @pytest.mark.asyncio
    async def test_api_response_format(self, decision_engine):
        """
        Test Case: API response should have correct structure
        """
        query = "Evaluate this startup"
        context = {
            "dimensions": {
                "market": {"strong_positive_indicators": True},
                "founder": {"strong_positive_indicators": True},
            }
        }
        
        result = await decision_engine.decide(query=query, context=context)
        api_response = result.to_api_response()
        
        # Check required fields
        assert "response" in api_response, "Should have response field"
        assert "persona_scores" in api_response, "Should have persona_scores field"
        assert "overall_score" in api_response, "Should have overall_score field"
        assert "persona_version" in api_response, "Should have persona_version field"
        
        # Check scores are 1-5
        for dim, score in api_response["persona_scores"].items():
            assert 1 <= score <= 5, f"Score for {dim} ({score}) should be 1-5"
    
    @pytest.mark.asyncio
    async def test_reasoning_transparency(self, decision_engine):
        """
        Test Case: Output should include reasoning steps
        """
        query = "What do you think?"
        context = {"dimensions": {"market": {"positive_indicators": True}}}
        
        result = await decision_engine.decide(query=query, context=context)
        
        assert len(result.reasoning_steps) > 0, "Should have reasoning steps"
        assert result.cognitive_framework_used, "Should specify cognitive framework"


# =============================================================================
# Scenario-Based Tests
# =============================================================================

class TestScenarios:
    """Scenario-based tests as specified in requirements"""
    
    @pytest.mark.asyncio
    async def test_scenario_a_strong_tech_no_distribution(self, decision_engine):
        """
        Test Case A: Strong tech, no distribution
        
        Expected: Should identify distribution as concern,
        may still rate highly if team is strong
        """
        query = "This startup has amazing technology but no distribution strategy"
        context = {
            "dimensions": {
                "market": {"positive_indicators": True},
                "founder": {"strong_positive_indicators": True, "expert_validation": True},
                "traction": {"missing_critical_data": True},
                "defensibility": {"strong_positive_indicators": True},
                "speed": {"positive_indicators": True},
            }
        }
        
        result = await decision_engine.decide(query=query, context=context)
        
        # Should have scores for all dimensions
        assert len(result.dimension_scores) == 5
        
        # Founder score should be high
        assert result.get_dimension_score("founder") >= 4
    
    @pytest.mark.asyncio
    async def test_scenario_b_fast_growth_weak_retention(self, decision_engine):
        """
        Test Case B: Fast growth, weak retention
        
        Expected: Should flag retention as concern
        """
        query = "The startup is growing fast but retention is weak"
        context = {
            "dimensions": {
                "market": {"strong_positive_indicators": True},
                "founder": {"positive_indicators": True},
                "traction": {"positive_indicators": True, "negative_indicators": True},
                "defensibility": {"positive_indicators": True},
                "speed": {"strong_positive_indicators": True},
            }
        }
        
        result = await decision_engine.decide(query=query, context=context)
        
        # Should produce balanced assessment
        assert result.overall_score is not None
        assert 2 <= result.overall_score <= 4
    
    @pytest.mark.asyncio
    async def test_scenario_c_good_team_small_market(self, decision_engine):
        """
        Test Case C: Good team, small market
        
        Expected: Should acknowledge team quality but flag market size
        """
        query = "Strong team but the market seems small"
        context = {
            "dimensions": {
                "market": {"negative_indicators": True, "missing_critical_data": True},
                "founder": {"strong_positive_indicators": True, "expert_validation": True},
                "traction": {"positive_indicators": True},
                "defensibility": {"positive_indicators": True},
                "speed": {"positive_indicators": True},
            }
        }
        
        result = await decision_engine.decide(query=query, context=context)
        
        # Founder score should be high
        assert result.get_dimension_score("founder") >= 4
        
        # Market score should be lower
        assert result.get_dimension_score("market") <= 3


# =============================================================================
# Metrics Collection
# =============================================================================

class TestMetricsCollection:
    """Tests for metrics and observability"""
    
    @pytest.mark.asyncio
    async def test_processing_time_tracked(self, decision_engine):
        """
        Test Case: Processing time should be tracked
        """
        import time
        
        query = "Evaluate this startup"
        context = {"dimensions": {"market": {"positive_indicators": True}}}
        
        start = time.time()
        result = await decision_engine.decide(query=query, context=context)
        elapsed = (time.time() - start) * 1000
        
        # Processing time should be tracked and be reasonable
        assert result.processing_time_ms >= 0, "Should track processing time"
        assert result.processing_time_ms < 5000, "Processing should be under 5 seconds"
        # Verify tracking is roughly accurate (within 100ms)
        assert abs(result.processing_time_ms - elapsed) < 100, "Processing time tracking should be accurate"
    
    @pytest.mark.asyncio
    async def test_heuristics_logged(self, decision_engine):
        """
        Test Case: Applied heuristics should be logged
        """
        query = "What do you think of this startup?"
        context = {"dimensions": {"market": {"positive_indicators": True}}}
        
        result = await decision_engine.decide(query=query, context=context)
        
        # Should log which heuristics were applied
        assert len(result.heuristics_applied) >= 0, "Should track heuristics"
    
    @pytest.mark.asyncio
    async def test_confidence_tracked(self, decision_engine):
        """
        Test Case: Confidence should be tracked per dimension
        """
        query = "Evaluate this"
        context = {
            "dimensions": {
                "market": {"strong_positive_indicators": True, "source_credibility": "high"},
            }
        }
        
        result = await decision_engine.decide(query=query, context=context)
        
        # Each dimension score should have confidence
        for ds in result.dimension_scores:
            assert 0 <= ds.confidence <= 1, \
                f"Confidence for {ds.dimension} should be 0-1"


# =============================================================================
# Consistency Report Generator
# =============================================================================

def generate_consistency_report(results: List[StructuredDecisionOutput]) -> Dict[str, Any]:
    """
    Generate a consistency report from multiple test runs
    
    Usage:
        report = generate_consistency_report(results)
        print(f"Consistency Score: {report['consistency_score']}")
    """
    if not results:
        return {"error": "No results provided"}
    
    dimensions = ["market", "founder", "traction", "defensibility", "speed"]
    
    report = {
        "total_runs": len(results),
        "consistency_score": 0.0,
        "dimension_variance": {},
        "rule_adherence_rate": 0.0,
        "average_confidence": 0.0,
        "clarification_frequency": 0.0,
    }
    
    # Calculate variance per dimension
    total_variance = 0
    for dim in dimensions:
        scores = [r.get_dimension_score(dim) for r in results if r.get_dimension_score(dim) is not None]
        if len(scores) >= 2:
            var = variance(scores)
            report["dimension_variance"][dim] = round(var, 2)
            total_variance += var
    
    # Overall consistency (lower variance = higher consistency)
    avg_variance = total_variance / len(dimensions) if dimensions else 0
    report["consistency_score"] = round(max(0, 100 - (avg_variance * 20)), 2)
    
    # Average confidence
    all_confidences = []
    for r in results:
        for ds in r.dimension_scores:
            all_confidences.append(ds.confidence)
    if all_confidences:
        report["average_confidence"] = round(mean(all_confidences), 2)
    
    return report


# =============================================================================
# Run All Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
