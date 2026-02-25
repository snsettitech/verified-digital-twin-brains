"""
Exa Web Verification Integration (Phase 9 Enhancement)

Integrates ExaResearchService with existing Phase 9 web verification.
Provides enhanced verification using Exa's two-pass retrieval and
structured result capture.

Usage:
    from modules.exa_web_verification_integration import ExaWebVerifier
    
    verifier = ExaWebVerifier()
    verification = await verifier.verify_claim_exa(
        claim=research_claim,
        twin_id="twin-123",
    )
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from modules.exa_research_service import (
    ExaResearchService,
    ResearchResult,
    SourceFreshness,
    ExaCategory,
)
from modules.research_claim_web_search import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class ExaVerificationEvidence:
    """Evidence from Exa verification."""
    url: str
    title: str
    quote: str
    relevance_score: float
    source_quality: str
    published_date: Optional[str]
    is_supporting: bool
    verification_notes: List[str]


@dataclass
class ExaVerificationResult:
    """Result of Exa-based claim verification."""
    claim_id: str
    status: str  # supported, conflicting, insufficient_evidence, needs_review
    confidence: float
    evidence: List[ExaVerificationEvidence]
    sources_checked: int
    sources_with_evidence: int
    search_query: str
    freshness_applied: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "status": self.status,
            "confidence": self.confidence,
            "evidence": [
                {
                    "url": e.url,
                    "title": e.title,
                    "quote": e.quote,
                    "relevance_score": e.relevance_score,
                    "source_quality": e.source_quality,
                    "published_date": e.published_date,
                    "is_supporting": e.is_supporting,
                }
                for e in self.evidence
            ],
            "sources_checked": self.sources_checked,
            "sources_with_evidence": self.sources_with_evidence,
            "search_query": self.search_query,
            "freshness_applied": self.freshness_applied,
        }


class ExaWebVerifier:
    """
    Enhanced web verifier using ExaResearchService.
    
    Integrates with Phase 9 web verification to provide:
    - Two-pass retrieval (highlights -> full content)
    - Source quality assessment
    - Structured evidence capture
    - Freshness controls
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Exa web verifier.
        
        Args:
            api_key: Exa API key (defaults to EXA_API_KEY env var)
        """
        self.exa_service = ExaResearchService(api_key=api_key)
        self.enabled = bool(self.exa_service.api_key)
        
        if not self.enabled:
            logger.warning("ExaWebVerifier initialized without API key - will return empty results")
    
    async def verify_claim(
        self,
        claim_text: str,
        claim_type: str,
        claim_id: str,
        freshness: SourceFreshness = SourceFreshness.EVERGREEN,
        num_candidates: int = 10,
        num_full_content: int = 3,
    ) -> ExaVerificationResult:
        """
        Verify a claim using Exa search.
        
        Args:
            claim_text: The claim text to verify
            claim_type: Type of claim (preference, belief, experience, etc.)
            claim_id: Unique claim identifier
            freshness: Content freshness requirement
            num_candidates: Number of candidate sources to retrieve
            num_full_content: Number of sources to fetch full content for
            
        Returns:
            ExaVerificationResult with verification status and evidence
        """
        if not self.enabled:
            logger.warning("Exa verification skipped - no API key")
            return ExaVerificationResult(
                claim_id=claim_id,
                status="insufficient_evidence",
                confidence=0.0,
                evidence=[],
                sources_checked=0,
                sources_with_evidence=0,
                search_query="",
                freshness_applied=freshness.value,
            )
        
        # Determine freshness based on claim type
        freshness = self._select_freshness(claim_type, freshness)
        
        # Search for evidence
        results = await self.exa_service.two_pass_search(
            query=claim_text,
            num_candidates=num_candidates,
            num_full_content=num_full_content,
            freshness=freshness,
        )
        
        if not results:
            return ExaVerificationResult(
                claim_id=claim_id,
                status="insufficient_evidence",
                confidence=0.0,
                evidence=[],
                sources_checked=0,
                sources_with_evidence=0,
                search_query=claim_text[:100],
                freshness_applied=freshness.value,
            )
        
        # Convert to evidence
        evidence_list = []
        supporting_count = 0
        conflicting_count = 0
        
        for result in results:
            evidence = self._convert_to_evidence(result, claim_text)
            evidence_list.append(evidence)
            
            if evidence.is_supporting:
                supporting_count += 1
            else:
                conflicting_count += 1
        
        # Determine status
        status, confidence = self._determine_verification_status(
            evidence_list, supporting_count, conflicting_count
        )
        
        return ExaVerificationResult(
            claim_id=claim_id,
            status=status,
            confidence=confidence,
            evidence=evidence_list,
            sources_checked=len(results),
            sources_with_evidence=len([e for e in evidence_list if e.quote]),
            search_query=claim_text[:200],
            freshness_applied=freshness.value,
        )
    
    async def verify_person_claim(
        self,
        claim_text: str,
        claim_id: str,
        person_name: str,
        person_company: Optional[str] = None,
    ) -> ExaVerificationResult:
        """
        Verify a claim about a specific person.
        
        Uses category="people" for better person-specific results.
        
        Args:
            claim_text: The claim text
            claim_id: Claim identifier
            person_name: Name of the person
            person_company: Company/organization (optional)
            
        Returns:
            ExaVerificationResult
        """
        if not self.enabled:
            return ExaVerificationResult(
                claim_id=claim_id,
                status="insufficient_evidence",
                confidence=0.0,
                evidence=[],
                sources_checked=0,
                sources_with_evidence=0,
                search_query="",
                freshness_applied="evergreen",
            )
        
        # Build person-focused query
        query_parts = [person_name]
        if person_company:
            query_parts.append(person_company)
        query_parts.append(claim_text)
        query = " ".join(query_parts)
        
        # Search with people category
        results = await self.exa_service.search_highlights(
            query=query,
            num_results=10,
            category=ExaCategory.PEOPLE,
            freshness=SourceFreshness.EVERGREEN,
        )
        
        # Fetch full content for top results
        if results:
            urls = [r.url for r in results[:3]]
            full_contents = await self.exa_service.fetch_full_contents(urls)
            
            # Merge full contents
            content_map = {c.url: c for c in full_contents}
            for result in results:
                if result.url in content_map:
                    full = content_map[result.url]
                    result.text = full.text
                    result.text_length = full.text_length
        
        # Convert to evidence
        evidence_list = []
        for result in results:
            evidence = self._convert_to_evidence(result, claim_text)
            evidence_list.append(evidence)
        
        supporting = len([e for e in evidence_list if e.is_supporting])
        status, confidence = self._determine_verification_status(
            evidence_list, supporting, len(evidence_list) - supporting
        )
        
        return ExaVerificationResult(
            claim_id=claim_id,
            status=status,
            confidence=confidence,
            evidence=evidence_list,
            sources_checked=len(results),
            sources_with_evidence=len([e for e in evidence_list if e.quote]),
            search_query=query[:200],
            freshness_applied="evergreen",
        )
    
    async def discover_person_context(
        self,
        name: str,
        company: Optional[str] = None,
        topics: Optional[List[str]] = None,
    ) -> List[ResearchResult]:
        """
        Discover context about a person.
        
        Args:
            name: Person's name
            company: Company/organization
            topics: Topics of expertise
            
        Returns:
            List of ResearchResult with person information
        """
        if not self.enabled:
            return []
        
        return await self.exa_service.discover_person(
            name=name,
            company=company,
            topics=topics,
            num_results=10,
            fetch_full_content=True,
        )
    
    def _select_freshness(
        self,
        claim_type: str,
        default: SourceFreshness
    ) -> SourceFreshness:
        """Select appropriate freshness based on claim type."""
        freshness_map = {
            "news": SourceFreshness.NEWS,
            "recent": SourceFreshness.NEWS,
            "preference": SourceFreshness.EVERGREEN,
            "belief": SourceFreshness.EVERGREEN,
            "value": SourceFreshness.EVERGREEN,
            "experience": SourceFreshness.EVERGREEN,
            "heuristic": SourceFreshness.EVERGREEN,
        }
        return freshness_map.get(claim_type, default)
    
    def _convert_to_evidence(
        self,
        result: ResearchResult,
        claim_text: str
    ) -> ExaVerificationEvidence:
        """Convert ResearchResult to ExaVerificationEvidence."""
        # Extract best quote
        quote = ""
        if result.highlights:
            quote = result.highlights[0]
        elif result.text:
            # Extract a relevant snippet
            quote = self._extract_relevant_snippet(result.text, claim_text)
        
        # Assess if supporting (simplified)
        is_supporting = result.source_quality in ["high", "medium"]
        
        # Calculate relevance
        relevance = result.score if result.score else 0.5
        if result.source_quality == "high":
            relevance = min(1.0, relevance + 0.2)
        
        return ExaVerificationEvidence(
            url=result.url,
            title=result.title,
            quote=quote,
            relevance_score=relevance,
            source_quality=result.source_quality,
            published_date=result.published_date,
            is_supporting=is_supporting,
            verification_notes=result.verification_notes,
        )
    
    def _extract_relevant_snippet(self, text: str, claim_text: str) -> str:
        """Extract a relevant snippet from text matching claim."""
        # Simple extraction - first 200 chars
        # In production, use semantic similarity or keyword matching
        max_len = 300
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
    
    def _determine_verification_status(
        self,
        evidence: List[ExaVerificationEvidence],
        supporting: int,
        conflicting: int,
    ) -> tuple:
        """
        Determine verification status from evidence.
        
        Returns:
            Tuple of (status, confidence)
        """
        if not evidence:
            return "insufficient_evidence", 0.0
        
        # High confidence if multiple high-quality supporting sources
        high_quality_supporting = len([
            e for e in evidence
            if e.is_supporting and e.source_quality == "high"
        ])
        
        if high_quality_supporting >= 2:
            return "supported", 0.9
        
        if supporting >= 2:
            return "supported", 0.75
        
        if supporting == 1:
            return "needs_review", 0.5
        
        if conflicting >= 1:
            return "conflicting", 0.3
        
        return "insufficient_evidence", 0.1
    
    def to_web_search_results(self, exa_results: List[ResearchResult]) -> List[SearchResult]:
        """
        Convert Exa ResearchResults to legacy SearchResults.
        
        For backward compatibility with existing Phase 9 code.
        
        Args:
            exa_results: Results from ExaResearchService
            
        Returns:
            List of SearchResult (legacy format)
        """
        return [
            SearchResult(
                url=r.url,
                title=r.title,
                snippet=r.highlights[0] if r.highlights else (r.text[:200] if r.text else ""),
                score=r.score,
                published_date=r.published_date,
                source="exa",
            )
            for r in exa_results
        ]


# ============================================================================
# Integration with Existing Phase 9 Service
# ============================================================================

class ExaEnhancedWebVerificationService:
    """
    Drop-in enhancement for ResearchClaimWebVerificationService.
    
    Uses Exa for primary search, falls back to other providers if needed.
    """
    
    def __init__(self):
        self.exa_verifier = ExaWebVerifier()
        self.exa_enabled = self.exa_verifier.enabled
        
        if self.exa_enabled:
            logger.info("Exa-enhanced web verification initialized")
        else:
            logger.info("Exa not available, using standard web verification")
    
    async def search_for_claim(
        self,
        claim_text: str,
        claim_type: str,
        num_results: int = 5,
    ) -> List[SearchResult]:
        """
        Search for claim evidence (Exa-enhanced).
        
        Args:
            claim_text: Claim to search for
            claim_type: Type of claim
            num_results: Number of results
            
        Returns:
            List of SearchResult
        """
        if not self.exa_enabled:
            # Return empty - let caller fall back to other providers
            return []
        
        # Use Exa two-pass search
        exa_results = await self.exa_verifier.exa_service.two_pass_search(
            query=claim_text,
            num_candidates=num_results + 5,  # Get extra for filtering
            num_full_content=min(3, num_results),
        )
        
        # Convert to legacy format
        return self.exa_verifier.to_web_search_results(exa_results)


# ============================================================================
# Convenience Functions
# ============================================================================

async def verify_with_exa(
    claim_text: str,
    claim_type: str,
    claim_id: str,
    **kwargs
) -> ExaVerificationResult:
    """Convenience function for Exa verification."""
    verifier = ExaWebVerifier()
    return await verifier.verify_claim(claim_text, claim_type, claim_id, **kwargs)


async def discover_person(
    name: str,
    **kwargs
) -> List[ResearchResult]:
    """Convenience function for person discovery."""
    verifier = ExaWebVerifier()
    return await verifier.discover_person_context(name, **kwargs)
