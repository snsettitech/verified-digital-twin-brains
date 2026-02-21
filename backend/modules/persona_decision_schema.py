"""
Structured Decision Output Schema

Defines the standardized output format for decisions made by the 5-Layer Persona.
This schema ensures:
- Structured scoring (1-5 per dimension)
- Reasoning transparency
- Determinism validation
- Audit trail
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class DimensionScore(BaseModel):
    """
    Score for a single dimension in the value hierarchy
    
    Scores are 1-5 with:
    1 = Poor/Unsatisfactory
    2 = Below Average
    3 = Average/Acceptable
    4 = Good
    5 = Excellent/Outstanding
    """
    dimension: str = Field(description="Dimension name (e.g., 'market')")
    score: int = Field(
        ge=1,
        le=5,
        description="Score on 1-5 scale"
    )
    reasoning: str = Field(
        description="Explanation for this score"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in this score (0-1)"
    )
    evidence_citations: List[str] = Field(
        default_factory=list,
        description="Source IDs that support this score"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "reasoning": self.reasoning,
            "confidence": round(self.confidence, 2),
            "evidence_citations": self.evidence_citations,
        }


class ValueConflictEncountered(BaseModel):
    """
    Record of a value conflict that was encountered and resolved
    """
    conflict_description: str = Field(
        description="Description of the conflict situation"
    )
    values_in_conflict: List[str] = Field(
        description="Names of values that were in conflict"
    )
    resolution_applied: str = Field(
        description="Resolution that was applied"
    )
    resolution_type: str = Field(
        default="rule_based",
        description="How resolution was determined (rule_based, context_dependent, etc.)"
    )
    reasoning: str = Field(
        description="Explanation for the resolution"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_description": self.conflict_description,
            "values_in_conflict": self.values_in_conflict,
            "resolution_applied": self.resolution_applied,
            "resolution_type": self.resolution_type,
            "reasoning": self.reasoning,
        }


class HeuristicApplied(BaseModel):
    """
    Record of a cognitive heuristic that was applied
    """
    heuristic_id: str = Field(description="ID of the heuristic")
    heuristic_name: str = Field(description="Name of the heuristic")
    applicability_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How applicable this heuristic was (0-1)"
    )
    steps_executed: List[str] = Field(
        default_factory=list,
        description="Steps that were executed"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "heuristic_id": self.heuristic_id,
            "heuristic_name": self.heuristic_name,
            "applicability_score": round(self.applicability_score, 2),
            "steps_executed": self.steps_executed,
        }


class MemoryAnchorApplied(BaseModel):
    """
    Record of a memory anchor that influenced the decision
    """
    anchor_id: str = Field(description="ID of the memory anchor")
    anchor_type: str = Field(description="Type of memory")
    content_summary: str = Field(
        description="Brief summary of the memory content"
    )
    influence_weight: float = Field(
        ge=0.0,
        le=1.0,
        description="How much this memory influenced the decision"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "anchor_type": self.anchor_type,
            "content_summary": self.content_summary,
            "influence_weight": round(self.influence_weight, 2),
        }


class SafetyCheckResult(BaseModel):
    """
    Result of safety boundary checks
    """
    boundary_id: str = Field(description="ID of the safety boundary")
    category: str = Field(description="Category of boundary")
    triggered: bool = Field(description="Whether the boundary was triggered")
    action_taken: str = Field(description="Action that was taken")
    matched_pattern: Optional[str] = Field(
        default=None,
        description="Pattern that matched (if triggered)"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "category": self.category,
            "triggered": self.triggered,
            "action_taken": self.action_taken,
            "matched_pattern": self.matched_pattern,
        }


class ResponseMetadata(BaseModel):
    """
    Metadata about how the response was generated
    """
    template_id: Optional[str] = Field(
        default=None,
        description="ID of template used (if any)"
    )
    template_applied: bool = Field(
        default=False,
        description="Whether a template was used"
    )
    slots_filled: Dict[str, Any] = Field(
        default_factory=dict,
        description="Slots that were filled in template"
    )
    signature_phrases_used: List[str] = Field(
        default_factory=list,
        description="Signature phrases that were included"
    )
    anti_patterns_avoided: List[str] = Field(
        default_factory=list,
        description="Anti-patterns that were checked"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_applied": self.template_applied,
            "slots_filled": self.slots_filled,
            "signature_phrases_used": self.signature_phrases_used,
            "anti_patterns_avoided": self.anti_patterns_avoided,
        }


class StructuredDecisionOutput(BaseModel):
    """
    Standardized decision output from the 5-Layer Persona
    
    This is the primary output format for all persona-driven decisions.
    It provides:
    - Structured dimension scores (1-5)
    - Transparent reasoning
    - Value conflict resolution
    - Memory influence tracking
    - Safety check results
    - Response metadata
    """
    
    # Input context
    query_summary: str = Field(
        description="Summary of the user query"
    )
    query_type: str = Field(
        description="Classified type of query"
    )
    query_intent: Optional[str] = Field(
        default=None,
        description="Detected intent label"
    )
    
    # Dimension scores (Layer 3 output)
    dimension_scores: List[DimensionScore] = Field(
        default_factory=list,
        description="Scores for each dimension"
    )
    overall_score: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=5.0,
        description="Weighted overall score (1-5)"
    )
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the decision"
    )
    
    # Value resolution (Layer 3 processing)
    value_conflicts_encountered: List[ValueConflictEncountered] = Field(
        default_factory=list,
        description="Value conflicts that were resolved"
    )
    values_prioritized: List[str] = Field(
        default_factory=list,
        description="Values that were prioritized in this decision"
    )
    
    # Reasoning (Layer 2 output)
    cognitive_framework_used: str = Field(
        default="",
        description="Primary cognitive framework used"
    )
    heuristics_applied: List[HeuristicApplied] = Field(
        default_factory=list,
        description="Heuristics that were applied"
    )
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="Step-by-step reasoning"
    )
    evidence_evaluation: Dict[str, Any] = Field(
        default_factory=dict,
        description="How evidence was evaluated"
    )
    
    # Memory influences (Layer 5 output)
    memory_anchors_applied: List[MemoryAnchorApplied] = Field(
        default_factory=list,
        description="Memory anchors that influenced the decision"
    )
    
    # Safety (Safety Boundary checks)
    safety_checks: List[SafetyCheckResult] = Field(
        default_factory=list,
        description="Safety boundary check results"
    )
    safety_blocked: bool = Field(
        default=False,
        description="Whether the query was blocked by safety"
    )
    safety_refusal_reason: Optional[str] = Field(
        default=None,
        description="Reason for safety refusal (if blocked)"
    )
    
    # Response (Layer 4 output)
    natural_language_response: str = Field(
        default="",
        description="Generated natural language response"
    )
    response_metadata: ResponseMetadata = Field(
        default_factory=ResponseMetadata,
        description="Metadata about response generation"
    )
    
    # Identity (Layer 1 context)
    identity_frame_applied: Dict[str, Any] = Field(
        default_factory=dict,
        description="Identity frame elements used"
    )
    
    # Metadata
    persona_version: str = Field(
        default="",
        description="Version of persona spec used"
    )
    persona_name: str = Field(
        default="",
        description="Name of persona used"
    )
    processing_time_ms: int = Field(
        default=0,
        ge=0,
        description="Processing time in milliseconds"
    )
    consistency_hash: str = Field(
        default="",
        description="Hash for determinism validation"
    )
    timestamp: str = Field(
        default="",
        description="ISO timestamp of decision"
    )
    
    @model_validator(mode='after')
    def calculate_overall_score(self) -> 'StructuredDecisionOutput':
        """Calculate overall score from dimension scores if not set"""
        if self.overall_score is None and self.dimension_scores:
            # Simple average (could be weighted)
            total = sum(ds.score for ds in self.dimension_scores)
            self.overall_score = round(total / len(self.dimension_scores), 2)
        return self
    
    def get_dimension_score(self, dimension: str) -> Optional[int]:
        """Get score for a specific dimension"""
        for ds in self.dimension_scores:
            if ds.dimension == dimension:
                return ds.score
        return None
    
    def get_dimension_reasoning(self, dimension: str) -> Optional[str]:
        """Get reasoning for a specific dimension"""
        for ds in self.dimension_scores:
            if ds.dimension == dimension:
                return ds.reasoning
        return None
    
    def compute_consistency_hash(self) -> str:
        """
        Compute a hash for determinism validation
        
        This hash should be consistent for the same input/query
        when the system is deterministic.
        """
        # Include only deterministic fields
        data = {
            "query_summary": self.query_summary,
            "query_type": self.query_type,
            "dimension_scores": [
                {"dimension": ds.dimension, "score": ds.score}
                for ds in self.dimension_scores
            ],
            "values_prioritized": sorted(self.values_prioritized),
            "cognitive_framework_used": self.cognitive_framework_used,
            "heuristics_applied": sorted([h.heuristic_id for h in self.heuristics_applied]),
            "memory_anchors_applied": sorted([m.anchor_id for m in self.memory_anchors_applied]),
            "safety_blocked": self.safety_blocked,
        }
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            "response": self.natural_language_response,
            "persona_scores": {
                ds.dimension: ds.score
                for ds in self.dimension_scores
            },
            "persona_scores_detailed": [
                ds.to_dict() for ds in self.dimension_scores
            ],
            "overall_score": self.overall_score,
            "overall_confidence": round(self.overall_confidence, 2),
            "reasoning_summary": self.reasoning_steps[:3] if self.reasoning_steps else [],
            "value_conflicts": [
                vc.to_dict() for vc in self.value_conflicts_encountered
            ],
            "persona_version": self.persona_version,
            "safety_blocked": self.safety_blocked,
            "processing_metadata": {
                "time_ms": self.processing_time_ms,
                "framework": self.cognitive_framework_used,
                "heuristics": [h.heuristic_name for h in self.heuristics_applied],
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to full dictionary (for storage/debugging)"""
        return {
            "query_summary": self.query_summary,
            "query_type": self.query_type,
            "query_intent": self.query_intent,
            "dimension_scores": [ds.to_dict() for ds in self.dimension_scores],
            "overall_score": self.overall_score,
            "overall_confidence": round(self.overall_confidence, 2),
            "value_conflicts_encountered": [vc.to_dict() for vc in self.value_conflicts_encountered],
            "values_prioritized": self.values_prioritized,
            "cognitive_framework_used": self.cognitive_framework_used,
            "heuristics_applied": [h.to_dict() for h in self.heuristics_applied],
            "reasoning_steps": self.reasoning_steps,
            "evidence_evaluation": self.evidence_evaluation,
            "memory_anchors_applied": [m.to_dict() for m in self.memory_anchors_applied],
            "safety_checks": [sc.to_dict() for sc in self.safety_checks],
            "safety_blocked": self.safety_blocked,
            "safety_refusal_reason": self.safety_refusal_reason,
            "natural_language_response": self.natural_language_response,
            "response_metadata": self.response_metadata.to_dict(),
            "identity_frame_applied": self.identity_frame_applied,
            "persona_version": self.persona_version,
            "persona_name": self.persona_name,
            "processing_time_ms": self.processing_time_ms,
            "consistency_hash": self.consistency_hash or self.compute_consistency_hash(),
            "timestamp": self.timestamp,
        }


