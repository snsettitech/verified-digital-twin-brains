"""
persona_bio_generator.py

Phase 4 Component: Generate grounded bios using only claims.
Every sentence must map to >=1 claim_id.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from modules.inference_router import invoke_json


# =============================================================================
# Bio Variant Types
# =============================================================================

BIO_VARIANTS = {
    "one_liner": {
        "max_length": 120,
        "style": "concise professional summary",
        "format": "{name} is {role} who {specialty}.",
    },
    "short": {
        "max_length": 300,
        "style": "brief bio for profiles",
        "format": "2-3 sentences",
    },
    "linkedin_about": {
        "max_length": 2000,
        "style": "LinkedIn About section",
        "format": "First person, professional tone",
    },
    "speaker_intro": {
        "max_length": 500,
        "style": "Conference speaker introduction",
        "format": "Third person, highlights expertise",
    },
    "full": {
        "max_length": 1000,
        "style": "Comprehensive bio",
        "format": "Multi-paragraph",
    },
}


# =============================================================================
# Bio Citation
# =============================================================================

@dataclass
class BioCitation:
    """Citation for a sentence in a bio."""
    sentence_index: int
    sentence_text: str
    claim_ids: List[str]


@dataclass
class BioVariant:
    """Generated bio variant with citations."""
    bio_type: str
    bio_text: str
    citations: List[BioCitation]
    validation_status: str  # valid, invalid_uncited, insufficient_data
    uncited_sentences: List[int]
    generated_at: datetime


# =============================================================================
# Bio Generation Prompts
# =============================================================================

BIO_GENERATION_PROMPT = """You are a professional bio writer for a Digital Twin.

TASK: Write a {bio_type} bio using ONLY the provided claims as source material.

BIO TYPE: {bio_type}
STYLE: {style}
MAX LENGTH: {max_length} characters

CLAIMS:
{claims_text}

TWIN NAME: {twin_name}

RULES:
1. EVERY sentence must be directly supported by at least one claim
2. Do NOT add information not present in claims
3. Do NOT make assumptions or inferences beyond the claims
4. If insufficient claims, state "INSUFFICIENT_DATA"
5. Keep sentences atomic (one idea per sentence)

OUTPUT FORMAT:
{
  "bio_text": "The generated bio text...",
  "sentences": [
    {
      "text": "Individual sentence",
      "supporting_claim_indices": [0, 2]  // Indices into claims list
    }
  ],
  "insufficient_data": false,
  "missing_claim_types": []
}

