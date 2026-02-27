"""
Tests for Crawl Ingestion Bridge (Phase 2.1)

Covers:
- Bridge creates sources from crawl pages
- Bridge skips unchanged pages
- Bridge loads content from artifacts
- Twin isolation enforcement
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from modules.crawl_ingestion_bridge import CrawlIngestionBridge


class TestShouldSkipIngestion:
    """Test the skip logic for crawl page ingestion."""
    
    def test_skip_unchanged_page(self):
        """Unchanged pages should be skipped."""
        page = {
            "id": "page_123",
            "status": "fetched",
            "classification": "unchanged",
            "normalized_artifact_path": "crawl/twin_123/crawl_456/pages/page_123/normalized.md"
        }
        
        should_skip, reason = CrawlIngestionBridge().should_skip_ingestion(page)
        
        assert should_skip is True
        assert reason == "unchanged_content"
    
    def test_skip_failed_page(self):
        """Failed pages should be skipped."""
        for status in ["failed", "blocked", "error"]:
            page = {
                "id": "page_123",
                "status": status,
                "classification": "new",
                "normalized_artifact_path": None
            }
            
            should_skip, reason = CrawlIngestionBridge().should_skip_ingestion(page)
            
            assert should_skip is True, f"Status {status} should be skipped"
            assert f"page_status_{status}" == reason
    
    def test_skip_no_artifact_path(self):
        """Pages without normalized artifact path should be skipped."""
        page = {
            "id": "page_123",
            "status": "fetched",
            "classification": "new",
            "normalized_artifact_path": None
        }
        
        should_skip, reason = CrawlIngestionBridge().should_skip_ingestion(page)
        
        assert should_skip is True
        assert reason == "no_normalized_artifact"
    
    def test_skip_missing_artifact(self):
        """Pages with missing artifact file should be skipped."""
        page = {
            "id": "page_123",
            "status": "fetched",
            "classification": "new",
            "normalized_artifact_path": "crawl/twin_123/crawl_456/pages/page_123/normalized.md",
            "crawl_id": "crawl_456",
            "twin_id": "twin_123"
        }
        
        bridge = CrawlIngestionBridge()
        # Mock artifact store to return False for exists
        bridge.artifact_store.artifact_exists = Mock(return_value=False)
        
        should_skip, reason = bridge.should_skip_ingestion(page)

        assert should_skip is True
        assert reason == "artifact_not_found"

    def test_skip_uses_context_twin_id_when_page_row_lacks_it(self):
        """Ingestion should resolve artifact scope from the crawl context, not crawl_pages.twin_id."""
        page = {
            "id": "page_123",
            "status": "fetched",
            "classification": "new",
            "normalized_artifact_path": "artifacts/crawl/twin_123/crawl_456/pages/page_123/normalized.md",
            "crawl_id": "crawl_456",
        }

        bridge = CrawlIngestionBridge()
        bridge.artifact_store.artifact_exists = Mock(return_value=True)

        should_skip, reason = bridge.should_skip_ingestion(page, twin_id="twin_123")

        assert should_skip is False
        assert reason == ""
        bridge.artifact_store.artifact_exists.assert_called_once_with(
            artifact_type="crawl",
            twin_id="twin_123",
            entity_id="crawl_456",
            filename="pages/page_123/normalized.md",
        )
    
    def test_process_changed_page(self):
        """Changed pages should be processed (not skipped)."""
        page = {
            "id": "page_123",
            "status": "fetched",
            "classification": "changed",
            "normalized_artifact_path": "crawl/twin_123/crawl_456/pages/page_123/normalized.md",
            "crawl_id": "crawl_456",
            "twin_id": "twin_123"
        }
        
        bridge = CrawlIngestionBridge()
        bridge.artifact_store.artifact_exists = Mock(return_value=True)
        
        should_skip, reason = bridge.should_skip_ingestion(page)
        
        assert should_skip is False

    def test_null_status_and_classification_do_not_crash(self):
        """Nullable crawl page fields should not crash ingestion skip checks."""
        page = {
            "id": "page_123",
            "status": None,
            "classification": None,
            "normalized_artifact_path": "crawl/twin_123/crawl_456/pages/page_123/normalized.md",
            "crawl_id": "crawl_456",
            "twin_id": "twin_123",
        }

        bridge = CrawlIngestionBridge()
        bridge.artifact_store.artifact_exists = Mock(return_value=True)

        should_skip, reason = bridge.should_skip_ingestion(page)

        assert should_skip is False
        assert reason == ""


class TestLoadPageContent:
    """Test loading content from artifact store."""
    
    def test_load_content_success(self):
        """Successfully load content from artifact."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456"
        }
        
        bridge = CrawlIngestionBridge()
        bridge.artifact_store.read_artifact = Mock(return_value="Page content here")
        
        content = bridge.load_page_content(page, "twin_123")
        
        assert content == "Page content here"
        bridge.artifact_store.read_artifact.assert_called_once_with(
            artifact_type="crawl",
            twin_id="twin_123",
            entity_id="crawl_456",
            filename="pages/page_123/normalized.md"
        )
    
    def test_load_content_bytes(self):
        """Handle bytes content by decoding to string."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456"
        }
        
        bridge = CrawlIngestionBridge()
        bridge.artifact_store.read_artifact = Mock(return_value=b"Page content bytes")
        
        content = bridge.load_page_content(page, "twin_123")
        
        assert content == "Page content bytes"
    
    def test_load_content_not_found(self):
        """Return None when artifact not found."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456"
        }
        
        bridge = CrawlIngestionBridge()
        bridge.artifact_store.read_artifact = Mock(return_value=None)
        
        content = bridge.load_page_content(page, "twin_123")
        
        assert content is None


