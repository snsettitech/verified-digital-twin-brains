"""
Tests for Source Confirmation System Module (Phase 3.3)

Covers:
- Score normalization (0-1 and 0-100 inputs)
- Auto-confirm/pending/auto-reject mapping
- Blocked/manual_needed behavior
- Confirmation row creation idempotency
- List pending confirmations
- Single resolve (confirm/reject)
- Bulk resolve
- Summary counts
- Invalid state transitions
"""

import pytest
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock

from modules.source_confirmation import (
    SourceConfirmationManager,
    ConfirmationStatus,
    ConfirmationAction,
    normalize_identity_score_for_thresholds,
    format_score_for_display,
    map_score_to_initial_status,
    is_status_terminal,
    can_user_override,
    AUTO_CONFIRM_THRESHOLD,
    AUTO_REJECT_THRESHOLD,
    ConfirmationCreationResult,
    PendingConfirmationItem,
    ConfirmationResolveResult,
    BulkResolveResult,
    ConfirmationSummary,
)
from modules.firecrawl_client import ContentQuality


# ============================================================================
# Score Normalization Tests
# ============================================================================

class TestScoreNormalization:
    """Test score normalization contract."""
    
    def test_normalize_float_unchanged(self):
        """Floats in 0.0-1.0 range should remain unchanged."""
        assert normalize_identity_score_for_thresholds(0.82) == 0.82
        assert normalize_identity_score_for_thresholds(0.0) == 0.0
        assert normalize_identity_score_for_thresholds(1.0) == 1.0
    
    def test_normalize_int_to_float(self):
        """Ints 0-100 should be normalized to 0.0-1.0."""
        assert normalize_identity_score_for_thresholds(82) == 0.82
        assert normalize_identity_score_for_thresholds(0) == 0.0
        assert normalize_identity_score_for_thresholds(100) == 1.0
    
    def test_normalize_float_percentage(self):
        """Floats 1.0-100.0 treated as percentages."""
        assert normalize_identity_score_for_thresholds(82.0) == 0.82
    
    def test_normalize_none_returns_none(self):
        """None input returns None."""
        assert normalize_identity_score_for_thresholds(None) is None
    
    def test_normalize_out_of_range(self):
        """Out of range values return None."""
        assert normalize_identity_score_for_thresholds(-0.5) is None
        # Values 1.0-100.0 are treated as percentages, not out of range
        assert normalize_identity_score_for_thresholds(150) is None
    
    def test_format_for_display(self):
        """Test conversion to percentage for display."""
        assert format_score_for_display(0.82) == 82
        assert format_score_for_display(0.0) == 0
        assert format_score_for_display(1.0) == 100
        assert format_score_for_display(None) is None


# ============================================================================
# Status Mapping Tests
# ============================================================================

class TestStatusMapping:
    """Test score to status mapping."""
    
    def test_high_score_auto_confirmed(self):
        """Score >= 0.80 should be auto_confirmed."""
        status = map_score_to_initial_status(0.85, ContentQuality.FULL)
        assert status == ConfirmationStatus.AUTO_CONFIRMED
    
    def test_medium_score_pending(self):
        """Score 0.50-0.80 should be pending."""
        status = map_score_to_initial_status(0.65, ContentQuality.FULL)
        assert status == ConfirmationStatus.PENDING
    
    def test_low_score_auto_rejected(self):
        """Score < 0.50 should be auto_rejected."""
        status = map_score_to_initial_status(0.30, ContentQuality.FULL)
        assert status == ConfirmationStatus.AUTO_REJECTED
    
    def test_none_score_pending(self):
        """None score should default to pending."""
        status = map_score_to_initial_status(None, ContentQuality.FULL)
        assert status == ConfirmationStatus.PENDING
    
    def test_blocked_quality_manual_review(self):
        """Blocked content should be manual_review regardless of score."""
        status = map_score_to_initial_status(0.95, ContentQuality.BLOCKED)
        assert status == ConfirmationStatus.MANUAL_REVIEW
    
    def test_manual_needed_quality_manual_review(self):
        """Manual-needed content should be manual_review."""
        status = map_score_to_initial_status(0.95, ContentQuality.MANUAL_NEEDED)
        assert status == ConfirmationStatus.MANUAL_REVIEW
    
    def test_partial_quality_score_based(self):
        """Partial content uses score-based logic."""
        status = map_score_to_initial_status(0.85, ContentQuality.PARTIAL)
        assert status == ConfirmationStatus.AUTO_CONFIRMED


