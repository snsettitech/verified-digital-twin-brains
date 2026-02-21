"""
5-Layer Persona Agent Integration

This module integrates the 5-Layer Persona Model with the LangGraph agent flow.

Integration Points:
1. router_node - Persona resolution and safety checks
2. planner_node - 5-Layer scoring and decision making
3. realizer_node - Voice application and response formatting

Usage:
    from modules.persona_agent_integration import (
        PersonaAgentIntegration,
        should_use_5layer_persona,
    )
    
    # In planner_node:
    if should_use_5layer_persona(state):
        integration = PersonaAgentIntegration(state)
        result = await integration.process_with_5layer()
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from modules.persona_spec_v2 import PersonaSpecV2
from modules.persona_decision_engine import PersonaDecisionEngine
from modules.persona_decision_schema import StructuredDecisionOutput
from modules.persona_spec_store_v2 import (
    get_active_persona_spec_unified,
    PERSONA_5LAYER_ENABLED,
)


# =============================================================================
# Feature Flag Check
# =============================================================================

def should_use_5layer_persona(state: Dict[str, Any]) -> bool:
    """
    Check if 5-Layer persona should be used for this request.
    
    CRITICAL: For new twins created via onboarding v2, 5-Layer is ALWAYS enabled.
    Legacy twins may be controlled by the global feature flag.
    
    Priority (highest first):
    1. State override (if state["use_5layer_persona"] is explicitly set)
    2. Twin setting (full_settings["use_5layer_persona"]) - NEW TWINS ALWAYS TRUE
    3. Global feature flag (PERSONA_5LAYER_ENABLED env var) - LEGACY FALLBACK
    """
    # Check twin settings FIRST (new twins have use_5layer_persona = True)
    full_settings = state.get("full_settings") or {}
    twin_flag = full_settings.get("use_5layer_persona")
    
    # NEW TWINS: Always use 5-Layer if explicitly enabled
    if twin_flag is True:
        return True
    if twin_flag is False:
        return False
    
    # State override (for testing/debugging)
    if state.get("use_5layer_persona") is True:
        return True
    if state.get("use_5layer_persona") is False:
        return False
    
    # LEGACY TWINS: Fall back to global feature flag
    # This preserves backwards compatibility for existing twins
    return PERSONA_5LAYER_ENABLED


# =============================================================================
# State Extensions for 5-Layer Persona
# =============================================================================

PERSONA_V2_STATE_FIELDS = {
    # 5-Layer Persona State
    "persona_v2_enabled": bool,  # Whether v2 was used for this turn
    "persona_v2_spec_version": str,  # Version of v2 spec used
    "persona_v2_dimension_scores": Dict[str, int],  # 1-5 scores per dimension
    "persona_v2_overall_score": float,  # Weighted overall score
    "persona_v2_reasoning_steps": List[str],  # Step-by-step reasoning
    "persona_v2_values_prioritized": List[str],  # Values used in decision
    "persona_v2_value_conflicts": List[Dict],  # Conflicts encountered
    "persona_v2_heuristics_applied": List[str],  # Cognitive heuristics used
    "persona_v2_memory_anchors": List[str],  # Memories that influenced decision
    "persona_v2_safety_checks": List[Dict],  # Safety boundary results
    "persona_v2_safety_blocked": bool,  # Whether safety blocked the request
    "persona_v2_consistency_hash": str,  # For determinism validation
    "persona_v2_processing_time_ms": int,  # Processing time
}


def get_persona_v2_state_defaults() -> Dict[str, Any]:
    """Get default values for 5-Layer persona state fields"""
    return {
        "persona_v2_enabled": False,
        "persona_v2_spec_version": None,
        "persona_v2_dimension_scores": {},
        "persona_v2_overall_score": None,
        "persona_v2_reasoning_steps": [],
        "persona_v2_values_prioritized": [],
        "persona_v2_value_conflicts": [],
        "persona_v2_heuristics_applied": [],
        "persona_v2_memory_anchors": [],
        "persona_v2_safety_checks": [],
        "persona_v2_safety_blocked": False,
        "persona_v2_consistency_hash": None,
        "persona_v2_processing_time_ms": 0,
    }


def extract_persona_v2_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all 5-Layer persona fields from state"""
    return {
        field: state.get(field, default)
        for field, default in get_persona_v2_state_defaults().items()
    }


