"""
Tests for 5-Layer Persona Bootstrap from Onboarding

These tests verify that onboarding data is correctly converted to
structured 5-Layer Persona Spec v2.
"""

import pytest
from typing import Dict, Any, List

from modules.persona_bootstrap import (
    bootstrap_persona_from_onboarding,
    _build_identity_frame,
    _build_cognitive_heuristics,
    _build_value_hierarchy,
    _build_communication_patterns,
    _build_memory_anchors,
    _get_default_values_for_specialization,
)
from modules.persona_spec_v2 import PersonaSpecV2, ValueItem, CognitiveHeuristic


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def minimal_onboarding_data() -> Dict[str, Any]:
    """Minimal valid onboarding data."""
    return {
        "twin_name": "TestTwin",
        "specialization": "vanilla",
    }


@pytest.fixture
def founder_onboarding_data() -> Dict[str, Any]:
    """Founder specialization onboarding data."""
    return {
        "twin_name": "FounderTwin",
        "tagline": "Startup advisor and operator",
        "specialization": "founder",
        "role_definition": "Experienced founder who has built and scaled multiple startups",
        "selected_domains": ["SaaS", "B2B", "Fintech"],
        "custom_expertise": ["Enterprise Sales", "Fundraising"],
        "background": "Built 3 startups, 2 exits. 15 years in tech.",
        "success_outcomes": ["Series A raised", "Product-market fit achieved"],
        "reasoning_style": "analytical",
        "relationship_type": "mentor",
        "scope": "startup_evaluation",
        "boundaries": ["No investment promises", "No legal advice"],
        "heuristics": [
            {
                "id": "team_first",
                "name": "Team Quality First",
                "description": "Prioritize team evaluation",
                "applicable_types": ["evaluation"],
                "steps": ["Check founder background", "Assess team completeness"],
                "priority": 10,
            }
        ],
        "decision_framework": "evidence_based",
        "clarifying_behavior": "ask",
        "prioritized_values": [
            {"name": "team_quality", "description": "Strong founding team"},
            {"name": "traction", "description": "Product-market fit"},
            {"name": "market_size", "description": "Large addressable market"},
        ],
        "personality": {
            "tone": "professional",
            "response_length": "concise",
            "firstPerson": True,
        },
        "signature_phrases": ["Here's my take", "The key insight is"],
        "key_experiences": [
            {
                "content": "Scaling from 0 to 100 employees",
                "context": "First startup growth phase",
                "applicable_intents": ["advice", "evaluation"],
            }
        ],
    }


# =============================================================================
# Bootstrap Integration Tests
# =============================================================================

