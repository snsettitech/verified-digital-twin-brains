"""
Twin Readiness Checker Module (Phase 5)

Determines whether a twin is ready after onboarding research completion.

Phase 5 evaluates readiness using:
- Confirmed source count >= 1
- Bio variant exists (at least 1)
- Mind score >= threshold (configurable)
- No unresolved confirmations for the research run
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from modules.observability import supabase

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def get_min_ready_mind_score() -> int:
    """Get minimum mind score threshold for readiness (default: 30)."""
    return int(os.getenv("DR_MIN_READY_MIND_SCORE", "30"))


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ReadinessRequirements:
    """Individual readiness requirement checks."""
    has_confirmed_source: bool = False
    has_bio_variant: bool = False
    mind_score_threshold_met: bool = False
    no_pending_confirmations: bool = False


@dataclass
class ReadinessCounts:
    """Source confirmation counts for readiness evaluation."""
    confirmed: int = 0
    auto_confirmed: int = 0
    pending: int = 0
    manual_review: int = 0
    rejected: int = 0


@dataclass
class ReadinessResult:
    """Twin readiness evaluation result."""
    # Core result
    is_ready: bool = False
    status: str = "pending"  # pending, evaluated, failed
    
    # Thresholds used
    thresholds: Dict[str, int] = field(default_factory=dict)
    
    # Requirement breakdown
    requirements: ReadinessRequirements = field(default_factory=ReadinessRequirements)
    
    # Source counts
    counts: ReadinessCounts = field(default_factory=ReadinessCounts)
    
    # Metadata
    evaluated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    errors: List[str] = field(default_factory=list)


# =============================================================================
# Twin Readiness Checker
# =============================================================================

class TwinReadinessChecker:
    """
    Determine whether a twin is ready after onboarding research.
    
    Phase 5 readiness criteria:
    - At least 1 confirmed or auto_confirmed source
    - At least 1 bio variant generated/stored
    - Mind score >= threshold (default: 30)
    - No pending/manual_review confirmations for research run
    """
    
    def __init__(self, min_mind_score: Optional[int] = None):
        """
        Initialize readiness checker.
        
        Args:
            min_mind_score: Minimum mind score for readiness (default from env)
        """
        self.min_mind_score = min_mind_score or get_min_ready_mind_score()
    
    async def get_readiness_status(
        self,
        twin_id: str,
        research_run_id: Optional[str] = None,
    ) -> ReadinessResult:
        """
        Evaluate twin readiness after onboarding research.
        
        Args:
            twin_id: Twin ID to evaluate
            research_run_id: Optional specific research run to evaluate
                            If not provided, uses latest non-failed run
        
        Returns:
            ReadinessResult with detailed evaluation
        """
        try:
            # Get research run if not specified
            if not research_run_id:
                research_run_id = await self._get_latest_research_run_id(twin_id)
            
            if not research_run_id:
                return ReadinessResult(
                    is_ready=False,
                    status="failed",
                    thresholds={"min_mind_score": self.min_mind_score},
                    errors=["No research run found for twin"],
                )
            
            # Get source confirmation counts
            counts = await self._get_confirmation_counts(research_run_id, twin_id)
            
            # Get mind score from twin settings
            mind_score = await self._get_mind_score(twin_id)
            
            # Check bio variant exists
            has_bio = await self._has_bio_variant(twin_id)
            
            # Evaluate requirements
            requirements = ReadinessRequirements(
                has_confirmed_source=(counts.confirmed + counts.auto_confirmed) >= 1,
                has_bio_variant=has_bio,
                mind_score_threshold_met=mind_score >= self.min_mind_score,
                no_pending_confirmations=(counts.pending + counts.manual_review) == 0,
            )
            
            # Determine overall readiness
            is_ready = all([
                requirements.has_confirmed_source,
                requirements.has_bio_variant,
                requirements.mind_score_threshold_met,
                requirements.no_pending_confirmations,
            ])
            
            return ReadinessResult(
                is_ready=is_ready,
                status="evaluated",
                thresholds={"min_mind_score": self.min_mind_score},
                requirements=requirements,
                counts=counts,
                errors=[],
            )
            
        except Exception as e:
            logger.error(f"Phase 5: Error evaluating readiness for twin {twin_id}: {e}")
            return ReadinessResult(
                is_ready=False,
                status="failed",
                thresholds={"min_mind_score": self.min_mind_score},
                errors=[str(e)],
            )
    
    async def _get_latest_research_run_id(
        self,
        twin_id: str,
    ) -> Optional[str]:
        """
        Get the latest non-failed research run ID for a twin.
        
        Selection rule:
        1. Latest by created_at
        2. Exclude failed status
        3. Prefer completed/bio_generated states
        
        Args:
            twin_id: Twin ID
            
        Returns:
            Research run ID or None
        """
        try:
            # Query latest non-failed research run
            response = supabase.table("research_runs").select(
                "id, status, created_at"
            ).eq("twin_id", twin_id).not_.eq("status", "failed").order(
                "created_at", desc=True
            ).limit(1).execute()
            
            if response.data:
                return response.data[0]["id"]
            
            return None
            
        except Exception as e:
            logger.error(f"Phase 5: Error getting latest research run: {e}")
            return None
    
    async def _get_confirmation_counts(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> ReadinessCounts:
        """
        Get source confirmation counts for a research run.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
            
        Returns:
            ReadinessCounts with breakdown by status
        """
        try:
            # Query counts by status
            response = supabase.table("source_confirmations").select(
                "status"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            if not response.data:
                return ReadinessCounts()
            
            # Count by status
            counts = ReadinessCounts()
            for row in response.data:
                status = row.get("status", "")
                if status == "confirmed":
                    counts.confirmed += 1
                elif status == "auto_confirmed":
                    counts.auto_confirmed += 1
                elif status == "pending":
                    counts.pending += 1
                elif status == "manual_review":
                    counts.manual_review += 1
                elif status == "rejected":
                    counts.rejected += 1
                elif status == "auto_rejected":
                    counts.rejected += 1  # Count auto_rejected as rejected
            
            return counts
            
        except Exception as e:
            logger.error(f"Phase 5: Error getting confirmation counts: {e}")
            return ReadinessCounts()
    
    async def _get_mind_score(self, twin_id: str) -> int:
        """
        Get current mind score from twin settings.
        
        Args:
            twin_id: Twin ID
            
        Returns:
            Mind score (0-100) or 0 if not found
        """
        try:
            response = supabase.table("twins").select(
                "settings"
            ).eq("id", twin_id).single().execute()
            
            if not response.data:
                return 0
            
            settings = response.data.get("settings") or {}
            training_metrics = settings.get("training_metrics", {})
            
            return training_metrics.get("mind_score", 0)
            
        except Exception as e:
            logger.error(f"Phase 5: Error getting mind score: {e}")
            return 0
    
    async def _has_bio_variant(self, twin_id: str) -> bool:
        """
        Check if twin has at least one bio variant.
        
        Args:
            twin_id: Twin ID
            
        Returns:
            True if bio variant exists
        """
        try:
            # Check for bio variants in the bios table
            # This is the table used by persona_bio_generator
            response = supabase.table("bios").select(
                "id"
            ).eq("twin_id", twin_id).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                return True
            
            # Fallback: Check twin profile for bio
            response = supabase.table("twins").select(
                "profile"
            ).eq("id", twin_id).single().execute()
            
            if response.data:
                profile = response.data.get("profile") or {}
                # Check various bio fields
                if profile.get("bio") or profile.get("generated_bio"):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Phase 5: Error checking bio variant: {e}")
            return False


# =============================================================================
# Convenience Functions
# =============================================================================

async def check_twin_readiness(
    twin_id: str,
    research_run_id: Optional[str] = None,
    min_mind_score: Optional[int] = None,
) -> ReadinessResult:
    """
    Convenience function to check twin readiness.
    
    Args:
        twin_id: Twin ID
        research_run_id: Optional specific research run
        min_mind_score: Optional threshold override
        
    Returns:
        ReadinessResult
    """
    checker = TwinReadinessChecker(min_mind_score=min_mind_score)
    return await checker.get_readiness_status(twin_id, research_run_id)
