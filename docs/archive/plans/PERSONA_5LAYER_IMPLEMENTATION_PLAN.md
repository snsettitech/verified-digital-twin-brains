# 5-Layer Persona Model Implementation Plan

## Executive Summary

This document outlines the architectural upgrade from the current style-based persona system to a **5-Layer Cognitive Persona Model** designed for deterministic decision consistency, structured scoring output, and rule-based safety boundaries.

**Current System:** Style-based prompts (tone, voice, examples)  
**Target System:** 5-Layer Cognitive Architecture with deterministic reasoning

---

## 1. Current Architecture Analysis

### 1.1 Existing Persona Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CURRENT PERSONA PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Storage: twins.settings (JSONB)                                        │
│  └── persona_identity_pack: {                                           │
│      description, signature_phrases, style_exemplars, opinion_map       │
│  }                                                                      │
│                                                                         │
│  Versioned Specs: persona_specs table                                   │
│  ├── version (semver)                                                   │
│  ├── status (draft/active/archived)                                     │
│  ├── constitution[]                                                     │
│  ├── decision_policy{}                                                  │
│  ├── stance_values{}                                                    │
│  ├── identity_voice{}                                                   │
│  ├── interaction_style{}                                                │
│  ├── procedural_modules[]                                               │
│  ├── canonical_examples[]                                               │
│  └── deterministic_rules{}                                              │
│                                                                         │
│  Injection Points:                                                      │
│  1. router_node: Persona resolution for pronoun disambiguation          │
│  2. planner_node: compile_prompt_plan() adds persona constraints        │
│  3. realizer_node: Voice realization (limited)                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Current Gaps

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| **Structured Scoring** | No scoring output | HIGH - No 1-5 dimension scores |
| **Decision Consistency** | LLM-based reasoning | HIGH - No deterministic rule engine |
| **Value Hierarchy** | Flat stance_values | HIGH - No prioritized value conflicts |
| **Cognitive Heuristics** | Few-shot examples only | MEDIUM - No reasoning patterns |
| **Memory Anchors** | Owner memories separate | MEDIUM - Not integrated into decisions |
| **Safety Boundaries** | LLM-based refusals | HIGH - No rule-based hard blocks |
| **Determinism** | Temperature-based variance | HIGH - 5-run variance not measured |

---

## 2. Target Architecture: 5-Layer Persona Model

### 2.1 Layer Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    5-LAYER PERSONA MODEL                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 1: IDENTITY FRAME                                           │   │
│  │ Who this persona is (unchanging core identity)                    │   │
│  │ • Role definition, expertise domains, background                  │   │
│  │ • Communication style (not just tone but reasoning style)         │   │
│  │ • Relationship to user (mentor, peer, advisor)                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 2: COGNITIVE HEURISTICS                                     │   │
│  │ How this persona thinks (reasoning patterns)                      │   │
│  │ • Analysis frameworks (first principles, comparative, etc.)       │   │
│  │ • Evidence evaluation criteria                                    │   │
│  │ • Confidence thresholds for different question types              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 3: VALUE HIERARCHY                                          │   │
│  │ What this persona prioritizes when values conflict                │   │
│  │ • Ranked values with explicit priority scores                     │   │
│  │ • Conflict resolution rules (when values collide)                 │   │
│  │ • Context-specific value overrides                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 4: COMMUNICATION PATTERNS                                   │   │
│  │ How this persona expresses decisions (existing, enhanced)         │   │
│  │ • Response templates by intent type                               │   │
│  │ • Signature phrases and linguistic markers                        │   │
│  │ • Anti-patterns (what NOT to say)                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 5: MEMORY ANCHORS                                           │   │
│  │ What experiences shape this persona's perspective                 │   │
│  │ • Key experiences/stories that inform decisions                   │   │
│  │ • Past decisions and their outcomes                               │   │
│  │ • Learned patterns from feedback                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Interactions

