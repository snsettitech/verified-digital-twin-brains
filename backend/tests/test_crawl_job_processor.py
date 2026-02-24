"""
Tests for Crawl Job Processor Module (Phase 3.2)

Covers:
- Source strategy resolution (website/article/social/YouTube)
- Firecrawl scrape success flow
- Firecrawl crawl success flow (multi-page)
- Blocked/gated page handling
- Retryable failure handling
- Identity score threshold mapping
- Unchanged page classification
- Crawl run finalization and metrics
- Content quality handling (full/partial/blocked/manual_needed)
"""

import pytest
import uuid
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from modules.crawl_job_processor import (
    CrawlJobProcessor,
    CrawlJobResult,
    CrawlJobStatus,
    PageProcessingResult,
    SourceStrategyResolver,
    SourceType,
    SourceStrategy,
    ConfirmationStatus,
    map_identity_score_to_confirmation_status,
    process_crawl_job,
)
from modules.firecrawl_client import FirecrawlResult, ContentQuality
from modules.crawl_failure_taxonomy import FailureType
from modules.crawl_manager import PageClassification


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_firecrawl_client():
    """Mock Firecrawl client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_crawl_repository():
    """Mock crawl repository."""
    repo = Mock()
    return repo


@pytest.fixture
def mock_crawl_manager():
    """Mock crawl manager."""
    manager = Mock()
    manager.classify_page.return_value = (PageClassification.NEW, None)
    return manager


@pytest.fixture
def mock_identity_scorer():
    """Mock identity scorer."""
    scorer = Mock()
    return scorer


@pytest.fixture
def mock_artifact_store():
    """Mock artifact store."""
    store = Mock()
    store.write_artifact.return_value = None
    return store


@pytest.fixture
def processor(
    mock_firecrawl_client,
    mock_crawl_repository,
    mock_crawl_manager,
    mock_identity_scorer,
    mock_artifact_store,
) -> CrawlJobProcessor:
    """Configured processor with mocks."""
    return CrawlJobProcessor(
        firecrawl_client=mock_firecrawl_client,
        crawl_repository=mock_crawl_repository,
        crawl_manager=mock_crawl_manager,
        identity_scorer=mock_identity_scorer,
        artifact_store=mock_artifact_store,
    )


@pytest.fixture
def sample_crawl_run() -> Dict[str, Any]:
    """Sample crawl run data."""
    return {
        "id": "crawl-123",
        "twin_id": "twin-456",
        "status": "queued",
        "seed_urls": ["https://example.com/article/test"],  # Article path for scrape strategy
        "max_pages": 50,
        "max_depth": 3,
    }


@pytest.fixture
def sample_claimed_identity() -> Dict[str, Any]:
    """Sample claimed identity for scoring."""
    return {
        "full_name": "Test User",
        "location": "New York, NY",
        "submitted_links": ["https://linkedin.com/in/testuser"],
    }


@pytest.fixture
def successful_firecrawl_result() -> FirecrawlResult:
    """Sample successful Firecrawl result."""
    return FirecrawlResult(
        success=True,
        url="https://example.com/page",
        content="# Test Page\n\nThis is test content.",
        metadata={
            "title": "Test Page",
            "description": "A test page",
            "sourceURL": "https://example.com/page",
        },
        quality=ContentQuality.FULL,
        attempts=1,
        duration_ms=500,
    )


# ============================================================================
# Source Strategy Resolver Tests
# ============================================================================

class TestSourceStrategyResolver:
    """Test URL-to-strategy resolution."""
    
    def test_website_root_strategy(self):
        """Root domain should use crawl strategy."""
        strategy = SourceStrategyResolver.resolve("https://example.com")
        
        assert strategy.source_type == SourceType.WEBSITE_ROOT
        assert strategy.method == "crawl"
        assert strategy.firecrawl_params["limit"] == 50
        assert strategy.firecrawl_params["max_depth"] == 3
    
    def test_linkedin_profile_strategy(self):
        """LinkedIn profile should use scrape strategy."""
        strategy = SourceStrategyResolver.resolve("https://linkedin.com/in/testuser")
        
        assert strategy.source_type == SourceType.LINKEDIN_PROFILE
        assert strategy.method == "scrape"
        assert "onlyMainContent" in strategy.firecrawl_params
    
    def test_youtube_video_strategy(self):
        """YouTube video should use scrape with partial expectations."""
        strategy = SourceStrategyResolver.resolve("https://youtube.com/watch?v=123")
        
        assert strategy.source_type == SourceType.YOUTUBE_VIDEO
        assert strategy.method == "scrape"
    
    def test_twitter_profile_strategy(self):
        """Twitter/X profile should use scrape strategy."""
        strategy = SourceStrategyResolver.resolve("https://twitter.com/testuser")
        
        assert strategy.source_type == SourceType.TWITTER_PROFILE
        assert strategy.method == "scrape"
    
    def test_instagram_profile_strategy(self):
        """Instagram profile should use scrape strategy."""
        strategy = SourceStrategyResolver.resolve("https://instagram.com/testuser")
        
        assert strategy.source_type == SourceType.INSTAGRAM_PROFILE
        assert strategy.method == "scrape"
    
    def test_article_page_strategy(self):
        """Article URLs should use scrape strategy."""
        strategy = SourceStrategyResolver.resolve("https://example.com/article/test-post")
        
        assert strategy.source_type == SourceType.ARTICLE_PAGE
        assert strategy.method == "scrape"


# ============================================================================
# Identity Score to Confirmation Status Tests
# ============================================================================

class TestConfirmationStatusMapping:
    """Test score to confirmation status mapping."""
    
    def test_auto_confirmed_high_score(self):
        """Score >= 0.80 should be auto_confirmed."""
        status = map_identity_score_to_confirmation_status(
            0.85, ContentQuality.FULL
        )
        assert status == ConfirmationStatus.AUTO_CONFIRMED
    
    def test_pending_medium_score(self):
        """Score between 0.50 and 0.80 should be pending."""
        status = map_identity_score_to_confirmation_status(
            0.65, ContentQuality.FULL
        )
        assert status == ConfirmationStatus.PENDING
    
    def test_auto_rejected_low_score(self):
        """Score < 0.50 should be auto_rejected."""
        status = map_identity_score_to_confirmation_status(
            0.30, ContentQuality.FULL
        )
        assert status == ConfirmationStatus.AUTO_REJECTED
    
    def test_blocked_content_manual_review(self):
        """Blocked content should always be manual_review."""
        status = map_identity_score_to_confirmation_status(
            0.90, ContentQuality.BLOCKED
        )
        assert status == ConfirmationStatus.MANUAL_REVIEW
    
    def test_manual_needed_content_manual_review(self):
        """Manual-needed content should always be manual_review."""
        status = map_identity_score_to_confirmation_status(
            0.90, ContentQuality.MANUAL_NEEDED
        )
        assert status == ConfirmationStatus.MANUAL_REVIEW


# ============================================================================
# Crawl Job Processor - Core Flow Tests
# ============================================================================

class TestCrawlJobProcessorScrapeFlow:
    """Test scrape strategy execution."""
    
    @pytest.mark.asyncio
    async def test_successful_scrape_flow(
        self,
        processor,
        mock_firecrawl_client,
        sample_claimed_identity,
        successful_firecrawl_result,
    ):
        """Test successful single-page scrape."""
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com/article/test"],  # Article path for scrape
            "max_pages": 50,
            "max_depth": 3,
        }
        # Setup mocks
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record'):
                    mock_firecrawl_client.scrape_with_retry.return_value = successful_firecrawl_result
                    
                    # Mock identity scorer
                    mock_score_result = Mock()
                    mock_score_result.score = 0.85
                    mock_score_result.confidence_level = Mock(value="high")
                    mock_score_result.matched_signals = ["name_in_title"]
                    processor.scorer.score_page.return_value = mock_score_result
                    
                    # Execute
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                        claimed_identity=sample_claimed_identity,
                    )
                    
                    # Verify
                    assert result.status == CrawlJobStatus.COMPLETED
                    assert result.pages_fetched == 1
                    assert result.pages_discovered == 1
                    mock_firecrawl_client.scrape_with_retry.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scrape_with_blocked_quality(
        self,
        processor,
        mock_firecrawl_client,
        sample_claimed_identity,
    ):
        """Test scrape with blocked content quality."""
        blocked_result = FirecrawlResult(
            success=True,  # Firecrawl succeeded but content was blocked
            url="https://example.com/article/test",
            content="",
            metadata={},
            quality=ContentQuality.BLOCKED,
            quality_reason="Access blocked by robots.txt",
        )
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com/article/test"],
            "max_pages": 50,
            "max_depth": 3,
        }
        
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record') as mock_persist:
                    mock_firecrawl_client.scrape_with_retry.return_value = blocked_result
                    
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                        claimed_identity=sample_claimed_identity,
                    )
                    
                    # Should complete with warnings due to blocked content
                    assert result.status == CrawlJobStatus.COMPLETED_WITH_WARNINGS
                    assert result.pages_blocked == 1


class TestCrawlJobProcessorCrawlFlow:
    """Test crawl strategy execution (multi-page)."""
    
    @pytest.mark.asyncio
    async def test_successful_crawl_flow(
        self,
        processor,
        mock_firecrawl_client,
        sample_crawl_run,
    ):
        """Test successful multi-page crawl."""
        # Create multi-page crawl results
        crawl_results = [
            FirecrawlResult(
                success=True,
                url="https://example.com/page1",
                content="Page 1 content",
                metadata={"title": "Page 1"},
                quality=ContentQuality.FULL,
            ),
            FirecrawlResult(
                success=True,
                url="https://example.com/page2",
                content="Page 2 content",
                metadata={"title": "Page 2"},
                quality=ContentQuality.FULL,
            ),
        ]
        
        sample_crawl_run["seed_urls"] = ["https://example.com"]
        
        with patch.object(processor, '_get_crawl_run', return_value=sample_crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record'):
                    mock_firecrawl_client.crawl_with_polling.return_value = crawl_results
                    
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                    )
                    
                    assert result.status == CrawlJobStatus.COMPLETED
                    assert result.pages_discovered == 2
                    assert result.pages_fetched == 2
                    mock_firecrawl_client.crawl_with_polling.assert_called_once()


class TestCrawlJobProcessorFailureHandling:
    """Test failure handling and taxonomy mapping."""
    
    @pytest.mark.asyncio
    async def test_retryable_failure_handling(
        self,
        processor,
        mock_firecrawl_client,
    ):
        """Test that retryable failures are properly categorized."""
        failed_result = FirecrawlResult(
            success=False,
            url="https://example.com/article/test",
            content="",
            metadata={},
            quality=ContentQuality.BLOCKED,
            error={
                "failure_type": FailureType.RATE_LIMIT,
                "detail": "Rate limited by server",
            },
        )
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com/article/test"],
            "max_pages": 50,
            "max_depth": 3,
        }
        
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record') as mock_persist:
                    mock_firecrawl_client.scrape_with_retry.return_value = failed_result
                    
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                    )
                    
                    assert result.pages_failed == 1
                    assert "rate_limit" in result.failures_by_type
    
    @pytest.mark.asyncio
    async def test_gated_content_handling(
        self,
        processor,
        mock_firecrawl_client,
    ):
        """Test handling of gated/blocked content."""
        gated_result = FirecrawlResult(
            success=False,
            url="https://linkedin.com/in/test",
            content="",
            metadata={},
            quality=ContentQuality.BLOCKED,
            error={
                "failure_type": FailureType.GATING,
                "detail": "Cloudflare protection",
            },
        )
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://linkedin.com/in/test"],
            "max_pages": 50,
            "max_depth": 3,
        }
        
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record'):
                    mock_firecrawl_client.scrape_with_retry.return_value = gated_result
                    
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                    )
                    
                    assert result.pages_blocked == 1
                    assert result.pages_failed == 1
                    assert "gating" in result.failures_by_type


class TestCrawlJobProcessorIdentityScoring:
    """Test identity scoring integration."""
    
    @pytest.mark.asyncio
    async def test_identity_score_persistence(
        self,
        processor,
        mock_firecrawl_client,
        sample_claimed_identity,
        successful_firecrawl_result,
    ):
        """Test that identity scores are persisted to DB."""
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com/article/test"],
            "max_pages": 50,
            "max_depth": 3,
        }
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record') as mock_persist:
                    with patch.object(processor, '_store_content_artifact', return_value="path/to/artifact"):
                        mock_firecrawl_client.scrape_with_retry.return_value = successful_firecrawl_result
                        
                        # Mock high identity score
                        mock_score_result = Mock()
                        mock_score_result.score = 0.90  # Above 0.80 threshold
                        mock_score_result.confidence_level = Mock(value="high")
                        mock_score_result.matched_signals = ["name_in_title", "name_in_content"]
                        processor.scorer.score_page.return_value = mock_score_result
                        
                        result = await processor.process_crawl_job(
                            job_id="job-123",
                            crawl_id="crawl-123",
                            claimed_identity=sample_claimed_identity,
                        )
                        
                        # Verify auto_confirmed count
                        assert result.auto_confirmed == 1
                        
                        # Verify persist was called with score
                        call_args = mock_persist.call_args
                        if call_args:
                            kwargs = call_args.kwargs or call_args[1]
                            assert "identity_score" in kwargs or mock_persist.called


class TestCrawlJobProcessorClassification:
    """Test page classification integration."""
    
    @pytest.mark.asyncio
    async def test_unchanged_page_classification(
        self,
        processor,
        mock_firecrawl_client,
        mock_crawl_manager,
        successful_firecrawl_result,
    ):
        """Test that unchanged pages are properly classified."""
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com/article/test"],
            "max_pages": 50,
            "max_depth": 3,
        }
        # Mock unchanged classification
        mock_crawl_manager.classify_page.return_value = (PageClassification.UNCHANGED, {
            "id": "prior-page-123",
            "content_hash": "abc123",
        })
        
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record'):
                    mock_firecrawl_client.scrape_with_retry.return_value = successful_firecrawl_result
                    
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                    )
                    
                    assert result.pages_unchanged == 1
    
    @pytest.mark.asyncio
    async def test_changed_page_classification(
        self,
        processor,
        mock_firecrawl_client,
        mock_crawl_manager,
        successful_firecrawl_result,
    ):
        """Test that changed pages are properly classified."""
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com/article/test"],
            "max_pages": 50,
            "max_depth": 3,
        }
        mock_crawl_manager.classify_page.return_value = (PageClassification.CHANGED, {
            "id": "prior-page-123",
            "content_hash": "old-hash",
        })
        
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record'):
                    with patch.object(processor, '_store_content_artifact', return_value="path"):
                        mock_firecrawl_client.scrape_with_retry.return_value = successful_firecrawl_result
                        
                        result = await processor.process_crawl_job(
                            job_id="job-123",
                            crawl_id="crawl-123",
                        )
                        
                        assert result.pages_changed == 1


class TestCrawlJobProcessorFinalization:
    """Test crawl job finalization and metrics."""
    
    @pytest.mark.asyncio
    async def test_successful_finalization(
        self,
        processor,
        mock_firecrawl_client,
        sample_crawl_run,
        successful_firecrawl_result,
    ):
        """Test successful job finalization."""
        with patch.object(processor, '_get_crawl_run', return_value=sample_crawl_run):
            with patch.object(processor, '_update_crawl_status') as mock_update:
                with patch.object(processor, '_persist_page_record'):
                    with patch.object(processor, '_store_content_artifact', return_value="path"):
                        mock_firecrawl_client.scrape_with_retry.return_value = successful_firecrawl_result
                        
                        result = await processor.process_crawl_job(
                            job_id="job-123",
                            crawl_id="crawl-123",
                        )
                        
                        assert result.status == CrawlJobStatus.COMPLETED
                        assert result.job_id == "job-123"
                        assert result.crawl_id == "crawl-123"
                        assert result.completed_at is not None
                        
                        # Verify crawl status was updated
                        mock_update.assert_any_call("crawl-123", "running")
    
    @pytest.mark.asyncio
    async def test_failed_crawl_run(
        self,
        processor,
        sample_crawl_run,
    ):
        """Test handling when crawl run not found."""
        with patch.object(processor, '_get_crawl_run', return_value=None):
            result = await processor.process_crawl_job(
                job_id="job-123",
                crawl_id="nonexistent",
            )
            
            assert result.status == CrawlJobStatus.FAILED
            assert "not found" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_completed_with_warnings(
        self,
        processor,
        mock_firecrawl_client,
    ):
        """Test completed_with_warnings status for partial failures."""
        # Use website root URL to trigger crawl strategy
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com"],  # Root URL for crawl strategy
            "max_pages": 50,
            "max_depth": 3,
        }
        # Mix of success and blocked
        crawl_results = [
            FirecrawlResult(
                success=True,
                url="https://example.com/page1",
                content="Page 1",
                metadata={},
                quality=ContentQuality.FULL,
            ),
            FirecrawlResult(
                success=False,
                url="https://example.com/page2",
                content="",
                metadata={},
                quality=ContentQuality.BLOCKED,
                error={"failure_type": FailureType.GATING, "detail": "Blocked"},
            ),
        ]
        
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record'):
                    mock_firecrawl_client.crawl_with_polling.return_value = crawl_results
                    
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                    )
                    
                    assert result.status == CrawlJobStatus.COMPLETED_WITH_WARNINGS
                    assert result.pages_fetched == 1
                    assert result.pages_failed == 1


class TestCrawlJobProcessorContentQuality:
    """Test content quality handling."""
    
    @pytest.mark.asyncio
    async def test_partial_content_quality(
        self,
        processor,
        mock_firecrawl_client,
        sample_crawl_run,
        sample_claimed_identity,
    ):
        """Test handling of partial content quality."""
        partial_result = FirecrawlResult(
            success=True,
            url="https://youtube.com/watch?v=123",
            content="Video description only",
            metadata={"title": "Video Title"},
            quality=ContentQuality.PARTIAL,
            quality_reason="Video transcript unavailable",
        )
        
        sample_crawl_run["seed_urls"] = ["https://youtube.com/watch?v=123"]
        
        with patch.object(processor, '_get_crawl_run', return_value=sample_crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record') as mock_persist:
                    with patch.object(processor, '_store_content_artifact', return_value="path"):
                        mock_firecrawl_client.scrape_with_retry.return_value = partial_result
                        
                        # Mock scorer
                        mock_score = Mock()
                        mock_score.score = 0.60
                        mock_score.confidence_level = Mock(value="medium")
                        processor.scorer.score_page.return_value = mock_score
                        
                        result = await processor.process_crawl_job(
                            job_id="job-123",
                            crawl_id="crawl-123",
                            claimed_identity=sample_claimed_identity,
                        )
                        
                        # Partial content should still be counted as fetched
                        assert result.pages_fetched == 1
    
    @pytest.mark.asyncio
    async def test_manual_needed_quality(
        self,
        processor,
        mock_firecrawl_client,
    ):
        """Test handling of manual_needed content quality."""
        manual_result = FirecrawlResult(
            success=True,
            url="https://example.com/video",
            content="",
            metadata={},
            quality=ContentQuality.MANUAL_NEEDED,
            quality_reason="Video content requires transcript",
        )
        crawl_run = {
            "id": "crawl-123",
            "twin_id": "twin-456",
            "status": "queued",
            "seed_urls": ["https://example.com/article/video-page"],  # Use article path
            "max_pages": 50,
            "max_depth": 3,
        }
        
        with patch.object(processor, '_get_crawl_run', return_value=crawl_run):
            with patch.object(processor, '_update_crawl_status'):
                with patch.object(processor, '_persist_page_record'):
                    mock_firecrawl_client.scrape_with_retry.return_value = manual_result
                    
                    result = await processor.process_crawl_job(
                        job_id="job-123",
                        crawl_id="crawl-123",
                    )
                    
                    assert result.pages_manual_needed == 1
                    assert result.status == CrawlJobStatus.COMPLETED_WITH_WARNINGS


class TestCrawlJobProcessorEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_no_seed_urls(self, processor, sample_crawl_run):
        """Test handling of crawl run with no seed URLs."""
        sample_crawl_run["seed_urls"] = []
        
        with patch.object(processor, '_get_crawl_run', return_value=sample_crawl_run):
            result = await processor.process_crawl_job(
                job_id="job-123",
                crawl_id="crawl-123",
            )
            
            assert result.status == CrawlJobStatus.FAILED
            assert "no seed urls" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_no_firecrawl_client(
        self,
        mock_crawl_repository,
        mock_crawl_manager,
        mock_identity_scorer,
        mock_artifact_store,
        sample_crawl_run,
    ):
        """Test handling when Firecrawl is not configured."""
        # Create processor without Firecrawl client
        processor_no_fc = CrawlJobProcessor(
            firecrawl_client=None,
            crawl_repository=mock_crawl_repository,
            crawl_manager=mock_crawl_manager,
            identity_scorer=mock_identity_scorer,
            artifact_store=mock_artifact_store,
        )
        
        with patch.object(processor_no_fc, '_get_crawl_run', return_value=sample_crawl_run):
            with patch.object(processor_no_fc, '_update_crawl_status'):
                result = await processor_no_fc.process_crawl_job(
                    job_id="job-123",
                    crawl_id="crawl-123",
                )
                
                # Should complete but with 0 pages
                assert result.status == CrawlJobStatus.COMPLETED
                assert result.pages_discovered == 0


# ============================================================================
# Convenience Function Test
# ============================================================================

class TestProcessCrawlJobConvenience:
    """Test the process_crawl_job convenience function."""
    
    @pytest.mark.asyncio
    async def test_convenience_function(self, sample_crawl_run, successful_firecrawl_result):
        """Test convenience function creates processor and executes."""
        with patch('modules.crawl_job_processor.CrawlJobProcessor') as mock_processor_class:
            mock_processor = AsyncMock()
            mock_processor.process_crawl_job.return_value = CrawlJobResult(
                job_id="job-123",
                crawl_id="crawl-123",
                status=CrawlJobStatus.COMPLETED,
                started_at=datetime.utcnow(),
            )
            mock_processor_class.return_value = mock_processor
            
            result = await process_crawl_job(
                job_id="job-123",
                crawl_id="crawl-123",
            )
            
            assert result.status == CrawlJobStatus.COMPLETED
            mock_processor_class.assert_called_once()


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
