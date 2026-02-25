"""
Research Claim Web Verifier Module (Phase 9)

Verifies claims against web sources:
1. Fetches candidate pages via Firecrawl client
2. Scores support/conflict against claim using LLM + similarity
3. Deduplicates evidence URLs
4. Outputs structured evidence + decision

Usage:
    verifier = ClaimWebVerifier()
    result = await verifier.verify_claim(
        claim=research_claim,
        search_results=search_results,
        firecrawl_client=client
    )
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from modules.research_claim_extractor import ResearchClaim
from modules.research_claim_web_search import SearchResult

logger = logging.getLogger(__name__)


class WebVerificationStatus(str, Enum):
    """Web verification statuses for Phase 9."""
    PENDING = "pending"
    SUPPORTED = "supported"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"
    ERROR = "error"
    SKIPPED = "skipped"  # For ineligible claims


@dataclass
class WebEvidenceItem:
    """Single piece of web evidence for a claim."""
    source_url: str
    source_title: str
    source_snippet: str
    extracted_quote: str
    relevance_score: float  # 0.0 to 1.0
    evidence_type: str  # 'supporting' | 'conflicting' | 'neutral'
    content_quality: str  # 'full' | 'partial' | 'blocked'
    domain_tier: Optional[int] = None  # 1, 2, 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "source_url": self.source_url,
            "source_title": self.source_title,
            "source_snippet": self.source_snippet,
            "extracted_quote": self.extracted_quote,
            "relevance_score": self.relevance_score,
            "evidence_type": self.evidence_type,
            "content_quality": self.content_quality,
            "domain_tier": self.domain_tier,
        }


@dataclass
class WebVerificationResult:
    """Result of web verification for a single claim."""
    claim_id: str
    status: WebVerificationStatus
    confidence: float  # 0.0 to 1.0
    evidence: List[WebEvidenceItem]
    notes: str
    sources_searched: int = 0
    sources_found: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "notes": self.notes,
            "sources_searched": self.sources_searched,
            "sources_found": self.sources_found,
            "error_message": self.error_message,
        }


class ClaimWebVerifier:
    """
    Verifies claims against web sources.
    
    Uses Firecrawl for fetching and LLM for relevance assessment.
    Supports deterministic test mode via mockable components.
    """
    
    def __init__(
        self,
        firecrawl_client: Optional[Any] = None,
        llm_verify_func: Optional[Any] = None,
        similarity_threshold: float = 0.6,
        max_evidence_items: int = 5,
    ):
        """
        Initialize verifier.
        
        Args:
            firecrawl_client: Optional Firecrawl client for fetching
            llm_verify_func: Optional LLM function for verification (mockable)
            similarity_threshold: Minimum similarity score for relevance
            max_evidence_items: Max evidence items to return
        """
        self.firecrawl_client = firecrawl_client
        self.llm_verify_func = llm_verify_func
        self.similarity_threshold = similarity_threshold
        self.max_evidence_items = max_evidence_items
    
    def _compute_url_hash(self, url: str) -> str:
        """Compute hash for URL deduplication."""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
    
    def _get_domain_tier(self, url: str) -> int:
        """
        Determine source tier based on domain.
        
        Tier 1: Authoritative (.edu, .gov, major news)
        Tier 2: Established (industry pubs, known blogs)
        Tier 3: User-generated (social, forums, unknown)
        """
        url_lower = url.lower()
        
        # Tier 1 indicators
        tier_1_patterns = [
            '.edu', '.gov/', '.ac.', '.gc.ca', 'gov.uk',
            'reuters.com', 'ap.org', 'bloomberg.com', 'wsj.com',
            'nytimes.com', 'washingtonpost.com', 'ft.com',
            'nature.com', 'science.org', 'arxiv.org',
            'wikipedia.org', 'britannica.com',
        ]
        
        # Tier 2 indicators
        tier_2_patterns = [
            'medium.com', 'substack.com', 'techcrunch.com',
            'forbes.com', 'hbr.org', 'mit.edu',
            'linkedin.com', 'github.com', 'crunchbase.com',
        ]
        
        for pattern in tier_1_patterns:
            if pattern in url_lower:
                return 1
        
        for pattern in tier_2_patterns:
            if pattern in url_lower:
                return 2
        
        return 3
    
    async def _fetch_page_content(
        self,
        url: str
    ) -> Tuple[str, Dict[str, Any], str]:
        """
        Fetch page content using Firecrawl client.
        
        Returns:
            Tuple of (content, metadata, quality)
        """
        if self.firecrawl_client is None:
            # Try to get global client
            from modules.firecrawl_client import get_firecrawl_client
            self.firecrawl_client = get_firecrawl_client()
        
        if self.firecrawl_client is None:
            logger.warning("Firecrawl client not available")
            return "", {}, "blocked"
        
        try:
            result = await self.firecrawl_client.scrape_with_retry(url)
            
            if not result.success:
                logger.warning(f"Failed to fetch {url}: {result.error}")
                return "", result.metadata or {}, "blocked"
            
            return result.content, result.metadata, result.quality.value
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return "", {}, "blocked"
    
    async def _assess_relevance(
        self,
        claim_text: str,
        page_content: str,
        page_title: str
    ) -> Tuple[float, str, str]:
        """
        Assess how relevant the page content is to the claim.
        
        Returns:
            Tuple of (relevance_score, evidence_type, extracted_quote)
        """
        # First: Simple keyword overlap for fast filtering
        claim_words = set(claim_text.lower().split())
        content_words = set(page_content.lower().split()[:1000])  # First 1000 words
        
        if not claim_words or not content_words:
            return 0.0, "neutral", ""
        
        overlap = len(claim_words & content_words)
        overlap_ratio = overlap / len(claim_words)
        
        # If very low overlap, skip detailed analysis
        if overlap_ratio < 0.1:
            return overlap_ratio, "neutral", ""
        
        # Use LLM for detailed assessment if available
        if self.llm_verify_func:
            return await self._llm_assess_relevance(claim_text, page_content, page_title)
        
        # Simple heuristic: look for sentences containing claim keywords
        sentences = page_content.split('.')
        best_sentence = ""
        best_score = 0.0
        
        for sentence in sentences[:50]:  # Check first 50 sentences
            sentence_lower = sentence.lower()
            matches = sum(1 for word in claim_words if word in sentence_lower)
            score = matches / len(claim_words) if claim_words else 0
            
            if score > best_score:
                best_score = score
                best_sentence = sentence.strip()
        
        # Determine evidence type based on score
        if best_score > 0.7:
            evidence_type = "supporting"
        elif best_score < 0.3:
            evidence_type = "conflicting"
        else:
            evidence_type = "neutral"
        
        return best_score, evidence_type, best_sentence[:500]
    
    async def _llm_assess_relevance(
        self,
        claim_text: str,
        page_content: str,
        page_title: str
    ) -> Tuple[float, str, str]:
        """
        Use LLM to assess relevance (more accurate but slower).
        """
        # Truncate content for LLM
        truncated_content = page_content[:3000]
        
        prompt = f"""Assess whether the web content supports, contradicts, or is neutral to the claim.

