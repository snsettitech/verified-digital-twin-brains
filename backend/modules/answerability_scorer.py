"""
Person Completeness Pipeline - Stage 7: Answerability Scorer
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from modules.observability import supabase
from modules.person_completeness_config import AnswerabilityScoringConfig

logger = logging.getLogger(__name__)


@dataclass
class AnswerabilityResult:
    success: bool
    scores_computed: int = 0
    error_message: Optional[str] = None

    @property
    def item_count(self) -> int:
        """Compatibility count for pipeline metrics."""
        return self.scores_computed


class AnswerabilityScorer:
    """Computes answerability scores for topics and global scope."""
    
    def __init__(self, config: Optional[AnswerabilityScoringConfig] = None):
        self.config = config or AnswerabilityScoringConfig()
    
    async def run(self, twin_id: str, research_run_id: Optional[str] = None) -> AnswerabilityResult:
        try:
            logger.info(f"Computing answerability scores for twin {twin_id}")
            
            scores_computed = 0
            
            # Compute global score
            if self.config.enable_global_score:
                global_score = await self._compute_global_score(twin_id)
                await self._store_score(twin_id, "global", "global", global_score)
                scores_computed += 1
            
            # Compute topic scores
            if self.config.enable_topic_scores:
                topics = await self._get_topics(twin_id)
                for topic in topics:
                    score = await self._compute_topic_score(twin_id, topic)
                    await self._store_score(twin_id, "topic", topic["topic_slug"], score)
                    scores_computed += 1
            
            logger.info(f"Answerability scoring complete: {scores_computed} scores")
            return AnswerabilityResult(success=True, scores_computed=scores_computed)
        
        except Exception as e:
            logger.exception(f"Error computing answerability: {e}")
            return AnswerabilityResult(success=False, error_message=str(e))
    
    async def _compute_global_score(self, twin_id: str) -> Dict[str, Any]:
        """Compute global answerability score."""
        # Get metrics
        source_count = await self._count_sources(twin_id)
        claim_count = await self._count_claims(twin_id)
        verified_claims = await self._count_verified_claims(twin_id)
        contradiction_count = await self._count_contradictions(twin_id)
        
        # Calculate component scores (0-100)
        coverage = min(100, source_count * 10 + claim_count * 2)
        verification = int((verified_claims / claim_count * 100) if claim_count > 0 else 0)
        consistency = max(0, 100 - (contradiction_count * 20))
        recency = 75  # Placeholder - would calculate from source dates
        style_fidelity = 70  # Placeholder
        
        # Composite score
        answerability = int(
            coverage * 0.25 +
            verification * 0.25 +
            recency * 0.20 +
            consistency * 0.20 +
            style_fidelity * 0.10
        )
        
        return {
            "coverage": coverage,
            "verification": verification,
            "recency": recency,
            "consistency": consistency,
            "style_fidelity": style_fidelity,
            "answerability": answerability,
            "explanation": {
                "coverage_reason": f"{source_count} sources, {claim_count} claims",
                "verification_reason": f"{verified_claims} verified of {claim_count} claims",
                "consistency_reason": f"{contradiction_count} contradictions detected",
            }
        }
    
    async def _compute_topic_score(self, twin_id: str, topic: Dict) -> Dict[str, Any]:
        """Compute answerability score for a topic."""
        # Use existing topic profile scores if available
        coverage = int(topic.get("coverage_score", 0) * 100)
        verification = int(topic.get("verification_score", 0) * 100)
        recency = int(topic.get("recency_score", 0.5) * 100)
        consistency = int(topic.get("consistency_score", 0.8) * 100)
        
        answerability = int(
            coverage * 0.30 +
            verification * 0.25 +
            recency * 0.20 +
            consistency * 0.25
        )
        
        return {
            "coverage": coverage,
            "verification": verification,
            "recency": recency,
            "consistency": consistency,
            "style_fidelity": 70,  # Default
            "answerability": answerability,
            "explanation": {
                "topic": topic.get("topic_name"),
                "evidence_count": topic.get("evidence_count", 0),
            }
        }
    
    async def _store_score(self, twin_id: str, scope_type: str, scope_key: str, 
                          scores: Dict[str, Any]):
        try:
            explanation = scores.get("explanation", {})
            
            data = {
                "coverage_score": scores["coverage"],
                "verification_score": scores["verification"],
                "recency_score": scores["recency"],
                "consistency_score": scores["consistency"],
                "style_fidelity_score": scores["style_fidelity"],
                "answerability_score": scores["answerability"],
                "score_explanation_json": explanation,
                "last_computed_at": datetime.utcnow().isoformat(),
            }
            
            # Check for existing
            existing = supabase.table("person_answerability_scores") \
                .select("id") \
                .eq("twin_id", twin_id) \
                .eq("scope_type", scope_type) \
                .eq("scope_key", scope_key) \
                .execute()
            
            if existing.data:
                supabase.table("person_answerability_scores") \
                    .update(data) \
                    .eq("id", existing.data[0]["id"]) \
                    .execute()
            else:
                data["twin_id"] = twin_id
                data["scope_type"] = scope_type
                data["scope_key"] = scope_key
                supabase.table("person_answerability_scores").insert(data).execute()
        
        except Exception as e:
            logger.warning(f"Error storing score: {e}")
    
    async def _get_topics(self, twin_id: str) -> list:
        try:
            response = supabase.table("person_topic_profiles") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .execute()
            return response.data or []
        except Exception:
            return []
    
    async def _count_sources(self, twin_id: str) -> int:
        try:
            response = supabase.table("person_source_registry") \
                .select("id", count="exact") \
                .eq("twin_id", twin_id) \
                .eq("is_active", True) \
                .execute()
            return response.count or 0
        except Exception:
            return 0
    
    async def _count_claims(self, twin_id: str) -> int:
        try:
            response = supabase.table("person_claims") \
                .select("id", count="exact") \
                .eq("twin_id", twin_id) \
                .eq("is_active", True) \
                .execute()
            return response.count or 0
        except Exception:
            return 0
    
    async def _count_verified_claims(self, twin_id: str) -> int:
        try:
            response = supabase.table("person_claims") \
                .select("id", count="exact") \
                .eq("twin_id", twin_id) \
                .eq("verification_status", "verified") \
                .eq("is_active", True) \
                .execute()
            return response.count or 0
        except Exception:
            return 0
    
    async def _count_contradictions(self, twin_id: str) -> int:
        try:
            response = supabase.table("person_contradictions") \
                .select("id", count="exact") \
                .eq("twin_id", twin_id) \
                .eq("status", "open") \
                .eq("is_active", True) \
                .execute()
            return response.count or 0
        except Exception:
            return 0