class TestBootstrapFromOnboarding:
    """Integration tests for full bootstrap flow."""
    
    def test_minimal_bootstrap(self, minimal_onboarding_data):
        """Test bootstrap with minimal data produces valid spec."""
        spec = bootstrap_persona_from_onboarding(minimal_onboarding_data)
        
        assert isinstance(spec, PersonaSpecV2)
        assert spec.version == "2.0.0"
        assert spec.identity_frame is not None
        assert spec.cognitive_heuristics is not None
        assert spec.value_hierarchy is not None
        assert spec.communication_patterns is not None
        assert spec.memory_anchors is not None
        assert spec.safety_boundaries is not None
        assert len(spec.safety_boundaries) >= 3  # Default boundaries
    
    def test_founder_bootstrap(self, founder_onboarding_data):
        """Test bootstrap with founder data produces detailed spec."""
        spec = bootstrap_persona_from_onboarding(founder_onboarding_data)
        
        # Check identity frame
        assert spec.identity_frame.role_definition == founder_onboarding_data["role_definition"]
        assert "SaaS" in spec.identity_frame.expertise_domains
        assert "Enterprise Sales" in spec.identity_frame.expertise_domains
        assert spec.identity_frame.reasoning_style == "analytical"
        assert spec.identity_frame.relationship_to_user == "mentor"
        
        # Check cognitive heuristics
        assert len(spec.cognitive_heuristics.heuristics) >= 1
        assert any(h.name == "Team Quality First" for h in spec.cognitive_heuristics.heuristics)
        
        # Check value hierarchy
        assert len(spec.value_hierarchy.values) == 3
        assert spec.value_hierarchy.values[0].name == "team_quality"
        assert spec.value_hierarchy.values[0].priority == 1
        
        # Check communication patterns
        assert spec.communication_patterns.brevity_preference == "concise"
        assert "Here's my take" in spec.communication_patterns.signature_phrases
    
    def test_bootstrap_preserves_all_layers(self):
        """Verify all 5 layers are populated from onboarding data."""
        data = {
            "twin_name": "CompleteTwin",
            "specialization": "technical",
            "role_definition": "CTO and technical advisor",
            "heuristics": [{"id": "h1", "name": "Test Heuristic", "priority": 50}],
            "prioritized_values": [
                {"name": "technical_excellence"},
                {"name": "security"},
            ],
            "personality": {"tone": "technical", "response_length": "detailed"},
            "key_experiences": [{"content": "Building scalable systems"}],
        }
        
        spec = bootstrap_persona_from_onboarding(data)
        
        # Layer 1: Identity
        assert spec.identity_frame.role_definition == "CTO and technical advisor"
        
        # Layer 2: Cognitive
        assert len(spec.cognitive_heuristics.heuristics) >= 1
        
        # Layer 3: Values
        assert len(spec.value_hierarchy.values) == 2
        
        # Layer 4: Communication
        assert spec.communication_patterns is not None
        
        # Layer 5: Memory
        assert len(spec.memory_anchors.anchors) >= 1
    
    def test_default_safety_boundaries(self):
        """Verify default safety boundaries are always added."""
        data = {"twin_name": "Test", "specialization": "vanilla"}
        spec = bootstrap_persona_from_onboarding(data)
        
        boundary_ids = [b.id for b in spec.safety_boundaries]
        assert "no_investment_promises" in boundary_ids
        assert "no_legal_advice" in boundary_ids
        assert "no_medical_advice" in boundary_ids
    
    def test_specialization_inferred_heuristics(self):
        """Test that heuristics are inferred from specialization when not provided."""
        data = {
            "twin_name": "Founder",
            "specialization": "founder",
            "what_i_look_for_first": "team",
        }
        spec = bootstrap_persona_from_onboarding(data)
        
        # Should infer team-first heuristic
        heuristic_names = [h.name for h in spec.cognitive_heuristics.heuristics]
        assert any("team" in name.lower() for name in heuristic_names)
    
    def test_clarifying_behavior_adds_heuristic(self):
        """Test that 'ask' clarifying behavior adds clarify-before-evaluate heuristic."""
        data = {
            "twin_name": "Test",
            "specialization": "vanilla",
            "clarifying_behavior": "ask",
        }
        spec = bootstrap_persona_from_onboarding(data)
        
        heuristic_names = [h.name for h in spec.cognitive_heuristics.heuristics]
        assert any("clarify" in name.lower() for name in heuristic_names)


# =============================================================================
# Individual Layer Tests
# =============================================================================

class TestIdentityFrameBuilding:
    """Tests for Layer 1: Identity Frame."""
    
    def test_expertise_domains_combined(self):
        """Test that selected and custom expertise are combined."""
        data = {
            "twin_name": "Test",
            "selected_domains": ["AI", "SaaS"],
            "custom_expertise": ["Leadership", "Strategy"],
        }
        frame = _build_identity_frame(data)
        
        assert "AI" in frame.expertise_domains
        assert "SaaS" in frame.expertise_domains
        assert "Leadership" in frame.expertise_domains
        assert "Strategy" in frame.expertise_domains
    
    def test_role_from_specialization(self):
        """Test role definition is inferred from specialization."""
        test_cases = [
            ("founder", "founder"),
            ("technical", "technical expert"),
            ("vanilla", "professional advisor"),
        ]
        
        for spec, expected in test_cases:
            data = {"twin_name": "Test", "specialization": spec}
            frame = _build_identity_frame(data)
            assert expected in frame.role_definition.lower()
    
    def test_success_outcomes_in_background(self):
        """Test that success outcomes are appended to background."""
        data = {
            "twin_name": "Test",
            "background": "Experienced operator",
            "success_outcomes": ["IPO", "Acquisition"],
        }
        frame = _build_identity_frame(data)
        
        assert "Experienced operator" in frame.background_summary
        assert "IPO" in frame.background_summary
        assert "Acquisition" in frame.background_summary
    
    def test_adaptive_maps_to_balanced(self):
        """Test adaptive reasoning style maps to balanced."""
        data = {
            "twin_name": "Test",
            "reasoning_style": "adaptive",
        }
        frame = _build_identity_frame(data)
        assert frame.reasoning_style == "balanced"