CLAIM: {claim_text}

PAGE TITLE: {page_title}

PAGE CONTENT:
{truncated_content}

Respond with JSON:
{{
  "relevance_score": 0.0-1.0,
  "evidence_type": "supporting" | "conflicting" | "neutral",
  "supporting_quote": "most relevant quote from content",
  "reasoning": "brief explanation"
}}
"""
        
        try:
            result = await self.llm_verify_func([{"role": "user", "content": prompt}])
            response = result[0] if isinstance(result, tuple) else result
            
            relevance = response.get("relevance_score", 0.5)
            evidence_type = response.get("evidence_type", "neutral")
            quote = response.get("supporting_quote", "")
            
            return relevance, evidence_type, quote
            
        except Exception as e:
            logger.warning(f"LLM relevance assessment failed: {e}")
            # Fall back to simple score
            return 0.5, "neutral", ""
    
    def _determine_verification_status(
        self,
        evidence_items: List[WebEvidenceItem]
    ) -> Tuple[WebVerificationStatus, float, str]:
        """
        Determine final verification status from evidence.
        
        Returns:
            Tuple of (status, confidence, notes)
        """
        if not evidence_items:
            return WebVerificationStatus.INSUFFICIENT_EVIDENCE, 0.0, "No web evidence found"
        
        # Filter by relevance threshold
        relevant = [e for e in evidence_items if e.relevance_score >= self.similarity_threshold]
        
        if not relevant:
            return WebVerificationStatus.INSUFFICIENT_EVIDENCE, 0.0, "Evidence below relevance threshold"
        
        supporting = [e for e in relevant if e.evidence_type == "supporting"]
        conflicting = [e for e in relevant if e.evidence_type == "conflicting"]
        
        # Calculate confidence
        support_score = sum(e.relevance_score for e in supporting)
        conflict_score = sum(e.relevance_score for e in conflicting)
        
        if supporting and not conflicting:
            # Strong support
            confidence = min(0.9, 0.5 + support_score / len(supporting) * 0.4)
            return WebVerificationStatus.SUPPORTED, confidence, f"Found {len(supporting)} supporting sources"
        
        elif conflicting and not supporting:
            # Strong conflict
            confidence = min(0.9, 0.5 + conflict_score / len(conflicting) * 0.4)
            return WebVerificationStatus.CONFLICTING, confidence, f"Found {len(conflicting)} conflicting sources"
        
        elif supporting and conflicting:
            # Mixed evidence
            if support_score > conflict_score * 1.5:
                confidence = 0.6
                return WebVerificationStatus.SUPPORTED, confidence, "Mixed evidence, support stronger"
            elif conflict_score > support_score * 1.5:
                confidence = 0.6
                return WebVerificationStatus.CONFLICTING, confidence, "Mixed evidence, conflict stronger"
            else:
                return WebVerificationStatus.NEEDS_REVIEW, 0.5, "Conflicting evidence found - needs review"
        
        else:
            return WebVerificationStatus.NEEDS_REVIEW, 0.3, "Evidence ambiguous"
    
    async def verify_claim(
        self,
        claim: ResearchClaim,
        search_results: List[SearchResult],
        skip_fetch_failures: bool = True
    ) -> WebVerificationResult:
        """
        Verify a single claim against web search results.
        
        Args:
            claim: The claim to verify
            search_results: Web search results to check
            skip_fetch_failures: If True, skip failed fetches; if False, mark as error
            
        Returns:
            WebVerificationResult
        """
        if not search_results:
            return WebVerificationResult(
                claim_id=claim.id or "",
                status=WebVerificationStatus.INSUFFICIENT_EVIDENCE,
                confidence=0.0,
                evidence=[],
                notes="No search results provided",
                sources_searched=0,
                sources_found=0,
            )
        
        seen_urls: set = set()
        evidence_items: List[WebEvidenceItem] = []
        fetch_failures = 0
        blocked_count = 0
        
        for result in search_results:
            # Deduplicate by URL hash
            url_hash = self._compute_url_hash(result.url)
            if url_hash in seen_urls:
                continue
            seen_urls.add(url_hash)
            
            # Fetch page content
            content, metadata, quality = await self._fetch_page_content(result.url)
            
            if not content and quality == "blocked":
                blocked_count += 1
                if not skip_fetch_failures:
                    continue
            
            if not content:
                fetch_failures += 1
                continue
            
            # Assess relevance
            relevance, evidence_type, quote = await self._assess_relevance(
                claim.claim_text,
                content,
                result.title
            )
            
            # Create evidence item
            evidence = WebEvidenceItem(
                source_url=result.url,
                source_title=result.title,
                source_snippet=result.snippet,
                extracted_quote=quote,
                relevance_score=relevance,
                evidence_type=evidence_type,
                content_quality=quality,
                domain_tier=self._get_domain_tier(result.url),
            )
            
            evidence_items.append(evidence)
        
        # Determine final status
        status, confidence, notes = self._determine_verification_status(evidence_items)
        
        # Update notes with fetch stats
        if fetch_failures > 0:
            notes += f" ({fetch_failures} fetch failures)"
        if blocked_count > 0:
            notes += f" ({blocked_count} blocked)"
        
        # Sort by relevance and limit
        evidence_items.sort(key=lambda e: e.relevance_score, reverse=True)
        evidence_items = evidence_items[:self.max_evidence_items]
        
        return WebVerificationResult(
            claim_id=claim.id or "",
            status=status,
            confidence=confidence,
            evidence=evidence_items,
            notes=notes,
            sources_searched=len(search_results),
            sources_found=len(seen_urls),
        )


# =============================================================================
# Convenience Functions
# =============================================================================

async def verify_claim_against_web(
    claim: ResearchClaim,
    search_results: List[SearchResult],
    firecrawl_client: Optional[Any] = None,
    similarity_threshold: float = 0.6
) -> WebVerificationResult:
    """
    Convenience function to verify a claim against web sources.
    
    Args:
        claim: The claim to verify
        search_results: Web search results
        firecrawl_client: Optional Firecrawl client
        similarity_threshold: Relevance threshold
        
    Returns:
        WebVerificationResult
    """
    verifier = ClaimWebVerifier(
        firecrawl_client=firecrawl_client,
        similarity_threshold=similarity_threshold
    )
    return await verifier.verify_claim(claim, search_results)
