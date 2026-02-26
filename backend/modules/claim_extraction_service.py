"""
Person Completeness Pipeline - Stage 2: Claim Extraction Service

Extracts structured claims from sources with evidence spans.
Features:
- Deterministic + LLM-assisted extraction
- Evidence span attachment
- Claim deduplication via fingerprinting
- First vs third party source detection
"""

import hashlib
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from modules.observability import supabase
from modules.person_completeness_config import ClaimExtractionConfig

logger = logging.getLogger(__name__)


@dataclass
class ExtractedClaim:
    """A claim extracted from source content."""
    claim_text: str
    claim_type: str
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    claim_time_start: Optional[str] = None
    claim_time_end: Optional[str] = None
    tense_status: str = "active"
    confidence: float = 0.5
    extraction_method: str = "llm"
    evidence_spans: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_fingerprint(self) -> str:
        """Compute fingerprint for deduplication."""
        # Normalize claim text for fingerprinting
        normalized = self.claim_text.lower().strip().replace(".", "").replace(",", "")
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


@dataclass
class ClaimExtractionResult:
    """Result of claim extraction."""
    success: bool
    claims_extracted: int = 0
    evidence_spans_attached: int = 0
    claims_deduped: int = 0
    error_message: Optional[str] = None

    @property
    def item_count(self) -> int:
        """Compatibility count for pipeline metrics."""
        return self.claims_extracted


