"""
persona_claim_extractor.py

Phase 2 Component: Extract atomic claims from chunks.
Converts text chunks into structured, citable claims.
"""

import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pydantic import BaseModel, Field

from modules.inference_router import invoke_json


# =============================================================================
# Claim Schema
# =============================================================================

class ClaimCitation(BaseModel):
    """Stable citation object for claims."""
    source_id: str
    chunk_id: Optional[str] = None
    span_start: int  # Character offset in source
    span_end: int    # Character offset end
    quote: str       # Exact quoted text
    content_hash: str  # SHA-256 of source content


class PersonaClaim(BaseModel):
    """Atomic claim extracted from content."""
    id: Optional[str] = None  # Set by database
    twin_id: str
    
    # Claim content
    claim_text: str
    claim_type: str  # preference, belief, heuristic, value, experience, boundary, uncertain
    
    # Citation
    citation: ClaimCitation
    
    # Authority and confidence
    authority: str = "extracted"  # extracted, owner_direct, inferred, uncertain
    confidence: float = Field(ge=0.0, le=1.0)
    
    # Temporal scope
    time_scope_start: Optional[datetime] = None
    time_scope_end: Optional[datetime] = None
    
    # Extraction metadata
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_version: str = "1.0.0"
    extractor_model: str = ""


# =============================================================================
# Claim Extraction Prompt
# =============================================================================

CLAIM_EXTRACTION_PROMPT = """You are a precise claim extraction system for a Digital Twin Persona.

TASK: Extract atomic claims from the provided text content.

RULES:
1. Each claim must be a single, verifiable statement about the owner's:
   - Preferences ("I prefer X over Y")
   - Beliefs ("I believe that...")
   - Heuristics ("When evaluating, I...")
   - Values ("X matters more than Y")
   - Experiences ("In 2020, I learned...")
   - Boundaries ("I don't/won't...")

2. For each claim:
   - Provide exact quote from source
   - Classify into one type: preference, belief, heuristic, value, experience, boundary, uncertain
   - Assign confidence 0.0-1.0 based on clarity and explicitness
   - Note character span (start, end)

3. REJECT vague or unclear statements
4. REJECT claims without explicit textual support
5. SPLIT compound statements into separate atomic claims

EXTRACTION CRITERIA:
- preference: Explicit preference statements
- belief: Core beliefs or opinions
- heuristic: Decision-making rules or frameworks
- value: Priority values or principles
- experience: Specific past experiences or lessons
- boundary: Hard limits or refusals
- uncertain: Low confidence or ambiguous

Respond with JSON:
{
  "claims": [
    {
      "claim_text": "Clean, standalone claim",
      "claim_type": "preference|belief|heuristic|value|experience|boundary|uncertain",
      "quote": "Exact text from source",
      "span_start": 0,
      "span_end": 50,
      "confidence": 0.9,
      "time_scope": "2020-2022"  // Optional temporal reference
    }
  ],
  "rejected_fragments": ["text that couldn't be claimed"]
}

SOURCE CONTENT:
{content}

SOURCE METADATA:
{metadata}
"""


# =============================================================================
# Extraction Engine
# =============================================================================