```
                    ┌─────────────────┐
                    │  USER QUERY     │
                    └────────┬────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│ Layer 2: COGNITIVE HEURISTICS                                   │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│ │  Analyze    │→ │  Evaluate   │→ │  Apply Confidence       │  │
│ │  Query Type │  │  Evidence   │  │  Thresholds             │  │
│ └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│ Layer 3: VALUE HIERARCHY (Conflict Resolution)                  │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│ │  Score      │→ │  Rank by    │→ │  Generate Structured    │  │
│ │  Dimensions │  │  Priority   │  │  Output (1-5 scores)    │  │
│ └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│      • market (1-5)                                             │
│      • founder (1-5)                                            │
│      • traction (1-5)                                           │
│      • defensibility (1-5)                                      │
│      • speed (1-5)                                              │
└────────────────────────────────────────────────────────────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│ Layer 1 + Layer 4: IDENTITY + COMMUNICATION                     │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│ │  Apply      │→ │  Select     │→ │  Realize Voice          │  │
│ │  Identity   │  │  Template   │  │  (natural language)     │  │
│ └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│ Layer 5: MEMORY ANCHORS (Validation)                            │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│ │  Check      │→ │  Adjust     │→ │  Final Output           │  │
│ │  Against    │  │  Based on   │  │  + Citations            │  │
│ │  Memory     │  │  Past       │  │  + Confidence           │  │
│ └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Schema Design

### 3.1 Enhanced PersonaSpec (5-Layer Version)

```python
# backend/modules/persona_spec_v2.py

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class IdentityFrame(BaseModel):
    """Layer 1: Who this persona is"""
    role_definition: str = Field(default="", description="Core role of the persona")
    expertise_domains: List[str] = Field(default_factory=list)
    background_summary: str = Field(default="")
    reasoning_style: Literal["analytical", "intuitive", "balanced", "first_principles"] = "balanced"
    relationship_to_user: Literal["mentor", "peer", "advisor", "collaborator"] = "advisor"
    communication_tendencies: Dict[str, Any] = Field(default_factory=dict)
    

class CognitiveHeuristic(BaseModel):
    """Single reasoning pattern"""
    id: str
    name: str
    description: str
    applicable_query_types: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    active: bool = True
    priority: int = 50  # Lower = higher priority


class CognitiveHeuristics(BaseModel):
    """Layer 2: How this persona thinks"""
    default_framework: str = Field(default="evidence_based")
    heuristics: List[CognitiveHeuristic] = Field(default_factory=list)
    evidence_evaluation_criteria: List[str] = Field(default_factory=list)
    confidence_thresholds: Dict[str, float] = Field(default_factory=lambda: {
        "factual_question": 0.7,
        "advice_request": 0.6,
        "evaluation_request": 0.8,
    })


class ValueItem(BaseModel):
    """Single value with priority"""
    name: str
    priority: int = Field(ge=1, le=100, description="1 = highest priority")
    description: str = ""
    applicable_contexts: List[str] = Field(default_factory=list)


class ValueConflictRule(BaseModel):
    """How to resolve conflicts between specific values"""
    value_a: str
    value_b: str
    resolution: Literal["prioritize_a", "prioritize_b", "context_dependent", "escalate"]
    context_override: Optional[str] = None


class ValueHierarchy(BaseModel):
    """Layer 3: What this persona prioritizes"""
    values: List[ValueItem] = Field(default_factory=list)
    conflict_rules: List[ValueConflictRule] = Field(default_factory=list)
    scoring_dimensions: List[str] = Field(default_factory=lambda: [
        "market", "founder", "traction", "defensibility", "speed"
    ])
    dimension_descriptions: Dict[str, str] = Field(default_factory=lambda: {
        "market": "Market size and growth potential",
        "founder": "Founder/market fit and team strength", 
        "traction": "Evidence of product-market fit",
        "defensibility": "Competitive moat and barriers to entry",
        "speed": "Velocity of execution and iteration",
    })


class ResponseTemplate(BaseModel):
    """Template for specific response types"""
    id: str
    intent_label: str
    template: str
    required_slots: List[str] = Field(default_factory=list)
    

