"""
Research Claim Enrichment Service (Phase 8)

Orchestrates claim extraction and verification for research runs.
- Extract claims from confirmed sources
- Verify against ingested content
- Persist to database
- Track enrichment progress

Idempotent: Safe to retry. Checks existing state before processing.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from modules.observability import supabase
from modules.research_claim_extractor import (
    ResearchClaim,
    VerificationStatus,
    extract_claims_from_research_sources,
)
from modules.research_claim_verifier import (
    verify_research_claims,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class EnrichmentStatus(str, Enum):
    """Status of claim enrichment for a research run."""
    PENDING = "pending"
    ENRICHING = "enriching"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EnrichmentSummary:
    """Summary of claim enrichment results."""
    research_run_id: str
    status: EnrichmentStatus
    total_claims: int = 0
    supported_count: int = 0
    insufficient_count: int = 0
    conflicting_count: int = 0
    needs_review_count: int = 0
    pending_count: int = 0
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ResearchClaimService:
    """
    Service for claim enrichment operations.
    
    Orchestrates:
    1. Fetch confirmed sources for research run
    2. Extract claims
    3. Verify claims against sources
    4. Persist results
    5. Update enrichment status
    """
    
    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client (for testing)."""
        self.db = supabase_client or supabase
    
    async def get_enrichment_status(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> Optional[EnrichmentSummary]:
        """
        Get current enrichment status for a research run.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
        
        Returns:
            EnrichmentSummary or None if not started
        """
        try:
            result = self.db.table("research_claim_enrichment").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).limit(1).execute()

            rows = result.data or []
            if not rows:
                return None

            data = rows[0]
            return EnrichmentSummary(
                research_run_id=data["research_run_id"],
                status=EnrichmentStatus(data.get("status", "pending")),
                total_claims=data.get("total_claims", 0),
                supported_count=data.get("supported_count", 0),
                insufficient_count=data.get("insufficient_count", 0),
                conflicting_count=data.get("conflicting_count", 0),
                needs_review_count=data.get("needs_review_count", 0),
                pending_count=data.get("pending_count", 0),
                error_message=data.get("error_message"),
                started_at=data.get("started_at"),
                completed_at=data.get("completed_at"),
            )
            
        except Exception as e:
            logger.error(f"Error getting enrichment status: {e}")
            return None
    
    async def start_enrichment(
        self,
        research_run_id: str,
        twin_id: str,
        model: str = "gpt-4o-mini",
    ) -> EnrichmentSummary:
        """
        Start or continue claim enrichment for a research run.
        
        Idempotent: If already completed, returns existing summary.
        If in progress, returns current status.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID
            model: Model to use for extraction
        
        Returns:
            EnrichmentSummary
        """
        # Check current status
        existing = await self.get_enrichment_status(research_run_id, twin_id)
        
        if existing:
            if existing.status == EnrichmentStatus.COMPLETED:
                logger.info(f"Claim enrichment already completed for {research_run_id}")
                return existing
            
            if existing.status == EnrichmentStatus.ENRICHING:
                logger.info(f"Claim enrichment already in progress for {research_run_id}")
                return existing
        
        # Set status to enriching
        await self._update_status(research_run_id, twin_id, EnrichmentStatus.ENRICHING)
        
        try:
            # Fetch confirmed sources
            sources = await self._get_confirmed_sources(research_run_id, twin_id)
            
            if not sources:
                logger.warning(f"No confirmed sources found for {research_run_id}")
                summary = await self._complete_enrichment(
                    research_run_id, twin_id, [], "No confirmed sources available"
                )
                return summary
            
            # Extract claims
            logger.info(f"Extracting claims from {len(sources)} sources for {research_run_id}")
            extraction_result = await extract_claims_from_research_sources(
                sources=sources,
                twin_id=twin_id,
                research_run_id=research_run_id,
                model=model,
            )
            
            claims = extraction_result["claims"]
            
            if not claims:
                logger.info(f"No claims extracted for {research_run_id}")
                summary = await self._complete_enrichment(
                    research_run_id, twin_id, [], "No claims extracted"
                )
                return summary
            
            # Verify claims
            logger.info(f"Verifying {len(claims)} claims for {research_run_id}")
            verification_result = await verify_research_claims(
                claims=claims,
                sources=sources,
                similarity_threshold=0.7,
                use_llm=False,  # MVP: no LLM verification
            )
            
            # Persist verified claims
            await self._persist_claims(verification_result["results"])
            
            # Complete enrichment
            summary = await self._complete_enrichment(
                research_run_id,
                twin_id,
                verification_result["results"],
            )
            
            logger.info(f"Claim enrichment completed for {research_run_id}: "
                       f"{summary.total_claims} claims, "
                       f"{summary.supported_count} supported")
            
            return summary
            
        except Exception as e:
            logger.error(f"Claim enrichment failed for {research_run_id}: {e}")
            await self._update_status(
                research_run_id,
                twin_id,
                EnrichmentStatus.FAILED,
                error_message=str(e),
            )
            return EnrichmentSummary(
                research_run_id=research_run_id,
                status=EnrichmentStatus.FAILED,
                error_message=str(e),
            )
    
    async def _get_confirmed_sources(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch confirmed sources with content for a research run.
        
        Returns:
            List of source dicts with content, id, url, title
        """
        try:
            conf_result = self.db.table("source_confirmations").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
        except Exception as e:
            logger.error(f"Error fetching confirmed source confirmations: {e}")
            return []

        rows = conf_result.data or []
        if not rows:
            return []

        confirmed_page_ids = []
        for row in rows:
            status_value = (
                row.get("confirmation_status")
                or row.get("status")
                or row.get("state")
                or ""
            )
            if status_value not in ("confirmed", "auto_confirmed"):
                continue
            page_id = row.get("crawl_page_id")
            if page_id:
                confirmed_page_ids.append(page_id)

        if not confirmed_page_ids:
            return []

        sources: List[Dict[str, Any]] = []
        seen_source_ids = set()

        def _append_source_row(row: Dict[str, Any]) -> None:
            source_id = row.get("id")
            if not source_id or source_id in seen_source_ids:
                return
            seen_source_ids.add(source_id)
            sources.append({
                "id": source_id,
                "content": row.get("content_text", ""),
                "url": row.get("citation_url", ""),
                "title": row.get("filename", "Unknown"),
            })

        # Preferred mapping: sources.metadata.crawl_page_id == confirmation.crawl_page_id
        unresolved_page_ids: List[str] = []
        for page_id in confirmed_page_ids:
            try:
                source_result = self.db.table("sources").select(
                    "id, content_text, citation_url, filename, created_at"
                ).eq("twin_id", twin_id).contains(
                    "metadata", {"crawl_page_id": page_id}
                ).order("created_at", desc=True).limit(1).execute()
                rows = source_result.data or []
                if rows:
                    _append_source_row(rows[0])
                    continue
            except Exception as e:
                logger.debug(f"Metadata-based source lookup failed for page {page_id}: {e}")
            unresolved_page_ids.append(page_id)

        if not unresolved_page_ids:
            return sources

        # Fallback mapping: crawl_pages.canonical_url -> sources.citation_url
        try:
            pages_result = self.db.table("crawl_pages").select(
                "id, canonical_url"
            ).in_("id", unresolved_page_ids).execute()
        except Exception as e:
            logger.warning(f"Error fetching crawl pages for fallback source lookup: {e}")
            return sources

        page_rows = pages_result.data or []
        ordered_urls: List[str] = []
        seen_urls = set()
        for page_id in unresolved_page_ids:
            page_row = next((row for row in page_rows if row.get("id") == page_id), None)
            url = (page_row or {}).get("canonical_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                ordered_urls.append(url)

        if not ordered_urls:
            return sources

        try:
            sources_result = self.db.table("sources").select(
                "id, content_text, citation_url, filename, created_at"
            ).eq("twin_id", twin_id).in_(
                "citation_url", ordered_urls
            ).order("created_at", desc=True).execute()
        except Exception as e:
            logger.warning(f"Error fetching fallback sources by citation_url: {e}")
            return sources

        source_rows = sources_result.data or []
        source_by_url: Dict[str, Dict[str, Any]] = {}
        for row in source_rows:
            url = row.get("citation_url")
            if url and url not in source_by_url:
                source_by_url[url] = row

        for url in ordered_urls:
            row = source_by_url.get(url)
            if row:
                _append_source_row(row)

        return sources
    
    async def _persist_claims(self, results: List[VerificationResult]) -> None:
        """Persist verified claims to database."""
        for result in results:
            claim = result.claim
            
            # Update verification status
            if not claim.id:
                claim.id = str(uuid.uuid4())
            claim.verification_status = result.status
            claim.confidence = result.confidence
            
            # Add supporting evidence
            claim.evidence_quotes = result.supporting_evidence
            
            # Insert into database
            try:
                data = claim.to_dict()
                self.db.table("research_claims").insert(data).execute()
            except Exception as e:
                logger.error(f"Error persisting claim: {e}")
    
    async def _update_status(
        self,
        research_run_id: str,
        twin_id: str,
        status: EnrichmentStatus,
        error_message: Optional[str] = None,
        counts: Optional[Dict[str, int]] = None,
    ) -> None:
        """Update enrichment status in database."""
        data = {
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "status": status.value,
        }
        
        if status == EnrichmentStatus.ENRICHING:
            data["started_at"] = datetime.utcnow().isoformat()
        
        if error_message:
            data["error_message"] = error_message
        
        if counts:
            data.update(counts)
        
        try:
            self.db.table("research_claim_enrichment").upsert(data).execute()
        except Exception as e:
            logger.error(f"Error updating enrichment status: {e}")
    
    async def _complete_enrichment(
        self,
        research_run_id: str,
        twin_id: str,
        results: List[VerificationResult],
        error_message: Optional[str] = None,
    ) -> EnrichmentSummary:
        """Complete enrichment and update database."""
        # Count by status
        counts = {
            "total_claims": len(results),
            "supported_count": 0,
            "insufficient_count": 0,
            "conflicting_count": 0,
            "needs_review_count": 0,
            "pending_count": 0,
        }
        
        for result in results:
            if result.status == VerificationStatus.SUPPORTED:
                counts["supported_count"] += 1
            elif result.status == VerificationStatus.INSUFFICIENT_EVIDENCE:
                counts["insufficient_count"] += 1
            elif result.status == VerificationStatus.CONFLICTING:
                counts["conflicting_count"] += 1
            elif result.status == VerificationStatus.NEEDS_REVIEW:
                counts["needs_review_count"] += 1
            else:
                counts["pending_count"] += 1
        
        status = EnrichmentStatus.FAILED if error_message else EnrichmentStatus.COMPLETED
        
        # Update database
        await self._update_status(
            research_run_id,
            twin_id,
            status,
            error_message=error_message,
            counts=counts,
        )
        
        # If completed, set completed_at
        if status == EnrichmentStatus.COMPLETED:
            try:
                self.db.table("research_claim_enrichment").update({
                    "completed_at": datetime.utcnow().isoformat()
                }).eq("research_run_id", research_run_id).execute()
            except Exception as e:
                logger.error(f"Error setting completed_at: {e}")
        
        return EnrichmentSummary(
            research_run_id=research_run_id,
            status=status,
            **counts,
            error_message=error_message,
            completed_at=datetime.utcnow().isoformat() if status == EnrichmentStatus.COMPLETED else None,
        )
    
    async def list_claims(
        self,
        research_run_id: str,
        twin_id: str,
        verification_status: Optional[VerificationStatus] = None,
        claim_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ResearchClaim]:
        """
        List claims for a research run with optional filters.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID
            verification_status: Filter by status
            claim_type: Filter by type
            limit: Max results
            offset: Pagination offset
        
        Returns:
            List of ResearchClaim objects
        """
        query = self.db.table("research_claims").select("*").eq(
            "research_run_id", research_run_id
        ).eq("twin_id", twin_id).eq("is_active", True)
        
        if verification_status:
            query = query.eq("verification_status", verification_status.value)
        
        if claim_type:
            query = query.eq("claim_type", claim_type)
        
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        
        try:
            result = query.execute()
            return [ResearchClaim.from_dict(row) for row in (result.data or [])]
        except Exception as e:
            logger.error(f"Error listing claims: {e}")
            return []
    
    async def resolve_claim(
        self,
        claim_id: str,
        research_run_id: str,
        twin_id: str,
        new_status: VerificationStatus,
        reviewed_by: Optional[str] = None,
        review_notes: Optional[str] = None,
    ) -> bool:
        """
        Manually resolve a claim's verification status.
        
        Args:
            claim_id: Claim ID
            research_run_id: Research run ID
            twin_id: Twin ID
            new_status: New verification status
            reviewed_by: User ID who reviewed
            review_notes: Optional review notes
        
        Returns:
            True if successful
        """
        try:
            data = {
                "verification_status": new_status.value,
                "reviewed_at": datetime.utcnow().isoformat(),
            }
            
            if reviewed_by:
                data["reviewed_by"] = reviewed_by
            if review_notes:
                data["review_notes"] = review_notes
            
            self.db.table("research_claims").update(data).eq(
                "id", claim_id
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error resolving claim: {e}")
            return False


# =============================================================================
# Convenience Functions
# =============================================================================

async def enrich_research_claims(
    research_run_id: str,
    twin_id: str,
    model: str = "gpt-4o-mini",
) -> EnrichmentSummary:
    """
    Main entry point: enrich claims for a research run.
    
    Args:
        research_run_id: Research run ID
        twin_id: Twin ID
        model: Model to use
    
    Returns:
        EnrichmentSummary
    """
    service = ResearchClaimService()
    return await service.start_enrichment(research_run_id, twin_id, model)
