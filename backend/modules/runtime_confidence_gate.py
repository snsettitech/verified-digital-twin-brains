"""
Runtime Confidence Gate

Integrates person completeness scores into runtime answering.
Features:
- Answerability score checking
- Confidence threshold gating
- Fallback message generation
- Contradiction awareness
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from modules.observability import supabase

logger = logging.getLogger(__name__)


class GateDecision(str, Enum):
    """Gate decisions for answering."""
    ALLOW = "allow"
    PARTIAL = "partial"  # Allow but reduce confidence
    BLOCK = "block"


@dataclass
class ConfidenceGateResult:
    """Result of confidence gate check."""
    decision: GateDecision
    answerability_score: int = 0
    confidence_threshold: float = 0.5
    fallback_message: Optional[str] = None
    reason: str = ""
    open_contradictions: int = 0
    topic_coverage: Dict[str, Any] = None


class RuntimeConfidenceGate:
    """Gates answers based on confidence and answerability."""
    
    DEFAULT_FALLBACK_MESSAGES = {
        "i_dont_know": "I don't have enough verified information to answer that confidently.",
        "clarify": "I'm not certain about this. Could you provide more context or ask about a specific aspect?",
        "escalate": "This question requires more research. I've flagged it for review.",
    }
    
    def __init__(self, twin_id: str):
        self.twin_id = twin_id
        self._policy = None
        self._global_score = None
    
    async def check(
        self,
        query: str,
        query_topic: Optional[str] = None,
        retrieved_chunks: Optional[List[Dict]] = None,
    ) -> ConfidenceGateResult:
        """
        Check if answer should be gated.
        
        Args:
            query: User query
            query_topic: Optional detected topic
            retrieved_chunks: Retrieved evidence chunks
            
        Returns:
            ConfidenceGateResult with decision
        """
        try:
            # Get policy
            policy = await self._get_policy()
            
            # Get answerability score
            if query_topic:
                score_data = await self._get_topic_score(query_topic)
            else:
                score_data = await self._get_global_score()
            
            if not score_data:
                # No scores available - use default policy
                return ConfidenceGateResult(
                    decision=GateDecision.ALLOW,
                    answerability_score=50,
                    reason="No answerability scores available, using default"
                )
            
            answerability = score_data.get("answerability_score", 50)
            threshold = int(policy.get("confidence_threshold_answer", 0.5) * 100)
            
            # Check for open contradictions
            open_contra = await self._count_open_contradictions(query_topic)
            
            # Decision logic
            if answerability < threshold:
                # Below threshold - block or partial
                fallback_behavior = policy.get("fallback_behavior", "i_dont_know")
                fallback_msg = policy.get("fallback_message_template") or \
                              self.DEFAULT_FALLBACK_MESSAGES.get(fallback_behavior)
                
                return ConfidenceGateResult(
                    decision=GateDecision.BLOCK,
                    answerability_score=answerability,
                    confidence_threshold=threshold / 100,
                    fallback_message=fallback_msg,
                    reason=f"Answerability score {answerability} below threshold {threshold}",
                    open_contradictions=open_contra
                )
            
            if open_contra > 0:
                # Open contradictions - allow but warn
                return ConfidenceGateResult(
                    decision=GateDecision.PARTIAL,
                    answerability_score=answerability,
                    confidence_threshold=threshold / 100,
                    reason=f"Answerable but {open_contra} open contradictions detected",
                    open_contradictions=open_contra
                )
            
            # All clear
            return ConfidenceGateResult(
                decision=GateDecision.ALLOW,
                answerability_score=answerability,
                confidence_threshold=threshold / 100,
                reason="Answerability sufficient, no contradictions"
            )
        
        except Exception as e:
            logger.exception(f"Error in confidence gate: {e}")
            # Fail open
            return ConfidenceGateResult(
                decision=GateDecision.ALLOW,
                reason=f"Gate error, failing open: {e}"
            )
    
    async def _get_policy(self) -> Dict[str, Any]:
        """Get runtime policy for twin."""
        if self._policy is not None:
            return self._policy
        
        try:
            response = supabase.table("person_runtime_policies") \
                .select("*") \
                .eq("twin_id", self.twin_id) \
                .eq("is_active", True) \
                .order("priority", desc=True) \
                .limit(1) \
                .execute()
            
            if response.data:
                self._policy = response.data[0]
            else:
                # Default policy
                self._policy = {
                    "confidence_threshold_answer": 0.5,
                    "confidence_threshold_style": 0.6,
                    "fallback_behavior": "i_dont_know",
                    "require_citation": True,
                }
        except Exception as e:
            logger.warning(f"Error fetching policy: {e}")
            self._policy = {
                "confidence_threshold_answer": 0.5,
                "fallback_behavior": "i_dont_know",
            }
        
        return self._policy
    
    async def _get_global_score(self) -> Optional[Dict]:
        """Get global answerability score."""
        if self._global_score is not None:
            return self._global_score
        
        try:
            response = supabase.table("person_answerability_scores") \
                .select("*") \
                .eq("twin_id", self.twin_id) \
                .eq("scope_type", "global") \
                .eq("scope_key", "global") \
                .single() \
                .execute()
            
            self._global_score = response.data
            return self._global_score
        except Exception:
            return None
    
    async def _get_topic_score(self, topic: str) -> Optional[Dict]:
        """Get topic-specific answerability score."""
        try:
            response = supabase.table("person_answerability_scores") \
                .select("*") \
                .eq("twin_id", self.twin_id) \
                .eq("scope_type", "topic") \
                .eq("scope_key", topic.lower().replace(" ", "_")) \
                .single() \
                .execute()
            
            if response.data:
                return response.data
            
            # Fall back to global
            return await self._get_global_score()
        except Exception:
            return await self._get_global_score()
    
    async def _count_open_contradictions(self, topic: Optional[str] = None) -> int:
        """Count open contradictions, optionally for a topic."""
        try:
            query = supabase.table("person_contradictions") \
                .select("id", count="exact") \
                .eq("twin_id", self.twin_id) \
                .eq("status", "open") \
                .eq("is_active", True)
            
            response = query.execute()
            return response.count or 0
        except Exception:
            return 0
    
    def format_response_with_confidence(
        self,
        base_response: str,
        gate_result: ConfidenceGateResult,
        include_citation: bool = True,
    ) -> str:
        """
        Format response with confidence disclosure.
        
        Args:
            base_response: Original generated response
            gate_result: Gate check result
            include_citation: Whether citations are required
            
        Returns:
            Formatted response
        """
        if gate_result.decision == GateDecision.BLOCK:
            return gate_result.fallback_message or self.DEFAULT_FALLBACK_MESSAGES["i_dont_know"]
        
        if gate_result.decision == GateDecision.PARTIAL:
            # Add uncertainty disclaimer
            disclaimer = f"\n\n[Note: I'm moderately confident about this answer (confidence: {gate_result.answerability_score}%). There {'is' if gate_result.open_contradictions == 1 else 'are'} {gate_result.open_contradictions} unresolved question{'' if gate_result.open_contradictions == 1 else 's'} about this topic.]"
            return base_response + disclaimer
        
        # ALLOW - return as-is, maybe add citation
        if include_citation and gate_result.topic_coverage:
            # Could add citation info here
            pass
        
        return base_response


# Convenience functions

async def check_answer_confidence(
    twin_id: str,
    query: str,
    query_topic: Optional[str] = None,
) -> ConfidenceGateResult:
    """Convenience function to check confidence."""
    gate = RuntimeConfidenceGate(twin_id)
    return await gate.check(query, query_topic)


def get_fallback_message(behavior: str, custom_template: Optional[str] = None) -> str:
    """Get fallback message for a behavior type."""
    if custom_template:
        return custom_template
    return RuntimeConfidenceGate.DEFAULT_FALLBACK_MESSAGES.get(
        behavior, 
        RuntimeConfidenceGate.DEFAULT_FALLBACK_MESSAGES["i_dont_know"]
    )