If you cannot write a complete bio due to missing claims, set insufficient_data=true and list what's needed.
"""


# =============================================================================
# Bio Validator
# =============================================================================

class BioValidator:
    """Validate that every sentence in a bio cites claims."""
    
    def __init__(self, min_citation_ratio: float = 1.0):
        """
        Args:
            min_citation_ratio: Minimum ratio of sentences that must have citations
        """
        self.min_citation_ratio = min_citation_ratio
    
    def split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def validate_bio(
        self,
        bio_text: str,
        sentence_claims: List[Dict[str, Any]],
    ) -> Tuple[str, List[int]]:
        """
        Validate bio citations.
        
        Returns:
            (status, uncited_sentence_indices)
        """
        sentences = self.split_sentences(bio_text)
        uncited = []
        
        for idx, sentence in enumerate(sentences):
            # Check if this sentence has supporting claims
            matching = [
                sc for sc in sentence_claims
                if sc.get("sentence_index") == idx and sc.get("supporting_claim_indices")
            ]
            
            if not matching:
                uncited.append(idx)
        
        # Determine status
        if not sentences:
            return "insufficient_data", []
        
        cited_ratio = (len(sentences) - len(uncited)) / len(sentences)
        
        if cited_ratio >= self.min_citation_ratio:
            return "valid", []
        elif cited_ratio >= 0.5:
            return "invalid_uncited", uncited
        else:
            return "insufficient_data", uncited


# =============================================================================
# Bio Generator
# =============================================================================

class BioGenerator:
    """Generate grounded bio variants from claims."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.validator = BioValidator(min_citation_ratio=1.0)
    
    def _format_claims_for_prompt(
        self,
        claims: List[Dict[str, Any]],
        max_claims: int = 20,
    ) -> str:
        """Format claims for the generation prompt."""
        lines = []
        
        # Prioritize high-confidence, owner_direct claims
        sorted_claims = sorted(
            claims,
            key=lambda c: (
                c.get("authority") == "owner_direct",
                c.get("confidence", 0),
            ),
            reverse=True,
        )
        
        for idx, claim in enumerate(sorted_claims[:max_claims]):
            claim_type = claim.get("claim_type", "unknown")
            claim_text = claim.get("claim_text", "")
            authority = claim.get("authority", "extracted")
            
            lines.append(f"[{idx}] ({claim_type}/{authority}) {claim_text}")
        
        return "\n".join(lines)
    
    async def generate_bio_variant(
        self,
        twin_id: str,
        bio_type: str,
        claims: List[Dict[str, Any]],
        twin_name: str = "Digital Twin",
    ) -> BioVariant:
        """
        Generate a single bio variant from claims.
        
        Args:
            twin_id: Twin ID
            bio_type: Type of bio (one_liner, short, etc.)
            claims: List of claims to use as source
            twin_name: Name to use in bio
        
        Returns:
            BioVariant with citations
        """
        variant_config = BIO_VARIANTS.get(bio_type, BIO_VARIANTS["short"])
        
        # Check minimum claims
        if len(claims) < 3:
            return BioVariant(
                bio_type=bio_type,
                bio_text="",
                citations=[],
                validation_status="insufficient_data",
                uncited_sentences=[],
                generated_at=datetime.utcnow(),
            )
        
        # Format claims
        claims_text = self._format_claims_for_prompt(claims)
        
        # Build prompt
        prompt = BIO_GENERATION_PROMPT.format(
            bio_type=bio_type,
            style=variant_config["style"],
            max_length=variant_config["max_length"],
            claims_text=claims_text,
            twin_name=twin_name,
        )
        
        try:
            result, _ = await invoke_json(
                [{"role": "user", "content": prompt}],
                task="structured",
                temperature=0.3,
                max_tokens=1500,
            )
            
            # Check for insufficient data
            if result.get("insufficient_data"):
                missing_types = result.get("missing_claim_types", [])
                return BioVariant(
                    bio_type=bio_type,
                    bio_text="",
                    citations=[],
                    validation_status="insufficient_data",
                    uncited_sentences=[],
                    generated_at=datetime.utcnow(),
                )
            
            bio_text = result.get("bio_text", "")
            sentences_data = result.get("sentences", [])
            
            # Build citations
            citations = []
            for sent_data in sentences_data:
                citation = BioCitation(
                    sentence_index=sent_data.get("sentence_index", 0),
                    sentence_text=sent_data.get("text", ""),
                    claim_ids=[
                        claims[i].get("id") 
                        for i in sent_data.get("supporting_claim_indices", [])
                        if i < len(claims)
                    ],
                )
                citations.append(citation)
            
            # Validate
            sentence_claims = [
                {
                    "sentence_index": s.get("sentence_index", i),
                    "supporting_claim_indices": s.get("supporting_claim_indices", []),
                }
                for i, s in enumerate(sentences_data)
            ]
            
            status, uncited = self.validator.validate_bio(bio_text, sentence_claims)
            
            return BioVariant(
                bio_type=bio_type,
                bio_text=bio_text,
                citations=citations,
                validation_status=status,
                uncited_sentences=uncited,
                generated_at=datetime.utcnow(),
            )
            
        except Exception as e:
            print(f"[BioGenerator] Generation failed: {e}")
            return BioVariant(
                bio_type=bio_type,
                bio_text="",
                citations=[],
                validation_status="insufficient_data",
                uncited_sentences=[],
                generated_at=datetime.utcnow(),
            )
    
    async def generate_all_variants(
        self,
        twin_id: str,
        claims: List[Dict[str, Any]],
        twin_name: str = "Digital Twin",
    ) -> Dict[str, BioVariant]:
        """
        Generate all bio variants.
        
        Returns:
            Dict mapping bio_type to BioVariant
        """
        results = {}
        
        for bio_type in BIO_VARIANTS.keys():
            variant = await self.generate_bio_variant(
                twin_id=twin_id,
                bio_type=bio_type,
                claims=claims,
                twin_name=twin_name,
            )
            results[bio_type] = variant
        
        return results


# =============================================================================
# Storage
# =============================================================================

async def store_bio_variants(
    twin_id: str,
    variants: Dict[str, BioVariant],
    supabase_client,
) -> List[str]:
    """
    Store generated bio variants to database.
    
    Returns:
        List of stored variant IDs
    """
    stored_ids = []
    
    for bio_type, variant in variants.items():
        data = {
            "twin_id": twin_id,
            "bio_type": bio_type,
            "bio_text": variant.bio_text,
            "citations": [
                {
                    "sentence_index": c.sentence_index,
                    "claim_ids": c.claim_ids,
                }
                for c in variant.citations
            ],
            "validation_status": variant.validation_status,
            "uncited_sentences": variant.uncited_sentences,
        }
        
        try:
            result = supabase_client.table("persona_bio_variants").insert(data).execute()
            if result.data:
                stored_ids.append(result.data[0]["id"])
        except Exception as e:
            print(f"[BioStorage] Failed to store {bio_type}: {e}")
    
    return stored_ids


# =============================================================================
# Main Interface
# =============================================================================

async def generate_and_store_bios(
    twin_id: str,
    claims: List[Dict[str, Any]],
    supabase_client,
    twin_name: str = "Digital Twin",
) -> Dict[str, Any]:
    """
    Main entry point: generate and store all bio variants.
    
    Returns:
        {
            "generated_count": int,
            "valid_count": int,
            "variant_ids": List[str],
            "variants": Dict[str, BioVariant],
        }
    """
    generator = BioGenerator()
    
    # Generate all variants
    variants = await generator.generate_all_variants(
        twin_id=twin_id,
        claims=claims,
        twin_name=twin_name,
    )
    
    # Count valid
    valid_count = sum(
        1 for v in variants.values() 
        if v.validation_status == "valid"
    )
    
    # Store
    variant_ids = await store_bio_variants(twin_id, variants, supabase_client)
    
    return {
        "generated_count": len(variants),
        "valid_count": valid_count,
        "variant_ids": variant_ids,
        "variants": variants,
    }