class ClaimExtractionService:
    """Extracts structured claims from source content."""

    VALID_CLAIM_TYPES = {
        "identity",
        "work_experience",
        "education",
        "credential",
        "project",
        "achievement",
        "preference",
        "belief",
        "goal",
        "bio_fact",
        "skill",
        "media_appearance",
        "timeline_event",
        "expertise",
        "uncertain",
    }
    
    def __init__(self, config: Optional[ClaimExtractionConfig] = None):
        self.config = config or ClaimExtractionConfig()
        self.extraction_prompt = self._build_extraction_prompt()
    
    async def run(
        self,
        twin_id: str,
        research_run_id: Optional[str] = None,
    ) -> ClaimExtractionResult:
        """
        Extract claims for a twin.
        
        Args:
            twin_id: The twin to process
            research_run_id: Optional research run for context
            
        Returns:
            ClaimExtractionResult
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"Extracting claims for twin {twin_id}")
            
            # Get sources from registry
            sources = await self._get_sources(twin_id)
            
            if not sources:
                logger.info(f"No sources found for twin {twin_id}")
                return ClaimExtractionResult(success=True, claims_extracted=0)
            
            claims_extracted = 0
            evidence_spans_attached = 0
            claims_deduped = 0
            seen_fingerprints: set = set()
            
            for source in sources:
                try:
                    # Extract claims from source
                    claims = await self._extract_from_source(source, twin_id)
                    
                    for claim in claims:
                        # Check deduplication
                        fingerprint = claim.compute_fingerprint()
                        if fingerprint in seen_fingerprints:
                            claims_deduped += 1
                            continue
                        seen_fingerprints.add(fingerprint)
                        
                        # Store claim
                        claim_id = await self._store_claim(twin_id, claim, fingerprint)
                        
                        if claim_id:
                            claims_extracted += 1
                            
                            # Store evidence spans
                            for span in claim.evidence_spans:
                                await self._store_evidence_span(claim_id, span, source["id"])
                                evidence_spans_attached += 1
                
                except Exception as e:
                    logger.warning(f"Error processing source {source.get('id')}: {e}")
                    continue
            
            duration = time.time() - start_time
            logger.info(f"Claim extraction completed in {duration:.2f}s: "
                       f"{claims_extracted} claims, {evidence_spans_attached} evidence spans, "
                       f"{claims_deduped} deduped")
            
            return ClaimExtractionResult(
                success=True,
                claims_extracted=claims_extracted,
                evidence_spans_attached=evidence_spans_attached,
                claims_deduped=claims_deduped
            )
        
        except Exception as e:
            logger.exception(f"Error extracting claims: {e}")
            return ClaimExtractionResult(
                success=False,
                error_message=str(e)
            )
    
    async def _get_sources(self, twin_id: str) -> List[Dict[str, Any]]:
        """Get sources from registry for processing."""
        try:
            response = supabase.table("person_source_registry") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .eq("is_active", True) \
                .order("authority_tier", desc=False) \
                .limit(max(20, self.config.max_sources_per_twin * 3)) \
                .execute()

            # Keep sources with authority tier <= configured threshold (lower tier = higher authority).
            # If authority tier is missing, keep the source so we do not silently drop novel providers.
            filtered: List[Dict[str, Any]] = []
            for src in response.data or []:
                tier = src.get("authority_tier")
                if isinstance(tier, (int, float)) and int(tier) > self.config.min_authority_tier:
                    continue
                filtered.append(src)

            filtered.sort(
                key=lambda row: int(row.get("authority_tier")) if isinstance(row.get("authority_tier"), (int, float)) else 99
            )
            return filtered[: self.config.max_sources_per_twin]
        except Exception as e:
            logger.error(f"Error fetching sources: {e}")
            return []
    
    async def _extract_from_source(
        self,
        source: Dict[str, Any],
        twin_id: str
    ) -> List[ExtractedClaim]:
        """Extract claims from a single source."""
        claims = []
        
        # Get source content
        content = await self._get_source_content(source, twin_id)
        if not content or len(content.strip()) < 50:
            return claims
        
        # Try rule-based extraction first (fast, deterministic)
        rule_claims = self._extract_rule_based(content, source)
        claims.extend(rule_claims)
        
        # LLM-assisted extraction for remaining content
        if len(claims) < self.config.max_claims_per_source // 2:
            llm_claims = await self._extract_with_llm(content, source)
            claims.extend(llm_claims)
        
        # Limit claims per source
        return claims[:self.config.max_claims_per_source]
    
    async def _get_source_content(
        self,
        source: Dict[str, Any],
        twin_id: str
    ) -> Optional[str]:
        """Get content for a source."""
        # Try to get from raw_reference_json
        raw_ref = source.get("raw_reference_json", {})
        
        # If linked to sources table
        source_table_id = raw_ref.get("source_id")
        if source_table_id:
            try:
                response = supabase.table("sources") \
                    .select("content_text") \
                    .eq("id", source_table_id) \
                    .single() \
                    .execute()
                if response.data and response.data.get("content_text"):
                    return response.data["content_text"]
            except Exception:
                pass
        
        # Try to get from web evidence
        web_evidence_id = raw_ref.get("web_evidence_id")
        if web_evidence_id:
            try:
                response = supabase.table("research_claim_web_evidence") \
                    .select("source_snippet, extracted_quote") \
                    .eq("id", web_evidence_id) \
                    .single() \
                    .execute()
                if response.data:
                    return response.data.get("extracted_quote") or response.data.get("source_snippet", "")
            except Exception:
                pass
        
        return None
    
    def _extract_rule_based(
        self,
        content: str,
        source: Dict[str, Any]
    ) -> List[ExtractedClaim]:
        """Rule-based claim extraction (deterministic)."""
        claims = []
        
        # Pattern-based extraction for common claim types
        patterns = [
            # Work experience
            (r"(?:I am|I've been|I have been) (?:a|an) ([^,.]+) (?:at|with) ([^,.]+)", 
             "work_experience", "experience"),
            # Education
            (r"(?:I studied|I graduated from|I have a [^,.]+ degree from) ([^,.]+)",
             "education", "education"),
            # Expertise
            (r"(?:I specialize in|My expertise is in|I focus on|I work on) ([^,.]+)",
             "expertise", "expertise"),
            # Preferences
            (r"(?:I prefer|I like|I enjoy|I love|I believe) ([^,.]+)",
             "preference", "preference"),
        ]
        
        import re
        content_sample = content[:20000]  # Limit for regex performance
        
        for pattern, claim_type, context in patterns:
            if claim_type not in self.config.enabled_claim_types:
                continue
                
            matches = re.finditer(pattern, content_sample, re.IGNORECASE)
            for match in matches:
                claim_text = match.group(0).strip()
                if len(claim_text) < 20 or len(claim_text) > 500:
                    continue
                
                # Detect first vs third party
                source_party = self._detect_source_party(claim_text)
                
                claim = ExtractedClaim(
                    claim_text=claim_text,
                    claim_type=self._normalize_claim_type(claim_type),
                    subject="I" if "I " in claim_text[:5] else None,
                    extraction_method="rule",
                    confidence=0.6 if source_party == "first_party" else 0.4,
                    evidence_spans=[{
                        "evidence_text": claim_text,
                        "evidence_type": "quote",
                        "source_party": source_party,
                        "start_offset": match.start(),
                        "end_offset": match.end(),
                    }]
                )
                claims.append(claim)
        
        return claims
    
    async def _extract_with_llm(
        self,
        content: str,
        source: Dict[str, Any]
    ) -> List[ExtractedClaim]:
        """LLM-assisted claim extraction."""
        claims = []
        
        # Truncate content for LLM
        content_truncated = content[:10000]
        
        try:
            from modules.inference_router import invoke_json
            
            prompt = self.extraction_prompt.format(
                content=content_truncated,
                title=source.get("title", "Unknown"),
                url=source.get("url", "Unknown"),
                claim_types=", ".join(self.config.enabled_claim_types[:8])
            )
            
            result, _ = await invoke_json(
                [{"role": "user", "content": prompt}],
                task="structured",
                temperature=0.0,
                max_tokens=2000,
            )
            
            for claim_data in result.get("claims", []):
                # Detect first vs third party
                evidence_text = claim_data.get("quote", claim_data.get("claim_text", ""))
                source_party = self._detect_source_party(evidence_text)
                
                claim = ExtractedClaim(
                    claim_text=claim_data.get("claim_text", ""),
                    claim_type=self._normalize_claim_type(claim_data.get("claim_type", "uncertain")),
                    subject=claim_data.get("subject"),
                    predicate=claim_data.get("predicate"),
                    object=claim_data.get("object"),
                    claim_time_start=claim_data.get("time_start"),
                    claim_time_end=claim_data.get("time_end"),
                    tense_status=claim_data.get("tense", "active"),
                    confidence=claim_data.get("confidence", 0.5),
                    extraction_method="llm",
                    evidence_spans=[{
                        "evidence_text": evidence_text,
                        "evidence_type": "quote",
                        "source_party": source_party,
                    }],
                    metadata={
                        "time_scope": claim_data.get("time_scope"),
                        "context": claim_data.get("context"),
                    }
                )
                
                # Filter by confidence
                if claim.confidence >= self.config.min_confidence_threshold:
                    claims.append(claim)
        
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
        
        return claims
    
    def _detect_source_party(self, text: str) -> str:
        """Detect if text is first or third party."""
        first_person_markers = ["i ", "i'm", "my ", "we ", "our ", "i've", "i'd", "i'll"]
        text_lower = text.lower()
        
        for marker in first_person_markers:
            if marker in text_lower[:200]:  # Check start of text
                return "first_party"
        
        return "third_party"

    def _normalize_claim_type(self, claim_type: Optional[str]) -> str:
        """Normalize model/rule output claim types to DB-safe values."""
        value = str(claim_type or "").strip().lower()
        if value in self.VALID_CLAIM_TYPES:
            return value
        return "uncertain"
    
    async def _store_claim(
        self,
        twin_id: str,
        claim: ExtractedClaim,
        fingerprint: str
    ) -> Optional[str]:
        """Store claim in database."""
        try:
            insert_data = {
                "twin_id": twin_id,
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "object": claim.object,
                "claim_time_start": claim.claim_time_start,
                "claim_time_end": claim.claim_time_end,
                "tense_status": claim.tense_status,
                "extraction_method": claim.extraction_method,
                "extraction_confidence": claim.confidence,
                "claim_fingerprint": fingerprint,
                "verification_status": "unverified",
                "owner_approval_status": "not_required",
                "public_visibility": "public",
                "metadata_json": claim.metadata,
            }
            
            response = supabase.table("person_claims").insert(insert_data).execute()
            return response.data[0]["id"] if response.data else None
        
        except Exception as e:
            logger.warning(f"Error storing claim: {e}")
            return None
    
    async def _store_evidence_span(
        self,
        claim_id: str,
        span: Dict[str, Any],
        source_registry_id: str
    ):
        """Store evidence span in database."""
        try:
            insert_data = {
                "claim_id": claim_id,
                "source_registry_id": source_registry_id,
                "evidence_type": span.get("evidence_type", "quote"),
                "evidence_text": span.get("evidence_text", "")[:2000],  # Limit length
                "evidence_confidence": 0.8 if span.get("source_party") == "first_party" else 0.5,
                "source_party": span.get("source_party", "unknown"),
                "start_offset": span.get("start_offset"),
                "end_offset": span.get("end_offset"),
            }
            
            supabase.table("person_claim_evidence_spans").insert(insert_data).execute()
        
        except Exception as e:
            logger.warning(f"Error storing evidence span: {e}")
    
    def _build_extraction_prompt(self) -> str:
        """Build the extraction prompt template."""
        return """You are a precise claim extraction system for Digital Twin research.

