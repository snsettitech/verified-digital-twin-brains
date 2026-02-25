"""
Research Claim Web Verification Service (Phase 9)

Orchestrates web verification for research runs:
1. Fetch Phase 8 claims from database
2. Filter by eligibility (using taxonomy)
3. Search web for each claim
4. Verify claims against web sources
5. Persist results to database
6. Track verification progress

Idempotent: Safe to retry without duplication.

Usage:
    service = ResearchClaimWebVerificationService()
    summary = await service.verify_research_run(run_id, twin_id)
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from modules.observability import supabase
from modules.research_claim_extractor import ResearchClaim, ClaimType, VerificationStatus
from modules.research_claim_web_search import (
    WebSearchProvider,
    create_search_provider_with_fallback,
    build_claim_search_query,
)
from modules.research_claim_web_verifier import (
    ClaimWebVerifier,
    WebVerificationResult,
    WebVerificationStatus,
    WebEvidenceItem,
)
from modules.deep_research_config import get_config, is_web_verification_eligible

logger = logging.getLogger(__name__)


class WebVerificationRunStatus(str, Enum):
    """Status of web verification for a research run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some claims failed but others succeeded


@dataclass
class WebVerificationSummary:
    """Summary of web verification results for a research run."""
    research_run_id: str
    twin_id: str
    status: WebVerificationRunStatus
    total_claims: int = 0
    verified_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "research_run_id": self.research_run_id,
            "twin_id": self.twin_id,
            "status": self.status.value,
            "total_claims": self.total_claims,
            "verified_count": self.verified_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "by_status": self.by_status,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ClaimWithVerification:
    """Claim with both Phase 8 local and Phase 9 web verification."""
    claim: ResearchClaim
    web_verification_status: Optional[WebVerificationStatus] = None
    web_verification_confidence: float = 0.0
    web_verification_notes: Optional[str] = None
    web_verified_at: Optional[str] = None
    web_evidence_count: int = 0


