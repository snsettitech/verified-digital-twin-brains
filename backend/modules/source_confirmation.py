"""
Source Confirmation System Module (Phase 3.3)

Manages user confirmation workflow for crawled sources.

Integrates with:
- Crawl pages (Phase 3.2) with identity confidence scores
- Research runs for confirmation scoping
- User actions for confirm/reject resolution

Usage:
    manager = SourceConfirmationManager()
    
    # Create confirmations from crawl results
    result = await manager.create_confirmations_for_crawl(
        research_run_id="run-123",
        crawl_id="crawl-456",
        user_id="user-789"
    )
    
    # List pending confirmations
    pending = await manager.list_pending_confirmations(
        research_run_id="run-123",
        twin_id="twin-abc"
    )
    
    # Resolve a confirmation
    resolved = await manager.resolve_confirmation(
        research_run_id="run-123",
        confirmation_id="conf-xyz",
        twin_id="twin-abc",
        actor_user_id="user-789",
        action="confirm"
    )
"""

import uuid
import logging
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from modules.observability import supabase
from modules.firecrawl_client import ContentQuality

logger = logging.getLogger(__name__)


# ============================================================================
# Score Normalization Contract (Phase 3.3)
# ============================================================================

def normalize_identity_score_for_thresholds(value: Union[float, int, None]) -> Optional[float]:
    """
    Normalize identity confidence score to 0.0-1.0 range for threshold comparisons.
    
    Handles both normalized floats (0.0-1.0) and percentage ints (0-100).
    
    Args:
        value: Raw score value (float 0.0-1.0, int 0-100, or None)
    
    Returns:
        Normalized float 0.0-1.0, or None if input is None/invalid
    
    Examples:
        >>> normalize_identity_score_for_thresholds(0.85)
        0.85
        >>> normalize_identity_score_for_thresholds(85)
        0.85
        >>> normalize_identity_score_for_thresholds(None)
        None
    """
    if value is None:
        return None
    
    # Handle floats (assume already normalized if < 1.0)
    if isinstance(value, float):
        if 0.0 <= value <= 1.0:
            return round(value, 3)
        elif 1.0 < value <= 100.0:
            # Likely a percentage stored as float
            return round(value / 100.0, 3)
        else:
            logger.warning(f"Unexpected float score value: {value}")
            return None
    
    # Handle ints (assume 0-100 percentage)
    if isinstance(value, int):
        if 0 <= value <= 100:
            return round(value / 100.0, 3)
        else:
            logger.warning(f"Unexpected int score value: {value}")
            return None
    
    logger.warning(f"Unknown score type: {type(value)}")
    return None


def format_score_for_display(normalized_score: Optional[float]) -> Optional[int]:
    """
    Convert normalized score (0.0-1.0) to percentage (0-100) for display.
    
    Args:
        normalized_score: Score in 0.0-1.0 range
    
    Returns:
        Percentage 0-100, or None if input is None
    """
    if normalized_score is None:
        return None
    return int(normalized_score * 100)


def score_to_identity_match_tier(
    normalized_score: Optional[float],
    content_quality: Optional[ContentQuality] = None,
) -> Optional[str]:
    if content_quality in (ContentQuality.BLOCKED, ContentQuality.MANUAL_NEEDED):
        return "unclear"
    if normalized_score is None:
        return None
    if normalized_score >= 0.9:
        return "exact"
    if normalized_score >= AUTO_CONFIRM_THRESHOLD:
        return "likely"
    if normalized_score >= AUTO_REJECT_THRESHOLD:
        return "unclear"
    return "mismatch"


# ============================================================================
# Confirmation Status Contract (Phase 3.3)
# ============================================================================

class ConfirmationStatus(str, Enum):
    """
    Authoritative confirmation statuses for source_confirmations table.
    
    State Transitions:
    - pending -> confirmed (user action)
    - pending -> rejected (user action)
    - auto_confirmed -> (terminal, user can override to rejected)
    - auto_rejected -> rejected (user can confirm, but flagged)
    - manual_review -> confirmed or rejected (user action)
    """
    PENDING = "pending"                   # Awaiting user decision
    AUTO_CONFIRMED = "auto_confirmed"     # High confidence auto-accepted
    AUTO_REJECTED = "auto_rejected"       # Low confidence auto-rejected
    MANUAL_REVIEW = "manual_review"       # Blocked/manual-needed quality
    CONFIRMED = "confirmed"               # User confirmed
    REJECTED = "rejected"                 # User rejected


