"""
5-Layer Persona Specification (Version 2)

This module defines the enhanced persona schema with 5 cognitive layers:
1. Identity Frame - Who this persona is
2. Cognitive Heuristics - How this persona thinks
3. Value Hierarchy - What this persona prioritizes
4. Communication Patterns - How this persona expresses decisions
5. Memory Anchors - What experiences shape this persona
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# Layer 1: Identity Frame
# =============================================================================

class IdentityFrame(BaseModel):
    """
    Layer 1: Who this persona is
    
    Defines the core identity that remains consistent across interactions.
    This layer shapes the foundation for all other layers.
    """
    role_definition: str = Field(
        default="",
        description="Core role of the persona (e.g., 'Experienced angel investor')"
    )
    expertise_domains: List[str] = Field(
        default_factory=list,
        description="List of domains where the persona has expertise"
    )
    background_summary: str = Field(
        default="",
        description="Brief background that informs the persona's perspective"
    )
    reasoning_style: Literal["analytical", "intuitive", "balanced", "first_principles", "pattern_based"] = Field(
        default="balanced",
        description="Primary approach to reasoning and analysis"
    )
    relationship_to_user: Literal["mentor", "peer", "advisor", "collaborator", "evaluator"] = Field(
        default="advisor",
        description="The relationship stance this persona takes with users"
    )
    communication_tendencies: Dict[str, Any] = Field(
        default_factory=lambda: {
            "directness": "moderate",  # direct, moderate, diplomatic
            "formality": "professional",  # casual, professional, formal
            "verbosity": "concise",  # concise, moderate, detailed
        },
        description="Tendencies that shape communication style"
    )


# =============================================================================
# Layer 2: Cognitive Heuristics
# =============================================================================

class CognitiveHeuristic(BaseModel):
    """
    Single reasoning pattern or mental model
    
    Heuristics are applied based on query type and context.
    """
    id: str = Field(description="Unique identifier for this heuristic")
    name: str = Field(description="Human-readable name")
    description: str = Field(default="", description="What this heuristic does")
    applicable_query_types: List[str] = Field(
        default_factory=list,
        description="Query types where this heuristic applies (e.g., 'evaluation', 'comparison')"
    )
    steps: List[str] = Field(
        default_factory=list,
        description="Ordered steps for applying this heuristic"
    )
    active: bool = Field(default=True, description="Whether this heuristic is active")
    priority: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Priority (lower = higher priority, like z-index)"
    )


class CognitiveHeuristics(BaseModel):
    """
    Layer 2: How this persona thinks
    
    Defines the reasoning frameworks and evaluation criteria used
    when making decisions or providing analysis.
    """
    default_framework: str = Field(
        default="evidence_based",
        description="Default reasoning framework when no specific heuristic applies"
    )
    heuristics: List[CognitiveHeuristic] = Field(
        default_factory=list,
        description="Available reasoning patterns"
    )
    evidence_evaluation_criteria: List[str] = Field(
        default_factory=lambda: [
            "source_credibility",
            "recency",
            "relevance",
            "corroboration"
        ],
        description="Criteria for evaluating evidence quality"
    )
    confidence_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "factual_question": 0.7,
            "advice_request": 0.6,
            "evaluation_request": 0.8,
            "opinion_request": 0.5,
        },
        description="Minimum confidence required for different query types"
    )


# =============================================================================
# Layer 3: Value Hierarchy
# =============================================================================

class ValueItem(BaseModel):
    """
    Single value with priority in the hierarchy
    
    Lower priority numbers = higher importance.
    Values with the same priority are considered co-equal.
    """
    name: str = Field(description="Name of the value (e.g., 'transparency', 'speed')")
    priority: int = Field(
        ge=1,
        le=100,
        description="Priority rank (1 = highest priority)"
    )
    description: str = Field(default="", description="What this value means")
    applicable_contexts: List[str] = Field(
        default_factory=list,
        description="Contexts where this value is most relevant"
    )


class ValueConflictRule(BaseModel):
    """
    Rule for resolving conflicts between specific values
    
    When values A and B conflict, this rule determines resolution.
    """
    value_a: str = Field(description="First value in conflict")
    value_b: str = Field(description="Second value in conflict")
    resolution: Literal[
        "prioritize_a", "prioritize_b", "prioritize_quality", "prioritize_speed",
        "prioritize_transparency", "prioritize_privacy", "prioritize_safety",
        "context_dependent", "escalate"
    ] = Field(description="How to resolve this conflict")
    context_override: Optional[str] = Field(
        default=None,
        description="Context that overrides the default resolution"
    )


class ScoringDimension(BaseModel):
    """
    A dimension used for structured scoring
    """
    name: str = Field(description="Dimension name (e.g., 'market')")
    description: str = Field(description="What this dimension measures")
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Weight for overall score calculation"
    )
    scoring_criteria: Dict[int, str] = Field(
        default_factory=dict,
        description="Criteria for each score level (1-5)"
    )


class ValueHierarchy(BaseModel):
    """
    Layer 3: What this persona prioritizes
    
    Defines values in priority order and rules for resolving conflicts.
    Also defines the dimensions used for structured scoring output.
    """
    values: List[ValueItem] = Field(
        default_factory=list,
        description="Ranked list of values"
    )
    conflict_rules: List[ValueConflictRule] = Field(
        default_factory=list,
        description="Rules for resolving value conflicts"
    )
    scoring_dimensions: List[ScoringDimension] = Field(
        default_factory=lambda: [
            ScoringDimension(
                name="market",
                description="Market size and growth potential",
                weight=1.0
            ),
            ScoringDimension(
                name="founder",
                description="Founder/market fit and team strength",
                weight=1.2
            ),
            ScoringDimension(
                name="traction",
                description="Evidence of product-market fit",
                weight=1.0
            ),
            ScoringDimension(
                name="defensibility",
                description="Competitive moat and barriers to entry",
                weight=0.9
            ),
            ScoringDimension(
                name="speed",
                description="Velocity of execution and iteration",
                weight=0.8
            ),
        ],
        description="Dimensions for structured scoring output"
    )
    
    @model_validator(mode='after')
    def validate_unique_value_names(self) -> 'ValueHierarchy':
        """Ensure value names are unique"""
        names = [v.name for v in self.values]
        if len(names) != len(set(names)):
            raise ValueError("Value names must be unique")
        return self


# =============================================================================
# Layer 4: Communication Patterns
# =============================================================================

class ResponseTemplate(BaseModel):
    """
    Template for specific response types
    
    Templates use Jinja2-style syntax for slot filling.
    Example: "I think {{ subject }} has strong {{ strength }}."
    """
    id: str = Field(description="Unique template identifier")
    intent_label: str = Field(description="Intent this template applies to")
    template: str = Field(description="Template string with {{slots}}")
    required_slots: List[str] = Field(
        default_factory=list,
        description="Slots that must be filled for this template"
    )
    optional_slots: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional slots with default values"
    )
    priority: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Template priority (lower = higher priority)"
    )


class CommunicationPatterns(BaseModel):
    """
    Layer 4: How this persona communicates
    
    Defines templates, phrases, linguistic markers, and anti-patterns.
    """
    response_templates: List[ResponseTemplate] = Field(
        default_factory=list,
        description="Templates for different response types"
    )
    signature_phrases: List[str] = Field(
        default_factory=list,
        description="Phrases characteristic of this persona"
    )
    linguistic_markers: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "agreement": ["I think that's right", "Agreed"],
            "disagreement": ["I see it differently", "I'd push back on that"],
            "uncertainty": ["I'm not sure", "It's unclear"],
            "emphasis": ["The key thing is", "What matters here"],
        },
        description="Markers used in different contexts"
    )
    anti_patterns: List[str] = Field(
        default_factory=lambda: [
            "As an AI language model",
            "I cannot provide investment advice",
            "Based on my training data",
        ],
        description="Phrases this persona should NOT use"
    )
    brevity_preference: Literal["concise", "moderate", "detailed"] = Field(
        default="moderate",
        description="Default verbosity level"
    )
    

# =============================================================================
# Layer 5: Memory Anchors
# =============================================================================

class MemoryAnchor(BaseModel):
    """
    Specific memory that informs decisions
    
    Memories are retrieved based on query similarity and context.
    """
    id: str = Field(description="Unique memory identifier")
    type: Literal["experience", "decision", "feedback", "principle", "lesson"] = Field(
        description="Type of memory"
    )
    content: str = Field(description="The memory content")
    context: str = Field(default="", description="When this memory is relevant")
    applicable_intents: List[str] = Field(
        default_factory=list,
        description="Intents where this memory applies"
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Influence weight (0-1)"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for retrieval"
    )


class MemoryAnchors(BaseModel):
    """
    Layer 5: What experiences shape this persona
    
    Defines memories that influence decision-making.
    """
    anchors: List[MemoryAnchor] = Field(
        default_factory=list,
        description="Available memory anchors"
    )
    max_anchors_per_query: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum memories to retrieve per query"
    )
    retrieval_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity for memory retrieval"
    )


# =============================================================================
# Safety Boundaries
# =============================================================================

class SafetyBoundary(BaseModel):
    """
    Hard refusal rule (not LLM-based)
    
    Safety boundaries are checked before any processing.
    """
    id: str = Field(description="Unique boundary identifier")
    pattern: str = Field(description="Regex pattern to match")
    category: Literal[
        "investment_promise",
        "legal_advice", 
        "medical_advice",
        "confidential_info",
        "harmful",
        "unethical",
        "personal_data"
    ] = Field(description="Category of boundary")
    action: Literal["refuse", "escalate", "warn", "log"] = Field(
        description="Action to take when boundary is hit"
    )
    refusal_template: str = Field(
        default="I'm not able to provide that type of guidance.",
        description="Response template when refusing"
    )
    is_regex: bool = Field(
        default=True,
        description="Whether pattern is a regex (True) or literal string (False)"
    )


# =============================================================================
# Complete 5-Layer Persona Spec
# =============================================================================

class PersonaSpecV2(BaseModel):
    """
    Complete 5-Layer Persona Specification (Version 2)
    
    This schema defines a persona with 5 cognitive layers designed for:
    - Deterministic decision consistency
    - Structured scoring output
    - Rule-based safety boundaries
    """
    
    # Metadata
    version: str = Field(default="2.0.0", description="Spec version (semver)")
    name: str = Field(default="", description="Persona name")
    description: str = Field(default="", description="Persona description")
    
    # 5 Layers
    identity_frame: IdentityFrame = Field(
        default_factory=IdentityFrame,
        description="Layer 1: Identity Frame"
    )
    cognitive_heuristics: CognitiveHeuristics = Field(
        default_factory=CognitiveHeuristics,
        description="Layer 2: Cognitive Heuristics"
    )
    value_hierarchy: ValueHierarchy = Field(
        default_factory=ValueHierarchy,
        description="Layer 3: Value Hierarchy"
    )
    communication_patterns: CommunicationPatterns = Field(
        default_factory=CommunicationPatterns,
        description="Layer 4: Communication Patterns"
    )
    memory_anchors: MemoryAnchors = Field(
        default_factory=MemoryAnchors,
        description="Layer 5: Memory Anchors"
    )
    
    # Safety
    safety_boundaries: List[SafetyBoundary] = Field(
        default_factory=list,
        description="Hard safety boundaries"
    )
    
    # Legacy compatibility (for v1 migration)
    constitution: List[str] = Field(
        default_factory=list,
        description="Legacy: Constitutional rules"
    )
    deterministic_rules: Dict[str, Any] = Field(
        default_factory=dict,
        description="Legacy: Deterministic rules"
    )
    
    # Runtime metadata (not stored)
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update timestamp")
    status: Literal["draft", "active", "archived"] = Field(
        default="draft",
        description="Spec status"
    )
    
    # Configuration
    config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "temperature": 0.0,  # 0.0 for deterministic scoring
            "max_tokens": 500,
            "enable_structured_output": True,
            "enable_safety_checks": True,
        },
        description="Runtime configuration"
    )
    
    def get_active_heuristics(self, query_type: Optional[str] = None) -> List[CognitiveHeuristic]:
        """Get heuristics, optionally filtered by query type"""
        heuristics = [h for h in self.cognitive_heuristics.heuristics if h.active]
        if query_type:
            heuristics = [
                h for h in heuristics 
                if not h.applicable_query_types or query_type in h.applicable_query_types
            ]
        return sorted(heuristics, key=lambda h: h.priority)
    
    def get_top_values(self, n: int = 5) -> List[ValueItem]:
        """Get top N values by priority"""
        sorted_values = sorted(self.value_hierarchy.values, key=lambda v: v.priority)
        return sorted_values[:n]
    
    def get_conflict_rule(self, value_a: str, value_b: str) -> Optional[ValueConflictRule]:
        """Find conflict rule for two values"""
        for rule in self.value_hierarchy.conflict_rules:
            if (rule.value_a == value_a and rule.value_b == value_b) or \
               (rule.value_a == value_b and rule.value_b == value_a):
                return rule
        return None
    
    def get_relevant_memories(self, intent: str, limit: int = 3) -> List[MemoryAnchor]:
        """Get memories relevant to an intent"""
        relevant = [
            m for m in self.memory_anchors.anchors 
            if not m.applicable_intents or intent in m.applicable_intents
        ]
        # Sort by weight, then limit
        relevant.sort(key=lambda m: m.weight, reverse=True)
        return relevant[:limit]


# =============================================================================
# Version Utilities
# =============================================================================

def next_patch_version(current: Optional[str]) -> str:
    """Generate next patch version (e.g., 2.0.0 -> 2.0.1)"""
    if not current:
        return "2.0.0"
    parts = current.split(".")
    if len(parts) != 3:
        return "2.0.0"
    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{major}.{minor}.{patch + 1}"
    except ValueError:
        return "2.0.0"


def is_v2_spec(spec: Dict[str, Any]) -> bool:
    """Check if a spec dict is a v2 spec"""
    version = spec.get("version", "")
    return version.startswith("2.") or "identity_frame" in spec


def migrate_v1_to_v2(v1_spec: Dict[str, Any]) -> PersonaSpecV2:
    """
    Migrate a v1 persona spec to v2
    
    This is a best-effort migration that maps v1 fields to v2 layers.
    """
    from modules.persona_spec import PersonaSpec as PersonaSpecV1
    
    # Parse v1 spec
    if isinstance(v1_spec, dict):
        v1 = PersonaSpecV1.model_validate(v1_spec)
    else:
        v1 = v1_spec
    
    # Build v2 spec
    v2 = PersonaSpecV2(
        version="2.0.0",
        name=v1_spec.get("name", ""),
        description=v1_spec.get("description", ""),
        
        # Layer 1: Identity Frame (from v1 identity_voice)
        identity_frame=IdentityFrame(
            role_definition=v1.identity_voice.get("role", ""),
            expertise_domains=v1.identity_voice.get("domains", []),
            background_summary=v1.identity_voice.get("background", ""),
            reasoning_style=v1.identity_voice.get("reasoning_style", "balanced"),
            relationship_to_user=v1.identity_voice.get("relationship", "advisor"),
            communication_tendencies=v1.identity_voice.get("communication", {}),
        ),
        
        # Layer 2: Cognitive Heuristics (from v1 decision_policy)
        cognitive_heuristics=CognitiveHeuristics(
            default_framework=v1.decision_policy.get("framework", "evidence_based"),
            heuristics=[],  # Would need manual curation
            evidence_evaluation_criteria=v1.decision_policy.get("evidence_criteria", []),
            confidence_thresholds=v1.decision_policy.get("thresholds", {}),
        ),
        
        # Layer 3: Value Hierarchy (from v1 stance_values)
        value_hierarchy=ValueHierarchy(
            values=[
                ValueItem(name=k, priority=50, description=str(v))
                for k, v in v1.stance_values.items()
            ],
            conflict_rules=[],  # Would need manual curation
        ),
        
        # Layer 4: Communication Patterns (from v1 interaction_style)
        communication_patterns=CommunicationPatterns(
            response_templates=[],  # Would need manual curation
            signature_phrases=v1.interaction_style.get("signatures", []),
            anti_patterns=v1.interaction_style.get("avoid", []),
            brevity_preference=v1.interaction_style.get("brevity", "moderate"),
        ),
        
        # Layer 5: Memory Anchors (empty - would need manual curation)
        memory_anchors=MemoryAnchors(),
        
        # Safety (from v1 deterministic_rules)
        safety_boundaries=[],  # Would need manual curation
        
        # Legacy compatibility
        constitution=v1.constitution,
        deterministic_rules=v1.deterministic_rules,
        
        status=v1_spec.get("status", "draft"),
    )
    
    return v2
