"""
Crawl Job Processor Module (Phase 3.2)

Production-grade crawl job processor that orchestrates Firecrawl-based crawling
with identity confidence scoring and confirmation status mapping.

Integrates:
- Firecrawl client (Phase 3.0) for content fetching
- Identity confidence scorer (Phase 3.1) for source verification
- Existing crawl repository/manager (Phases 1A-1B) for persistence/classification
- Artifact store for content storage
- Failure taxonomy for error handling

Usage:
    processor = CrawlJobProcessor()
    result = await processor.process_crawl_job(
        job_id="job-123",
        crawl_id="crawl-456",
        twin_id="twin-789"
    )
"""

import uuid
import logging
import sys
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from modules.firecrawl_client import (
    FirecrawlClient,
    FirecrawlConfig,
    FirecrawlResult,
    ContentQuality,
    get_firecrawl_client,
)
from modules.identity_confidence_scorer import (
    IdentityConfidenceScorer,
    IdentityScoreResult,
    score_identity_confidence,
)
from modules.crawl_repository import CrawlRepository
from modules.crawl_manager import CrawlManager, PageClassification
from modules.crawl_failure_taxonomy import FailureType, create_failure_artifact
from modules.artifact_store import get_artifact_store, ArtifactStore
from modules.url_canonicalizer import canonicalize_url
from modules.content_hasher import compute_secure_hash

logger = logging.getLogger(__name__)

# Keep module identity stable across both import paths:
# "modules.crawl_job_processor" and "backend.modules.crawl_job_processor".
if __name__.startswith("modules."):
    sys.modules.setdefault(f"backend.{__name__}", sys.modules[__name__])
elif __name__.startswith("backend.modules."):
    sys.modules.setdefault(__name__.replace("backend.", "", 1), sys.modules[__name__])

_AUTO_FIRECRAWL_CLIENT = object()


# ============================================================================
# Confirmation Status Constants (Phase 3.2)
# ============================================================================

class ConfirmationStatus(str, Enum):
    """
    Source confirmation status based on identity confidence score.
    
    These are Phase 3.2 temporary classifications until full confirmation
    system (Phase 3.3) is implemented.
    """
    AUTO_CONFIRMED = "auto_confirmed"    # score >= 0.80
    PENDING = "pending"                   # 0.50 <= score < 0.80
    AUTO_REJECTED = "auto_rejected"       # score < 0.50
    MANUAL_REVIEW = "manual_review"       # For blocked/manual-needed quality


# Score thresholds (match Phase 3.1 IdentityScoreResult)
AUTO_CONFIRM_THRESHOLD = 0.80
AUTO_REJECT_THRESHOLD = 0.50


def map_identity_score_to_confirmation_status(
    score: float,
    content_quality: ContentQuality
) -> ConfirmationStatus:
    """
    Map identity confidence score and content quality to confirmation status.
    
    Args:
        score: Identity confidence score (0.0 to 1.0)
        content_quality: Content quality from Firecrawl
    
    Returns:
        ConfirmationStatus enum value
    """
    # Blocked or manual-needed content goes to manual review regardless of score
    if content_quality in (ContentQuality.BLOCKED, ContentQuality.MANUAL_NEEDED):
        return ConfirmationStatus.MANUAL_REVIEW
    
    if score >= AUTO_CONFIRM_THRESHOLD:
        return ConfirmationStatus.AUTO_CONFIRMED
    elif score >= AUTO_REJECT_THRESHOLD:
        return ConfirmationStatus.PENDING
    else:
        return ConfirmationStatus.AUTO_REJECTED


# ============================================================================
# Source Strategy Resolver
# ============================================================================

class SourceType(str, Enum):
    """Classification of crawl source types."""
    WEBSITE_ROOT = "website_root"      # Root domain to crawl
    ARTICLE_PAGE = "article_page"      # Single article/page
    LINKEDIN_PROFILE = "linkedin_profile"
    YOUTUBE_VIDEO = "youtube_video"
    TWITTER_PROFILE = "twitter_profile"
    INSTAGRAM_PROFILE = "instagram_profile"
    GENERIC_SOCIAL = "generic_social"  # Other social platforms
    UNKNOWN = "unknown"