class TestCognitiveHeuristicsBuilding:
    """Tests for Layer 2: Cognitive Heuristics."""
    
    def test_explicit_heuristics_used(self):
        """Test that explicit heuristics from onboarding are used."""
        data = {
            "twin_name": "Test",
            "heuristics": [
                {
                    "id": "h1",
                    "name": "Custom Heuristic",
                    "description": "Test",
                    "applicable_types": ["evaluation"],
                    "steps": ["Step 1", "Step 2"],
                    "priority": 25,
                }
            ],
        }
        heuristics = _build_cognitive_heuristics(data)
        
        assert len(heuristics.heuristics) == 1
        assert heuristics.heuristics[0].name == "Custom Heuristic"
        assert heuristics.heuristics[0].priority == 25
    
    def test_default_evidence_based_heuristic(self):
        """Test that evidence-based heuristic is always included."""
        data = {"twin_name": "Test", "specialization": "vanilla"}
        heuristics = _build_cognitive_heuristics(data)
        
        assert any(h.name == "Evidence-Based Evaluation" for h in heuristics.heuristics)
    
    def test_confidence_thresholds_defaults(self):
        """Test default confidence thresholds."""
        data = {"twin_name": "Test"}
        heuristics = _build_cognitive_heuristics(data)
        
        assert "factual_question" in heuristics.confidence_thresholds
        assert heuristics.confidence_thresholds["factual_question"] > 0


class TestValueHierarchyBuilding:
    """Tests for Layer 3: Value Hierarchy."""
    
    def test_prioritized_values_preserved_order(self):
        """Test that value order from onboarding is preserved as priority."""
        data = {
            "twin_name": "Test",
            "prioritized_values": [
                {"name": "quality", "description": "High quality"},
                {"name": "speed", "description": "Fast execution"},
                {"name": "cost", "description": "Low cost"},
            ],
        }
        hierarchy = _build_value_hierarchy(data)
        
        assert len(hierarchy.values) == 3
        assert hierarchy.values[0].name == "quality"
        assert hierarchy.values[0].priority == 1
        assert hierarchy.values[1].name == "speed"
        assert hierarchy.values[1].priority == 2
        assert hierarchy.values[2].name == "cost"
        assert hierarchy.values[2].priority == 3
    
    def test_default_values_by_specialization(self):
        """Test default values are assigned based on specialization."""
        founder_defaults = _get_default_values_for_specialization("founder")
        assert founder_defaults[0]["name"] == "team_quality"
        
        tech_defaults = _get_default_values_for_specialization("technical")
        assert tech_defaults[0]["name"] == "technical_excellence"
    
    def test_tradeoff_preferences_become_conflict_rules(self):
        """Test that tradeoff preferences are converted to conflict rules."""
        data = {
            "twin_name": "Test",
            "tradeoff_preferences": [
                {
                    "value_a": "speed",
                    "value_b": "quality",
                    "resolution": "context_dependent",
                    "context_override": "prioritize quality for production",
                }
            ],
        }
        hierarchy = _build_value_hierarchy(data)
        
        assert len(hierarchy.conflict_rules) >= 1
        assert hierarchy.conflict_rules[0].value_a == "speed"
        assert hierarchy.conflict_rules[0].value_b == "quality"
    
    def test_scoring_dimensions_defaults(self):
        """Test default scoring dimensions are added."""
        data = {"twin_name": "Test"}
        hierarchy = _build_value_hierarchy(data)
        
        dimension_names = [d.name for d in hierarchy.scoring_dimensions]
        assert "market" in dimension_names
        assert "founder" in dimension_names
        assert "traction" in dimension_names


class TestCommunicationPatternsBuilding:
    """Tests for Layer 4: Communication Patterns."""
    
    def test_tone_maps_to_linguistic_markers(self):
        """Test that tone selection maps to appropriate linguistic markers."""
        data = {
            "twin_name": "Test",
            "personality": {"tone": "professional"},
        }
        patterns = _build_communication_patterns(data)
        
        assert "agreement" in patterns.linguistic_markers
        assert "I concur" in patterns.linguistic_markers["agreement"]
    
    def test_signature_phrases_from_onboarding(self):
        """Test that custom signature phrases are preserved."""
        data = {
            "twin_name": "Test",
            "signature_phrases": ["Custom phrase 1", "Custom phrase 2"],
        }
        patterns = _build_communication_patterns(data)
        
        assert "Custom phrase 1" in patterns.signature_phrases
        assert "Custom phrase 2" in patterns.signature_phrases
    
    def test_brevity_from_response_length(self):
        """Test that response_length maps to brevity_preference."""
        test_cases = [
            ("concise", "concise"),
            ("balanced", "balanced"),
            ("detailed", "detailed"),
        ]
        
        for response_length, expected_brevity in test_cases:
            data = {
                "twin_name": "Test",
                "personality": {"response_length": response_length},
            }
            patterns = _build_communication_patterns(data)
            assert patterns.brevity_preference == expected_brevity


