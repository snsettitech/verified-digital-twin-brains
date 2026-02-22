# backend/tests/test_reasoning_engine.py
"""Unit tests for Phase 3: Reasoning Engine.

Tests:
- Cognitive node retrieval/filtering
- LLM prompt construction (mocked)
- Decision trace parsing
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from modules.reasoning_engine import ReasoningEngine, DecisionTrace, StanceType
from modules import reasoning_engine # Import module for inspection if needed.

class TestReasoningEngine(unittest.TestCase):
    
    @patch('modules.reasoning_engine.get_openai_client')
    @patch('modules.graph_context._select_seeds')
    @patch('modules.graph_context._expand_one_hop')
    def test_find_relevant_cognitive_nodes(self, mock_expand, mock_seeds, mock_client):
        """Test finding and filtering cognitive nodes."""
        import asyncio

        # Mock seeds
        mock_seeds.return_value = [
            {"id": "1", "name": "Value 1", "type": "Value", "description": "Desc 1"},
            {"id": "2", "name": "Fact 1", "type": "Fact", "description": "Desc 2"}
        ]
        # Mock expansion
        mock_expand.return_value = ([], [])
        
        engine = ReasoningEngine("twin-123")
        nodes = asyncio.run(engine._find_relevant_cognitive_nodes("test topic"))
        
        self.assertEqual(len(nodes), 2)
        # Check if type preserved
        self.assertEqual(nodes[0]["type"], "Value")
    
    @patch('modules.reasoning_engine.get_openai_client')
    @patch('modules.graph_context._select_seeds')
    @patch('modules.graph_context._expand_one_hop') 
    def test_predict_stance_success(self, mock_expand, mock_seeds, mock_client):
        """Test full prediction flow with mocked LLM."""
        import asyncio
        
        mock_seeds.return_value = [{"id": "1", "name": "V1", "type": "Value", "description": "D1"}]
        mock_expand.return_value = ([], [])
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "stance": "positive",
            "confidence": 0.85,
            "logic_chain": ["Step 1", "Step 2"],
            "key_factors": ["Factor A"]
        })
        mock_client.return_value.chat.completions.create.return_value = mock_response
        
        engine = ReasoningEngine("twin-123")
        trace = asyncio.run(engine.predict_stance("test topic"))
        
        self.assertEqual(trace.final_stance, StanceType.POSITIVE)
        self.assertEqual(trace.confidence_score, 0.85)
        self.assertEqual(len(trace.logic_chain), 2)
        self.assertEqual(trace.key_factors[0], "Factor A")
        
    def test_decision_trace_formatting(self):
        """Test human-readable trace generation."""
        from modules.reasoning_engine import LogicStep
        
        trace = DecisionTrace(
            topic="Test",
            final_stance=StanceType.NEGATIVE,
            confidence_score=0.9,
            logic_chain=[
                LogicStep(step_number=1, description="Step 1", nodes_involved=[], inference_type="deduction"),
                LogicStep(step_number=2, description="Step 2", nodes_involved=[], inference_type="deduction")
            ],
            key_factors=["Factor 1"]
        )
        
        readable = trace.to_readable_trace()
        
        self.assertIn("NEGATIVE (Confidence: 90%)", readable)
        self.assertIn("1. Step 1", readable)
        self.assertIn("- Factor 1", readable)

if __name__ == "__main__":
    unittest.main(verbosity=2)
