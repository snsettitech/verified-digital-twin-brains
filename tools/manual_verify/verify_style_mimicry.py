
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

class TestStyleMimicry(unittest.TestCase):
    @patch('modules.graph_context.supabase')
    def test_style_retrieval(self, mock_supabase):
        # Import inside test to ensure mock is active
        from modules.graph_context import get_style_guidelines
        
        print("Testing Style Guideline Retrieval...")
        
        # Mock node response
        mock_nodes = [
            {"type": "style.tone", "name": "Tone", "description": "Sarcastic and witty"},
            {"type": "style.communication", "name": "Brevity", "description": "Short sentences only"},
            {"type": "knowledge.concept", "name": "Python", "description": "Programming language"} 
        ]
        
        # Configure mock
        mock_response = MagicMock()
        mock_response.data = mock_nodes
        mock_supabase.rpc.return_value.execute.return_value = mock_response
        
        # Run
        guidelines = get_style_guidelines("twin-123")
        
        print("\nGenerated Guidelines:\n" + "="*20)
        print(guidelines)
        print("="*20)
        
        # Verify
        self.assertIn("Sarcastic", guidelines)
        self.assertIn("Short sentences", guidelines)
        self.assertNotIn("Python", guidelines)
        print("PASSED: Style nodes correctly extracted and filtered.")

if __name__ == "__main__":
    unittest.main()