class CommunicationPatterns(BaseModel):
    """Layer 4: How this persona communicates"""
    response_templates: List[ResponseTemplate] = Field(default_factory=list)
    signature_phrases: List[str] = Field(default_factory=list)
    linguistic_markers: Dict[str, List[str]] = Field(default_factory=dict)
    anti_patterns: List[str] = Field(default_factory=list)
    brevity_preference: Literal["concise", "moderate", "detailed"] = "moderate"


class MemoryAnchor(BaseModel):
    """Specific memory that informs decisions"""
    id: str
    type: Literal["experience", "decision", "feedback", "principle"]
    content: str
    context: str = ""
    applicable_intents: List[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryAnchors(BaseModel):
    """Layer 5: What experiences shape this persona"""
    anchors: List[MemoryAnchor] = Field(default_factory=list)
    max_anchors_per_query: int = 3
    retrieval_threshold: float = 0.7


class SafetyBoundary(BaseModel):
    """Hard refusal rules"""
    id: str
    pattern: str  # Regex or keyword pattern
    category: Literal["investment_promise", "legal_advice", "confidential_info", "harmful"]
    action: Literal["refuse", "escalate", "warn"]
    refusal_template: str = "I'm not able to provide that type of guidance."


class PersonaSpecV2(BaseModel):
    """Complete 5-Layer Persona Specification"""
    version: str = Field(default="2.0.0")
    name: str = Field(default="")
    description: str = Field(default="")
    
    # 5 Layers
    identity_frame: IdentityFrame = Field(default_factory=IdentityFrame)
    cognitive_heuristics: CognitiveHeuristics = Field(default_factory=CognitiveHeuristics)
    value_hierarchy: ValueHierarchy = Field(default_factory=ValueHierarchy)
    communication_patterns: CommunicationPatterns = Field(default_factory=CommunicationPatterns)
    memory_anchors: MemoryAnchors = Field(default_factory=MemoryAnchors)
    
    # Safety
    safety_boundaries: List[SafetyBoundary] = Field(default_factory=list)
    
    # Legacy compatibility (for migration)
    constitution: List[str] = Field(default_factory=list)
    deterministic_rules: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    status: Literal["draft", "active", "archived"] = "draft"
```

### 3.2 Structured Decision Output Schema

```python
# backend/modules/persona_decision_schema.py

from typing import List, Optional
from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    """Score for a single dimension"""
    dimension: str
    score: int = Field(ge=1, le=5, description="1-5 scale")
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class ValueConflictResolution(BaseModel):
    """How a value conflict was resolved"""
    conflict_description: str
    values_in_conflict: List[str]
    resolution_applied: str
    reasoning: str


class StructuredDecisionOutput(BaseModel):
    """Standardized decision output from 5-Layer Persona"""
    
    # Input summary
    query_summary: str
    query_type: str
    
    # Dimension scores (Layer 3)
    dimension_scores: List[DimensionScore]
    overall_score: Optional[float] = Field(None, ge=1.0, le=5.0)
    
    # Value resolution (Layer 3)
    value_conflicts_encountered: List[ValueConflictResolution] = Field(default_factory=list)
    
    # Reasoning (Layer 2)
    cognitive_framework_used: str
    reasoning_steps: List[str]
    
    # Memory influences (Layer 5)
    memory_anchors_applied: List[str] = Field(default_factory=list)
    
    # Response (Layer 4)
    response_template_id: Optional[str] = None
    natural_language_response: str
    
    # Safety
    safety_boundaries_checked: List[str] = Field(default_factory=list)
    
    # Metadata
    persona_version: str
    processing_time_ms: int
    consistency_hash: str  # For deterministic validation
```

---

## 4. Implementation Phases

### Phase 1: Foundation & Schema (Week 1)

```
Deliverables:
├── Schema Definition
│   ├── persona_spec_v2.py (5-Layer schema)
│   ├── persona_decision_schema.py (Structured output)
│   └── persona_migration.py (v1 → v2 converter)
│
├── Database Updates
│   ├── Migration: persona_specs table v2 support
│   └── Index: dimension_scores for analytics
│
├── Feature Flags
│   └── PERSONA_5LAYER_ENABLED (default: false)
│
└── Tests
    ├── test_persona_spec_v2.py
    └── test_persona_migration.py
```

### Phase 2: Layer Implementation (Weeks 2-3)

```
Layer 1: Identity Frame (Week 2)
├── Identity resolution in router_node
├── Relationship context injection
└── Communication style tagging

Layer 2: Cognitive Heuristics (Week 2)
├── Query type classification
├── Framework selection engine
└── Evidence evaluation criteria injection

Layer 3: Value Hierarchy (Week 2-3)
├── Scoring engine (1-5 per dimension)
├── Conflict resolution logic
└── Structured output generation

Layer 4: Communication Patterns (Week 3)
├── Template selection based on scores
├── Signature phrase injection
└── Anti-pattern enforcement

Layer 5: Memory Anchors (Week 3)
├── Memory retrieval integration
├── Anchor weighting system
└── Decision influence tracking
```

### Phase 3: Decision Engine (Week 4)

```
┌─────────────────────────────────────────────────────────────┐
│                    DECISION ENGINE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input: Query + Context                                     │
│                    ↓                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Safety Check (Hard Rules)                           │   │
│  │ • Investment promises → REFUSE                      │   │
│  │ • Legal advice → REFUSE                             │   │
│  │ • Confidential info → ESCALATE                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                    ↓ (pass)                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Cognitive Analysis                                  │   │
│  │ • Query classification                              │   │
│  │ • Framework selection                               │   │
│  │ • Evidence evaluation                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                    ↓                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Scoring Engine                                      │   │
│  │ • Score each dimension (1-5)                        │   │
│  │ • Apply value hierarchy                             │   │
│  │ • Resolve conflicts                                 │   │
│  │ • Calculate overall score                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                    ↓                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Response Generation                                 │   │
│  │ • Select template                                   │   │
│  │ • Apply communication patterns                      │   │
│  │ • Inject memory anchors                             │   │
│  │ • Generate natural language                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                    ↓                                        │
│  Output: StructuredDecisionOutput                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 4: Determinism & Testing (Week 5)

```
Deliverables:
├── Determinism Engine
│   ├── Temperature control (0.0 for scoring)
│   ├── Seed management
│   └── Consistency hashing
│
├── Evaluation Harness
│   ├── 5-run variance measurement
│   ├── Golden dataset creation
│   └── Automated consistency tests
│
└── Performance Monitoring
    ├── Decision latency tracking
    ├── Score distribution analytics
    └── Value conflict frequency
```

---

## 5. Key Features

### 5.1 Structured Scoring Output

Every decision must output:

```json
{
  "dimension_scores": [
    {"dimension": "market", "score": 4, "reasoning": "Large TAM with clear growth", "confidence": 0.85},
    {"dimension": "founder", "score": 5, "reasoning": "Strong domain expertise", "confidence": 0.92},
    {"dimension": "traction", "score": 3, "reasoning": "Early revenue but inconsistent", "confidence": 0.65},
    {"dimension": "defensibility", "score": 3, "reasoning": "Network effects not yet proven", "confidence": 0.70},
    {"dimension": "speed", "score": 4, "reasoning": "Fast iteration cycles", "confidence": 0.80}
  ],
  "overall_score": 3.8,
  "value_conflicts_encountered": [],
  "natural_language_response": "This looks promising from a team perspective..."
}
```

### 5.2 Safety Boundaries

Hard-coded refusal rules (not LLM-based):

```python
SAFETY_BOUNDARIES = [
    {
        "id": "no_investment_promises",
        "pattern": r"(should I invest|is this a good investment|will this make money)",
        "category": "investment_promise",
        "action": "refuse",
        "refusal_template": "I can't provide investment advice. I can share my perspective on the team and market, but you should consult with a financial advisor."
    },
    {
        "id": "no_legal_advice",
        "pattern": r"(is this legal|can I do this legally|legal implications)",
        "category": "legal_advice",
        "action": "refuse",
        "refusal_template": "I'm not qualified to provide legal advice. Please consult with a legal professional."
    },
]
```

### 5.3 Determinism Requirements

- Same input → Same scores (variance < 5% across 5 runs)
- Score variance measured per dimension
- Hash-based consistency validation
- Temperature = 0.0 for scoring layer

---

## 6. Integration Points

### 6.1 Agent Integration

```python
# backend/modules/agent.py

from modules.persona_engine_v2 import PersonaEngineV2
from modules.persona_spec_store import get_active_persona_spec_v2

async def planner_node(state: TwinState):
    # ... existing code ...
    
    # 5-Layer Persona (if enabled)
    if PERSONA_5LAYER_ENABLED:
        persona_spec_v2 = await get_active_persona_spec_v2(twin_id)
        engine = PersonaEngineV2(persona_spec_v2)
        
        decision_output = await engine.decide(
            query=user_query,
            context=retrieved_evidence,
            conversation_history=messages
        )
        
        # decision_output is StructuredDecisionOutput
        # Inject into planning_output
        planning_output["dimension_scores"] = decision_output.dimension_scores
        planning_output["persona_reasoning"] = decision_output.reasoning_steps
    ```

### 6.2 API Response

```python
# Response now includes structured scores
{
    "response": "Natural language response...",
    "citations": [...],
    "persona_scores": {
        "market": 4,
        "founder": 5,
        "traction": 3,
        "defensibility": 3,
        "speed": 4,
        "overall": 3.8
    },
    "persona_reasoning": ["Step 1...", "Step 2..."],
    "persona_version": "2.0.0"
}
```

---

## 7. Migration Strategy

### 7.1 Backward Compatibility

```python
# persona_spec_store.py

async def get_active_persona_spec(twin_id: str) -> Optional[Dict]:
    """Returns v1 or v2 spec depending on feature flag"""
    if PERSONA_5LAYER_ENABLED:
        spec = await get_active_persona_spec_v2(twin_id)
        if spec:
            return spec
        # Fallback: auto-migrate v1 → v2
        v1_spec = await get_active_persona_spec_v1(twin_id)
        return migrate_v1_to_v2(v1_spec)
    else:
        return await get_active_persona_spec_v1(twin_id)
```

### 7.2 Data Migration

```bash
# Migration script
python scripts/migrate_persona_v1_to_v2.py \
    --twin-id <twin_id> \
    --dry-run \
    --validate
```

---

## 8. Testing Strategy

### 8.1 Consistency Tests

```python
# tests/test_persona_5layer_consistency.py

async def test_five_run_variance():
    """Same query should produce scores with < 5% variance"""
    engine = PersonaEngineV2(spec)
    query = "What do you think of this startup idea?"
    
    results = []
    for _ in range(5):
        result = await engine.decide(query, context={})
        results.append(result)
    
    for dimension in ["market", "founder", "traction", "defensibility", "speed"]:
        scores = [r.get_score(dimension) for r in results]
        variance = max(scores) - min(scores)
        assert variance <= 1, f"{dimension} variance {variance} > 1"
```

### 8.2 Value Conflict Tests

```python
async def test_value_conflict_resolution():
    """Test that value conflicts are resolved according to hierarchy"""
    spec = create_spec_with_conflicting_values()
    engine = PersonaEngineV2(spec)
    
    # Query that triggers value conflict
    result = await engine.decide(
        "Should we prioritize speed or quality?",
        context={}
    )
    
    assert len(result.value_conflicts_encountered) > 0
    assert result.value_conflicts_encountered[0].resolution_applied == "prioritize_quality"
```

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Score Consistency** | < 5% variance | 5 runs, same input |
| **Safety Compliance** | 100% | Rule-based refusals |
| **Response Latency** | < 200ms | P95 for scoring layer |
| **Dimension Coverage** | 100% | All 5 dimensions scored |
| **Value Conflict Resolution** | > 90% | Automated without escalation |

---

## 10. Next Steps

1. **Review & Approve** this architecture plan
2. **Create Feature Branch** for 5-Layer implementation
3. **Implement Phase 1** (Schema & Foundation)
4. **Add Migration Tests** for backward compatibility
5. **Begin Layer 1** (Identity Frame) implementation

---

**Document Version:** 1.0  
**Last Updated:** February 20, 2026  
**Author:** Agent System  
**Status:** Draft - Pending Review