def build_persona_v2_state_updates(
    decision_output: StructuredDecisionOutput
) -> Dict[str, Any]:
    """
    Build state updates from 5-Layer decision output
    
    This is used to update the TwinState after processing
    """
    return {
        "persona_v2_enabled": True,
        "persona_v2_spec_version": decision_output.persona_version,
        "persona_v2_dimension_scores": {
            ds.dimension: ds.score
            for ds in decision_output.dimension_scores
        },
        "persona_v2_overall_score": decision_output.overall_score,
        "persona_v2_reasoning_steps": decision_output.reasoning_steps,
        "persona_v2_values_prioritized": decision_output.values_prioritized,
        "persona_v2_value_conflicts": [
            vc.to_dict() for vc in decision_output.value_conflicts_encountered
        ],
        "persona_v2_heuristics_applied": [
            h.heuristic_name for h in decision_output.heuristics_applied
        ],
        "persona_v2_memory_anchors": [
            m.anchor_id for m in decision_output.memory_anchors_applied
        ],
        "persona_v2_safety_checks": [
            sc.to_dict() for sc in decision_output.safety_checks
        ],
        "persona_v2_safety_blocked": decision_output.safety_blocked,
        "persona_v2_consistency_hash": decision_output.consistency_hash,
        "persona_v2_processing_time_ms": decision_output.processing_time_ms,
    }


# =============================================================================
# Persona Agent Integration
# =============================================================================

@dataclass
class PersonaIntegrationResult:
    """Result of 5-Layer persona integration"""
    used_5layer: bool
    decision_output: Optional[StructuredDecisionOutput] = None
    answer_points: List[str] = None
    confidence: float = 0.0
    citations: List[str] = None
    safety_blocked: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.answer_points is None:
            self.answer_points = []
        if self.citations is None:
            self.citations = []