@dataclass
class SourceStrategy:
    """Strategy decision for crawling a source."""
    source_type: SourceType
    method: str                          # "crawl" or "scrape"
    reason: str                          # Human-readable explanation
    firecrawl_params: Dict[str, Any] = field(default_factory=dict)


class SourceStrategyResolver:
    """
    Resolves crawling strategy based on URL patterns.
    
    Firecrawl-only production strategy matrix:
    - Website root -> crawl_with_polling() (discover subpages)
    - Single page/article -> scrape_with_retry()
    - LinkedIn/social -> scrape_with_retry() with gating awareness
    - YouTube -> scrape_with_retry() (partial extraction expected)
    """
    
    # URL patterns for classification
    PATTERNS = {
        SourceType.LINKEDIN_PROFILE: [
            r"linkedin\.com\/in\/",
            r"linkedin\.com\/company\/",
        ],
        SourceType.YOUTUBE_VIDEO: [
            r"youtube\.com\/watch",
            r"youtube\.com\/shorts",
            r"youtu\.be\/",
        ],
        SourceType.TWITTER_PROFILE: [
            r"twitter\.com\/",
            r"x\.com\/",
        ],
        SourceType.INSTAGRAM_PROFILE: [
            r"instagram\.com\/",
        ],
        SourceType.ARTICLE_PAGE: [
            r"\/article\/",
            r"\/blog\/",
            r"\/post\/",
            r"\/news\/",
            r"\.html?$",
        ],
    }
    
    @classmethod
    def resolve(cls, url: str) -> SourceStrategy:
        """
        Determine crawling strategy for a URL.
        
        Args:
            url: The URL to crawl
        
        Returns:
            SourceStrategy with method and parameters
        """
        import re
        url_lower = url.lower()
        
        # Check for specific platform patterns
        for source_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return cls._strategy_for_type(source_type, url)
        
        # Default: treat as website root for crawling
        return cls._strategy_for_type(SourceType.WEBSITE_ROOT, url)
    
    @classmethod
    def _strategy_for_type(cls, source_type: SourceType, url: str) -> SourceStrategy:
        """Create strategy configuration for source type."""
        
        if source_type == SourceType.WEBSITE_ROOT:
            return SourceStrategy(
                source_type=source_type,
                method="crawl",
                reason="Website root URL - use deep crawl to discover pages",
                firecrawl_params={
                    "limit": 50,
                    "max_depth": 3,
                    "scrapeOptions": {"formats": ["markdown"]},
                }
            )
        
        elif source_type == SourceType.YOUTUBE_VIDEO:
            return SourceStrategy(
                source_type=source_type,
                method="scrape",
                reason="YouTube video - single page scrape (description only expected)",
                firecrawl_params={
                    "formats": ["markdown"],
                    # Note: YouTube transcripts require special handling
                    "includeTags": ["title", "meta", "h1", "p"],
                }
            )
        
        elif source_type in (
            SourceType.LINKEDIN_PROFILE,
            SourceType.TWITTER_PROFILE,
            SourceType.INSTAGRAM_PROFILE,
            SourceType.GENERIC_SOCIAL
        ):
            return SourceStrategy(
                source_type=source_type,
                method="scrape",
                reason=f"{source_type.value} - single page scrape with gating awareness",
                firecrawl_params={
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                }
            )
        
        else:  # ARTICLE_PAGE or UNKNOWN
            return SourceStrategy(
                source_type=source_type,
                method="scrape",
                reason="Single page/article - use scrape",
                firecrawl_params={
                    "formats": ["markdown"],
                }
            )


# ============================================================================
# Crawl Job Result Models
# ============================================================================

class CrawlJobStatus(str, Enum):
    """Status of a crawl job execution."""
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PageProcessingResult:
    """Result of processing a single page."""
    page_id: str
    url: str
    canonical_url: str
    success: bool
    classification: Optional[PageClassification] = None
    content_quality: ContentQuality = ContentQuality.FULL
    identity_score: Optional[float] = None
    confirmation_status: Optional[ConfirmationStatus] = None
    failure_type: Optional[FailureType] = None
    error_message: Optional[str] = None
    artifact_path: Optional[str] = None
    content_hash: Optional[str] = None


