"""
Research Claim Verifier Module (Phase 8)

Local verification of claims against ingested/confirmed sources.
MVP verification statuses:
- supported: Evidence found in sources
- insufficient_evidence: No supporting evidence
- conflicting: Evidence contradicts claim
- needs_review: Uncertain, requires human judgment

Phase 8 is LOCAL verification only (no external web search).
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from modules.research_claim_extractor import (
    ResearchClaim, VerificationStatus, EvidenceQuote
)


@dataclass
class VerificationResult:
    """Result of verifying a single claim."""
    claim: ResearchClaim
    status: VerificationStatus
    confidence: float
    supporting_evidence: List[EvidenceQuote]
    conflicting_evidence: List[EvidenceQuote]
    reasoning: str


class ClaimVerifier:
    """
    Verify claims against local ingested sources.
    
    Phase 8 MVP uses local evidence only - no external web verification.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.7,
        llm_verify_func: Optional[Any] = None,
    ):
        """
        Initialize verifier.
        
        Args:
            similarity_threshold: Minimum similarity for text matching
            llm_verify_func: Optional LLM function for semantic verification
        """
        self.similarity_threshold = similarity_threshold
        self._llm_verify = llm_verify_func
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Compute simple text similarity (0.0 to 1.0).
        Uses SequenceMatcher for MVP.
        """
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _find_supporting_evidence(
        self,
        claim_text: str,
        sources: List[Dict[str, Any]],
    ) -> List[EvidenceQuote]:
        """
        Find evidence supporting the claim from sources.
        
        Args:
            claim_text: The claim to verify
            sources: List of source dicts with content
        
        Returns:
            List of supporting evidence quotes
        """
        supporting = []
        
        for source in sources:
            source_content = source.get("content", "")
            source_id = source.get("id", "")
            source_url = source.get("url", "")
            
            # Simple approach: check similarity with chunks
            # In production, this would use embeddings/vector search
            chunks = self._chunk_text(source_content, chunk_size=500, overlap=100)
            
            for chunk in chunks:
                similarity = self._text_similarity(claim_text, chunk)
                if similarity >= self.similarity_threshold:
                    supporting.append(EvidenceQuote(
                        quote=chunk[:200],  # Truncate for storage
                        source_id=source_id,
                        source_url=source_url,
                        relevance=similarity,
                    ))
        
        # Sort by relevance, take top 3
        supporting.sort(key=lambda e: e.relevance, reverse=True)
        return supporting[:3]
    
    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 100,
    ) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    async def _llm_semantic_verify(
        self,
        claim_text: str,
        evidence_quotes: List[str],
    ) -> Tuple[VerificationStatus, float, str]:
        """
        Use LLM for semantic verification when text similarity is inconclusive.
        
        Returns:
            (status, confidence, reasoning)
        """
        if not self._llm_verify:
            # Default: return needs_review if no LLM available
            return VerificationStatus.NEEDS_REVIEW, 0.5, "Semantic verification not available"
        
        prompt = f"""Analyze whether the evidence supports, contradicts, or is insufficient for the claim.

CLAIM: {claim_text}

EVIDENCE:
{chr(10).join(f"- {q}" for q in evidence_quotes[:3])}