class PersonaAgentIntegration:
    """
    Integration layer for 5-Layer Persona with LangGraph agent
    
    Handles:
    - Loading v2 persona spec
    - Running 5-Layer decision engine
    - Converting output to agent format
    - State management
    """
    
    def __init__(self, state: Dict[str, Any]):
        self.state = state
        self.twin_id = state.get("twin_id")
        self.engine: Optional[PersonaDecisionEngine] = None
        self.spec: Optional[PersonaSpecV2] = None
        self._decision_output: Optional[StructuredDecisionOutput] = None
    
    async def initialize(self) -> bool:
        """
        Initialize the 5-Layer engine for this twin
        
        Returns:
            True if v2 persona is available and engine created
        """
        if not self.twin_id:
            return False
        
        try:
            # Get unified spec (v2 if available, v1 otherwise)
            spec_data = await get_active_persona_spec_unified(self.twin_id)
            
            if not spec_data:
                return False
            
            # Check if it's v2
            if not spec_data.get("is_v2"):
                return False
            
            # Parse v2 spec
            self.spec = PersonaSpecV2.model_validate(spec_data.get("spec", {}))
            
            # Create engine
            self.engine = PersonaDecisionEngine(self.spec)
            
            return True
            
        except Exception as e:
            print(f"[PersonaAgentIntegration] Failed to initialize: {e}")
            return False
    
    async def process_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PersonaIntegrationResult:
        """
        Process a query through the 5-Layer engine
        
        Args:
            query: User query
            context: Evidence/context for decision
            
        Returns:
            PersonaIntegrationResult with processed output
        """
        if not self.engine:
            success = await self.initialize()
            if not success:
                return PersonaIntegrationResult(
                    used_5layer=False,
                    error="Failed to initialize 5-Layer persona engine"
                )
        
        try:
            # Run decision engine
            decision = await self.engine.decide(
                query=query,
                context=context or {},
                conversation_history=self._extract_conversation_history(),
            )
            
            self._decision_output = decision
            
            # Build result
            result = PersonaIntegrationResult(
                used_5layer=True,
                decision_output=decision,
                answer_points=[decision.natural_language_response],
                confidence=decision.overall_confidence or 0.7,
                citations=[],  # Could extract from dimension_scores
                safety_blocked=decision.safety_blocked,
            )
            
            # Add dimension scores as answer points if evaluation
            if decision.dimension_scores:
                score_summary = self._build_score_summary(decision)
                result.answer_points.append(score_summary)
            
            return result
            
        except Exception as e:
            print(f"[PersonaAgentIntegration] Processing error: {e}")
            return PersonaIntegrationResult(
                used_5layer=False,
                error=str(e)
            )
    
    def _extract_conversation_history(self) -> List[Dict[str, Any]]:
        """Extract conversation history from state"""
        messages = self.state.get("messages", [])
        history = []
        
        for msg in messages[-10:]:  # Last 10 messages
            if hasattr(msg, 'content'):
                role = "user" if msg.type == "human" else "assistant"
                history.append({
                    "role": role,
                    "content": msg.content
                })
        
        return history
    
    def _build_score_summary(self, decision: StructuredDecisionOutput) -> str:
        """Build a summary of dimension scores"""
        scores = decision.dimension_scores
        if not scores:
            return ""
        
        parts = []
        for ds in scores:
            parts.append(f"{ds.dimension}: {ds.score}/5")
        
        return f"Scores: {', '.join(parts)}"
    
    def get_state_updates(self) -> Dict[str, Any]:
        """Get state updates from the last decision"""
        if not self._decision_output:
            return {}
        
        return build_persona_v2_state_updates(self._decision_output)
    
    def build_planning_output(self) -> Dict[str, Any]:
        """
        Build planning_output format compatible with existing agent
        
        This converts 5-Layer output to the format expected by the agent's
        planning_output structure.
        """
        if not self._decision_output:
            return {}
        
        decision = self._decision_output
        
        # Build answerability structure
        answerability = {
            "answerability": "direct" if not decision.safety_blocked else "insufficient",
            "answerable": not decision.safety_blocked,
            "confidence": decision.overall_confidence or 0.7,
            "reasoning": " | ".join(decision.reasoning_steps[:3]),
            "missing_information": [],
            "ambiguity_level": "low",
        }
        
        # Build telemetry
        telemetry = {
            "persona_v2": True,
            "dimension_count": len(decision.dimension_scores),
            "heuristic_count": len(decision.heuristics_applied),
            "conflict_count": len(decision.value_conflicts_encountered),
            "processing_time_ms": decision.processing_time_ms,
        }
        
        return {
            "answer_points": [decision.natural_language_response],
            "citations": [],
            "follow_up_question": "",
            "confidence": decision.overall_confidence or 0.7,
            "teaching_questions": [],
            "render_strategy": "source_faithful",
            "reasoning_trace": "5-Layer Persona Engine: " + " | ".join(decision.reasoning_steps[:2]),
            "answerability": answerability,
            "telemetry": telemetry,
            # 5-Layer specific extensions
            "persona_v2_scores": {
                ds.dimension: ds.score
                for ds in decision.dimension_scores
            },
            "persona_v2_overall": decision.overall_score,
            "persona_v2_reasoning": decision.reasoning_steps,
        }


# =============================================================================
# Helper Functions for Agent Nodes
# =============================================================================

