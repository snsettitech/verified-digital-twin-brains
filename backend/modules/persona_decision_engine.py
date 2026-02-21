"""
5-Layer Persona Decision Engine

Core decision-making engine that implements the 5-Layer Persona Model:
1. Identity Frame - Who this persona is
2. Cognitive Heuristics - How this persona thinks
3. Value Hierarchy - What this persona prioritizes
4. Communication Patterns - How this persona expresses decisions
5. Memory Anchors - What experiences shape this persona

The engine produces:
- Structured dimension scores (1-5)
- Consistent decisions across runs
- Deterministic rule-based reasoning
- Transparent value conflict resolution
"""

from __future__ import annotations

import re
import time
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

from modules.persona_spec_v2 import PersonaSpecV2, SafetyBoundary
from modules.persona_decision_schema import (
    StructuredDecisionOutput,
    DimensionScore,
    DecisionOutputBuilder,
    HeuristicApplied,
    MemoryAnchorApplied,
    SafetyCheckResult,
    ValueConflictEncountered,
)


# =============================================================================
# Query Classification
# =============================================================================

@dataclass
class QueryClassification:
    """Classification of user query for processing"""
    query_type: str  # evaluation, factual, advice, opinion, etc.
    intent: str
    requires_evidence: bool
    confidence_required: float
    relevant_dimensions: List[str]


class QueryClassifier:
    """Classifies queries for appropriate processing"""
    
    EVALUATION_KEYWORDS = [
        "evaluate", "assess", "rate", "score", "analyze",
        "what do you think", "opinion on", "thoughts on",
        "startup", "founder", "market", "traction"
    ]
    
    ADVICE_KEYWORDS = [
        "should I", "what should", "recommend", "advice",
        "guide me", "help me decide", "what would you do"
    ]
    
    FACTUAL_KEYWORDS = [
        "what is", "how does", "when did", "who is",
        "explain", "tell me about"
    ]
    
    def classify(self, query: str) -> QueryClassification:
        """Classify a query"""
        query_lower = query.lower()
        
        # Determine query type
        if any(kw in query_lower for kw in self.EVALUATION_KEYWORDS):
            query_type = "evaluation"
            requires_evidence = True
            confidence_required = 0.8
            relevant_dimensions = ["market", "founder", "traction", "defensibility", "speed"]
        elif any(kw in query_lower for kw in self.ADVICE_KEYWORDS):
            query_type = "advice"
            requires_evidence = False
            confidence_required = 0.6
            relevant_dimensions = ["market", "founder"]
        elif any(kw in query_lower for kw in self.FACTUAL_KEYWORDS):
            query_type = "factual"
            requires_evidence = True
            confidence_required = 0.7
            relevant_dimensions = []
        else:
            query_type = "general"
            requires_evidence = False
            confidence_required = 0.5
            relevant_dimensions = ["market", "founder"]
        
        return QueryClassification(
            query_type=query_type,
            intent=query_type,
            requires_evidence=requires_evidence,
            confidence_required=confidence_required,
            relevant_dimensions=relevant_dimensions,
        )


# =============================================================================
# Safety Boundary Checker
# =============================================================================