# =============================================================================
# Decision Output Builder
# =============================================================================

class DecisionOutputBuilder:
    """
    Builder for constructing StructuredDecisionOutput
    
    Usage:
        builder = DecisionOutputBuilder(query="What do you think?", query_type="evaluation")
        builder.add_dimension_score("market", 4, "Large TAM", 0.85)
        builder.add_dimension_score("founder", 5, "Strong team", 0.92)
        output = builder.build()
    """
    
    def __init__(self, query_summary: str, query_type: str, query_intent: Optional[str] = None):
        self.data: Dict[str, Any] = {
            "query_summary": query_summary,
            "query_type": query_type,
            "query_intent": query_intent,
            "dimension_scores": [],
            "value_conflicts_encountered": [],
            "heuristics_applied": [],
            "reasoning_steps": [],
            "memory_anchors_applied": [],
            "safety_checks": [],
            "identity_frame_applied": {},
        }
    
    def add_dimension_score(
        self,
        dimension: str,
        score: int,
        reasoning: str,
        confidence: float,
        evidence_citations: Optional[List[str]] = None
    ) -> 'DecisionOutputBuilder':
        """Add a dimension score"""
        self.data["dimension_scores"].append(DimensionScore(
            dimension=dimension,
            score=score,
            reasoning=reasoning,
            confidence=confidence,
            evidence_citations=evidence_citations or []
        ))
        return self
    
    def add_value_conflict(
        self,
        description: str,
        values: List[str],
        resolution: str,
        reasoning: str,
        resolution_type: str = "rule_based"
    ) -> 'DecisionOutputBuilder':
        """Add a value conflict resolution"""
        self.data["value_conflicts_encountered"].append(ValueConflictEncountered(
            conflict_description=description,
            values_in_conflict=values,
            resolution_applied=resolution,
            resolution_type=resolution_type,
            reasoning=reasoning
        ))
        return self
    
    def add_heuristic(
        self,
        heuristic_id: str,
        heuristic_name: str,
        applicability: float,
        steps: Optional[List[str]] = None
    ) -> 'DecisionOutputBuilder':
        """Add an applied heuristic"""
        self.data["heuristics_applied"].append(HeuristicApplied(
            heuristic_id=heuristic_id,
            heuristic_name=heuristic_name,
            applicability_score=applicability,
            steps_executed=steps or []
        ))
        return self
    
    def add_memory_anchor(
        self,
        anchor_id: str,
        anchor_type: str,
        content_summary: str,
        influence_weight: float
    ) -> 'DecisionOutputBuilder':
        """Add a memory anchor influence"""
        self.data["memory_anchors_applied"].append(MemoryAnchorApplied(
            anchor_id=anchor_id,
            anchor_type=anchor_type,
            content_summary=content_summary,
            influence_weight=influence_weight
        ))
        return self
    
    def add_reasoning_step(self, step: str) -> 'DecisionOutputBuilder':
        """Add a reasoning step"""
        self.data["reasoning_steps"].append(step)
        return self
    
    def set_framework(self, framework: str) -> 'DecisionOutputBuilder':
        """Set the cognitive framework used"""
        self.data["cognitive_framework_used"] = framework
        return self
    
    def set_response(self, response: str, metadata: Optional[ResponseMetadata] = None) -> 'DecisionOutputBuilder':
        """Set the natural language response"""
        self.data["natural_language_response"] = response
        if metadata:
            self.data["response_metadata"] = metadata
        return self
    
    def set_safety_blocked(self, reason: str) -> 'DecisionOutputBuilder':
        """Mark as safety blocked"""
        self.data["safety_blocked"] = True
        self.data["safety_refusal_reason"] = reason
        return self
    
    def set_persona_info(self, version: str, name: str = "") -> 'DecisionOutputBuilder':
        """Set persona metadata"""
        self.data["persona_version"] = version
        self.data["persona_name"] = name
        return self
    
    def set_processing_time(self, ms: int) -> 'DecisionOutputBuilder':
        """Set processing time"""
        self.data["processing_time_ms"] = ms
        return self
    
    def build(self) -> StructuredDecisionOutput:
        """Build the final StructuredDecisionOutput"""
        return StructuredDecisionOutput(**self.data)
