"""
Research Claim Extractor Module (Phase 8)

Extracts atomic claims from confirmed/ingested source content for research runs.
This is Phase 8 specific - works with research runs post-completion.

Deterministic test mode supported via mockable LLM interface.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ClaimType(str, Enum):
    """Types of claims that can be extracted."""
    PREFERENCE = "preference"
    BELIEF = "belief"
    HEURISTIC = "heuristic"
    VALUE = "value"
    EXPERIENCE = "experience"
    BOUNDARY = "boundary"
    UNCERTAIN = "uncertain"


class VerificationStatus(str, Enum):
    """Verification statuses for Phase 8 MVP."""
    PENDING = "pending"
    SUPPORTED = "supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING = "conflicting"
    NEEDS_REVIEW = "needs_review"


@dataclass
class EvidenceQuote:
    """A quote from a source supporting or relating to a claim."""
    quote: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    relevance: float = 0.5  # 0.0 to 1.0


@dataclass
class ResearchClaim:
    """
    Atomic claim extracted from research source content.
    
    This is Phase 8's claim model - separate from persona_claims.
    """
    # IDs (set by database or service)
    id: Optional[str] = None
    research_run_id: Optional[str] = None
    twin_id: Optional[str] = None
    
    # Claim content
    claim_text: str = ""
    claim_type: ClaimType = ClaimType.UNCERTAIN
    
    # Verification (Phase 8)
    verification_status: VerificationStatus = VerificationStatus.PENDING
    confidence: float = 0.5
    authority: str = "extracted"  # extracted, owner_direct, inferred, uncertain
    
    # Source citation
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    
    # Evidence
    evidence_quotes: List[EvidenceQuote] = field(default_factory=list)
    
    # Extraction metadata
    extraction_version: str = "1.0.0"
    extractor_model: str = ""
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "research_run_id": self.research_run_id,
            "twin_id": self.twin_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type.value,
            "verification_status": self.verification_status.value,
            "confidence": self.confidence,
            "authority": self.authority,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "evidence_quotes": json.dumps([
                {"quote": e.quote, "source_id": e.source_id, 
                 "source_url": e.source_url, "relevance": e.relevance}
                for e in self.evidence_quotes
            ]),
            "extraction_version": self.extraction_version,
            "extractor_model": self.extractor_model,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchClaim":
        """Create from database dictionary."""
        evidence_data = data.get("evidence_quotes", "[]")
        if isinstance(evidence_data, str):
            evidence_data = json.loads(evidence_data)
        
        return cls(
            id=data.get("id"),
            research_run_id=data.get("research_run_id"),
            twin_id=data.get("twin_id"),
            claim_text=data.get("claim_text", ""),
            claim_type=ClaimType(data.get("claim_type", "uncertain")),
            verification_status=VerificationStatus(data.get("verification_status", "pending")),
            confidence=data.get("confidence", 0.5),
            authority=data.get("authority", "extracted"),
            source_id=data.get("source_id"),
            source_url=data.get("source_url"),
            source_title=data.get("source_title"),
            evidence_quotes=[
                EvidenceQuote(
                    quote=e.get("quote", ""),
                    source_id=e.get("source_id"),
                    source_url=e.get("source_url"),
                    relevance=e.get("relevance", 0.5)
                )
                for e in evidence_data
            ],
            extraction_version=data.get("extraction_version", "1.0.0"),
            extractor_model=data.get("extractor_model", ""),
        )


# =============================================================================
# Extraction Prompt
# =============================================================================

CLAIM_EXTRACTION_PROMPT = """You are a precise claim extraction system for Digital Twin research.

TASK: Extract atomic, factual claims from the provided source content.

RULES:
1. Each claim must be a single, verifiable statement
2. Classify each claim into one type:
   - preference: "I prefer X over Y", "My favorite..."
   - belief: "I believe that...", "In my opinion..."
   - heuristic: "When evaluating, I...", "My rule of thumb..."
   - value: "X matters more than Y", "I prioritize..."
   - experience: "In 2020, I learned...", "When I worked at..."
   - boundary: "I don't/won't...", "I never..."
   - uncertain: Low confidence or ambiguous statements

3. For each claim:
   - Provide exact supporting quote from source
   - Assign confidence 0.0-1.0 based on explicitness
   - Note if temporal/time-bound

4. REJECT vague statements without explicit support
5. SPLIT compound statements into separate atomic claims

EXTRACTION CRITERIA:
- Only extract claims attributable to the content owner
- Focus on first-person statements when available
- Capture expertise, positions, and stated preferences

Respond with JSON:
{{
  "claims": [
    {{
      "claim_text": "Clean, standalone claim",
      "claim_type": "preference|belief|heuristic|value|experience|boundary|uncertain",
      "quote": "Exact text from source",
      "confidence": 0.9,
      "time_scope": "2020-2022"
    }}
  ],
  "rejected_fragments": ["text that couldn't be claimed"]
}}