@dataclass
class CrawlJobResult:
    """Result of a crawl job execution."""
    job_id: str
    crawl_id: str
    status: CrawlJobStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Summary metrics
    total_urls: int = 0
    pages_discovered: int = 0
    pages_fetched: int = 0
    pages_new: int = 0
    pages_changed: int = 0
    pages_unchanged: int = 0
    pages_failed: int = 0
    pages_blocked: int = 0
    pages_manual_needed: int = 0
    
    # Identity confirmation summary
    auto_confirmed: int = 0
    pending: int = 0
    auto_rejected: int = 0
    manual_review: int = 0
    
    # Error tracking
    failures_by_type: Dict[str, int] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    # Page-level results
    page_results: List[PageProcessingResult] = field(default_factory=list)


# ============================================================================
# Crawl Job Processor
# ============================================================================

class CrawlJobProcessor:
    """
    Production-grade crawl job processor.
    
    Orchestrates:
    1. Source strategy resolution
    2. Firecrawl content fetching
    3. Page classification (existing crawl manager)
    4. Identity confidence scoring
    5. Artifact storage
    6. Database persistence
    7. Crawl run lifecycle management
    """
    
    def __init__(
        self,
        firecrawl_client: Optional[FirecrawlClient] | object = _AUTO_FIRECRAWL_CLIENT,
        crawl_repository: Optional[CrawlRepository] = None,
        crawl_manager: Optional[CrawlManager] = None,
        identity_scorer: Optional[IdentityConfidenceScorer] = None,
        artifact_store: Optional[ArtifactStore] = None,
    ):
        """
        Initialize processor with dependencies.
        
        Args:
            firecrawl_client: Firecrawl client for content fetching
            crawl_repository: Repository for crawl persistence
            crawl_manager: Manager for page classification
            identity_scorer: Scorer for identity confidence
            artifact_store: Store for content artifacts
        """
        # Sentinel semantics:
        # - omitted arg => auto-load configured Firecrawl client
        # - explicit None => disable Firecrawl (for tests/fallback execution)
        if firecrawl_client is _AUTO_FIRECRAWL_CLIENT:
            self.firecrawl = get_firecrawl_client()
        else:
            self.firecrawl = firecrawl_client
        self.repository = crawl_repository or CrawlRepository()
        self.manager = crawl_manager or CrawlManager()
        self.scorer = identity_scorer or IdentityConfidenceScorer()
        self.artifacts = artifact_store or get_artifact_store()
    
    async def process_crawl_job(
        self,
        job_id: str,
        crawl_id: str,
        twin_id: Optional[str] = None,
        claimed_identity: Optional[Dict[str, Any]] = None,
    ) -> CrawlJobResult:
        """
        Process a crawl job end-to-end.
        
        Args:
            job_id: Unique job execution ID
            crawl_id: Crawl run ID to process
            twin_id: Optional twin ID (fetched from crawl run if not provided)
            claimed_identity: Optional claimed identity for scoring
        
        Returns:
            CrawlJobResult with status and metrics
        """
        started_at = datetime.utcnow()
        
        try:
            # Fetch crawl run configuration
            crawl_run = self._get_crawl_run(crawl_id)
            if not crawl_run:
                return self._create_failed_result(
                    job_id, crawl_id, started_at, f"Crawl run {crawl_id} not found"
                )
            
            # Get twin_id from crawl run if not provided
            if not twin_id:
                twin_id = crawl_run.get("twin_id")
            
            if not twin_id:
                return self._create_failed_result(
                    job_id, crawl_id, started_at, "No twin_id available for crawl"
                )
            
            # Update crawl run status to running
            self._update_crawl_status(crawl_id, "running")
            
            # Get seed URLs
            seed_urls = crawl_run.get("seed_urls", [])
            if not seed_urls:
                return self._create_failed_result(
                    job_id, crawl_id, started_at, "No seed URLs in crawl run"
                )
            
            # Process each seed URL
            page_results: List[PageProcessingResult] = []
            
            for seed_url in seed_urls:
                try:
                    # Resolve strategy
                    strategy = SourceStrategyResolver.resolve(seed_url)
                    logger.info(f"Processing {seed_url} with strategy: {strategy.method}")
                    
                    # Execute based on strategy
                    if strategy.method == "crawl":
                        results = await self._process_crawl_strategy(
                            seed_url, crawl_id, twin_id, strategy, claimed_identity
                        )
                    else:
                        results = await self._process_scrape_strategy(
                            seed_url, crawl_id, twin_id, strategy, claimed_identity
                        )
                    
                    page_results.extend(results)
                    
                except Exception as e:
                    logger.error(f"Error processing seed URL {seed_url}: {e}")
                    page_results.append(PageProcessingResult(
                        page_id=str(uuid.uuid4()),
                        url=seed_url,
                        canonical_url=canonicalize_url(seed_url),
                        success=False,
                        error_message=str(e),
                    ))
            
            # Finalize crawl run
            result = self._finalize_job_result(
                job_id, crawl_id, started_at, page_results
            )
            
            # Update crawl run with final status
            self._update_crawl_status(crawl_id, result.status.value, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            self._update_crawl_status(crawl_id, "failed")
            return self._create_failed_result(job_id, crawl_id, started_at, str(e))
    
    def _get_crawl_run(self, crawl_id: str) -> Optional[Dict[str, Any]]:
        """Fetch crawl run from repository."""
        try:
            from modules.observability import supabase
            response = supabase.table("crawl_runs").select("*").eq("id", crawl_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching crawl run {crawl_id}: {e}")
            return None
    
    def _update_crawl_status(
        self,
        crawl_id: str,
        status: str,
        result: Optional[CrawlJobResult] = None
    ) -> None:
        """Update crawl run status in database."""
        try:
            update_data = {"status": status}
            
            if status == "running":
                update_data["started_at"] = datetime.utcnow().isoformat()
            elif status in ("completed", "failed", "completed_with_warnings"):
                update_data["completed_at"] = datetime.utcnow().isoformat()
            
            # Add summary metrics if available
            if result:
                update_data["pages_found"] = result.pages_discovered
                update_data["pages_ingested"] = result.pages_fetched
                update_data["pages_failed"] = result.pages_failed
            
            from modules.observability import supabase
            supabase.table("crawl_runs").update(update_data).eq("id", crawl_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating crawl status: {e}")
    
    async def _process_crawl_strategy(
        self,
        seed_url: str,
        crawl_id: str,
        twin_id: str,
        strategy: SourceStrategy,
        claimed_identity: Optional[Dict[str, Any]],
    ) -> List[PageProcessingResult]:
        """
        Process a crawl strategy (multi-page).
        
        Args:
            seed_url: Starting URL
            crawl_id: Crawl run ID
            twin_id: Twin ID
            strategy: Source strategy configuration
            claimed_identity: Identity for scoring
        
        Returns:
            List of page processing results
        """
        results = []
        
        if not self.firecrawl:
            logger.warning("Firecrawl not configured, skipping crawl")
            return results
        
        try:
            # Execute crawl via Firecrawl
            crawl_results = await self.firecrawl.crawl_with_polling(
                url=seed_url,
                limit=strategy.firecrawl_params.get("limit", 50),
                max_depth=strategy.firecrawl_params.get("max_depth", 3),
            )
            
            for firecrawl_result in crawl_results:
                page_result = await self._process_firecrawl_result(
                    firecrawl_result,
                    crawl_id,
                    twin_id,
                    seed_url,
                    claimed_identity,
                )
                results.append(page_result)
                
        except Exception as e:
            logger.error(f"Error in crawl strategy for {seed_url}: {e}")
            # Create failure result
            canonical_url = canonicalize_url(seed_url)
            page_id = str(uuid.uuid4())
            results.append(PageProcessingResult(
                page_id=page_id,
                url=seed_url,
                canonical_url=canonical_url,
                success=False,
                failure_type=FailureType.NETWORK,
                error_message=str(e),
            ))
        
        return results
    
    async def _process_scrape_strategy(
        self,
        seed_url: str,
        crawl_id: str,
        twin_id: str,
        strategy: SourceStrategy,
        claimed_identity: Optional[Dict[str, Any]],
    ) -> List[PageProcessingResult]:
        """
        Process a scrape strategy (single page).
        
        Args:
            seed_url: URL to scrape
            crawl_id: Crawl run ID
            twin_id: Twin ID
            strategy: Source strategy configuration
            claimed_identity: Identity for scoring
        
        Returns:
            List with single page processing result
        """
        if not self.firecrawl:
            logger.warning("Firecrawl not configured, skipping scrape")
            return []
        
        try:
            # Execute scrape via Firecrawl
            firecrawl_result = await self.firecrawl.scrape_with_retry(
                url=seed_url,
                formats=["markdown"],
            )
            
            page_result = await self._process_firecrawl_result(
                firecrawl_result,
                crawl_id,
                twin_id,
                seed_url,
                claimed_identity,
            )
            
            return [page_result]
            
        except Exception as e:
            logger.error(f"Error in scrape strategy for {seed_url}: {e}")
            canonical_url = canonicalize_url(seed_url)
            page_id = str(uuid.uuid4())
            return [PageProcessingResult(
                page_id=page_id,
                url=seed_url,
                canonical_url=canonical_url,
                success=False,
                failure_type=FailureType.NETWORK,
                error_message=str(e),
            )]
    
    async def _process_firecrawl_result(
        self,
        firecrawl_result: FirecrawlResult,
        crawl_id: str,
        twin_id: str,
        submitted_root_url: str,
        claimed_identity: Optional[Dict[str, Any]],
    ) -> PageProcessingResult:
        """
        Process a single Firecrawl result.
        
        Args:
            firecrawl_result: Result from Firecrawl
            crawl_id: Crawl run ID
            twin_id: Twin ID
            submitted_root_url: Original submitted URL for lineage
            claimed_identity: Identity for scoring
        
        Returns:
            PageProcessingResult
        """
        url = firecrawl_result.url
        canonical_url = canonicalize_url(url)
        page_id = str(uuid.uuid4())
        
        # Determine content quality
        content_quality = firecrawl_result.quality
        
        # Handle failed fetches
        if not firecrawl_result.success:
            failure_type = FailureType.NETWORK
            if firecrawl_result.error:
                failure_type = firecrawl_result.error.get("failure_type", FailureType.NETWORK)
            
            # Persist failure to crawl_pages
            self._persist_page_record(
                page_id=page_id,
                crawl_id=crawl_id,
                url=url,
                canonical_url=canonical_url,
                status="failed",
                failure_type=failure_type,
                content_quality=content_quality,
                submitted_root_url=submitted_root_url,
            )
            
            return PageProcessingResult(
                page_id=page_id,
                url=url,
                canonical_url=canonical_url,
                success=False,
                content_quality=content_quality,
                failure_type=failure_type,
                error_message=firecrawl_result.error.get("detail") if firecrawl_result.error else None,
            )
        
        # Compute content hash
        content = firecrawl_result.content
        content_hash = compute_secure_hash(content) if content else None
        
        # Classify page (new/changed/unchanged)
        classification, prior_page = self.manager.classify_page(
            twin_id=twin_id,
            crawl_id=crawl_id,
            canonical_url=canonical_url,
            content=content,
        )
        
        # Score identity confidence if claimed identity provided
        identity_score: Optional[float] = None
        confirmation_status: Optional[ConfirmationStatus] = None
        
        if claimed_identity:
            score_result = self.scorer.score_page(
                page_content=content,
                page_metadata=firecrawl_result.metadata,
                claimed_identity=claimed_identity,
                content_quality=content_quality.value,
            )
            identity_score = score_result.score
            confirmation_status = map_identity_score_to_confirmation_status(
                identity_score,
                content_quality
            )
        
        # Store content in artifact store
        artifact_path: Optional[str] = None
        if content and classification != PageClassification.UNCHANGED:
            artifact_path = self._store_content_artifact(
                crawl_id, page_id, content, firecrawl_result.metadata
            )
        
        # Persist page record
        status = "fetched"
        if content_quality == ContentQuality.BLOCKED:
            status = "blocked"
        elif content_quality == ContentQuality.MANUAL_NEEDED:
            status = "manual_needed"
        
        self._persist_page_record(
            page_id=page_id,
            crawl_id=crawl_id,
            url=url,
            canonical_url=canonical_url,
            status=status,
            classification=classification.value if classification else None,
            content_hash=content_hash,
            content_quality=content_quality,
            identity_score=identity_score,
            confirmation_status=confirmation_status,
            artifact_path=artifact_path,
            submitted_root_url=submitted_root_url,
            firecrawl_result=firecrawl_result,
        )
        
        return PageProcessingResult(
            page_id=page_id,
            url=url,
            canonical_url=canonical_url,
            success=True,
            classification=classification,
            content_quality=content_quality,
            identity_score=identity_score,
            confirmation_status=confirmation_status,
            artifact_path=artifact_path,
            content_hash=content_hash,
        )
    
    def _persist_page_record(
        self,
        page_id: str,
        crawl_id: str,
        url: str,
        canonical_url: str,
        status: str,
        classification: Optional[str] = None,
        content_hash: Optional[str] = None,
        content_quality: Optional[ContentQuality] = None,
        identity_score: Optional[float] = None,
        confirmation_status: Optional[ConfirmationStatus] = None,
        artifact_path: Optional[str] = None,
        submitted_root_url: Optional[str] = None,
        failure_type: Optional[FailureType] = None,
        firecrawl_result: Optional[FirecrawlResult] = None,
    ) -> None:
        """Persist page record to database."""
        try:
            from modules.observability import supabase
            from modules.url_canonicalizer import get_url_hash
            
            # Build insert data
            insert_data = {
                "id": page_id,
                "crawl_id": crawl_id,
                "url": url,
                "canonical_url": canonical_url,
                "url_hash": get_url_hash(canonical_url),
                "status": status,
                "classification": classification,
                "content_hash": content_hash,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            # Add Phase 3.0+ columns if available
            if content_quality:
                insert_data["content_quality"] = content_quality.value
            if identity_score is not None:
                # Store as integer 0-100 in DB
                insert_data["identity_confidence_score"] = int(identity_score * 100)
            if confirmation_status:
                insert_data["confirmation_status"] = confirmation_status.value
            if artifact_path:
                insert_data["normalized_artifact_path"] = artifact_path
            if submitted_root_url:
                insert_data["submitted_root_url"] = submitted_root_url
            if failure_type:
                insert_data["failure_type"] = failure_type.value
            
            # Add metadata from Firecrawl result
            if firecrawl_result:
                metadata = firecrawl_result.metadata
                if metadata.get("title"):
                    insert_data["title"] = metadata["title"]
                if firecrawl_result.http_status:
                    insert_data["http_status"] = firecrawl_result.http_status
                if firecrawl_result.attempts:
                    insert_data["fetch_attempts"] = firecrawl_result.attempts
            
            try:
                supabase.table("crawl_pages").insert(insert_data).execute()
            except Exception as insert_error:
                # Backward compatibility for environments where newer crawl_pages
                # columns are not yet present.
                message = str(insert_error).lower()
                if "could not find" in message and "crawl_pages" in message:
                    optional_columns = (
                        "classification",
                        "content_quality",
                        "identity_confidence_score",
                        "confirmation_status",
                        "submitted_root_url",
                        "failure_type",
                        "title",
                        "http_status",
                        "fetch_attempts",
                    )
                    fallback = dict(insert_data)
                    removed = False
                    for column in optional_columns:
                        if column in message:
                            fallback.pop(column, None)
                            removed = True
                    if removed:
                        supabase.table("crawl_pages").insert(fallback).execute()
                    else:
                        raise
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Error persisting page record: {e}")
    
    def _store_content_artifact(
        self,
        crawl_id: str,
        page_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Store content in artifact store."""
        try:
            # Build artifact path: crawls/{crawl_id}/pages/{page_id}/normalized.md
            artifact_path = f"crawls/{crawl_id}/pages/{page_id}/normalized.md"
            
            # Store content
            self.artifacts.write_artifact(artifact_path, content)
            
            # Store metadata alongside
            metadata_path = f"crawls/{crawl_id}/pages/{page_id}/metadata.json"
            self.artifacts.write_json(metadata_path, metadata)
            
            return artifact_path
            
        except Exception as e:
            logger.error(f"Error storing artifact: {e}")
            return ""
    
    def _finalize_job_result(
        self,
        job_id: str,
        crawl_id: str,
        started_at: datetime,
        page_results: List[PageProcessingResult],
    ) -> CrawlJobResult:
        """Finalize crawl job result with metrics."""
        completed_at = datetime.utcnow()
        
        # Calculate metrics
        total_urls = len(set(r.url for r in page_results))
        pages_discovered = len(page_results)
        pages_fetched = sum(1 for r in page_results if r.success)
        pages_failed = sum(1 for r in page_results if not r.success)
        
        pages_new = sum(1 for r in page_results if r.classification == PageClassification.NEW)
        pages_changed = sum(1 for r in page_results if r.classification == PageClassification.CHANGED)
        pages_unchanged = sum(1 for r in page_results if r.classification == PageClassification.UNCHANGED)
        
        pages_blocked = sum(1 for r in page_results if r.content_quality == ContentQuality.BLOCKED)
        pages_manual_needed = sum(1 for r in page_results if r.content_quality == ContentQuality.MANUAL_NEEDED)
        
        # Identity confirmation summary
        auto_confirmed = sum(1 for r in page_results if r.confirmation_status == ConfirmationStatus.AUTO_CONFIRMED)
        pending = sum(1 for r in page_results if r.confirmation_status == ConfirmationStatus.PENDING)
        auto_rejected = sum(1 for r in page_results if r.confirmation_status == ConfirmationStatus.AUTO_REJECTED)
        manual_review = sum(1 for r in page_results if r.confirmation_status == ConfirmationStatus.MANUAL_REVIEW)
        
        # Failure types
        failures_by_type: Dict[str, int] = {}
        for r in page_results:
            if r.failure_type:
                ft = r.failure_type.value
                failures_by_type[ft] = failures_by_type.get(ft, 0) + 1
        
        # Determine status
        status = CrawlJobStatus.COMPLETED
        if pages_failed > 0 and pages_fetched == 0:
            status = CrawlJobStatus.FAILED
        elif pages_failed > 0 or pages_blocked > 0 or pages_manual_needed > 0:
            status = CrawlJobStatus.COMPLETED_WITH_WARNINGS
        
        return CrawlJobResult(
            job_id=job_id,
            crawl_id=crawl_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            total_urls=total_urls,
            pages_discovered=pages_discovered,
            pages_fetched=pages_fetched,
            pages_new=pages_new,
            pages_changed=pages_changed,
            pages_unchanged=pages_unchanged,
            pages_failed=pages_failed,
            pages_blocked=pages_blocked,
            pages_manual_needed=pages_manual_needed,
            auto_confirmed=auto_confirmed,
            pending=pending,
            auto_rejected=auto_rejected,
            manual_review=manual_review,
            failures_by_type=failures_by_type,
            page_results=page_results,
        )
    
    def _create_failed_result(
        self,
        job_id: str,
        crawl_id: str,
        started_at: datetime,
        error_message: str,
    ) -> CrawlJobResult:
        """Create a failed crawl job result."""
        return CrawlJobResult(
            job_id=job_id,
            crawl_id=crawl_id,
            status=CrawlJobStatus.FAILED,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            error_message=error_message,
        )


# ============================================================================
# Public Entrypoint
# ============================================================================

async def process_crawl_job(
    job_id: str,
    crawl_id: str,
    twin_id: Optional[str] = None,
    claimed_identity: Optional[Dict[str, Any]] = None,
    firecrawl_client: Optional[FirecrawlClient] | object = _AUTO_FIRECRAWL_CLIENT,
    crawl_repository: Optional[CrawlRepository] = None,
    crawl_manager: Optional[CrawlManager] = None,
    identity_scorer: Optional[IdentityConfidenceScorer] = None,
    artifact_store: Optional[ArtifactStore] = None,
) -> CrawlJobResult:
    """
    Convenience function to process a crawl job without instantiating processor.
    
    Args:
        job_id: Unique job execution ID
        crawl_id: Crawl run ID to process
        twin_id: Optional twin ID
        claimed_identity: Optional claimed identity for scoring
        firecrawl_client: Optional Firecrawl client.
            Omit to auto-load configured client.
            Pass None explicitly to disable Firecrawl (tests/fallback).
        crawl_repository: Optional crawl repository
        crawl_manager: Optional crawl manager
        identity_scorer: Optional identity scorer
        artifact_store: Optional artifact store
    
    Returns:
        CrawlJobResult
    """
    processor = CrawlJobProcessor(
        firecrawl_client=firecrawl_client,
        crawl_repository=crawl_repository,
        crawl_manager=crawl_manager,
        identity_scorer=identity_scorer,
        artifact_store=artifact_store,
    )
    return await processor.process_crawl_job(
        job_id=job_id,
        crawl_id=crawl_id,
        twin_id=twin_id,
        claimed_identity=claimed_identity,
    )
