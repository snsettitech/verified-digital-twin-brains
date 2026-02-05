# backend/tests/test_api_integration.py
"""Integration tests for Phase 2 API endpoints.

Uses FastAPI TestClient to verify:
- Endpoint routing and availability
- Request validation
- Response formatting
- Error handling
"""

import sys
import os
import unittest
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from main import app

from modules.auth_guard import get_current_user
client = TestClient(app)

@pytest.fixture(autouse=True)
def _override_auth_and_supabase():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user", "tenant_id": "test-tenant"}
    with patch("modules.observability.supabase", MagicMock()), \
         patch("modules.ingestion.process_and_index_text", new_callable=AsyncMock, return_value=5):
        yield
    app.dependency_overrides = {}

class TestIngestionAPI(unittest.TestCase):
    
    @patch('modules.web_crawler.crawl_website')
    def test_crawl_website_endpoint(self, mock_crawl):
        """Test POST /ingest/website/{twin_id}"""
        mock_crawl.return_value = {"success": True, "source_id": "src-123", "pages_crawled": 5}
        
        response = client.post(
            "/ingest/website/twin-123",
            json={"url": "https://example.com", "max_pages": 5}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_id"], "src-123")
        mock_crawl.assert_called_once()
    
    @patch('modules.web_crawler.scrape_single_page')
    def test_single_page_endpoint(self, mock_scrape):
        """Test POST /ingest/website/{twin_id}/single"""
        mock_scrape.return_value = {
            "success": True, 
            "content": "# Title\nBody", 
            "metadata": {"title": "Test"}
        }
        
        response = client.post(
            "/ingest/website/twin-123/single",
            json={"url": "https://example.com/page"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
    
    @patch('modules.social_ingestion.RSSFetcher.ingest_feed')
    def test_rss_endpoint(self, mock_ingest):
        """Test POST /ingest/rss/{twin_id}"""
        mock_ingest.return_value = {"success": True, "entries_ingested": 10}
        
        response = client.post(
            "/ingest/rss/twin-123",
            json={"url": "https://example.com/feed.xml"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entries_ingested"], 10)

    @patch('modules.social_ingestion.TwitterScraper.ingest_user_tweets')
    def test_twitter_endpoint(self, mock_ingest):
        """Test POST /ingest/twitter/{twin_id}"""
        mock_ingest.return_value = {"success": True, "username": "test", "tweets_ingested": 20}
        
        response = client.post(
            "/ingest/twitter/twin-123",
            json={"username": "testuser"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "test")

    @patch('modules.auto_updater.PipelineManager.create_pipeline')
    def test_create_pipeline(self, mock_create):
        """Test POST /pipelines/{twin_id}"""
        mock_create.return_value = {"success": True, "pipeline_id": "pipe-123"}
        
        response = client.post(
            "/pipelines/twin-123",
            json={
                "source_url": "https://example.com",
                "source_type": "website",
                "schedule_hours": 12
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pipeline_id"], "pipe-123")
        
    @patch('modules.auto_updater.PipelineManager.list_pipelines')
    def test_list_pipelines(self, mock_list):
        """Test GET /pipelines/{twin_id}"""
        mock_list.return_value = [{"id": "pipe-1", "source_url": "http://a.com"}]
        
        response = client.get("/pipelines/twin-123")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["pipelines"]), 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
