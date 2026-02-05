# backend/tests/test_media_integration.py
"""Integration tests for Phase 5 Media endpoints.

Tests:
- POST /ingest/youtube/{twin_id}
"""

import sys
import os
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from main import app
from modules.auth_guard import get_current_user

client = TestClient(app)

class TestMediaIntegration(unittest.TestCase):
    
    def setUp(self):
        # Override Auth Dependency
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user", "tenant_id": "test-tenant"}
    
    def tearDown(self):
        app.dependency_overrides = {}

    @patch('routers.ingestion.verify_twin_ownership')
    @patch('routers.ingestion.ingest_youtube_transcript_wrapper', new_callable=AsyncMock)
    def test_youtube_endpoint(self, mock_ingest, mock_auth):
        """Test POST /ingest/youtube/{twin_id}"""
        # Mock auth to always succeed
        mock_auth.return_value = True
        mock_ingest.return_value = "src-123"
        
        response = client.post(
            "/ingest/youtube/twin-123",
            json={"url": "http://youtube.com/watch?v=realvideo"}
        )
        
        if response.status_code != 200:
            print(f"FAIL BODY: {response.text}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_id"], "src-123")
        self.assertEqual(response.json()["status"], "processing")
        
        # Verify call
        mock_ingest.assert_called_with("twin-123", "http://youtube.com/watch?v=realvideo")

if __name__ == "__main__":
    unittest.main(verbosity=2)
