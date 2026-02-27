"""
Graph Claim Extractor (Phase 3)

Extracts structured claims from text using LLM.
Runs as async worker via outbox queue.
All operations are tenant/twin scoped via scope_id (single-profile mode)
or group_id (legacy twin-scoped mode during rollout).
"""

import json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import get_graph_memory_config, is_single_profile_enabled


@dataclass
class ExtractedClaim:
    """A structured claim extracted from text."""
    claim_id: str
    text: str
    confidence: float
    claim_type: str  # 'fact', 'opinion', 'preference', 'belief'
    source_ref: str
    source_type: str
    extracted_at: str
    content_hash: str  # For detecting changes


class GraphClaimExtractor:
    """
    Extracts claims from text and stores in graph memory.
    
    Usage (single-profile scope):
        extractor = GraphClaimExtractor(
            tenant_id=tenant_id,
            scope_id=f"{tenant_id}__{creator_id}",
            creator_id=creator_id,
            correlation_id=correlation_id
        )
        claims = await extractor.extract_claims(
            text="Owner prefers direct communication",
            source_type="escalation_resolution",
            source_ref="esc-123"
        )
    
    Usage (legacy twin-scoped, backward compatible):
        extractor = GraphClaimExtractor(
            tenant_id=tenant_id,
            twin_id=twin_id,
            correlation_id=correlation_id
        )
    """
    
    def __init__(
        self,
        tenant_id: str,
        twin_id: Optional[str] = None,
        scope_id: Optional[str] = None,
        creator_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        self.tenant_id = tenant_id
        self.twin_id = twin_id
        self.scope_id = scope_id
        self.creator_id = creator_id
        self.correlation_id = correlation_id or "no-correlation"
        self.config = get_graph_memory_config()
        
        # Determine if single-profile scope is enabled
        self._single_profile_enabled = is_single_profile_enabled()
        
        if self._single_profile_enabled and scope_id:
            # Single-profile mode: use scope_id directly
            self.group_id = scope_id
        elif scope_id and not twin_id:
            # Scope provided but no twin - use scope as group_id
            self.group_id = scope_id
        else:
            # Legacy mode or during rollout: derive group_id from tenant/twin
            # Default twin_id if not provided
            effective_twin_id = twin_id or "default"
            self.twin_id = effective_twin_id
            self.group_id = self.config.make_group_id(tenant_id, effective_twin_id)
            
            # Derive scope_id if not provided (for backward compatibility)
            if not self.scope_id and creator_id:
                self.scope_id = f"{tenant_id}__{creator_id}"
        
        self._client: Optional[GraphMemoryCore] = None
    
    def _make_idempotency_key(self, claim_id: str) -> str:
        """Generate idempotency key using scope_id (single-profile) or group_id (legacy)."""
        scope = self.scope_id if self._single_profile_enabled else self.group_id
        return f"claim:{scope}:{claim_id}"
    
    def _get_client(self) -> Optional[GraphMemoryCore]:
        """Lazy initialize GraphMemoryCore client."""
        if self._client is not None:
            return self._client
        
        if not self.config.is_write_allowed():
            return None
        
        # Use scope_id if available and single-profile is enabled, otherwise fall back to twin_id
        effective_scope = None
        if self._single_profile_enabled and self.scope_id:
            effective_scope = self.scope_id
        
        self._client = GraphMemoryCore(
            tenant_id=self.tenant_id,
            twin_id=self.twin_id or "default",
            scope_id=effective_scope,
            correlation_id=self.correlation_id
        )
        return self._client
    
    async def extract_claims(
        self,
        text: str,
        source_type: str,
        source_ref: str,
        context: Optional[Dict[str, Any]] = None,
        scope_id: Optional[str] = None
    ) -> List[ExtractedClaim]:
        """
        Extract claims from text using LLM.
        
        Args:
            text: Text to extract claims from
            source_type: Type of source (escalation_resolution, interview, etc)
            source_ref: Reference ID
            context: Optional context (question, metadata, etc)
            scope_id: Optional scope_id to override instance scope (for single-profile mode)
            
        Returns:
            List of extracted claims
        """
        # Allow scope_id override for single-profile operations
        if scope_id:
            self.scope_id = scope_id
            if self._single_profile_enabled:
                self.group_id = scope_id
        
        client = self._get_client()
        if not client:
            return []
        
        # Use LLM to extract claims
        claims_data = await self._llm_extract_claims(text, context)
        
        extracted_claims = []
        for claim_data in claims_data:
            claim = ExtractedClaim(
                claim_id=self._generate_claim_id(claim_data['text'], source_ref),
                text=claim_data['text'],
                confidence=claim_data.get('confidence', 0.8),
                claim_type=claim_data.get('type', 'fact'),
                source_ref=source_ref,
                source_type=source_type,
                extracted_at=datetime.utcnow().isoformat(),
                content_hash=self._hash_content(claim_data['text'])
            )
            extracted_claims.append(claim)
        
        return extracted_claims
    
    async def _llm_extract_claims(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to extract structured claims from text.
        
        Returns list of claim dicts with 'text', 'confidence', 'type'
        """
        from modules.clients import openai_client
        
        question = context.get('question', '') if context else ''
        
        prompt = f"""Extract factual claims from the following text. 

Original Question: {question}

Text to analyze:
"{text}"

Extract 1-5 specific claims that represent the owner's position, preferences, or facts stated.
For each claim, provide:
- The claim text (clear, standalone statement)
- Confidence score (0.0-1.0)
- Claim type: fact | opinion | preference | belief

Respond in JSON format:
{{
  "claims": [
    {{
      "text": "claim text here",
      "confidence": 0.95,
      "type": "fact"
    }}
  ]
}}

Rules:
- Only extract claims attributable to the owner
- Make claims specific and verifiable
- Confidence should reflect certainty in interpretation
- Type should categorize the nature of the claim"""

        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a precise claim extraction assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('claims', [])
            
        except Exception as e:
            # Fallback: create single claim from full text
            return [{
                'text': text[:200],
                'confidence': 0.7,
                'type': 'fact'
            }]
    
    def _generate_claim_id(self, text: str, source_ref: str) -> str:
        """Generate deterministic claim ID."""
        # Use scope_id if in single-profile mode, otherwise use group_id
        scope = self.scope_id if self._single_profile_enabled else self.group_id
        content = f"{scope}:{source_ref}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _hash_content(self, text: str) -> str:
        """Generate content hash for change detection."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    async def store_claims(
        self,
        claims: List[ExtractedClaim],
        async_write: bool = True,
        scope_id: Optional[str] = None
    ) -> List[str]:
        """
        Store extracted claims in graph memory.
        
        Args:
            claims: List of extracted claims
            async_write: If True, use outbox; if False, synchronous
            scope_id: Optional scope_id to override instance scope (for single-profile mode)
            
        Returns:
            List of job IDs (if async) or claim IDs (if sync)
        """
        # Allow scope_id override for single-profile operations
        if scope_id:
            self.scope_id = scope_id
            if self._single_profile_enabled:
                self.group_id = scope_id
        
        client = self._get_client()
        if not client:
            return []
        
        job_ids = []
        
        # Determine scope for payload
        payload_scope = self.scope_id if self._single_profile_enabled else self.group_id
        
        for claim in claims:
            # Create episode for each claim
            episode_body = f"""Claim: {claim.text}

Type: {claim.claim_type}
Confidence: {claim.confidence}
Extracted from: {claim.source_type}
"""
            
            # Use new idempotency key format with scope
            idempotency_key = self._make_idempotency_key(claim.claim_id)
            
            if async_write:
                # Submit to outbox
                job_id = client.outbox.submit(
                    tenant_id=self.tenant_id,
                    twin_id=self.twin_id or "default",
                    operation='create_claims',  # Will be handled by worker
                    idempotency_key=idempotency_key,
                    payload={
                        "claim_id": claim.claim_id,
                        "text": claim.text,
                        "claim_type": claim.claim_type,
                        "confidence": claim.confidence,
                        "source_type": claim.source_type,
                        "source_ref": claim.source_ref,
                        "content_hash": claim.content_hash,
                        "group_id": self.group_id,
                        "scope_id": self.scope_id,  # Include scope_id for single-profile mode
                        "creator_id": self.creator_id
                    },
                    correlation_id=self.correlation_id
                )
                job_ids.append(job_id)
            else:
                # Synchronous - create directly
                # This would call Graphiti to create entity/edge
                # For now, queue it
                job_id = client.outbox.submit(
                    tenant_id=self.tenant_id,
                    twin_id=self.twin_id or "default",
                    operation='create_claims',
                    idempotency_key=idempotency_key,
                    payload={
                        "claim_id": claim.claim_id,
                        "text": claim.text,
                        "claim_type": claim.claim_type,
                        "confidence": claim.confidence,
                        "source_type": claim.source_type,
                        "source_ref": claim.source_ref,
                        "content_hash": claim.content_hash,
                        "group_id": self.group_id,
                        "scope_id": self.scope_id,  # Include scope_id for single-profile mode
                        "creator_id": self.creator_id
                    },
                    correlation_id=self.correlation_id
                )
                job_ids.append(job_id)
        
        return job_ids


async def extract_claims(
    text: str,
    source_type: str,
    source_ref: str,
    tenant_id: str,
    twin_id: Optional[str] = None,
    scope_id: Optional[str] = None,
    creator_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> List[ExtractedClaim]:
    """
    Standalone function to extract claims from text.
    Supports both legacy twin-scoped mode and new single-profile scope mode.
    
    Args:
        text: Text to extract claims from
        source_type: Type of source (escalation_resolution, interview, etc)
        source_ref: Reference ID
        tenant_id: Tenant ID
        twin_id: Twin ID (legacy mode, optional if scope_id provided)
        scope_id: Scope ID in format "{tenant_id}__{creator_id}" (single-profile mode)
        creator_id: Creator ID (optional, for single-profile mode)
        context: Optional context (question, metadata, etc)
        correlation_id: For tracing
        
    Returns:
        List of extracted claims
    """
    extractor = GraphClaimExtractor(
        tenant_id=tenant_id,
        twin_id=twin_id,
        scope_id=scope_id,
        creator_id=creator_id,
        correlation_id=correlation_id
    )
    
    return await extractor.extract_claims(
        text=text,
        source_type=source_type,
        source_ref=source_ref,
        context=context,
        scope_id=scope_id
    )


async def process_extract_claims_job(
    tenant_id: str,
    twin_id: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> bool:
    """
    Process a claim extraction outbox job.
    Called by the background worker.
    
    Args:
        tenant_id: Tenant ID
        twin_id: Twin ID
        payload: Job payload with text, source_type, source_ref, context
        correlation_id: For tracing
        
    Returns:
        True if successful
    """
    try:
        # Support both legacy and single-profile modes
        scope_id = payload.get('scope_id')
        creator_id = payload.get('creator_id')
        
        extractor = GraphClaimExtractor(
            tenant_id=tenant_id,
            twin_id=twin_id,
            scope_id=scope_id,
            creator_id=creator_id,
            correlation_id=correlation_id
        )
        
        text = payload.get('text', '')
        source_type = payload.get('source_type', 'unknown')
        source_ref = payload.get('source_ref', 'unknown')
        context = payload.get('context', {})
        
        # Extract claims
        claims = await extractor.extract_claims(
            text=text,
            source_type=source_type,
            source_ref=source_ref,
            context=context,
            scope_id=scope_id
        )
        
        if claims:
            # Store in graph (async via outbox)
            await extractor.store_claims(claims, async_write=True, scope_id=scope_id)
            
        return True
        
    except Exception as e:
        # Log error and return False to trigger retry
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[GraphClaimExtractor] Failed to process job: {e}")
        return False