class ClaimExtractor:
    """Extract atomic claims from text chunks."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.extraction_version = "1.0.0"
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _validate_span(self, content: str, span_start: int, span_end: int, quote: str) -> bool:
        """Validate that span matches quote in content."""
        if span_start < 0 or span_end > len(content) or span_start >= span_end:
            return False
        
        extracted = content[span_start:span_end]
        
        # Allow minor whitespace differences
        normalized_extracted = re.sub(r'\s+', ' ', extracted).strip()
        normalized_quote = re.sub(r'\s+', ' ', quote).strip()
        
        # Check if quote is contained (allowing for context around it)
        if normalized_quote in normalized_extracted:
            return True
        
        # Check similarity (at least 80% match)
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, normalized_extracted, normalized_quote).ratio()
        
        return similarity >= 0.8
    
    def _find_span(self, content: str, quote: str) -> Optional[Tuple[int, int]]:
        """Find the span of a quote in content."""
        # Try exact match first
        idx = content.find(quote)
        if idx != -1:
            return (idx, idx + len(quote))
        
        # Try normalized match
        normalized_content = re.sub(r'\s+', ' ', content)
        normalized_quote = re.sub(r'\s+', ' ', quote)
        
        idx = normalized_content.find(normalized_quote)
        if idx != -1:
            # Map back to original indices (approximate)
            return (max(0, idx), min(len(content), idx + len(quote)))
        
        # Try fuzzy match for partial quotes
        from difflib import SequenceMatcher
        best_match = None
        best_ratio = 0.0
        
        # Sliding window search
        quote_len = len(quote)
        for i in range(len(content) - quote_len + 1):
            window = content[i:i + quote_len]
            ratio = SequenceMatcher(None, window, quote).ratio()
            if ratio > best_ratio and ratio > 0.8:
                best_ratio = ratio
                best_match = (i, i + quote_len)
        
        return best_match
    
    async def extract_from_text(
        self,
        text: str,
        source_id: str,
        twin_id: str,
        chunk_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[PersonaClaim]:
        """
        Extract claims from text content.
        
        Args:
            text: Content to extract from
            source_id: Source document ID
            twin_id: Twin ID
            chunk_id: Optional chunk ID
            metadata: Optional source metadata
        
        Returns:
            List of PersonaClaim objects
        """
        if not text or len(text.strip()) < 20:
            return []
        
        content_hash = self._compute_content_hash(text)
        metadata_str = str(metadata or {})
        
        # Call LLM for extraction
        prompt = CLAIM_EXTRACTION_PROMPT.format(
            content=text[:8000],  # Limit context
            metadata=metadata_str,
        )
        
        try:
            result, _ = await invoke_json(
                [{"role": "user", "content": prompt}],
                task="structured",
                temperature=0.0,  # Deterministic
                max_tokens=2000,
            )
            
            claims_data = result.get("claims", [])
            claims = []
            
            for claim_data in claims_data:
                # Validate and locate span
                span_start = claim_data.get("span_start", 0)
                span_end = claim_data.get("span_end", 0)
                quote = claim_data.get("quote", "")
                
                # If span invalid, try to find it
                if not self._validate_span(text, span_start, span_end, quote):
                    found_span = self._find_span(text, quote)
                    if found_span:
                        span_start, span_end = found_span
                    else:
                        # Skip claims without valid spans
                        print(f"[ClaimExtractor] Rejecting claim - no valid span: {quote[:50]}...")
                        continue
                
                # Parse temporal scope
                time_scope = claim_data.get("time_scope")
                time_start = None
                time_end = None
                
                if time_scope:
                    # Parse "2020-2022" or "2020" formats
                    try:
                        if "-" in str(time_scope):
                            parts = str(time_scope).split("-")
                            time_start = datetime(int(parts[0]), 1, 1)
                            time_end = datetime(int(parts[1]), 12, 31)
                        else:
                            year = int(time_scope)
                            time_start = datetime(year, 1, 1)
                            time_end = datetime(year, 12, 31)
                    except:
                        pass
                
                # Create claim
                claim = PersonaClaim(
                    twin_id=twin_id,
                    claim_text=claim_data["claim_text"],
                    claim_type=claim_data["claim_type"],
                    citation=ClaimCitation(
                        source_id=source_id,
                        chunk_id=chunk_id,
                        span_start=span_start,
                        span_end=span_end,
                        quote=quote,
                        content_hash=content_hash,
                    ),
                    confidence=claim_data.get("confidence", 0.5),
                    time_scope_start=time_start,
                    time_scope_end=time_end,
                    extractor_model=self.model,
                )
                
                claims.append(claim)
            
            return claims
            
        except Exception as e:
            print(f"[ClaimExtractor] Extraction failed: {e}")
            return []
    
    async def extract_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        twin_id: str,
    ) -> List[PersonaClaim]:
        """
        Extract claims from multiple chunks.
        
        Args:
            chunks: List of chunk dicts with text, source_id, chunk_id
            twin_id: Twin ID
        
        Returns:
            List of PersonaClaim objects
        """
        all_claims = []
        
        for chunk in chunks:
            claims = await self.extract_from_text(
                text=chunk.get("text", ""),
                source_id=chunk.get("source_id", ""),
                twin_id=twin_id,
                chunk_id=chunk.get("chunk_id"),
                metadata=chunk.get("metadata"),
            )
            all_claims.extend(claims)
        
        return all_claims


# =============================================================================
# Claim Storage
# =============================================================================

class ClaimStore:
    """Store and retrieve claims from database."""
    
    def __init__(self, supabase_client):
        self.db = supabase_client
    
    async def save_claims(self, claims: List[PersonaClaim]) -> List[str]:
        """
        Save claims to database.
        
        Returns:
            List of claim IDs
        """
        if not claims:
            return []
        
        claim_ids = []
        
        for claim in claims:
            data = {
                "twin_id": claim.twin_id,
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "source_id": claim.citation.source_id,
                "chunk_id": claim.citation.chunk_id,
                "span_start": claim.citation.span_start,
                "span_end": claim.citation.span_end,
                "quote": claim.citation.quote,
                "content_hash": claim.citation.content_hash,
                "authority": claim.authority,
                "confidence": claim.confidence,
                "time_scope_start": claim.time_scope_start.isoformat() if claim.time_scope_start else None,
                "time_scope_end": claim.time_scope_end.isoformat() if claim.time_scope_end else None,
                "extraction_version": claim.extraction_version,
                "extractor_model": claim.extractor_model,
            }
            
            try:
                result = self.db.table("persona_claims").insert(data).execute()
                if result.data:
                    claim_ids.append(result.data[0]["id"])
            except Exception as e:
                print(f"[ClaimStore] Failed to save claim: {e}")
        
        return claim_ids
    
    async def get_claims_for_twin(
        self,
        twin_id: str,
        claim_type: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Get claims for a twin with optional filtering."""
        query = (
            self.db.table("persona_claims")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("is_active", True)
            .gte("confidence", min_confidence)
        )
        
        if claim_type:
            query = query.eq("claim_type", claim_type)
        
        result = query.execute()
        return result.data or []
    
    async def update_claim_authority(
        self,
        claim_id: str,
        authority: str,
        verification_status: str = "confirmed",
    ):
        """Update claim authority (e.g., after owner clarification)."""
        data = {
            "authority": authority,
            "verification_status": verification_status,
            "verified_at": datetime.utcnow().isoformat(),
        }
        
        self.db.table("persona_claims").update(data).eq("id", claim_id).execute()


# =============================================================================
# Main Interface
# =============================================================================

async def extract_and_store_claims(
    chunks: List[Dict[str, Any]],
    twin_id: str,
    supabase_client,
) -> Dict[str, Any]:
    """
    Main entry point: extract claims from chunks and store them.
    
    Returns:
        {
            "extracted_count": int,
            "stored_count": int,
            "claim_ids": List[str],
        }
    """
    extractor = ClaimExtractor()
    store = ClaimStore(supabase_client)
    
    # Extract claims
    claims = await extractor.extract_from_chunks(chunks, twin_id)
    
    # Store claims
    claim_ids = await store.save_claims(claims)
    
    return {
        "extracted_count": len(claims),
        "stored_count": len(claim_ids),
        "claim_ids": claim_ids,
    }
