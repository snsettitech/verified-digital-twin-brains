"""
5-Layer Persona Agent Integration Tests

Tests for the integration between the 5-Layer Persona Model and the LangGraph agent.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.persona_agent_integration import (
    should_use_5layer_persona,
    get_persona_v2_state_defaults,
    build_persona_v2_state_updates,
    PersonaAgentIntegration,
    PersonaIntegrationResult,
    maybe_use_5layer_persona,
)
from modules.persona_spec_v2 import PersonaSpecV2, IdentityFrame
from modules.persona_decision_schema import StructuredDecisionOutput, DimensionScore


# =============================================================================
# Feature Flag Tests
# =============================================================================

class TestFeatureFlag:
    """Tests for 5-Layer persona feature flag"""
    
    def test_should_use_5layer_disabled_globally(self):
        """Test that 5-Layer is disabled when global flag is off"""
        with patch('modules.persona_agent_integration.PERSONA_5LAYER_ENABLED', False):
            state = {}
            assert should_use_5layer_persona(state) is False
    
    def test_should_use_5layer_enabled_globally(self):
        """Test that 5-Layer is enabled when global flag is on"""
        with patch('modules.persona_agent_integration.PERSONA_5LAYER_ENABLED', True):
            state = {}
            assert should_use_5layer_persona(state) is True
    
    def test_should_use_5layer_state_override_true(self):
        """Test state override can enable 5-Layer"""
        with patch('modules.persona_agent_integration.PERSONA_5LAYER_ENABLED', True):
            state = {"use_5layer_persona": True}
            assert should_use_5layer_persona(state) is True
    
    def test_should_use_5layer_state_override_false(self):
        """Test state override can disable 5-Layer"""
        with patch('modules.persona_agent_integration.PERSONA_5LAYER_ENABLED', True):
            state = {"use_5layer_persona": False}
            assert should_use_5layer_persona(state) is False
    
    def test_should_use_5layer_twin_settings(self):
        """Test twin settings can control 5-Layer"""
        with patch('modules.persona_agent_integration.PERSONA_5LAYER_ENABLED', True):
            state = {
                "full_settings": {"use_5layer_persona": True}
            }
            assert should_use_5layer_persona(state) is True


# =============================================================================
# State Management Tests
# =============================================================================

class TestStateManagement:
    """Tests for 5-Layer persona state management"""
    
    def test_get_persona_v2_state_defaults(self):
        """Test default state values"""
        defaults = get_persona_v2_state_defaults()
        assert defaults["persona_v2_enabled"] is False
        assert defaults["persona_v2_dimension_scores"] == {}
        assert defaults["persona_v2_safety_blocked"] is False
    
    def test_build_persona_v2_state_updates(self):
        """Test building state updates from decision output"""
        decision = StructuredDecisionOutput(
            query_summary="test",
            query_type="evaluation",
            dimension_scores=[
                DimensionScore(dimension="market", score=4, reasoning="", confidence=0.8),
                DimensionScore(dimension="founder", score=5, reasoning="", confidence=0.9),
            ],
            overall_score=4.5,
            persona_version="2.0.0",
            processing_time_ms=100,
            consistency_hash="abc123",
        )
        
        updates = build_persona_v2_state_updates(decision)
        
        assert updates["persona_v2_enabled"] is True
        assert updates["persona_v2_spec_version"] == "2.0.0"
        assert updates["persona_v2_dimension_scores"]["market"] == 4
        assert updates["persona_v2_dimension_scores"]["founder"] == 5
        assert updates["persona_v2_overall_score"] == 4.5
        assert updates["persona_v2_consistency_hash"] == "abc123"


# =============================================================================
# PersonaAgentIntegration Tests
# =============================================================================

class TestPersonaAgentIntegration:
    """Tests for PersonaAgentIntegration class"""
    
    @pytest.fixture
    def mock_state(self):
        """Create a mock state"""
        return {
            "twin_id": "test_twin_123",
            "messages": [],
            "full_settings": {},
        }
    
    @pytest.fixture
    def sample_spec(self):
        """Create a sample persona spec"""
        return PersonaSpecV2(
            version="2.0.0",
            name="Test Investor",
            identity_frame=IdentityFrame(
                role_definition="Angel Investor",
                reasoning_style="analytical",
            ),
        )
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_state, sample_spec):
        """Test successful initialization"""
        integration = PersonaAgentIntegration(mock_state)
        
        with patch('modules.persona_agent_integration.get_active_persona_spec_unified') as mock_get:
            mock_get.return_value = {
                "is_v2": True,
                "spec": sample_spec.model_dump(),
            }
            
            success = await integration.initialize()
            
            assert success is True
            assert integration.spec is not None
            assert integration.engine is not None
    
    @pytest.mark.asyncio
    async def test_initialize_not_v2(self, mock_state):
        """Test initialization fails when spec is not v2"""
        integration = PersonaAgentIntegration(mock_state)
        
        with patch('modules.persona_agent_integration.get_active_persona_spec_unified') as mock_get:
            mock_get.return_value = {
                "is_v2": False,
                "spec": {},
            }
            
            success = await integration.initialize()
            
            assert success is False
    
    @pytest.mark.asyncio
    async def test_initialize_no_spec(self, mock_state):
        """Test initialization fails when no spec found"""
        integration = PersonaAgentIntegration(mock_state)
        
        with patch('modules.persona_agent_integration.get_active_persona_spec_unified') as mock_get:
            mock_get.return_value = None
            
            success = await integration.initialize()
            
            assert success is False
    
    @pytest.mark.asyncio
    async def test_process_query_success(self, mock_state, sample_spec):
        """Test successful query processing"""
        integration = PersonaAgentIntegration(mock_state)
        
        # Mock the engine's decide method
        mock_decision = StructuredDecisionOutput(
            query_summary="test query",
            query_type="evaluation",
            natural_language_response="This looks promising!",
            dimension_scores=[
                DimensionScore(dimension="market", score=4, reasoning="Large TAM", confidence=0.8),
            ],
            overall_confidence=0.75,
            safety_blocked=False,
            persona_version="2.0.0",
        )
        
        with patch.object(integration, 'initialize', return_value=True):
            integration.engine = MagicMock()
            integration.engine.decide = AsyncMock(return_value=mock_decision)
            
            result = await integration.process_query(
                query="What do you think of this startup?",
                context={},
            )
            
            assert result.used_5layer is True
            assert result.safety_blocked is False
            assert result.confidence == 0.75
            assert "This looks promising!" in result.answer_points
    
    @pytest.mark.asyncio
    async def test_process_query_safety_blocked(self, mock_state, sample_spec):
        """Test safety boundary blocking"""
        integration = PersonaAgentIntegration(mock_state)
        
        mock_decision = StructuredDecisionOutput(
            query_summary="test query",
            query_type="evaluation",
            natural_language_response="I can't provide investment advice.",
            safety_blocked=True,
            persona_version="2.0.0",
        )
        
        with patch.object(integration, 'initialize', return_value=True):
            integration.engine = MagicMock()
            integration.engine.decide = AsyncMock(return_value=mock_decision)
            
            result = await integration.process_query(
                query="Should I invest $10,000?",
                context={},
            )
            
            assert result.used_5layer is True
            assert result.safety_blocked is True
            assert "can't provide investment advice" in result.answer_points[0]
    
    @pytest.mark.asyncio
    async def test_process_query_not_initialized(self, mock_state):
        """Test processing when engine not initialized"""
        integration = PersonaAgentIntegration(mock_state)
        
        with patch.object(integration, 'initialize', return_value=False):
            result = await integration.process_query(
                query="What do you think?",
                context={},
            )
            
            assert result.used_5layer is False
            assert result.error is not None


# =============================================================================
# Integration Flow Tests
# =============================================================================

class TestIntegrationFlow:
    """Tests for end-to-end integration flow"""
    
    @pytest.mark.asyncio
    async def test_maybe_use_5layer_for_evaluation_query(self):
        """Test 5-Layer is used for evaluation-type queries"""
        state = {
            "twin_id": "test_twin",
            "messages": [],
        }
        query = "What do you think of this fintech startup?"
        context_data = [{"text": "Market is large", "source_id": "s1"}]
        
        mock_decision = StructuredDecisionOutput(
            query_summary=query,
            query_type="evaluation",
            natural_language_response="Strong potential!",
            dimension_scores=[
                DimensionScore(dimension="market", score=4, reasoning="", confidence=0.8),
            ],
            safety_blocked=False,
            persona_version="2.0.0",
        )
        
        with patch('modules.persona_agent_integration.PERSONA_5LAYER_ENABLED', True):
            with patch('modules.persona_agent_integration.get_active_persona_spec_unified') as mock_get:
                mock_get.return_value = {
                    "is_v2": True,
                    "spec": PersonaSpecV2(
                        version="2.0.0",
                        identity_frame=IdentityFrame(role_definition="Investor"),
                    ).model_dump(),
                }
                
                with patch('modules.persona_decision_engine.PersonaDecisionEngine.decide') as mock_decide:
                    mock_decide.return_value = mock_decision
                    
                    used, result = await maybe_use_5layer_persona(state, query, context_data)
                    
                    assert used is True
                    assert result is not None
                    assert result.used_5layer is True
    
    @pytest.mark.asyncio
    async def test_maybe_use_5layer_skips_non_evaluation(self):
        """Test 5-Layer is skipped for non-evaluation queries"""
        state = {
            "twin_id": "test_twin",
            "messages": [],
        }
        query = "What is the weather today?"
        context_data = []
        
        with patch('modules.persona_agent_integration.PERSONA_5LAYER_ENABLED', True):
            used, result = await maybe_use_5layer_persona(state, query, context_data)
            
            # Should skip because it's not an evaluation query
            assert used is False
            assert result is None


# =============================================================================
# State Update Tests
# =============================================================================

class TestStateUpdates:
    """Tests for state update building"""
    
    def test_build_state_updates_complete(self):
        """Test building complete state updates"""
        decision = StructuredDecisionOutput(
            query_summary="test",
            query_type="evaluation",
            dimension_scores=[
                DimensionScore(dimension="market", score=4, reasoning="Large TAM", confidence=0.85),
                DimensionScore(dimension="founder", score=5, reasoning="Strong team", confidence=0.92),
                DimensionScore(dimension="traction", score=3, reasoning="Early", confidence=0.65),
            ],
            overall_score=4.0,
            overall_confidence=0.81,
            values_prioritized=["team_quality", "market_size"],
            reasoning_steps=["Classified query", "Applied heuristics", "Scored dimensions"],
            natural_language_response="Looks promising!",
            persona_version="2.0.1",
            processing_time_ms=45,
            consistency_hash="hash123",
            safety_blocked=False,
        )
        
        updates = build_persona_v2_state_updates(decision)
        
        assert updates["persona_v2_enabled"] is True
        assert updates["persona_v2_dimension_scores"]["market"] == 4
        assert updates["persona_v2_dimension_scores"]["founder"] == 5
        assert updates["persona_v2_dimension_scores"]["traction"] == 3
        assert updates["persona_v2_overall_score"] == 4.0
        assert updates["persona_v2_values_prioritized"] == ["team_quality", "market_size"]
        assert len(updates["persona_v2_reasoning_steps"]) == 3
        assert updates["persona_v2_consistency_hash"] == "hash123"
        assert updates["persona_v2_processing_time_ms"] == 45


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
