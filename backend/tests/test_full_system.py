# backend/tests/test_full_system.py
"""Full System Integration Test (Verification Loop 2).

Verifies the "Life of a Thought":
1. Ingestion triggers (Mocked)
2. Reasoning Engine activation
3. Response Generation with Decision Trace
"""

import sys
import os
import unittest
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from main import app
from modules.reasoning_engine import DecisionTrace, StanceType, LogicStep
from modules.auth_guard import get_current_user

client = TestClient(app)

@pytest.fixture(autouse=True)
def _override_auth_and_supabase():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user", "tenant_id": "test-tenant"}
    with patch("modules.observability.supabase", MagicMock()) as mock_sb, \
         patch("modules.ingestion.process_and_index_text", new_callable=AsyncMock, return_value=1):
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "settings": {},
            "tenant_id": "test-tenant"
        }
        yield
    app.dependency_overrides = {}

class TestFullSystemFlow(unittest.TestCase):
    
    @patch('modules.reasoning_engine.ReasoningEngine.predict_stance')
    @patch('modules.graph_context.get_graph_stats')
    def test_life_of_a_thought(self, mock_stats, mock_predict):
        """
        Verify end-to-end flow:
        User asks "Would I...?" -> Reasoning Engine -> Decision Trace -> API Response
        """
        # 1. Setup Twins State (Mock Graph)
        mock_stats.return_value = {"has_graph": True, "node_count": 50}
        
        # 2. Mock Reasoning Result
        mock_trace = DecisionTrace(
            topic="Space Travel",
            final_stance=StanceType.POSITIVE,
            confidence_score=0.99,
            logic_chain=[
                LogicStep(step_number=1, description="I value 'Exploration'.", nodes_involved=["n1"], inference_type="match"),
                LogicStep(step_number=2, description="'Space Travel' is the ultimate exploration.", nodes_involved=[], inference_type="deduction")
            ],
            key_factors=["Exploration", "Future"]
        )
        mock_predict.return_value = mock_trace
        
        # 3. Simulate User Query
        query = "Would I want to go to Mars?"
        response = client.post(
            "/chat/twin-123",
            json={"query": query, "conversation_id": "conv-full-flow"}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # 4. Analyze Stream Response
        stream_content = response.text
        blocks = []
        for line in stream_content.strip().split('\n'):
            if line:
                try: blocks.append(json.loads(line))
                except: pass
                
        # 5. Verify Decision Trace is present in Metadata
        metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
        self.assertIsNotNone(metadata, "Metadata block missing from response")
        self.assertIn("decision_trace", metadata, "Decision trace missing from metadata")
        
        trace = metadata["decision_trace"]
        self.assertEqual(trace["final_stance"], "positive")
        self.assertEqual(trace["confidence_score"], 0.99)
        self.assertEqual(len(trace["logic_chain"]), 2)
        
        # 6. Verify Content Block matches trace readable output
        content_block = next((b for b in blocks if b.get("type") == "content"), None)
        self.assertIsNotNone(content_block)
        self.assertIn("POSITIVE", content_block["content"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
