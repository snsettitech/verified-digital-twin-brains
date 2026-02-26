"""
Person Completeness Pipeline - Stage 6: Contradiction Detector
"""

import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

from modules.observability import supabase
from modules.person_completeness_config import ContradictionDetectionConfig

logger = logging.getLogger(__name__)


@dataclass
class ContradictionResult:
    success: bool
    contradictions_found: int = 0
    error_message: Optional[str] = None

    @property
    def item_count(self) -> int:
        """Compatibility count for pipeline metrics."""
        return self.contradictions_found


class ContradictionDetector:
    """Detects contradictions between claims."""
    
    def __init__(self, config: Optional[ContradictionDetectionConfig] = None):
        self.config = config or ContradictionDetectionConfig()
    
    async def run(self, twin_id: str, research_run_id: Optional[str] = None) -> ContradictionResult:
        try:
            logger.info(f"Detecting contradictions for twin {twin_id}")
            
            contradictions_found = 0
            
            # Get claims for analysis
            claims = await self._get_claims(twin_id)
            
            # Check for timeline conflicts
            if self.config.enable_timeline_conflicts:
                timeline_contra = await self._check_timeline_conflicts(twin_id, claims)
                contradictions_found += timeline_contra
            
            # Check for role conflicts
            if self.config.enable_role_conflicts:
                role_contra = await self._check_role_conflicts(twin_id, claims)
                contradictions_found += role_contra
            
            # Check for factual conflicts
            if self.config.enable_factual_conflicts:
                factual_contra = await self._check_factual_conflicts(twin_id, claims)
                contradictions_found += factual_contra
            
            logger.info(f"Contradiction detection complete: {contradictions_found} found")
            return ContradictionResult(success=True, contradictions_found=contradictions_found)
        
        except Exception as e:
            logger.exception(f"Error detecting contradictions: {e}")
            return ContradictionResult(success=False, error_message=str(e))
    
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
    
    async def _check_timeline_conflicts(self, twin_id: str, claims: List[Dict]) -> int:
        """Check for timeline overlap conflicts."""
        found = 0
        
        # Get timeline events
        events_response = supabase.table("person_timeline_events") \
            .select("*") \
            .eq("twin_id", twin_id) \
            .eq("is_active", True) \
            .execute()
        
        events = events_response.data or []
        
        # Check for overlapping jobs at same organization
        org_events: Dict[str, List[Dict]] = {}
        for event in events:
            org = event.get("organization")
            if org:
                if org not in org_events:
                    org_events[org] = []
                org_events[org].append(event)
        
        for org, org_evts in org_events.items():
            if len(org_evts) < 2:
                continue
            
            # Check for same start date (simplified)
            for i, evt1 in enumerate(org_evts):
                for evt2 in org_evts[i+1:]:
                    if evt1.get("start_date") == evt2.get("start_date"):
                        claim_id_a = self._extract_primary_claim_id(evt1)
                        claim_id_b = self._extract_primary_claim_id(evt2)
                        if not claim_id_a or not claim_id_b:
                            continue
                        if claim_id_a == claim_id_b:
                            continue
                        await self._store_contradiction(
                            twin_id, claim_id_a, claim_id_b,
                            "timeline_conflict", "medium",
                            f"Overlapping timeline events at {org}"
                        )
                        found += 1
        
        return found
    
    async def _check_role_conflicts(self, twin_id: str, claims: List[Dict]) -> int:
        """Check for mutually exclusive role claims."""
        found = 0
        
        # Find claims about current roles
        role_claims = [c for c in claims if c.get("claim_type") == "work_experience" 
                       and c.get("tense_status") == "active"]
        
        # Simple check: multiple "current" roles at different orgs
        orgs = set()
        for claim in role_claims:
            # Extract org from claim text (simplified)
            text = claim.get("claim_text", "")
            if " at " in text:
                org = text.split(" at ")[-1].split()[0]
                if org in orgs:
                    # This is a simplified check - real implementation would be more nuanced
                    pass
                orgs.add(org)
        
        return found
    
    async def _check_factual_conflicts(self, twin_id: str, claims: List[Dict]) -> int:
        """Check for conflicting factual claims."""
        # Simplified implementation
        # Real implementation would use embeddings to find semantically similar but contradictory claims
        return 0

    def _extract_primary_claim_id(self, event: Dict) -> Optional[str]:
        """Pull one originating claim id from a timeline event."""
        claim_ids = event.get("derived_from_claim_ids")
        if isinstance(claim_ids, list) and claim_ids:
            first = claim_ids[0]
            if first:
                return str(first)
        return None
    
    async def _store_contradiction(self, twin_id: str, claim_id_a: str, claim_id_b: str,
                                   contra_type: str, severity: str, description: str):
        try:
            # Canonical ordering avoids duplicate A/B and B/A rows.
            pair = sorted([str(claim_id_a), str(claim_id_b)])
            claim_id_a, claim_id_b = pair[0], pair[1]

            # Check if already exists
            existing = supabase.table("person_contradictions") \
                .select("id") \
                .eq("twin_id", twin_id) \
                .eq("claim_id_a", claim_id_a) \
                .eq("claim_id_b", claim_id_b) \
                .execute()
            
            if existing.data:
                return
            
            data = {
                "twin_id": twin_id,
                "contradiction_type": contra_type,
                "claim_id_a": claim_id_a,
                "claim_id_b": claim_id_b,
                "severity": severity,
                "status": "open",
                "detection_confidence": self.config.min_confidence_for_detection,
                "metadata_json": {"description": description},
            }
            
            supabase.table("person_contradictions").insert(data).execute()
        except Exception as e:
            logger.warning(f"Error storing contradiction: {e}")