async def maybe_use_5layer_persona(
    state: Dict[str, Any],
    user_query: str,
    context_data: List[Dict[str, Any]],
) -> Tuple[bool, Optional[PersonaIntegrationResult]]:
    """
    Check if 5-Layer persona should be used and process if so
    
    Returns:
        (used_5layer, result)
        used_5layer: True if 5-Layer was used
        result: Integration result (if used_5layer is True)
    """
    if not should_use_5layer_persona(state):
        return False, None
    
    # Check if query type is suitable for 5-Layer
    query_lower = user_query.lower()
    evaluation_keywords = [
        "evaluate", "assess", "rate", "score", "analyze",
        "what do you think", "opinion on", "thoughts on",
        "startup", "founder", "market", "traction"
    ]
    
    is_evaluation = any(kw in query_lower for kw in evaluation_keywords)
    
    if not is_evaluation:
        # Only use 5-Layer for evaluation-type queries
        return False, None
    
    # Initialize integration
    integration = PersonaAgentIntegration(state)
    
    # Prepare context for dimensions
    context = _build_dimension_context(context_data)
    
    # Process
    result = await integration.process_query(user_query, context)
    
    if result.used_5layer and not result.error:
        return True, result
    
    return False, None


def _build_dimension_context(context_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build dimension context from retrieved evidence
    
    This maps evidence to the dimension structure expected by the
    5-Layer scoring engine.
    """
    # Simple heuristic: scan evidence for dimension-relevant keywords
    dimensions = {
        "market": {"keywords": ["market", "tam", "sam", "growth", "industry"], "evidence": []},
        "founder": {"keywords": ["founder", "team", "ceo", "background", "experience"], "evidence": []},
        "traction": {"keywords": ["revenue", "growth", "users", "customers", "mrr", "arr"], "evidence": []},
        "defensibility": {"keywords": ["moat", "competitive", "patent", "secret sauce", "network effects"], "evidence": []},
        "speed": {"keywords": ["iterate", "launch", "ship", "velocity", "execution"], "evidence": []},
    }
    
    # Sort evidence into dimensions
    for item in context_data[:10]:  # Top 10 evidence items
        text = str(item.get("text", "")).lower()
        source_id = item.get("source_id", "")
        
        for dim_name, dim_data in dimensions.items():
            if any(kw in text for kw in dim_data["keywords"]):
                dim_data["evidence"].append({
                    "text": text[:200],
                    "source_id": source_id,
                })
    
    # Build context structure for scoring engine
    context = {"dimensions": {}}
    
    for dim_name, dim_data in dimensions.items():
        if dim_data["evidence"]:
            context["dimensions"][dim_name] = {
                "positive_indicators": len(dim_data["evidence"]) > 0,
                "source_credibility": "medium",
                "evidence_count": len(dim_data["evidence"]),
            }
        else:
            context["dimensions"][dim_name] = {
                "missing_critical_data": True
            }
    
    return context


# =============================================================================
# Backward Compatibility
# =============================================================================

def merge_v2_into_planning_output(
    planning_output: Dict[str, Any],
    v2_result: PersonaIntegrationResult,
) -> Dict[str, Any]:
    """
    Merge 5-Layer result into existing planning_output
    
    This allows gradual migration while maintaining compatibility
    with existing response formatting.
    """
    if not v2_result.used_5layer:
        return planning_output
    
    decision = v2_result.decision_output
    if not decision:
        return planning_output
    
    # Enhance planning_output with v2 data
    enhanced = dict(planning_output)
    
    # Add v2 scores
    enhanced["persona_v2_scores"] = {
        ds.dimension: ds.score
        for ds in decision.dimension_scores
    }
    enhanced["persona_v2_overall"] = decision.overall_score
    
    # Add reasoning
    if decision.reasoning_steps:
        enhanced["reasoning_trace"] = enhanced.get("reasoning_trace", "") + \
            " | 5-Layer: " + " | ".join(decision.reasoning_steps[:2])
    
    # Add telemetry
    telemetry = enhanced.get("telemetry", {})
    telemetry["persona_v2"] = True
    telemetry["persona_v2_time_ms"] = decision.processing_time_ms
    enhanced["telemetry"] = telemetry
    
    return enhanced