class ConfirmationAction(str, Enum):
    """Actions that can be taken on a confirmation."""
    CONFIRM = "confirm"
    REJECT = "reject"


# Phase 3.3 Score Thresholds (using normalized 0.0-1.0 scale)
AUTO_CONFIRM_THRESHOLD = 0.80
AUTO_REJECT_THRESHOLD = 0.50


def map_score_to_initial_status(
    normalized_score: Optional[float],
    content_quality: Optional[ContentQuality]
) -> ConfirmationStatus:
    """
    Map identity score and content quality to initial confirmation status.
    
    Args:
        normalized_score: Normalized score 0.0-1.0 (or None)
        content_quality: Content quality from Firecrawl
    
    Returns:
        Initial ConfirmationStatus
    """
    # Blocked or manual-needed content requires manual review
    if content_quality in (ContentQuality.BLOCKED, ContentQuality.MANUAL_NEEDED):
        return ConfirmationStatus.MANUAL_REVIEW
    
    # No score available - default to pending
    if normalized_score is None:
        return ConfirmationStatus.PENDING
    
    # Score-based classification
    if normalized_score >= AUTO_CONFIRM_THRESHOLD:
        return ConfirmationStatus.AUTO_CONFIRMED
    elif normalized_score >= AUTO_REJECT_THRESHOLD:
        return ConfirmationStatus.PENDING
    else:
        return ConfirmationStatus.AUTO_REJECTED


def is_status_terminal(status: ConfirmationStatus) -> bool:
    """Check if a confirmation status is terminal (no further action needed)."""
    return status in (
        ConfirmationStatus.CONFIRMED,
        ConfirmationStatus.REJECTED,
    )


def can_user_override(status: ConfirmationStatus) -> bool:
    """
    Check if user can override an auto-assigned status.
    
    Policy:
    - auto_confirmed: User can override to rejected if needed
    - auto_rejected: User can override to confirmed
    - manual_review: User must resolve to confirmed or rejected
    - pending: User must resolve to confirmed or rejected
    """
    return status in (
        ConfirmationStatus.AUTO_CONFIRMED,
        ConfirmationStatus.AUTO_REJECTED,
        ConfirmationStatus.MANUAL_REVIEW,
        ConfirmationStatus.PENDING,
    )


# ============================================================================
# Result Models
# ============================================================================

@dataclass
class ConfirmationCreationResult:
    """Result of creating confirmations from crawl."""
    research_run_id: str
    crawl_id: str
    total_pages: int
    created: int
    skipped: int
    by_status: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class PendingConfirmationItem:
    """Single pending confirmation item for API response."""
    confirmation_id: str
    crawl_page_id: str
    url: str
    canonical_url: str
    title: Optional[str]
    snippet: Optional[str]
    content_quality: str
    identity_confidence_percent: Optional[int]
    identity_match_tier: Optional[str]
    match_details: Optional[Dict[str, Any]]
    submitted_root_url: Optional[str]
    status: str
    created_at: str


@dataclass
class PendingConfirmationList:
    """List of pending confirmations with pagination."""
    items: List[PendingConfirmationItem]
    total: int
    limit: int
    offset: int
    has_more: bool


@dataclass
class ConfirmationResolveResult:
    """Result of resolving a single confirmation."""
    confirmation_id: str
    research_run_id: str
    previous_status: str
    new_status: str
    action: str
    resolved_at: str
    user_override: bool  # True if user overrode auto-assigned status
    error: Optional[str] = None


