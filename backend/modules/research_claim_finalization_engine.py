"""
Research Claim Finalization Engine (Phase 10)

Deterministic rule-based claim finalization.
Combines Phase 8 local verification + Phase 9 web verification into final decisions.

Usage:
    engine = FinalizationEngine()
    decision = engine.finalize_claim(
        claim=claim,
        local_status=VerificationStatus.SUPPORTED,
        local_confidence=0.9,
        web_status=WebVerificationStatus.SUPPORTED,
        web_confidence=0.8
    )
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from modules.research_claim_extractor import ResearchClaim, VerificationStatus
from modules.research_claim_web_verifier import WebVerificationStatus

logger = logging.getLogger(__name__)


class FinalClaimStatus(str, Enum):
    """Final claim statuses for Phase 10."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    UNRESOLVED = "unresolved"
    OVERRIDDEN = "overridden"  # Manual override applied


@dataclass
class FinalizationDecision:
    """Result of finalization for a single claim."""
    final_status: FinalClaimStatus
    final_confidence: float
    reason_codes: List[str] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "final_status": self.final_status.value,
            "final_confidence": self.final_confidence,
            "reason_codes": self.reason_codes,
            "notes": self.notes,
        }


class FinalizationEngine:
    """
    Deterministic rule-based claim finalization engine.
    
    Rules (applied in priority order):
    1. Strong Agreement: local=supported AND web=supported -> accepted
    2. Strong Conflict: local=conflicting OR web=conflicting -> rejected
    3. Needs Review Flag: local=needs_review OR web=needs_review -> needs_review
    4. Single Source Success: web=None AND local=supported -> accepted (note: "local only")
    5. Status Mismatch: local != web (neither None) -> needs_review (note: "verification conflict")
    6. Insufficient Evidence: local=insufficient AND web in [None, insufficient] -> rejected
    7. Default: -> unresolved
    """
    
    def __init__(self):
        """Initialize the finalization engine."""
        self.rules_applied = 0
    
    def finalize_claim(
        self,
        claim: ResearchClaim,
        local_status: VerificationStatus,
        local_confidence: float,
        web_status: Optional[WebVerificationStatus],
        web_confidence: float,
    ) -> FinalizationDecision:
        """
        Apply finalization rules to determine final status.
        
        Args:
            claim: The claim being finalized
            local_status: Phase 8 local verification status
            local_confidence: Phase 8 local confidence (0.0-1.0)
            web_status: Phase 9 web verification status (None if not run)
            web_confidence: Phase 9 web confidence (0.0-1.0)
            
        Returns:
            FinalizationDecision with status, confidence, and reason codes
        """
        # Normalize web status
        web = web_status  # May be None
        local = local_status
        
        # Rule 1: Strong Agreement - both sources agree on support
        if (local == VerificationStatus.SUPPORTED and 
            web == WebVerificationStatus.SUPPORTED):
            confidence = self._calculate_confidence(local_confidence, web_confidence)
            return FinalizationDecision(
                final_status=FinalClaimStatus.ACCEPTED,
                final_confidence=confidence,
                reason_codes=["rule_1_strong_agreement", "both_supported"],
                notes="Both local and web verification support this claim"
            )
        
        # Rule 2: Strong Conflict - either source reports conflict
        if (local == VerificationStatus.CONFLICTING or 
            web == WebVerificationStatus.CONFLICTING):
            confidence = self._calculate_confidence(local_confidence, web_confidence)
            return FinalizationDecision(
                final_status=FinalClaimStatus.REJECTED,
                final_confidence=confidence,
                reason_codes=["rule_2_strong_conflict", "conflicting_evidence"],
                notes="Conflicting evidence found in local or web verification"
            )
        
        # Rule 3: Needs Review Flag - either source flagged for review
        if (local == VerificationStatus.NEEDS_REVIEW or 
            web == WebVerificationStatus.NEEDS_REVIEW):
            confidence = self._calculate_confidence(local_confidence, web_confidence)
            return FinalizationDecision(
                final_status=FinalClaimStatus.NEEDS_REVIEW,
                final_confidence=confidence,
                reason_codes=["rule_3_needs_review_flag", "manual_review_required"],
                notes="Claim flagged for manual review by verification system"
            )
        
        # Rule 4: Single Source Success - web not run, local supports
        if web is None and local == VerificationStatus.SUPPORTED:
            confidence = local_confidence * 0.9  # Slight penalty for no web verification
            return FinalizationDecision(
                final_status=FinalClaimStatus.ACCEPTED,
                final_confidence=confidence,
                reason_codes=["rule_4_single_source_success", "local_only"],
                notes="Accepted based on local verification only (web verification not run)"
            )
        
        # Rule 5: Status Mismatch - sources disagree (neither is None)
        if web is not None and not self._statuses_compatible(local, web):
            confidence = self._calculate_confidence(local_confidence, web_confidence)
            return FinalizationDecision(
                final_status=FinalClaimStatus.NEEDS_REVIEW,
                final_confidence=confidence,
                reason_codes=["rule_5_status_mismatch", "verification_conflict"],
                notes=f"Local ({local.value}) and web ({web.value}) verifications disagree"
            )
        
        # Rule 6: Insufficient Evidence - both sources lack evidence
        if (local == VerificationStatus.INSUFFICIENT_EVIDENCE and 
            (web is None or web == WebVerificationStatus.INSUFFICIENT_EVIDENCE)):
            confidence = 0.3
            return FinalizationDecision(
                final_status=FinalClaimStatus.REJECTED,
                final_confidence=confidence,
                reason_codes=["rule_6_insufficient_evidence", "no_supporting_evidence"],
                notes="No sufficient evidence found in local or web verification"
            )
        
        # Rule 7: Default - unresolved
        confidence = self._calculate_confidence(local_confidence, web_confidence)
        return FinalizationDecision(
            final_status=FinalClaimStatus.UNRESOLVED,
            final_confidence=confidence,
            reason_codes=["rule_7_default_unresolved"],
            notes=f"Could not determine final status from local ({local.value}) and web ({web.value if web else 'N/A'})"
        )
    
    def _statuses_compatible(
        self,
        local: VerificationStatus,
        web: WebVerificationStatus
    ) -> bool:
        """
        Check if local and web statuses are compatible (not contradictory).
        
        Returns:
            True if statuses are compatible
        """
        # Map to simplified categories
        local_cat = self._categorize_local_status(local)
        web_cat = self._categorize_web_status(web)
        
        # Same category = compatible
        if local_cat == web_cat:
            return True
        
        # Both pending/neutral = compatible
        if local_cat in ("pending", "neutral") and web_cat in ("pending", "neutral"):
            return True
        
        # One positive and one pending = compatible (incomplete)
        if local_cat == "positive" and web_cat in ("pending", "neutral"):
            return True
        if web_cat == "positive" and local_cat in ("pending", "neutral"):
            return True
        
        # Conflicting categories
        if local_cat == "positive" and web_cat == "negative":
            return False
        if local_cat == "negative" and web_cat == "positive":
            return False
        
        return True
    
    def _categorize_local_status(self, status: VerificationStatus) -> str:
        """Categorize local status into positive/negative/pending/neutral."""
        mapping = {
            VerificationStatus.SUPPORTED: "positive",
            VerificationStatus.CONFLICTING: "negative",
            VerificationStatus.INSUFFICIENT_EVIDENCE: "negative",
            VerificationStatus.NEEDS_REVIEW: "needs_review",
            VerificationStatus.PENDING: "pending",
        }
        return mapping.get(status, "neutral")
    
    def _categorize_web_status(self, status: WebVerificationStatus) -> str:
        """Categorize web status into positive/negative/pending/neutral."""
        mapping = {
            WebVerificationStatus.SUPPORTED: "positive",
            WebVerificationStatus.CONFLICTING: "negative",
            WebVerificationStatus.INSUFFICIENT_EVIDENCE: "negative",
            WebVerificationStatus.NEEDS_REVIEW: "needs_review",
            WebVerificationStatus.PENDING: "pending",
            WebVerificationStatus.BLOCKED: "neutral",
            WebVerificationStatus.ERROR: "neutral",
            WebVerificationStatus.SKIPPED: "neutral",
        }
        return mapping.get(status, "neutral")
    
    def _calculate_confidence(
        self,
        local_confidence: float,
        web_confidence: float
    ) -> float:
        """
        Calculate final confidence from local and web confidences.
        
        Both available: average
        Local only: local * 0.9
        """
        if web_confidence > 0:
            return (local_confidence + web_confidence) / 2
        else:
            return local_confidence * 0.9