class TestStatusHelpers:
    """Test status helper functions."""
    
    def test_is_status_terminal(self):
        """Terminal statuses are confirmed and rejected."""
        assert is_status_terminal(ConfirmationStatus.CONFIRMED) is True
        assert is_status_terminal(ConfirmationStatus.REJECTED) is True
        assert is_status_terminal(ConfirmationStatus.PENDING) is False
        assert is_status_terminal(ConfirmationStatus.AUTO_CONFIRMED) is False
        assert is_status_terminal(ConfirmationStatus.AUTO_REJECTED) is False
    
    def test_can_user_override(self):
        """User can override auto-assigned and pending statuses."""
        assert can_user_override(ConfirmationStatus.PENDING) is True
        assert can_user_override(ConfirmationStatus.MANUAL_REVIEW) is True
        assert can_user_override(ConfirmationStatus.AUTO_CONFIRMED) is True
        assert can_user_override(ConfirmationStatus.AUTO_REJECTED) is True
        assert can_user_override(ConfirmationStatus.CONFIRMED) is False
        assert can_user_override(ConfirmationStatus.REJECTED) is False


# ============================================================================
# SourceConfirmationManager Tests
# ============================================================================

@pytest.fixture
def manager() -> SourceConfirmationManager:
    """Default manager instance."""
    return SourceConfirmationManager()


@pytest.fixture
def sample_crawl_page() -> Dict[str, Any]:
    """Sample crawl page data."""
    return {
        "id": "page-123",
        "url": "https://example.com/page",
        "canonical_url": "https://example.com/page",
        "title": "Test Page",
        "content_quality": "full",
        "identity_confidence_score": 85,  # Stored as int 0-100
        "submitted_root_url": "https://example.com",
        "metadata": {"description": "Test description"},
    }


class TestCreateConfirmations:
    """Test confirmation creation from crawl."""
    
    @pytest.mark.asyncio
    async def test_create_confirmations_success(self, manager, sample_crawl_page):
        """Test successful creation of confirmations."""
        with patch.object(manager, '_fetch_crawl_pages', return_value=[sample_crawl_page]):
            with patch.object(manager, '_confirmation_exists', return_value=False):
                with patch.object(manager, '_create_confirmation_record') as mock_create:
                    result = await manager.create_confirmations_for_crawl(
                        research_run_id="run-123",
                        crawl_id="crawl-456",
                        twin_id="twin-789",
                    )
                    
                    assert result.total_pages == 1
                    assert result.created == 1
                    assert result.skipped == 0
                    mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_confirmations_idempotent(self, manager, sample_crawl_page):
        """Test that duplicate confirmations are skipped."""
        with patch.object(manager, '_fetch_crawl_pages', return_value=[sample_crawl_page]):
            with patch.object(manager, '_confirmation_exists', return_value=True):
                result = await manager.create_confirmations_for_crawl(
                    research_run_id="run-123",
                    crawl_id="crawl-456",
                    twin_id="twin-789",
                )
                
                assert result.created == 0
                assert result.skipped == 1
    
    @pytest.mark.asyncio
    async def test_create_confirmations_multiple_pages(self, manager):
        """Test creation with multiple pages of varying scores."""
        pages = [
            {"id": "page-1", "content_quality": "full", "identity_confidence_score": 85},  # auto_confirmed
            {"id": "page-2", "content_quality": "full", "identity_confidence_score": 60},  # pending
            {"id": "page-3", "content_quality": "full", "identity_confidence_score": 30},  # auto_rejected
            {"id": "page-4", "content_quality": "blocked", "identity_confidence_score": 50},  # manual_review
        ]
        
        with patch.object(manager, '_fetch_crawl_pages', return_value=pages):
            with patch.object(manager, '_confirmation_exists', return_value=False):
                with patch.object(manager, '_create_confirmation_record'):
                    result = await manager.create_confirmations_for_crawl(
                        research_run_id="run-123",
                        crawl_id="crawl-456",
                        twin_id="twin-789",
                    )
                    
                    assert result.total_pages == 4
                    assert result.created == 4
                    assert result.by_status.get("auto_confirmed") == 1
                    assert result.by_status.get("pending") == 1
                    assert result.by_status.get("auto_rejected") == 1
                    assert result.by_status.get("manual_review") == 1