TASK: Extract atomic, factual claims from the provided source content.

RULES:
1. Each claim must be a single, verifiable statement
2. Classify each claim into one type: {claim_types}

3. For each claim provide:
   - claim_text: Clean, standalone claim statement
   - claim_type: One of the allowed types
   - quote: Exact supporting text from source
   - confidence: 0.0-1.0 based on explicitness and clarity
   - subject/predicate/object: Optional SPO triple
   - time_start/time_end: Optional temporal bounds
   - tense: active, historical, uncertain

4. REJECT vague statements without explicit support
5. SPLIT compound statements into separate atomic claims
6. PRESERVE first-person attribution when present

EXTRACTION CRITERIA:
- Extract claims attributable to the content owner/subject
- Focus on first-person statements ("I...", "My...", "We...")
- Capture expertise, positions, preferences, experiences
- Note temporal information (dates, durations)

Respond with JSON:
{{
  "claims": [
    {{
      "claim_text": "Clean standalone claim",
      "claim_type": "type_from_list",
      "subject": "optional",
      "predicate": "optional",
      "object": "optional",
      "quote": "Exact text from source",
      "confidence": 0.9,
      "time_start": "optional ISO date",
      "time_end": "optional ISO date",
      "time_scope": "description of temporal context",
      "tense": "active|historical|uncertain"
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