Respond with JSON:
{{
  "status": "supported|insufficient_evidence|conflicting|needs_review",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation"
}}
"""
        
        try:
            result = await self._llm_verify([{"role": "user", "content": prompt}])
            response = result[0] if isinstance(result, tuple) else result
            
            status_str = response.get("status", "needs_review")
            status = VerificationStatus(status_str)
            confidence = response.get("confidence", 0.5)
            reasoning = response.get("reasoning", "")
            
            return status, confidence, reasoning
            
        except Exception as e:
            return VerificationStatus.NEEDS_REVIEW, 0.5, f"Verification error: {e}"
    
    async def verify_claim(
        self,
        claim: ResearchClaim,
        sources: List[Dict[str, Any]],
        use_llm: bool = False,
    ) -> VerificationResult:
        """
        Verify a single claim against sources.
        
        Args:
            claim: The claim to verify
            sources: List of source dicts with content
            use_llm: Whether to use LLM for semantic verification
        
        Returns:
            VerificationResult with status and evidence
        """
        # Find supporting evidence
        supporting = self._find_supporting_evidence(claim.claim_text, sources)
        
        # Determine status based on evidence
        if len(supporting) >= 2:
            # Strong support
            status = VerificationStatus.SUPPORTED
            confidence = sum(e.relevance for e in supporting) / len(supporting)
            reasoning = f"Found {len(supporting)} supporting evidence items"
            
        elif len(supporting) == 1:
            # Weak support - may need review
            if supporting[0].relevance > 0.85:
                status = VerificationStatus.SUPPORTED
                confidence = supporting[0].relevance
                reasoning = "Single strong evidence match"
            else:
                status = VerificationStatus.NEEDS_REVIEW
                confidence = supporting[0].relevance
                reasoning = "Single weak evidence match"
                
        else:
            # No evidence found
            status = VerificationStatus.INSUFFICIENT_EVIDENCE
            confidence = 0.3
            reasoning = "No supporting evidence found in sources"
        
        # If inconclusive and LLM enabled, do semantic verification
        if use_llm and status == VerificationStatus.NEEDS_REVIEW:
            llm_status, llm_confidence, llm_reasoning = await self._llm_semantic_verify(
                claim.claim_text,
                [e.quote for e in supporting] if supporting else ["No direct evidence"],
            )
            status = llm_status
            confidence = llm_confidence
            reasoning = llm_reasoning
        
        return VerificationResult(
            claim=claim,
            status=status,
            confidence=confidence,
            supporting_evidence=supporting,
            conflicting_evidence=[],  # MVP: not detecting conflicts
            reasoning=reasoning,
        )
    
    async def verify_claims(
        self,
        claims: List[ResearchClaim],
        sources: List[Dict[str, Any]],
        use_llm: bool = False,
    ) -> List[VerificationResult]:
        """
        Verify multiple claims against sources.
        
        Args:
            claims: List of claims to verify
            sources: List of source dicts with content
            use_llm: Whether to use LLM for semantic verification
        
        Returns:
            List of VerificationResult objects
        """
        results = []
        
        for claim in claims:
            result = await self.verify_claim(claim, sources, use_llm)
            results.append(result)
        
        return results


# =============================================================================
# Convenience Function
# =============================================================================

async def verify_research_claims(
    claims: List[ResearchClaim],
    sources: List[Dict[str, Any]],
    similarity_threshold: float = 0.7,
    use_llm: bool = False,
    llm_verify_func: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Main entry point: verify claims against sources.
    
    Args:
        claims: List of claims to verify
        sources: List of source dicts with content, id, url
        similarity_threshold: Minimum similarity for text matching
        use_llm: Whether to use LLM for semantic verification
        llm_verify_func: Optional custom LLM function
    
    Returns:
        {
            "verified_count": int,
            "by_status": Dict[VerificationStatus, int],
            "results": List[VerificationResult],
        }
    """
    verifier = ClaimVerifier(
        similarity_threshold=similarity_threshold,
        llm_verify_func=llm_verify_func,
    )
    
    results = await verifier.verify_claims(claims, sources, use_llm)
    
    # Count by status
    by_status: Dict[VerificationStatus, int] = {
        VerificationStatus.SUPPORTED: 0,
        VerificationStatus.INSUFFICIENT_EVIDENCE: 0,
        VerificationStatus.CONFLICTING: 0,
        VerificationStatus.NEEDS_REVIEW: 0,
        VerificationStatus.PENDING: 0,
    }
    
    for result in results:
        by_status[result.status] = by_status.get(result.status, 0) + 1
    
    return {
        "verified_count": len(results),
        "by_status": by_status,
        "results": results,
    }