class TestMemoryAnchorsBuilding:
    """Tests for Layer 5: Memory Anchors."""
    
    def test_key_experiences_become_anchors(self):
        """Test that key experiences are converted to memory anchors."""
        data = {
            "twin_name": "Test",
            "key_experiences": [
                {
                    "content": "Led team of 50 engineers",
                    "context": "Growth phase",
                    "applicable_intents": ["leadership", "advice"],
                }
            ],
        }
        memory = _build_memory_anchors(data)
        
        assert len(memory.anchors) == 1
        assert memory.anchors[0].type == "experience"
        assert "Led team of 50 engineers" in memory.anchors[0].content
    
    def test_lessons_learned_separate_type(self):
        """Test that lessons learned are typed as 'lesson'."""
        data = {
            "twin_name": "Test",
            "lessons_learned": [
                {"content": "Always validate assumptions early"}
            ],
        }
        memory = _build_memory_anchors(data)
        
        assert any(a.type == "lesson" for a in memory.anchors)


# =============================================================================
# End-to-End Integration Tests
# =============================================================================

class TestEndToEndBootstrap:
    """Full integration tests with database."""
    
    @pytest.mark.asyncio
    async def test_twin_creation_with_bootstrap(self):
        """
        Integration test: Twin creation bootstraps v2 persona.
        
        This test requires database setup. Mark with @pytest.mark.integration
        to skip in unit test runs.
        """
        pytest.skip("Integration test - requires database")
        
        # Test would go here:
        # 1. Create twin with persona_v2_data
        # 2. Verify persona_spec created in database
        # 3. Verify twin settings updated
        pass
    
    def test_bootstrap_output_is_valid_json(self):
        """Verify bootstrap output can be serialized to JSON."""
        data = founder_onboarding_data()
        spec = bootstrap_persona_from_onboarding(data)
        
        # Should not raise
        json_output = spec.model_dump_json()
        assert isinstance(json_output, str)
        assert len(json_output) > 0
    
    def test_bootstrap_roundtrip(self):
        """Verify spec can be serialized and re-parsed."""
        from modules.persona_spec_v2 import PersonaSpecV2
        
        data = founder_onboarding_data()
        spec = bootstrap_persona_from_onboarding(data)
        
        # Serialize
        json_dict = spec.model_dump()
        
        # Re-parse
        spec2 = PersonaSpecV2.model_validate(json_dict)
        
        assert spec2.identity_frame.role_definition == spec.identity_frame.role_definition
        assert len(spec2.value_hierarchy.values) == len(spec.value_hierarchy.values)


# =============================================================================
# Edge Cases
# =============================================================================

class TestBootstrapEdgeCases:
    """Edge case tests."""
    
    def test_empty_onboarding_data(self):
        """Test bootstrap handles empty data gracefully."""
        data = {}
        spec = bootstrap_persona_from_onboarding(data)
        
        # Should still produce valid spec with defaults
        assert isinstance(spec, PersonaSpecV2)
        assert spec.identity_frame is not None
    
    def test_missing_optional_fields(self):
        """Test bootstrap works without optional fields."""
        data = {"twin_name": "Minimal"}  # Only required field
        spec = bootstrap_persona_from_onboarding(data)
        
        assert spec.identity_frame.role_definition == "Minimal"
        assert len(spec.safety_boundaries) >= 3  # Defaults still applied
    
    def test_specialization_case_handling(self):
        """Test bootstrap handles unknown specializations."""
        data = {
            "twin_name": "Test",
            "specialization": "unknown_specialization",
        }
        spec = bootstrap_persona_from_onboarding(data)
        
        # Should use vanilla defaults
        assert spec is not None
        assert len(spec.cognitive_heuristics.heuristics) > 0