@dataclass
class BulkResolveResult:
    """Result of bulk resolving confirmations."""
    research_run_id: str
    action: str
    requested: int
    succeeded: int
    failed: int
    results: List[ConfirmationResolveResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ConfirmationSummary:
    """Summary of confirmation status counts."""
    research_run_id: str
    twin_id: str
    total: int
    pending: int
    auto_confirmed: int
    auto_rejected: int
    manual_review: int
    confirmed: int
    rejected: int
    all_resolved: bool
    resolution_percent: float  # 0.0-100.0


# ============================================================================
# Source Confirmation Manager
# ============================================================================

class SourceConfirmationManager:
    """
    Manages source confirmation workflow for research runs.
    
    Responsibilities:
    - Create confirmation records from crawl pages
    - Apply auto-resolution thresholds
    - Fetch pending confirmations for user review
    - Resolve single confirmations (confirm/reject)
    - Bulk resolve confirmations
    - Compute aggregate confirmation summaries
    """
    
    def __init__(
        self,
        auto_confirm_threshold: float = AUTO_CONFIRM_THRESHOLD,
        auto_reject_threshold: float = AUTO_REJECT_THRESHOLD,
    ):
        """
        Initialize manager with thresholds.
        
        Args:
            auto_confirm_threshold: Score >= this value -> auto_confirmed
            auto_reject_threshold: Score < this value -> auto_rejected
        """
        self.auto_confirm_threshold = auto_confirm_threshold
        self.auto_reject_threshold = auto_reject_threshold
    
    async def create_confirmations_for_crawl(
        self,
        research_run_id: str,
        crawl_id: str,
        twin_id: str,
        user_id: Optional[str] = None,
    ) -> ConfirmationCreationResult:
        """
        Create confirmation records from crawl pages.
        
        Idempotent: Will not create duplicates for existing confirmations.
        
        Args:
            research_run_id: Research run ID to associate with
            crawl_id: Crawl run ID to source pages from
            twin_id: Twin ID for scoping
            user_id: Optional user who initiated the crawl
        
        Returns:
            ConfirmationCreationResult with counts by status
        """
        try:
            # Fetch crawl pages with identity scores
            pages = self._fetch_crawl_pages(crawl_id, twin_id)
            
            created = 0
            skipped = 0
            by_status: Dict[str, int] = {}
            
            for page in pages:
                page_id = page.get("id")
                
                # Check if confirmation already exists
                if self._confirmation_exists(research_run_id, page_id):
                    skipped += 1
                    continue
                
                # Normalize score
                raw_score = page.get("identity_confidence_score")
                normalized_score = normalize_identity_score_for_thresholds(raw_score)
                
                # Parse content quality
                quality_str = page.get("content_quality", "full")
                try:
                    content_quality = ContentQuality(quality_str)
                except ValueError:
                    content_quality = ContentQuality.FULL
                
                # Determine initial status
                initial_status = map_score_to_initial_status(
                    normalized_score,
                    content_quality
                )
                
                # Create confirmation record
                self._create_confirmation_record(
                    research_run_id=research_run_id,
                    crawl_page_id=page_id,
                    twin_id=twin_id,
                    initial_status=initial_status,
                    normalized_score=normalized_score,
                    content_quality=content_quality,
                    page_data=page,
                )
                
                created += 1
                by_status[initial_status.value] = by_status.get(initial_status.value, 0) + 1
            
            return ConfirmationCreationResult(
                research_run_id=research_run_id,
                crawl_id=crawl_id,
                total_pages=len(pages),
                created=created,
                skipped=skipped,
                by_status=by_status,
            )
            
        except Exception as e:
            logger.error(f"Error creating confirmations: {e}")
            return ConfirmationCreationResult(
                research_run_id=research_run_id,
                crawl_id=crawl_id,
                total_pages=0,
                created=0,
                skipped=0,
                error=str(e),
            )
    
    def _fetch_crawl_pages(self, crawl_id: str, twin_id: str) -> List[Dict[str, Any]]:
        """Fetch crawl pages with identity scores."""
        try:
            response = supabase.table("crawl_pages").select(
                "*"
            ).eq("crawl_id", crawl_id).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching crawl pages: {e}")
            return []
    
    def _confirmation_exists(self, research_run_id: str, crawl_page_id: str) -> bool:
        """Check if confirmation already exists for this page and research run."""
        try:
            response = supabase.table("source_confirmations").select(
                "id"
            ).eq("research_run_id", research_run_id).eq(
                "crawl_page_id", crawl_page_id
            ).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking confirmation existence: {e}")
            return False
    
    def _create_confirmation_record(
        self,
        research_run_id: str,
        crawl_page_id: str,
        twin_id: str,
        initial_status: ConfirmationStatus,
        normalized_score: Optional[float],
        content_quality: ContentQuality,
        page_data: Dict[str, Any],
    ) -> None:
        """Create a single confirmation record."""
        try:
            insert_data = {
                "id": str(uuid.uuid4()),
                "research_run_id": research_run_id,
                "crawl_page_id": crawl_page_id,
                "twin_id": twin_id,
                "confirmation_status": initial_status.value,
                "identity_confidence_score": format_score_for_display(normalized_score),
                "content_quality": content_quality.value,
                "url": page_data.get("url"),
                "canonical_url": page_data.get("canonical_url"),
                "title": page_data.get("title"),
                "snippet": self._extract_snippet(page_data),
                "submitted_root_url": page_data.get("submitted_root_url"),
                "match_details": page_data.get("identity_match_details"),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            supabase.table("source_confirmations").insert(insert_data).execute()
            
        except Exception as e:
            logger.error(f"Error creating confirmation record: {e}")
            raise
    
    def _extract_snippet(self, page_data: Dict[str, Any]) -> Optional[str]:
        """Extract a snippet from page data for display."""
        # Try to get from metadata or content
        metadata = page_data.get("metadata", {})
        if isinstance(metadata, dict):
            snippet = metadata.get("description") or metadata.get("og:description")
            if snippet:
                return snippet[:500]  # Limit length
        
        return None
    
    async def list_pending_confirmations(
        self,
        research_run_id: str,
        twin_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> PendingConfirmationList:
        """
        List pending confirmations awaiting user review.
        
        Returns items that need user action:
        - pending
        - manual_review
        - auto_rejected (user can override)
        
        Excludes terminal statuses (confirmed, rejected, auto_confirmed).
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
            limit: Max items to return
            offset: Pagination offset
        
        Returns:
            PendingConfirmationList
        """
        try:
            # Query for non-terminal statuses that need review
            statuses_needing_review = [
                ConfirmationStatus.PENDING.value,
                ConfirmationStatus.MANUAL_REVIEW.value,
                ConfirmationStatus.AUTO_REJECTED.value,
            ]
            
            response = supabase.table("source_confirmations").select(
                "*"
            ).eq("research_run_id", research_run_id).eq(
                "twin_id", twin_id
            ).in_("confirmation_status", statuses_needing_review).order(
                "created_at", desc=False
            ).range(offset, offset + limit - 1).execute()
            
            items = []
            for row in response.data or []:
                raw_score = row.get("identity_confidence_score")
                normalized = normalize_identity_score_for_thresholds(raw_score)
                quality_str = row.get("content_quality", "full")
                try:
                    content_quality = ContentQuality(quality_str)
                except ValueError:
                    content_quality = ContentQuality.FULL
                
                items.append(PendingConfirmationItem(
                    confirmation_id=row["id"],
                    crawl_page_id=row["crawl_page_id"],
                    url=row.get("url", ""),
                    canonical_url=row.get("canonical_url", ""),
                    title=row.get("title"),
                    snippet=row.get("snippet"),
                    content_quality=row.get("content_quality", "full"),
                    identity_confidence_percent=format_score_for_display(normalized),
                    identity_match_tier=score_to_identity_match_tier(
                        normalized,
                        content_quality=content_quality,
                    ),
                    match_details=row.get("match_details"),
                    submitted_root_url=row.get("submitted_root_url"),
                    status=row["confirmation_status"],
                    created_at=row["created_at"],
                ))
            
            # Get total count
            count_response = supabase.table("source_confirmations").select(
                "id", count="exact"
            ).eq("research_run_id", research_run_id).eq(
                "twin_id", twin_id
            ).in_("confirmation_status", statuses_needing_review).execute()
            
            total = count_response.count or len(items)
            
            return PendingConfirmationList(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
                has_more=(offset + len(items)) < total,
            )
            
        except Exception as e:
            logger.error(f"Error listing pending confirmations: {e}")
            return PendingConfirmationList(
                items=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False,
            )
    
    async def resolve_confirmation(
        self,
        research_run_id: str,
        confirmation_id: str,
        twin_id: str,
        actor_user_id: str,
        action: str,
        feedback: Optional[str] = None,
    ) -> ConfirmationResolveResult:
        """
        Resolve a single confirmation (confirm or reject).
        
        Args:
            research_run_id: Research run ID
            confirmation_id: Confirmation ID to resolve
            twin_id: Twin ID for authorization
            actor_user_id: User performing the action
            action: "confirm" or "reject"
            feedback: Optional user feedback/reason
        
        Returns:
            ConfirmationResolveResult
        """
        try:
            # Validate action
            if action not in (ConfirmationAction.CONFIRM.value, ConfirmationAction.REJECT.value):
                return ConfirmationResolveResult(
                    confirmation_id=confirmation_id,
                    research_run_id=research_run_id,
                    previous_status="",
                    new_status="",
                    action=action,
                    resolved_at=datetime.utcnow().isoformat(),
                    user_override=False,
                    error=f"Invalid action: {action}. Must be 'confirm' or 'reject'.",
                )
            
            # Fetch confirmation
            confirmation = self._fetch_confirmation(confirmation_id, research_run_id, twin_id)
            if not confirmation:
                return ConfirmationResolveResult(
                    confirmation_id=confirmation_id,
                    research_run_id=research_run_id,
                    previous_status="",
                    new_status="",
                    action=action,
                    resolved_at=datetime.utcnow().isoformat(),
                    user_override=False,
                    error="Confirmation not found or does not belong to this research run",
                )
            
            previous_status = confirmation["confirmation_status"]
            
            # Check if already terminal
            if is_status_terminal(ConfirmationStatus(previous_status)):
                return ConfirmationResolveResult(
                    confirmation_id=confirmation_id,
                    research_run_id=research_run_id,
                    previous_status=previous_status,
                    new_status=previous_status,
                    action=action,
                    resolved_at=datetime.utcnow().isoformat(),
                    user_override=False,
                    error=f"Confirmation already resolved with status: {previous_status}",
                )
            
            # Determine new status
            new_status = (
                ConfirmationStatus.CONFIRMED.value
                if action == ConfirmationAction.CONFIRM.value
                else ConfirmationStatus.REJECTED.value
            )
            
            # Check if user is overriding auto-assigned status
            user_override = previous_status in (
                ConfirmationStatus.AUTO_CONFIRMED.value,
                ConfirmationStatus.AUTO_REJECTED.value,
            )
            
            # Update confirmation
            self._update_confirmation_status(
                confirmation_id=confirmation_id,
                new_status=new_status,
                actor_user_id=actor_user_id,
                feedback=feedback,
            )
            
            return ConfirmationResolveResult(
                confirmation_id=confirmation_id,
                research_run_id=research_run_id,
                previous_status=previous_status,
                new_status=new_status,
                action=action,
                resolved_at=datetime.utcnow().isoformat(),
                user_override=user_override,
            )
            
        except Exception as e:
            logger.error(f"Error resolving confirmation: {e}")
            return ConfirmationResolveResult(
                confirmation_id=confirmation_id,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                action=action,
                resolved_at=datetime.utcnow().isoformat(),
                user_override=False,
                error=str(e),
            )
    
    def _fetch_confirmation(
        self,
        confirmation_id: str,
        research_run_id: str,
        twin_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single confirmation with authorization checks."""
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                response = supabase.table("source_confirmations").select(
                    "*"
                ).eq("id", confirmation_id).eq(
                    "research_run_id", research_run_id
                ).eq("twin_id", twin_id).execute()

                if response.data:
                    return response.data[0]
                return None
            except Exception as e:
                last_error = e
                if "server disconnected" in str(e).lower() and attempt == 0:
                    logger.warning("Transient disconnection fetching confirmation; retrying once")
                    continue
                logger.error(f"Error fetching confirmation: {e}")
                raise

        if last_error:
            raise RuntimeError(f"Error fetching confirmation: {last_error}") from last_error
        return None
    
    def _update_confirmation_status(
        self,
        confirmation_id: str,
        new_status: str,
        actor_user_id: str,
        feedback: Optional[str],
    ) -> None:
        """Update confirmation status in database."""
        update_data = {
            "confirmation_status": new_status,
            "confirmed_by_user_id": actor_user_id,
            "confirmed_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        if feedback:
            update_data["rejection_reason"] = feedback
        
        supabase.table("source_confirmations").update(update_data).eq(
            "id", confirmation_id
        ).execute()
    
    async def bulk_resolve_confirmations(
        self,
        research_run_id: str,
        twin_id: str,
        actor_user_id: str,
        confirmation_ids: List[str],
        action: str,
        feedback: Optional[str] = None,
    ) -> BulkResolveResult:
        """
        Resolve multiple confirmations in bulk.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
            actor_user_id: User performing the action
            confirmation_ids: List of confirmation IDs to resolve
            action: "confirm" or "reject"
            feedback: Optional user feedback/reason
        
        Returns:
            BulkResolveResult with individual results
        """
        results = []
        errors = []
        succeeded = 0
        failed = 0
        
        for confirmation_id in confirmation_ids:
            result = await self.resolve_confirmation(
                research_run_id=research_run_id,
                confirmation_id=confirmation_id,
                twin_id=twin_id,
                actor_user_id=actor_user_id,
                action=action,
                feedback=feedback,
            )
            
            results.append(result)
            
            if result.error:
                errors.append(f"{confirmation_id}: {result.error}")
                failed += 1
            else:
                succeeded += 1
        
        return BulkResolveResult(
            research_run_id=research_run_id,
            action=action,
            requested=len(confirmation_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
            errors=errors,
        )
    
    async def get_confirmation_summary(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> ConfirmationSummary:
        """
        Get summary of confirmation statuses for a research run.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
        
        Returns:
            ConfirmationSummary with counts and resolution status
        """
        try:
            # Fetch all confirmations for this research run
            response = supabase.table("source_confirmations").select(
                "confirmation_status"
            ).eq("research_run_id", research_run_id).eq(
                "twin_id", twin_id
            ).execute()
            
            # Count by status
            counts: Dict[str, int] = {}
            for row in response.data or []:
                status = row["confirmation_status"]
                counts[status] = counts.get(status, 0) + 1
            
            total = len(response.data or [])
            pending = counts.get(ConfirmationStatus.PENDING.value, 0)
            auto_confirmed = counts.get(ConfirmationStatus.AUTO_CONFIRMED.value, 0)
            auto_rejected = counts.get(ConfirmationStatus.AUTO_REJECTED.value, 0)
            manual_review = counts.get(ConfirmationStatus.MANUAL_REVIEW.value, 0)
            confirmed = counts.get(ConfirmationStatus.CONFIRMED.value, 0)
            rejected = counts.get(ConfirmationStatus.REJECTED.value, 0)
            
            # Calculate resolution
            resolved = confirmed + rejected + auto_confirmed
            all_resolved = total > 0 and (pending + manual_review + auto_rejected) == 0
            resolution_percent = (resolved / total * 100) if total > 0 else 100.0
            
            return ConfirmationSummary(
                research_run_id=research_run_id,
                twin_id=twin_id,
                total=total,
                pending=pending,
                auto_confirmed=auto_confirmed,
                auto_rejected=auto_rejected,
                manual_review=manual_review,
                confirmed=confirmed,
                rejected=rejected,
                all_resolved=all_resolved,
                resolution_percent=round(resolution_percent, 1),
            )
            
        except Exception as e:
            logger.error(f"Error getting confirmation summary: {e}")
            return ConfirmationSummary(
                research_run_id=research_run_id,
                twin_id=twin_id,
                total=0,
                pending=0,
                auto_confirmed=0,
                auto_rejected=0,
                manual_review=0,
                confirmed=0,
                rejected=0,
                all_resolved=False,
                resolution_percent=0.0,
            )
    
    async def are_all_confirmations_resolved(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> bool:
        """
        Check if all confirmations are resolved (no pending/manual_review).
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
        
        Returns:
            True if all confirmations are resolved
        """
        summary = await self.get_confirmation_summary(research_run_id, twin_id)
        return summary.all_resolved


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_confirmations_for_crawl(
    research_run_id: str,
    crawl_id: str,
    twin_id: str,
    user_id: Optional[str] = None,
) -> ConfirmationCreationResult:
    """Convenience function to create confirmations without instantiating manager."""
    manager = SourceConfirmationManager()
    return await manager.create_confirmations_for_crawl(
        research_run_id=research_run_id,
        crawl_id=crawl_id,
        twin_id=twin_id,
        user_id=user_id,
    )


async def resolve_confirmation(
    research_run_id: str,
    confirmation_id: str,
    twin_id: str,
    actor_user_id: str,
    action: str,
    feedback: Optional[str] = None,
) -> ConfirmationResolveResult:
    """Convenience function to resolve confirmation without instantiating manager."""
    manager = SourceConfirmationManager()
    return await manager.resolve_confirmation(
        research_run_id=research_run_id,
        confirmation_id=confirmation_id,
        twin_id=twin_id,
        actor_user_id=actor_user_id,
        action=action,
        feedback=feedback,
    )