SOURCE CONTENT:
{content}

SOURCE METADATA:
Title: {title}
URL: {url}
"""


# =============================================================================
# Extraction Engine
# =============================================================================

class ResearchClaimExtractor:
    """
    Extract atomic claims from source content for research runs.
    
    Supports deterministic test mode via injectable LLM function.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        llm_invoke_func: Optional[Any] = None,
    ):
        """
        Initialize extractor.
        
        Args:
            model: Model name for extraction
            llm_invoke_func: Optional custom LLM function for testing
        """
        self.model = model
        self.extraction_version = "1.0.0"
        self._llm_invoke = llm_invoke_func or self._default_llm_invoke
    
    async def _default_llm_invoke(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Tuple[Dict[str, Any], Any]:
        """Default LLM invocation using inference_router."""
        from modules.inference_router import invoke_json
        return await invoke_json(messages, **kwargs)
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    async def extract_from_source(
        self,
        content: str,
        source_id: str,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
        twin_id: Optional[str] = None,
        research_run_id: Optional[str] = None,
    ) -> List[ResearchClaim]:
        """
        Extract claims from a single source.
        
        Args:
            content: Source text content
            source_id: Source UUID
            source_url: Optional source URL
            source_title: Optional source title
            twin_id: Optional twin ID
            research_run_id: Optional research run ID
        
        Returns:
            List of ResearchClaim objects
        """
        if not content or len(content.strip()) < 20:
            return []
        
        # Prepare prompt
        prompt = CLAIM_EXTRACTION_PROMPT.format(
            content=content[:10000],  # Limit context
            title=source_title or "Unknown",
            url=source_url or "Unknown",
        )
        
        try:
            result, _ = await self._llm_invoke(
                [{"role": "user", "content": prompt}],
                task="structured",
                temperature=0.0,  # Deterministic
                max_tokens=2000,
            )
            
            claims_data = result.get("claims", [])
            claims = []
            
            for claim_data in claims_data:
                # Parse claim type
                claim_type_str = claim_data.get("claim_type", "uncertain").lower()
                try:
                    claim_type = ClaimType(claim_type_str)
                except ValueError:
                    claim_type = ClaimType.UNCERTAIN
                
                # Create evidence quote
                quote_text = claim_data.get("quote", "")
                evidence = [EvidenceQuote(
                    quote=quote_text,
                    source_id=source_id,
                    source_url=source_url,
                    relevance=claim_data.get("confidence", 0.5)
                )] if quote_text else []
                
                claim = ResearchClaim(
                    research_run_id=research_run_id,
                    twin_id=twin_id,
                    claim_text=claim_data.get("claim_text", ""),
                    claim_type=claim_type,
                    verification_status=VerificationStatus.PENDING,
                    confidence=claim_data.get("confidence", 0.5),
                    authority="extracted",
                    source_id=source_id,
                    source_url=source_url,
                    source_title=source_title,
                    evidence_quotes=evidence,
                    extractor_model=self.model,
                    extraction_version=self.extraction_version,
                )
                
                claims.append(claim)
            
            return claims
            
        except Exception as e:
            print(f"[ResearchClaimExtractor] Extraction failed: {e}")
            return []
    
    async def extract_from_sources(
        self,
        sources: List[Dict[str, Any]],
        twin_id: Optional[str] = None,
        research_run_id: Optional[str] = None,
    ) -> List[ResearchClaim]:
        """
        Extract claims from multiple sources.
        
        Args:
            sources: List of source dicts with content, id, url, title
            twin_id: Twin ID
            research_run_id: Research run ID
        
        Returns:
            List of ResearchClaim objects
        """
        all_claims = []
        
        for source in sources:
            claims = await self.extract_from_source(
                content=source.get("content", ""),
                source_id=source.get("id", ""),
                source_url=source.get("url"),
                source_title=source.get("title"),
                twin_id=twin_id,
                research_run_id=research_run_id,
            )
            all_claims.extend(claims)
        
        return all_claims


# =============================================================================
# Convenience Function
# =============================================================================

async def extract_claims_from_research_sources(
    sources: List[Dict[str, Any]],
    twin_id: str,
    research_run_id: str,
    model: str = "gpt-4o-mini",
    llm_invoke_func: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Main entry point: extract claims from research sources.
    
    Args:
        sources: List of source dicts with content, id, url, title
        twin_id: Twin ID
        research_run_id: Research run ID
        model: Model to use for extraction
        llm_invoke_func: Optional custom LLM function for testing
    
    Returns:
        {
            "extracted_count": int,
            "claims": List[ResearchClaim],
        }
    """
    extractor = ResearchClaimExtractor(
        model=model,
        llm_invoke_func=llm_invoke_func,
    )
    
    claims = await extractor.extract_from_sources(
        sources=sources,
        twin_id=twin_id,
        research_run_id=research_run_id,
    )
    
    return {
        "extracted_count": len(claims),
        "claims": claims,
    }