class ResearchClaimWebVerificationService:
    """
    Service for web verification operations (Phase 9).
    
    Orchestrates:
    1. Fetch claims from Phase 8
    2. Filter by web verification eligibility
    3. Search and verify each claim
    4. Persist results
    5. Update verification status
    
    Idempotent: Safe to retry. Checks existing state before processing.
    """
    
    def __init__(
        self,
        supabase_client=None,
        search_provider: Optional[WebSearchProvider] = None,
        verifier: Optional[ClaimWebVerifier] = None,
    ):
        """
        Initialize service.
        
        Args:
            supabase_client: Optional Supabase client (for testing)
            search_provider: Optional search provider (auto-created if None)
            verifier: Optional claim verifier (auto-created if None)
        """
        self.db = supabase_client or supabase
        self.search_provider = search_provider or create_search_provider_with_fallback()
        self.verifier = verifier or ClaimWebVerifier()
    
    async def get_verification_status(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> Optional[WebVerificationSummary]:
        """
        Get current web verification status for a research run.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
            
        Returns:
            WebVerificationSummary or None if not started
        """
        try:
            result = self.db.table("research_web_verification_runs").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).single().execute()
            
            if not result.data:
                return None
            
            data = result.data
            
            # Get status breakdown
            status_result = self.db.table("research_claim_web_verifications").select(
                "web_verification_status"
            ).eq("research_run_id", research_run_id).execute()
            
            by_status = {}
            if status_result.data:
                for row in status_result.data:
                    status = row.get("web_verification_status", "unknown")
                    by_status[status] = by_status.get(status, 0) + 1
            
            return WebVerificationSummary(
                research_run_id=data["research_run_id"],
                twin_id=data["twin_id"],
                status=WebVerificationRunStatus(data.get("status", "pending")),
                total_claims=data.get("total_claims", 0),
                verified_count=data.get("verified_count", 0),
                failed_count=data.get("failed_count", 0),
                skipped_count=data.get("skipped_count", 0),
                by_status=by_status,
                error_message=data.get("error_message"),
                started_at=data.get("started_at"),
                completed_at=data.get("completed_at"),
            )
            
        except Exception as e:
            logger.error(f"Error getting web verification status: {e}")
            return None
    
    async def verify_research_run(
        self,
        research_run_id: str,
        twin_id: str,
        max_results_per_claim: int = 5,
    ) -> WebVerificationSummary:
        """
        Start or continue web verification for a research run.
        
        Idempotent:
        - If already completed, returns existing summary
        - If in progress, returns current status
        - If not started, begins verification process
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID
            max_results_per_claim: Max search results per claim
            
        Returns:
            WebVerificationSummary
        """
        # Check current status
        existing = await self.get_verification_status(research_run_id, twin_id)
        
        if existing:
            if existing.status == WebVerificationRunStatus.COMPLETED:
                logger.info(f"Web verification already completed for {research_run_id}")
                return existing
            
            if existing.status == WebVerificationRunStatus.RUNNING:
                logger.info(f"Web verification already in progress for {research_run_id}")
                return existing
        
        # Set status to running
        await self._update_run_status(
            research_run_id, twin_id, WebVerificationRunStatus.RUNNING
        )
        
        try:
            # Fetch Phase 8 claims
            claims = await self._get_claims(research_run_id, twin_id)
            
            if not claims:
                logger.warning(f"No claims found for {research_run_id}")
                summary = await self._complete_verification(
                    research_run_id, twin_id, [], "No claims available"
                )
                return summary
            
            # Filter eligible claims
            eligible_claims = self._filter_eligible_claims(claims)
            skipped_count = len(claims) - len(eligible_claims)
            
            logger.info(f"Verifying {len(eligible_claims)} claims (skipped {skipped_count}) for {research_run_id}")
            
            # Verify each eligible claim
            results = []
            failed_count = 0
            
            for claim in eligible_claims:
                try:
                    result = await self._verify_single_claim(
                        claim, max_results_per_claim
                    )
                    results.append(result)
                    
                    # Persist result
                    await self._persist_verification_result(
                        research_run_id, twin_id, claim, result
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to verify claim {claim.id}: {e}")
                    failed_count += 1
                    # Continue with other claims
            
            # Complete verification
            summary = await self._complete_verification(
                research_run_id,
                twin_id,
                results,
                failed_count=failed_count,
                skipped_count=skipped_count,
            )
            
            logger.info(f"Web verification completed for {research_run_id}: "
                       f"{summary.verified_count} verified, {failed_count} failed, {skipped_count} skipped")
            
            return summary
            
        except Exception as e:
            logger.error(f"Web verification failed for {research_run_id}: {e}")
            await self._update_run_status(
                research_run_id,
                twin_id,
                WebVerificationRunStatus.FAILED,
                error_message=str(e),
            )
            return WebVerificationSummary(
                research_run_id=research_run_id,
                twin_id=twin_id,
                status=WebVerificationRunStatus.FAILED,
                error_message=str(e),
            )
    
    async def _get_claims(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> List[ResearchClaim]:
        """Fetch claims from Phase 8."""
        try:
            result = self.db.table("research_claims").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            if not result.data:
                return []
            
            return [ResearchClaim.from_dict(row) for row in result.data]
            
        except Exception as e:
            logger.error(f"Error fetching claims: {e}")
            return []
    
    def _filter_eligible_claims(
        self,
        claims: List[ResearchClaim]
    ) -> List[ResearchClaim]:
        """
        Filter claims by web verification eligibility.
        
        Uses claim class taxonomy from deep_research_config.
        """
        eligible = []
        
        for claim in claims:
            # Map claim type to claim class
            claim_class = self._map_claim_type_to_class(claim.claim_type)
            
            if is_web_verification_eligible(claim_class, policy="eligible_only"):
                eligible.append(claim)
            else:
                logger.debug(f"Claim {claim.id} ineligible for web verification (type: {claim.claim_type})")
        
        return eligible
    
    def _map_claim_type_to_class(self, claim_type: ClaimType) -> str:
        """Map claim type to claim class for eligibility checking."""
        mapping = {
            ClaimType.PREFERENCE: "opinion",
            ClaimType.BELIEF: "owner_stance",
            ClaimType.HEURISTIC: "procedural",
            ClaimType.VALUE: "owner_stance",
            ClaimType.EXPERIENCE: "private_fact",
            ClaimType.BOUNDARY: "owner_stance",
            ClaimType.UNCERTAIN: "opinion",
        }
        return mapping.get(claim_type, "opinion")
    
    async def _verify_single_claim(
        self,
        claim: ResearchClaim,
        max_results: int
    ) -> WebVerificationResult:
        """Verify a single claim against web sources."""
        # Build search query
        query = build_claim_search_query(
            claim.claim_text,
            claim.claim_type.value
        )
        
        # Search web
        search_results = await self.search_provider.search(query, max_results)
        
        # Verify claim
        result = await self.verifier.verify_claim(claim, search_results)
        
        return result
    
    async def _persist_verification_result(
        self,
        research_run_id: str,
        twin_id: str,
        claim: ResearchClaim,
        result: WebVerificationResult,
    ) -> None:
        """Persist verification result to database."""
        try:
            # Upsert verification record
            verification_data = {
                "claim_id": claim.id,
                "research_run_id": research_run_id,
                "twin_id": twin_id,
                "web_verification_status": result.status.value,
                "web_verification_confidence": result.confidence,
                "web_verification_notes": result.notes,
                "sources_searched": result.sources_searched,
                "sources_found": result.sources_found,
                "supporting_evidence_count": len([e for e in result.evidence if e.evidence_type == "supporting"]),
                "conflicting_evidence_count": len([e for e in result.evidence if e.evidence_type == "conflicting"]),
                "search_query": build_claim_search_query(claim.claim_text),
                "search_provider": self.search_provider.name,
                "web_verified_at": datetime.utcnow().isoformat(),
            }
            
            # Use upsert with claim_id as unique key
            self.db.table("research_claim_web_verifications").upsert(
                verification_data,
                on_conflict="claim_id"
            ).execute()
            
            # Get verification ID for evidence
            verif_result = self.db.table("research_claim_web_verifications").select(
                "id"
            ).eq("claim_id", claim.id).single().execute()
            
            if verif_result.data:
                verification_id = verif_result.data["id"]
                
                # Delete old evidence
                self.db.table("research_claim_web_evidence").delete().eq(
                    "verification_id", verification_id
                ).execute()
                
                # Insert new evidence
                for evidence in result.evidence:
                    evidence_data = {
                        "verification_id": verification_id,
                        "claim_id": claim.id,
                        "source_url": evidence.source_url,
                        "source_title": evidence.source_title,
                        "source_snippet": evidence.source_snippet,
                        "extracted_quote": evidence.extracted_quote,
                        "relevance_score": evidence.relevance_score,
                        "evidence_type": evidence.evidence_type,
                        "content_quality": evidence.content_quality,
                        "domain_tier": evidence.domain_tier,
                        "url_hash": self._compute_url_hash(evidence.source_url),
                    }
                    self.db.table("research_claim_web_evidence").insert(evidence_data).execute()
                    
        except Exception as e:
            logger.error(f"Error persisting verification result: {e}")
            raise
    
    def _compute_url_hash(self, url: str) -> str:
        """Compute hash for URL deduplication."""
        import hashlib
        return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
    
    async def _update_run_status(
        self,
        research_run_id: str,
        twin_id: str,
        status: WebVerificationRunStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update verification run status in database."""
        data = {
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "status": status.value,
        }
        
        if status == WebVerificationRunStatus.RUNNING:
            data["started_at"] = datetime.utcnow().isoformat()
        
        if error_message:
            data["error_message"] = error_message
        
        try:
            self.db.table("research_web_verification_runs").upsert(
                data,
                on_conflict="research_run_id"
            ).execute()
        except Exception as e:
            logger.error(f"Error updating verification run status: {e}")
    
    async def _complete_verification(
        self,
        research_run_id: str,
        twin_id: str,
        results: List[WebVerificationResult],
        error_message: Optional[str] = None,
        failed_count: int = 0,
        skipped_count: int = 0,
    ) -> WebVerificationSummary:
        """Complete verification and update database."""
        # Count by status
        by_status: Dict[str, int] = {}
        for result in results:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        verified_count = len(results)
        total_claims = verified_count + failed_count + skipped_count
        
        # Determine overall status
        if error_message:
            status = WebVerificationRunStatus.FAILED
        elif failed_count > 0:
            status = WebVerificationRunStatus.PARTIAL
        else:
            status = WebVerificationRunStatus.COMPLETED
        
        # Update database
        data = {
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "status": status.value,
            "total_claims": total_claims,
            "verified_count": verified_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "error_message": error_message,
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        try:
            self.db.table("research_web_verification_runs").upsert(
                data,
                on_conflict="research_run_id"
            ).execute()
        except Exception as e:
            logger.error(f"Error completing verification: {e}")
        
        return WebVerificationSummary(
            research_run_id=research_run_id,
            twin_id=twin_id,
            status=status,
            total_claims=total_claims,
            verified_count=verified_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            by_status=by_status,
            error_message=error_message,
            completed_at=datetime.utcnow().isoformat(),
        )
    
    async def list_claims_with_verification(
        self,
        research_run_id: str,
        twin_id: str,
        include_web: bool = True,
        verification_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ClaimWithVerification]:
        """
        List claims with both Phase 8 local and Phase 9 web verification.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID
            include_web: Include web verification data
            verification_status: Filter by web verification status
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of ClaimWithVerification
        """
        # Fetch claims
        claims = await self._get_claims(research_run_id, twin_id)
        
        if not include_web:
            return [ClaimWithVerification(claim=c) for c in claims]
        
        # Fetch web verifications
        try:
            query = self.db.table("research_claim_web_verifications").select(
                "*"
            ).eq("research_run_id", research_run_id)
            
            if verification_status:
                query = query.eq("web_verification_status", verification_status)
            
            verif_result = query.execute()
            
            # Build lookup dict
            verifications = {}
            if verif_result.data:
                for row in verif_result.data:
                    verifications[row["claim_id"]] = row
            
            # Combine
            results = []
            for claim in claims:
                verif = verifications.get(claim.id, {})
                results.append(ClaimWithVerification(
                    claim=claim,
                    web_verification_status=WebVerificationStatus(
                        verif.get("web_verification_status", "pending")
                    ) if verif.get("web_verification_status") else None,
                    web_verification_confidence=verif.get("web_verification_confidence", 0.0),
                    web_verification_notes=verif.get("web_verification_notes"),
                    web_verified_at=verif.get("web_verified_at"),
                    web_evidence_count=verif.get("supporting_evidence_count", 0) + 
                                      verif.get("conflicting_evidence_count", 0),
                ))
            
            # Apply pagination
            return results[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error fetching web verifications: {e}")
            return [ClaimWithVerification(claim=c) for c in claims[offset:offset + limit]]
    
    async def get_web_evidence(
        self,
        claim_id: str,
        research_run_id: str,
        twin_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get web evidence for a specific claim.
        
        Args:
            claim_id: Claim ID
            research_run_id: Research run ID
            twin_id: Twin ID
            
        Returns:
            List of evidence items
        """
        try:
            result = self.db.table("research_claim_web_evidence").select(
                "*"
            ).eq("claim_id", claim_id).order("relevance_score", desc=True).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error fetching web evidence: {e}")
            return []
    
    async def resolve_web_verification(
        self,
        claim_id: str,
        research_run_id: str,
        twin_id: str,
        new_status: WebVerificationStatus,
        reviewed_by: Optional[str] = None,
        review_notes: Optional[str] = None,
    ) -> bool:
        """
        Manually resolve a claim's web verification status.
        
        Args:
            claim_id: Claim ID
            research_run_id: Research run ID
            twin_id: Twin ID
            new_status: New web verification status
            reviewed_by: User ID who reviewed
            review_notes: Optional review notes
            
        Returns:
            True if successful
        """
        try:
            data = {
                "web_verification_status": new_status.value,
                "web_verification_notes": review_notes or "Manually resolved",
                "web_verified_at": datetime.utcnow().isoformat(),
            }
            
            self.db.table("research_claim_web_verifications").update(data).eq(
                "claim_id", claim_id
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error resolving web verification: {e}")
            return False


# =============================================================================
# Convenience Functions
# =============================================================================

async def verify_research_run_web_claims(
    research_run_id: str,
    twin_id: str,
    max_results_per_claim: int = 5,
) -> WebVerificationSummary:
    """
    Main entry point: verify claims for a research run via web.
    
    Args:
        research_run_id: Research run ID
        twin_id: Twin ID
        max_results_per_claim: Max search results per claim
        
    Returns:
        WebVerificationSummary
    """
    service = ResearchClaimWebVerificationService()
    return await service.verify_research_run(
        research_run_id, twin_id, max_results_per_claim
    )