class TestCreateSourceFromPage:
    """Test source creation from crawl pages."""
    
    @patch("modules.crawl_ingestion_bridge.supabase")
    def test_create_source_success(self, mock_supabase):
        """Successfully create source from page."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456",
            "canonical_url": "https://example.com/page",
            "content_hash": "abc123",
            "metadata": {"title": "Example Page"}
        }
        
        bridge = CrawlIngestionBridge()
        bridge.load_page_content = Mock(return_value="Page content here")
        
        source_id = bridge.create_source_from_page(page, "twin_123", "crawl_456")
        
        assert source_id is not None
        assert isinstance(source_id, str)
        # Verify source was inserted
        mock_supabase.table.return_value.insert.assert_called_once()
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["twin_id"] == "twin_123"
        assert call_args["citation_url"] == "https://example.com/page"
        assert call_args["content_hash"] == "abc123"
    
    def test_create_source_no_content(self):
        """Return None when content cannot be loaded."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456",
            "canonical_url": "https://example.com/page"
        }
        
        bridge = CrawlIngestionBridge()
        bridge.load_page_content = Mock(return_value=None)
        
        source_id = bridge.create_source_from_page(page, "twin_123", "crawl_456")
        
        assert source_id is None
    
    @patch("modules.crawl_ingestion_bridge.supabase")
    def test_create_source_fallback_title(self, mock_supabase):
        """Use URL path as title fallback when no metadata title."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456",
            "canonical_url": "https://example.com/blog/my-post",
            "metadata": {}  # No title
        }
        
        bridge = CrawlIngestionBridge()
        bridge.load_page_content = Mock(return_value="Content")
        
        source_id = bridge.create_source_from_page(page, "twin_123", "crawl_456")
        
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert "my-post" in call_args["filename"] or "Web:" in call_args["filename"]

    @patch("modules.crawl_ingestion_bridge.supabase")
    def test_create_source_handles_null_metadata(self, mock_supabase):
        """Nullable metadata should not crash source creation."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456",
            "canonical_url": "https://example.com/blog/my-post",
            "metadata": None,
        }

        bridge = CrawlIngestionBridge()
        bridge.load_page_content = Mock(return_value="Content")

        source_id = bridge.create_source_from_page(page, "twin_123", "crawl_456")

        assert source_id is not None
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["filename"].startswith("Web:")

    @patch("modules.crawl_ingestion_bridge.supabase")
    def test_create_source_retries_without_staging_status(self, mock_supabase):
        """Older sources schemas without staging_status should still accept crawl ingestion."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456",
            "canonical_url": "https://example.com/blog/my-post",
            "metadata": {"title": "My Post"},
        }

        insert_mock = mock_supabase.table.return_value.insert.return_value
        insert_mock.execute.side_effect = [
            Exception("Could not find the 'staging_status' column of 'sources' in the schema cache"),
            Mock(),
        ]

        bridge = CrawlIngestionBridge()
        bridge.load_page_content = Mock(return_value="Content")

        source_id = bridge.create_source_from_page(page, "twin_123", "crawl_456")

        assert source_id is not None
        assert insert_mock.execute.call_count == 2
        retry_payload = mock_supabase.table.return_value.insert.call_args_list[-1][0][0]
        assert "staging_status" not in retry_payload


class TestProcessPage:
    """Test full page processing flow."""
    
    @pytest.mark.asyncio
    async def test_process_unchanged_page(self):
        """Unchanged pages return skip result."""
        page = {
            "id": "page_123",
            "status": "fetched",
            "classification": "unchanged"
        }
        
        bridge = CrawlIngestionBridge()
        result = await bridge.process_page(page, "twin_123", "crawl_456")
        
        assert result["status"] == "skipped"
        assert result["reason"] == "unchanged_content"
        assert result["chunks_indexed"] == 0
    
    @pytest.mark.asyncio
    @patch("modules.crawl_ingestion_bridge.supabase")
    async def test_process_new_page(self, mock_supabase):
        """New pages are indexed successfully."""
        page = {
            "id": "page_123",
            "status": "fetched",
            "classification": "new",
            "canonical_url": "https://example.com",
            "content_hash": "abc123",
            "normalized_artifact_path": "crawl/twin_123/crawl_456/pages/page_123/normalized.md",
            "crawl_id": "crawl_456",
        }
        
        bridge = CrawlIngestionBridge()
        bridge.artifact_store.artifact_exists = Mock(return_value=True)
        bridge.load_page_content = Mock(return_value="Test content for chunking")
        bridge.artifact_store.read_artifact = Mock(return_value="Test content")
        
        # Mock the indexing to avoid Pinecone calls
        with patch.object(bridge, 'index_page_chunks', return_value=3):
            result = await bridge.process_page(page, "twin_123", "crawl_456")
        
        assert result["status"] == "indexed"
        assert result["chunks_indexed"] == 3
        assert "source_id" in result


class TestTwinIsolation:
    """Test twin isolation in bridge operations."""
    
    @pytest.mark.asyncio
    @patch("modules.crawl_ingestion_bridge.supabase")
    async def test_source_created_with_correct_twin_id(self, mock_supabase):
        """Source must be created with twin_id from crawl run."""
        page = {
            "id": "page_123",
            "crawl_id": "crawl_456",
            "status": "fetched",
            "classification": "new",
            "canonical_url": "https://example.com",
            "normalized_artifact_path": "crawl/twin_abc/crawl_456/pages/page_123/normalized.md"
        }
        
        bridge = CrawlIngestionBridge()
        bridge.artifact_store.artifact_exists = Mock(return_value=True)
        bridge.load_page_content = Mock(return_value="Content")
        
        with patch.object(bridge, 'index_page_chunks', return_value=1):
            await bridge.process_page(page, "twin_abc", "crawl_456")
        
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["twin_id"] == "twin_abc"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