# =============================================================================
# Convenience Functions
# =============================================================================

def finalize_claim(
    claim: ResearchClaim,
    local_status: VerificationStatus,
    local_confidence: float,
    web_status: Optional[WebVerificationStatus] = None,
    web_confidence: float = 0.0,
) -> FinalizationDecision:
    """
    Convenience function to finalize a single claim.
    
    Args:
        claim: The claim to finalize
        local_status: Phase 8 local verification status
        local_confidence: Phase 8 local confidence
        web_status: Phase 9 web verification status (optional)
        web_confidence: Phase 9 web confidence
        
    Returns:
        FinalizationDecision
    """
    engine = FinalizationEngine()
    return engine.finalize_claim(
        claim=claim,
        local_status=local_status,
        local_confidence=local_confidence,
        web_status=web_status,
        web_confidence=web_confidence,
    )


def get_decision_explanation(decision: FinalizationDecision) -> str:
    """
    Get a human-readable explanation of a finalization decision.
    
    Args:
        decision: The finalization decision
        
    Returns:
        Human-readable explanation
    """
    status_descriptions = {
        FinalClaimStatus.ACCEPTED: "The claim has been accepted based on supporting evidence.",
        FinalClaimStatus.REJECTED: "The claim has been rejected due to insufficient or conflicting evidence.",
        FinalClaimStatus.NEEDS_REVIEW: "The claim requires manual review before a final decision can be made.",
        FinalClaimStatus.UNRESOLVED: "The claim's status could not be determined automatically.",
        FinalClaimStatus.OVERRIDDEN: "The claim's status has been manually overridden.",
    }
    
    base = status_descriptions.get(decision.final_status, "Unknown status")
    return f"{base} {decision.notes}"
