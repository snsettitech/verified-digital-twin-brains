"""
Person Completeness Pipeline - Stage 4: Topic Graph Builder
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from modules.observability import supabase
from modules.person_completeness_config import TopicGraphConfig

logger = logging.getLogger(__name__)


@dataclass
class TopicGraphResult:
    success: bool
    topics_created: int = 0
    error_message: Optional[str] = None

    @property
    def item_count(self) -> int:
        """Compatibility count for pipeline metrics."""
        return self.topics_created


class TopicGraphBuilder:
    """Builds topic profiles from claims."""
    
    def __init__(self, config: Optional[TopicGraphConfig] = None):
        self.config = config or TopicGraphConfig()
    
    async def run(self, twin_id: str, research_run_id: Optional[str] = None) -> TopicGraphResult:
        try:
            logger.info(f"Building topic graph for twin {twin_id}")
            
            # Get verified claims
            claims = await self._get_claims(twin_id)
            
            # Aggregate topics (simplified - just count by claim type for now)
            topic_counts: Dict[str, Dict] = {}
            
            for claim in claims:
                claim_type = claim.get("claim_type", "uncertain")
                
                if claim_type not in topic_counts:
                    topic_counts[claim_type] = {
                        "count": 0,
                        "first_party": 0,
                        "third_party": 0,
                        "verified": 0,
                    }
                
                topic_counts[claim_type]["count"] += 1
                
                # Get evidence spans for party detection
                spans = await self._get_evidence_spans(claim["id"])
                first_party = any(s.get("source_party") == "first_party" for s in spans)
                
                if first_party:
                    topic_counts[claim_type]["first_party"] += 1
                else:
                    topic_counts[claim_type]["third_party"] += 1
                
                if claim.get("verification_status") == "verified":
                    topic_counts[claim_type]["verified"] += 1
            
            # Create/update topic profiles
            topics_created = 0
            for topic_name, counts in topic_counts.items():
                if counts["count"] < self.config.min_evidence_count:
                    continue
                
                # Calculate scores
                coverage = min(1.0, counts["count"] / 10)
                verification = counts["verified"] / counts["count"] if counts["count"] > 0 else 0
                first_party_ratio = counts["first_party"] / counts["count"] if counts["count"] > 0 else 0
                
                # Composite answerability score
                answerability = (
                    coverage * self.config.coverage_weight +
                    verification * self.config.verification_weight +
                    first_party_ratio * 0.5  # Bonus for first-party evidence
                )
                
                await self._upsert_topic(twin_id, topic_name, counts, coverage, verification, answerability)
                topics_created += 1
            
            logger.info(f"Topic graph built: {topics_created} topics")
            return TopicGraphResult(success=True, topics_created=topics_created)
        
        except Exception as e:
            logger.exception(f"Error building topic graph: {e}")
            return TopicGraphResult(success=False, error_message=str(e))
    
    async def _get_claims(self, twin_id: str) -> List[Dict]:
        try:
            response = supabase.table("person_claims") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .eq("is_active", True) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching claims: {e}")
            return []
    
    async def _get_evidence_spans(self, claim_id: str) -> List[Dict]:
        try:
            response = supabase.table("person_claim_evidence_spans") \
                .select("source_party") \
                .eq("claim_id", claim_id) \
                .execute()
            return response.data or []
        except Exception:
            return []
    
    async def _upsert_topic(self, twin_id: str, topic_name: str, counts: Dict, 
                           coverage: float, verification: float, answerability: float):
        try:
            slug = topic_name.lower().replace(" ", "_")
            
            # Check for existing
            existing = supabase.table("person_topic_profiles") \
                .select("id") \
                .eq("twin_id", twin_id) \
                .eq("topic_slug", slug) \
                .execute()
            
            data = {
                "evidence_count": counts["count"],
                "first_party_evidence_count": counts["first_party"],
                "third_party_evidence_count": counts["third_party"],
                "coverage_score": round(coverage, 2),
                "verification_score": round(verification, 2),
                "consistency_score": 0.8,  # Placeholder
                "answerability_score": round(answerability, 2),
                "confidence_to_answer": round(answerability, 2),
                "last_computed_at": datetime.utcnow().isoformat(),
            }
            
            if existing.data:
                supabase.table("person_topic_profiles") \
                    .update(data) \
                    .eq("id", existing.data[0]["id"]) \
                    .execute()
            else:
                data["twin_id"] = twin_id
                data["topic_name"] = topic_name.replace("_", " ").title()
                data["topic_slug"] = slug
                supabase.table("person_topic_profiles").insert(data).execute()
        
        except Exception as e:
            logger.warning(f"Error upserting topic: {e}")