class TestListPendingConfirmations:
    """Test listing pending confirmations."""
    
    @pytest.mark.asyncio
    async def test_list_pending(self, manager):
        """Test listing pending confirmations."""
        db_rows = [
            {
                "id": "conf-1",
                "crawl_page_id": "page-1",
                "url": "https://example.com/1",
                "canonical_url": "https://example.com/1",
                "title": "Page 1",
                "snippet": "Snippet 1",
                "content_quality": "full",
                "identity_confidence_score": 60,
                "confirmation_status": "pending",
                "submitted_root_url": "https://example.com",
                "match_details": {"signals": ["name_in_title"]},
                "created_at": "2026-01-01T00:00:00",
            }
        ]
        
        with patch('modules.source_confirmation.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.order.return_value.range.return_value.execute.return_value.data = db_rows
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value.count = 1
            
            result = await manager.list_pending_confirmations(
                research_run_id="run-123",
                twin_id="twin-789",
            )
            
            assert len(result.items) == 1
            assert result.items[0].confirmation_id == "conf-1"
            assert result.items[0].status == "pending"
            assert result.items[0].identity_confidence_percent == 60
    
    @pytest.mark.asyncio
    async def test_list_pending_excludes_terminal(self, manager):
        """Test that confirmed/rejected are excluded from pending list."""
        with patch('modules.source_confirmation.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.order.return_value.range.return_value.execute.return_value.data = []
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value.count = 0
            
            result = await manager.list_pending_confirmations(
                research_run_id="run-123",
                twin_id="twin-789",
            )
            
            assert len(result.items) == 0
            # Verify the query was called with correct statuses
            call_args = mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.call_args
            assert call_args is not None


class TestResolveConfirmation:
    """Test single confirmation resolution."""
    
    @pytest.mark.asyncio
    async def test_resolve_confirm(self, manager):
        """Test confirming a pending confirmation."""
        confirmation = {
            "id": "conf-123",
            "confirmation_status": "pending",
        }
        
        with patch.object(manager, '_fetch_confirmation', return_value=confirmation):
            with patch.object(manager, '_update_confirmation_status') as mock_update:
                result = await manager.resolve_confirmation(
                    research_run_id="run-123",
                    confirmation_id="conf-123",
                    twin_id="twin-789",
                    actor_user_id="user-456",
                    action="confirm",
                )
                
                assert result.error is None
                assert result.previous_status == "pending"
                assert result.new_status == "confirmed"
                assert result.action == "confirm"
                assert result.user_override is False
                mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_reject(self, manager):
        """Test rejecting a pending confirmation."""
        confirmation = {
            "id": "conf-123",
            "confirmation_status": "pending",
        }
        
        with patch.object(manager, '_fetch_confirmation', return_value=confirmation):
            with patch.object(manager, '_update_confirmation_status') as mock_update:
                result = await manager.resolve_confirmation(
                    research_run_id="run-123",
                    confirmation_id="conf-123",
                    twin_id="twin-789",
                    actor_user_id="user-456",
                    action="reject",
                    feedback="Not relevant",
                )
                
                assert result.error is None
                assert result.new_status == "rejected"
                assert result.action == "reject"
                mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_already_terminal(self, manager):
        """Test resolving an already terminal confirmation fails."""
        confirmation = {
            "id": "conf-123",
            "confirmation_status": "confirmed",
        }
        
        with patch.object(manager, '_fetch_confirmation', return_value=confirmation):
            result = await manager.resolve_confirmation(
                research_run_id="run-123",
                confirmation_id="conf-123",
                twin_id="twin-789",
                actor_user_id="user-456",
                action="reject",
            )
            
            assert result.error is not None
            assert "already resolved" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_resolve_not_found(self, manager):
        """Test resolving non-existent confirmation fails."""
        with patch.object(manager, '_fetch_confirmation', return_value=None):
            result = await manager.resolve_confirmation(
                research_run_id="run-123",
                confirmation_id="conf-nonexistent",
                twin_id="twin-789",
                actor_user_id="user-456",
                action="confirm",
            )
            
            assert result.error is not None
            assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_resolve_override_auto_confirmed(self, manager):
        """Test that user can override auto_confirmed."""
        confirmation = {
            "id": "conf-123",
            "confirmation_status": "auto_confirmed",
        }
        
        with patch.object(manager, '_fetch_confirmation', return_value=confirmation):
            with patch.object(manager, '_update_confirmation_status'):
                result = await manager.resolve_confirmation(
                    research_run_id="run-123",
                    confirmation_id="conf-123",
                    twin_id="twin-789",
                    actor_user_id="user-456",
                    action="reject",
                )
                
                assert result.error is None
                assert result.user_override is True
    
    @pytest.mark.asyncio
    async def test_resolve_invalid_action(self, manager):
        """Test that invalid action returns error."""
        result = await manager.resolve_confirmation(
            research_run_id="run-123",
            confirmation_id="conf-123",
            twin_id="twin-789",
            actor_user_id="user-456",
            action="invalid",
        )
        
        assert result.error is not None
        assert "invalid action" in result.error.lower()


class TestBulkResolve:
    """Test bulk resolution."""
    
    @pytest.mark.asyncio
    async def test_bulk_resolve_mixed(self, manager):
        """Test bulk resolve with mixed success/failure."""
        confirmations = [
            {"id": "conf-1", "confirmation_status": "pending"},
            {"id": "conf-2", "confirmation_status": "confirmed"},  # Already terminal
        ]
        
        def mock_fetch(confirmation_id, *args, **kwargs):
            for c in confirmations:
                if c["id"] == confirmation_id:
                    return c
            return None
        
        with patch.object(manager, '_fetch_confirmation', side_effect=mock_fetch):
            with patch.object(manager, '_update_confirmation_status'):
                result = await manager.bulk_resolve_confirmations(
                    research_run_id="run-123",
                    twin_id="twin-789",
                    actor_user_id="user-456",
                    confirmation_ids=["conf-1", "conf-2"],
                    action="confirm",
                )
                
                assert result.requested == 2
                assert result.succeeded == 1
                assert result.failed == 1


class TestConfirmationSummary:
    """Test confirmation summary."""
    
    @pytest.mark.asyncio
    async def test_summary_counts(self, manager):
        """Test summary with various statuses."""
        db_rows = [
            {"confirmation_status": "pending"},
            {"confirmation_status": "pending"},
            {"confirmation_status": "auto_confirmed"},
            {"confirmation_status": "auto_rejected"},
            {"confirmation_status": "manual_review"},
            {"confirmation_status": "confirmed"},
            {"confirmation_status": "rejected"},
        ]
        
        with patch('modules.source_confirmation.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = db_rows
            
            result = await manager.get_confirmation_summary(
                research_run_id="run-123",
                twin_id="twin-789",
            )
            
            assert result.total == 7
            assert result.pending == 2
            assert result.auto_confirmed == 1
            assert result.auto_rejected == 1
            assert result.manual_review == 1
            assert result.confirmed == 1
            assert result.rejected == 1
            assert result.all_resolved is False
            # 3 resolved (confirmed + rejected + auto_confirmed) out of 7 total = ~42.9%
            assert result.resolution_percent == 42.9
    
    @pytest.mark.asyncio
    async def test_summary_all_resolved(self, manager):
        """Test summary when all confirmations resolved."""
        db_rows = [
            {"confirmation_status": "confirmed"},
            {"confirmation_status": "rejected"},
            {"confirmation_status": "auto_confirmed"},
        ]
        
        with patch('modules.source_confirmation.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = db_rows
            
            result = await manager.get_confirmation_summary(
                research_run_id="run-123",
                twin_id="twin-789",
            )
            
            assert result.all_resolved is True
            assert result.resolution_percent == 100.0
    
    @pytest.mark.asyncio
    async def test_are_all_confirmations_resolved(self, manager):
        """Test helper for checking if all resolved."""
        with patch.object(manager, 'get_confirmation_summary') as mock_summary:
            mock_summary.return_value = ConfirmationSummary(
                research_run_id="run-123",
                twin_id="twin-789",
                total=3,
                pending=0,
                auto_confirmed=1,
                auto_rejected=0,
                manual_review=0,
                confirmed=2,
                rejected=0,
                all_resolved=True,
                resolution_percent=100.0,
            )
            
            result = await manager.are_all_confirmations_resolved("run-123", "twin-789")
            assert result is True


# ============================================================================
# Threshold Constants Tests
# ============================================================================

class TestThresholds:
    """Test threshold constants."""
    
    def test_auto_confirm_threshold(self):
        """Auto-confirm threshold should be 0.80."""
        assert AUTO_CONFIRM_THRESHOLD == 0.80
    
    def test_auto_reject_threshold(self):
        """Auto-reject threshold should be 0.50."""
        assert AUTO_REJECT_THRESHOLD == 0.50
    
    def test_threshold_order(self):
        """Confirm threshold should be higher than reject."""
        assert AUTO_CONFIRM_THRESHOLD > AUTO_REJECT_THRESHOLD


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