class SafetyBoundaryChecker:
    """
    Rule-based safety boundary checker
    
    Implements hard refusal rules that are evaluated BEFORE
    any LLM processing. This ensures deterministic safety.
    """
    
    def __init__(self, boundaries: List[SafetyBoundary]):
        self.boundaries = boundaries
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance"""
        for boundary in self.boundaries:
            if boundary.is_regex:
                try:
                    self._compiled_patterns[boundary.id] = re.compile(
                        boundary.pattern, 
                        re.IGNORECASE
                    )
                except re.error:
                    # Invalid regex, skip
                    pass
    
    def check(self, query: str) -> Tuple[bool, Optional[SafetyCheckResult]]:
        """
        Check if query violates any safety boundaries
        
        Returns:
            (is_safe, check_result)
            is_safe: True if query passes all boundaries
            check_result: Result of first triggered boundary (if any)
        """
        for boundary in self.boundaries:
            triggered = False
            matched_pattern = None
            
            if boundary.is_regex and boundary.id in self._compiled_patterns:
                match = self._compiled_patterns[boundary.id].search(query)
                if match:
                    triggered = True
                    matched_pattern = match.group(0)
            else:
                # Literal string match
                if boundary.pattern.lower() in query.lower():
                    triggered = True
                    matched_pattern = boundary.pattern
            
            if triggered:
                result = SafetyCheckResult(
                    boundary_id=boundary.id,
                    category=boundary.category,
                    triggered=True,
                    action_taken=boundary.action,
                    matched_pattern=matched_pattern,
                )
                # Store refusal template for later use
                result._refusal_template = boundary.refusal_template
                
                # Return False for refuse/escalate actions
                is_safe = boundary.action not in ["refuse", "escalate"]
                return is_safe, result
        
        return True, None
    
    def check_all(self, query: str) -> List[SafetyCheckResult]:
        """Check all boundaries and return all results"""
        results = []
        for boundary in self.boundaries:
            triggered = False
            matched_pattern = None
            
            if boundary.is_regex and boundary.id in self._compiled_patterns:
                match = self._compiled_patterns[boundary.id].search(query)
                if match:
                    triggered = True
                    matched_pattern = match.group(0)
            else:
                if boundary.pattern.lower() in query.lower():
                    triggered = True
                    matched_pattern = boundary.pattern
            
            results.append(SafetyCheckResult(
                boundary_id=boundary.id,
                category=boundary.category,
                triggered=triggered,
                action_taken=boundary.action if triggered else "pass",
                matched_pattern=matched_pattern,
            ))
        
        return results


# =============================================================================
# Scoring Engine
# =============================================================================

class ScoringEngine:
    """
    Deterministic scoring engine for dimension evaluation
    
    Produces 1-5 scores for each dimension based on:
    - Evidence quality
    - Value hierarchy
    - Cognitive heuristics
    """
    
    def __init__(self, persona_spec: PersonaSpecV2):
        self.spec = persona_spec
        self.dimensions = persona_spec.value_hierarchy.scoring_dimensions
    
    def score_dimension(
        self,
        dimension: str,
        evidence: Dict[str, Any],
        reasoning_steps: List[str]
    ) -> DimensionScore:
        """
        Score a single dimension based on evidence
        
        This is a deterministic scoring algorithm that uses:
        - Evidence presence and quality
        - Confidence thresholds
        - Value weighting
        """
        # Get dimension config
        dim_config = next(
            (d for d in self.dimensions if d.name == dimension),
            None
        )
        
        if not dim_config:
            return DimensionScore(
                dimension=dimension,
                score=3,
                reasoning=f"No configuration for dimension {dimension}",
                confidence=0.5,
            )
        
        # Calculate base score from evidence
        evidence_score = self._calculate_evidence_score(evidence)
        
        # Apply value weighting
        value_adjustment = self._apply_value_weighting(dimension)
        
        # Calculate final score (1-5)
        raw_score = evidence_score + value_adjustment
        final_score = max(1, min(5, round(raw_score)))
        
        # Calculate confidence
        confidence = self._calculate_confidence(evidence, final_score)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(dimension, evidence, final_score)
        
        return DimensionScore(
            dimension=dimension,
            score=final_score,
            reasoning=reasoning,
            confidence=confidence,
            evidence_citations=evidence.get("source_ids", []),
        )
    
    def _calculate_evidence_score(self, evidence: Dict[str, Any]) -> float:
        """Calculate base score from evidence (0-5 scale)"""
        if not evidence:
            return 2.5  # Neutral when no evidence
        
        # Factors that increase score
        score = 2.5
        
        if evidence.get("strong_positive_indicators"):
            score += 1.5
        if evidence.get("positive_indicators"):
            score += 0.5
        if evidence.get("traction_demonstrated"):
            score += 0.5
        if evidence.get("expert_validation"):
            score += 0.5
        
        # Factors that decrease score
        if evidence.get("strong_negative_indicators"):
            score -= 1.5
        if evidence.get("negative_indicators"):
            score -= 0.5
        if evidence.get("missing_critical_data"):
            score -= 0.5
        
        return max(0, min(5, score))
    
    def _apply_value_weighting(self, dimension: str) -> float:
        """Apply value hierarchy weighting to score"""
        # Find if this dimension aligns with high-priority values
        top_values = self.spec.get_top_values(n=3)
        value_names = [v.name for v in top_values]
        
        adjustment = 0.0
        if dimension in value_names:
            # Slight boost for dimensions that match top values
            adjustment = 0.1
        
        return adjustment
    
    def _calculate_confidence(
        self,
        evidence: Dict[str, Any],
        score: int
    ) -> float:
        """Calculate confidence in the score"""
        base_confidence = 0.6
        
        if not evidence:
            return 0.4  # Low confidence without evidence
        
        # Boost confidence based on evidence quality
        if evidence.get("source_credibility") == "high":
            base_confidence += 0.2
        if evidence.get("multiple_sources"):
            base_confidence += 0.1
        if evidence.get("recent_data"):
            base_confidence += 0.1
        
        # Reduce confidence for extreme scores without strong evidence
        if score in [1, 5] and not evidence.get("strong_evidence"):
            base_confidence -= 0.2
        
        return max(0.0, min(1.0, base_confidence))
    
    def _generate_reasoning(
        self,
        dimension: str,
        evidence: Dict[str, Any],
        score: int
    ) -> str:
        """Generate human-readable reasoning for the score"""
        if not evidence:
            return f"Insufficient data to evaluate {dimension}. Defaulting to neutral assessment."
        
        reasons = []
        
        if evidence.get("strong_positive_indicators"):
            reasons.append("strong positive indicators")
        elif evidence.get("positive_indicators"):
            reasons.append("positive indicators")
        
        if evidence.get("traction_demonstrated"):
            reasons.append("demonstrated traction")
        
        if evidence.get("expert_validation"):
            reasons.append("expert validation")
        
        if evidence.get("negative_indicators"):
            reasons.append("some concerns")
        
        if evidence.get("missing_critical_data"):
            reasons.append("incomplete data")
        
        if reasons:
            return f"Score based on: {', '.join(reasons)}."
        else:
            return f"Evaluation based on available {dimension} data."


# =============================================================================
# Value Conflict Resolver
# =============================================================================

class ValueConflictResolver:
    """
    Resolves conflicts between values based on priority rules
    """
    
    def __init__(self, persona_spec: PersonaSpecV2):
        self.spec = persona_spec
    
    def resolve_conflicts(
        self,
        context: Dict[str, Any]
    ) -> List[ValueConflictEncountered]:
        """
        Detect and resolve value conflicts
        
        Returns list of conflicts encountered and their resolutions
        """
        conflicts = []
        
        # Check each conflict rule
        for rule in self.spec.value_hierarchy.conflict_rules:
            # Check if this conflict is relevant to current context
            is_relevant = self._is_conflict_relevant(rule, context)
            
            if is_relevant:
                resolution = self._apply_resolution(rule, context)
                conflicts.append(ValueConflictEncountered(
                    conflict_description=f"Conflict between {rule.value_a} and {rule.value_b}",
                    values_in_conflict=[rule.value_a, rule.value_b],
                    resolution_applied=resolution,
                    resolution_type="rule_based",
                    reasoning=f"Applied conflict resolution rule: {rule.resolution}"
                ))
        
        return conflicts
    
    def _is_conflict_relevant(
        self,
        rule,
        context: Dict[str, Any]
    ) -> bool:
        """Check if a conflict rule is relevant to current context"""
        # Simple heuristic: if both values appear in context, conflict is relevant
        context_str = json.dumps(context).lower()
        return rule.value_a in context_str and rule.value_b in context_str
    
    def _apply_resolution(self, rule, context: Dict[str, Any]) -> str:
        """Apply the resolution strategy"""
        if rule.resolution == "prioritize_a":
            return f"Prioritized {rule.value_a}"
        elif rule.resolution == "prioritize_b":
            return f"Prioritized {rule.value_b}"
        elif rule.resolution == "context_dependent":
            return f"Resolution based on context: {rule.context_override or 'default'}"
        elif rule.resolution == "escalate":
            return "Escalated for human review"
        else:
            return f"Applied: {rule.resolution}"


# =============================================================================
# Response Generator
# =============================================================================

class ResponseGenerator:
    """
    Generates natural language responses from structured decisions
    
    Layer 4: Communication Patterns
    """
    
    def __init__(self, persona_spec: PersonaSpecV2):
        self.spec = persona_spec
    
    def generate(
        self,
        dimension_scores: List[DimensionScore],
        reasoning_steps: List[str],
        query_type: str,
    ) -> str:
        """
        Generate natural language response
        
        This is deterministic text generation based on:
        - Scores
        - Communication patterns
        - Templates
        """
        comms = self.spec.communication_patterns
        
        # Select template based on query type and scores
        template = self._select_template(query_type, dimension_scores)
        
        # Build response parts
        parts = []
        
        # Opening (signature phrase if available)
        if comms.signature_phrases and query_type == "evaluation":
            parts.append(comms.signature_phrases[0])
        
        # Main assessment
        overall = self._calculate_overall_sentiment(dimension_scores)
        parts.append(self._generate_assessment(overall, dimension_scores))
        
        # Key points
        key_points = self._generate_key_points(dimension_scores)
        if key_points:
            parts.append(key_points)
        
        # Combine
        response = " ".join(parts)
        
        # Apply brevity preference
        response = self._apply_brevity(response, comms.brevity_preference)
        
        return response
    
    def _select_template(
        self,
        query_type: str,
        scores: List[DimensionScore]
    ) -> Optional[str]:
        """Select appropriate template"""
        for template in self.spec.communication_patterns.response_templates:
            if template.intent_label == query_type:
                return template.template
        return None
    
    def _calculate_overall_sentiment(
        self,
        scores: List[DimensionScore]
    ) -> str:
        """Calculate overall sentiment from scores"""
        if not scores:
            return "neutral"
        
        avg_score = sum(s.score for s in scores) / len(scores)
        
        if avg_score >= 4:
            return "positive"
        elif avg_score >= 3:
            return "neutral-positive"
        elif avg_score >= 2:
            return "neutral-negative"
        else:
            return "negative"
    
    def _generate_assessment(
        self,
        sentiment: str,
        scores: List[DimensionScore]
    ) -> str:
        """Generate main assessment text"""
        if sentiment == "positive":
            return "This looks promising. The team and market positioning show strong potential."
        elif sentiment == "neutral-positive":
            return "There are some interesting elements here, though I'd want to understand a few things better."
        elif sentiment == "neutral-negative":
            return "I have some concerns that would need to be addressed before moving forward."
        elif sentiment == "negative":
            return "This doesn't align with what I'd typically look for."
        else:
            return "Here's my assessment:"
    
    def _generate_key_points(self, scores: List[DimensionScore]) -> str:
        """Generate key points from top dimensions"""
        # Sort by score
        sorted_scores = sorted(scores, key=lambda s: s.score, reverse=True)
        
        # Top strengths
        strengths = [s for s in sorted_scores if s.score >= 4][:2]
        # Concerns
        concerns = [s for s in sorted_scores if s.score <= 2][:1]
        
        points = []
        
        if strengths:
            strength_names = [s.dimension for s in strengths]
            points.append(f"Strengths in: {', '.join(strength_names)}.")
        
        if concerns:
            points.append(f"Concern around {concerns[0].dimension}.")
        
        return " ".join(points)
    
    def _apply_brevity(self, text: str, preference: str) -> str:
        """Apply brevity preference"""
        if preference == "concise":
            # Limit to ~2 sentences
            sentences = text.split(". ")
            return ". ".join(sentences[:2]) + "."
        elif preference == "detailed":
            # Already detailed by default
            return text
        else:  # moderate
            # Limit to ~3 sentences
            sentences = text.split(". ")
            return ". ".join(sentences[:3]) + "."


# =============================================================================
# Main Decision Engine
# =============================================================================

class PersonaDecisionEngine:
    """
    Main decision engine for 5-Layer Persona Model
    
    Usage:
        engine = PersonaDecisionEngine(persona_spec)
        result = await engine.decide(query="What do you think?", context={...})
    """
    
    def __init__(self, persona_spec: PersonaSpecV2):
        self.spec = persona_spec
        self.classifier = QueryClassifier()
        self.safety_checker = SafetyBoundaryChecker(persona_spec.safety_boundaries)
        self.scoring_engine = ScoringEngine(persona_spec)
        self.conflict_resolver = ValueConflictResolver(persona_spec)
        self.response_generator = ResponseGenerator(persona_spec)
    
    async def decide(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> StructuredDecisionOutput:
        """
        Make a decision using the 5-Layer Persona Model
        
        Args:
            query: User query
            context: Evidence/context for decision
            conversation_history: Previous conversation turns
            
        Returns:
            StructuredDecisionOutput with scores, reasoning, and response
        """
        start_time = time.time()
        context = context or {}
        
        # Initialize builder
        builder = DecisionOutputBuilder(
            query_summary=query[:200],
            query_type="unknown",
        )
        
        # Step 1: Safety Check (Layer 0 - pre-processing)
        is_safe, safety_result = self.safety_checker.check(query)
        all_safety_checks = self.safety_checker.check_all(query)
        
        for check in all_safety_checks:
            # We need to use the builder's internal data structure directly
            pass  # Will add via builder methods if needed
        
        if not is_safe and safety_result:
            # Return refusal
            builder.set_safety_blocked(safety_result.category)
            refusal_template = getattr(safety_result, '_refusal_template', None)
            builder.set_response(refusal_template or "I'm not able to provide that guidance.", None)
            builder.set_persona_info(self.spec.version, self.spec.name)
            builder.set_processing_time(int((time.time() - start_time) * 1000))
            
            output = builder.build()
            output.safety_checks = all_safety_checks
            output.consistency_hash = output.compute_consistency_hash()
            output.timestamp = datetime.now(timezone.utc).isoformat()
            return output
        
        # Step 2: Query Classification (informs Layer 2)
        classification = self.classifier.classify(query)
        builder.query_type = classification.query_type
        
        # Step 3: Apply Cognitive Heuristics (Layer 2)
        heuristics = self.spec.get_active_heuristics(classification.query_type)
        framework_used = self.spec.cognitive_heuristics.default_framework
        
        if heuristics:
            framework_used = heuristics[0].name
            for h in heuristics[:2]:  # Apply top 2 heuristics
                builder.add_heuristic(
                    heuristic_id=h.id,
                    heuristic_name=h.name,
                    applicability=0.8,
                    steps=h.steps[:3]
                )
        
        builder.set_framework(framework_used)
        
        # Add reasoning steps
        builder.add_reasoning_step(f"Classified query as: {classification.query_type}")
        builder.add_reasoning_step(f"Applied framework: {framework_used}")
        
        # Step 4: Score Dimensions (Layer 3)
        dimension_scores = []
        for dim_name in classification.relevant_dimensions:
            dim_evidence = context.get("dimensions", {}).get(dim_name, {})
            score = self.scoring_engine.score_dimension(
                dimension=dim_name,
                evidence=dim_evidence,
                reasoning_steps=[]
            )
            dimension_scores.append(score)
            builder.add_dimension_score(
                dimension=dim_name,
                score=score.score,
                reasoning=score.reasoning,
                confidence=score.confidence,
                evidence_citations=score.evidence_citations
            )
        
        # Step 5: Resolve Value Conflicts (Layer 3)
        conflicts = self.conflict_resolver.resolve_conflicts(context)
        for conflict in conflicts:
            builder.add_value_conflict(
                description=conflict.conflict_description,
                values=conflict.values_in_conflict,
                resolution=conflict.resolution_applied,
                reasoning=conflict.reasoning
            )
        
        # Add prioritized values
        top_values = self.spec.get_top_values(n=3)
        for v in top_values:
            builder.data.setdefault("values_prioritized", []).append(v.name)
        
        # Step 6: Apply Memory Anchors (Layer 5)
        relevant_memories = self.spec.get_relevant_memories(
            intent=classification.intent,
            limit=self.spec.memory_anchors.max_anchors_per_query
        )
        for memory in relevant_memories:
            builder.add_memory_anchor(
                anchor_id=memory.id,
                anchor_type=memory.type,
                content_summary=memory.content[:100],
                influence_weight=memory.weight
            )
        
        # Step 7: Generate Response (Layer 4)
        response = self.response_generator.generate(
            dimension_scores=dimension_scores,
            reasoning_steps=builder.data.get("reasoning_steps", []),
            query_type=classification.query_type,
        )
        builder.set_response(response, None)
        
        # Step 8: Finalize
        builder.set_persona_info(self.spec.version, self.spec.name)
        builder.set_processing_time(int((time.time() - start_time) * 1000))
        
        output = builder.build()
        output.safety_checks = all_safety_checks
        output.consistency_hash = output.compute_consistency_hash()
        output.timestamp = datetime.now(timezone.utc).isoformat()
        output.identity_frame_applied = {
            "role": self.spec.identity_frame.role_definition,
            "reasoning_style": self.spec.identity_frame.reasoning_style,
        }
        
        return output


# =============================================================================
# Engine Factory
# =============================================================================

def create_decision_engine(
    twin_id: str,
    use_v2: bool = True
) -> Optional[PersonaDecisionEngine]:
    """
    Factory function to create a decision engine for a twin
    
    Args:
        twin_id: The twin ID
        use_v2: Whether to use v2 (5-Layer) persona spec
        
    Returns:
        PersonaDecisionEngine or None
    """
    from modules.persona_spec_store_v2 import get_active_persona_spec_v2, get_active_persona_spec_unified
    
    import asyncio
    
    async def _get_spec():
        if use_v2:
            return await get_active_persona_spec_v2(twin_id)
        else:
            spec_dict = await get_active_persona_spec_unified(twin_id)
            if spec_dict and spec_dict.get("is_v2"):
                return PersonaSpecV2.model_validate(spec_dict.get("spec", {}))
        return None
    
    try:
        spec = asyncio.run(_get_spec())
        if spec:
            return PersonaDecisionEngine(spec)
    except Exception as e:
        print(f"[DecisionEngine] Failed to create engine: {e}")
    
    return None
