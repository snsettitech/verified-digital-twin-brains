"""
Person Completeness Pipeline - Stage 5: Style Profile Builder
"""

import logging
from typing import Optional
from dataclasses import dataclass

from modules.observability import supabase
from modules.person_completeness_config import StyleProfileConfig

logger = logging.getLogger(__name__)


@dataclass
class StyleProfileResult:
    success: bool
    profile_version: int = 0
    confidence: float = 0.0
    error_message: Optional[str] = None

    @property
    def item_count(self) -> int:
        """Compatibility count for pipeline metrics."""
        return 1 if self.profile_version > 0 else 0


class StyleProfileBuilder:
    """Builds style profile from first-party content."""
    
    def __init__(self, config: Optional[StyleProfileConfig] = None):
        self.config = config or StyleProfileConfig()
    
    async def run(self, twin_id: str, research_run_id: Optional[str] = None) -> StyleProfileResult:
        try:
            logger.info(f"Building style profile for twin {twin_id}")
            
            # Get first-party evidence spans
            spans = await self._get_first_party_spans(twin_id)
            
            if len(spans) < 3:
                logger.info(f"Insufficient first-party content for style profile")
                return StyleProfileResult(success=True, confidence=0.0)
            
            # Combine text for analysis
            combined_text = " ".join([s.get("evidence_text", "") for s in spans[:20]])
            
            if len(combined_text) < self.config.min_content_chars:
                return StyleProfileResult(success=True, confidence=0.0)
            
            # Simple heuristic analysis (can be enhanced with LLM)
            tone_descriptors = self._analyze_tone(combined_text)
            sentence_profile = self._analyze_sentences(combined_text)
            
            # Get next version
            version = await self._get_next_version(twin_id)
            
            # Deactivate old version
            await self._deactivate_old_version(twin_id)
            
            # Create new profile
            await self._create_profile(twin_id, version, tone_descriptors, 
                                      sentence_profile, len(spans))
            
            confidence = min(0.9, 0.3 + (len(spans) * 0.05))
            
            logger.info(f"Style profile built: version {version}, confidence {confidence:.2f}")
            return StyleProfileResult(success=True, profile_version=version, confidence=confidence)
        
        except Exception as e:
            logger.exception(f"Error building style profile: {e}")
            return StyleProfileResult(success=False, error_message=str(e))
    
    async def _get_first_party_spans(self, twin_id: str) -> list:
        try:
            claim_ids = [c["id"] for c in supabase.table("person_claims")
                        .select("id").eq("twin_id", twin_id).eq("is_active", True).execute().data or []]
            if not claim_ids:
                return []

            spans = []
            chunk_size = 100
            for i in range(0, len(claim_ids), chunk_size):
                chunk = claim_ids[i:i + chunk_size]
                response = supabase.table("person_claim_evidence_spans") \
                    .select("evidence_text") \
                    .in_("claim_id", chunk) \
                    .eq("source_party", "first_party") \
                    .execute()
                spans.extend(response.data or [])

            return spans
        except Exception as e:
            logger.error(f"Error fetching spans: {e}")
            return []
    
    def _analyze_tone(self, text: str) -> list:
        """Simple tone analysis."""
        tones = []
        text_lower = text.lower()
        
        # Check for markers
        if any(w in text_lower for w in ["i think", "perhaps", "maybe"]):
            tones.append("tentative")
        if any(w in text_lower for w in ["definitely", "always", "never", "must"]):
            tones.append("authoritative")
        if any(w in text_lower for w in ["love", "excited", "amazing", "great"]):
            tones.append("enthusiastic")
        if any(w in text_lower for w in ["we", "our", "team", "together"]):
            tones.append("collaborative")
        
        if not tones:
            tones.append("professional")
        
        return tones
    
    def _analyze_sentences(self, text: str) -> dict:
        """Analyze sentence structure."""
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if not sentences:
            return {}
        
        lengths = [len(s.split()) for s in sentences]
        avg_length = sum(lengths) / len(lengths)
        
        short_pct = sum(1 for l in lengths if l < 10) / len(lengths) * 100
        medium_pct = sum(1 for l in lengths if 10 <= l < 25) / len(lengths) * 100
        long_pct = sum(1 for l in lengths if l >= 25) / len(lengths) * 100
        
        return {
            "average_length": round(avg_length, 1),
            "short_pct": round(short_pct, 1),
            "medium_pct": round(medium_pct, 1),
            "long_pct": round(long_pct, 1),
        }
    
    async def _get_next_version(self, twin_id: str) -> int:
        try:
            response = supabase.table("person_style_profile") \
                .select("version") \
                .eq("twin_id", twin_id) \
                .order("version", desc=True) \
                .limit(1) \
                .execute()
            return (response.data[0]["version"] + 1) if response.data else 1
        except Exception:
            return 1
    
    async def _deactivate_old_version(self, twin_id: str):
        try:
            supabase.table("person_style_profile") \
                .update({"is_active_version": False}) \
                .eq("twin_id", twin_id) \
                .eq("is_active_version", True) \
                .execute()
        except Exception:
            pass
    
    async def _create_profile(self, twin_id: str, version: int, tones: list, 
                             sentence_profile: dict, source_count: int):
        data = {
            "twin_id": twin_id,
            "version": version,
            "is_active_version": True,
            "tone_descriptors": tones,
            "sentence_length_profile": sentence_profile,
            "style_confidence": min(0.9, 0.3 + (source_count * 0.05)),
            "generated_from_sources_count": source_count,
        }
        supabase.table("person_style_profile").insert(data).execute()
