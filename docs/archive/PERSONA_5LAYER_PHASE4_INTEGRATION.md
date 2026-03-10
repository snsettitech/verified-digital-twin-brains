# 5-Layer Persona Model - Phase 4 Agent Integration

## Integration Complete ✅

This document describes the integration of the 5-Layer Persona Model with the LangGraph agent flow.

---

## Integration Points

### 1. TwinState Extension

Added 5-Layer persona fields to `TwinState` in `backend/modules/agent.py`:

```python
# 5-Layer Persona State (Phase 4)
persona_v2_enabled: Optional[bool]
persona_v2_spec_version: Optional[str]
persona_v2_dimension_scores: Optional[Dict[str, int]]  # 1-5 per dimension
persona_v2_overall_score: Optional[float]
persona_v2_reasoning_steps: Optional[List[str]]
persona_v2_values_prioritized: Optional[List[str]]
persona_v2_value_conflicts: Optional[List[Dict[str, Any]]]
persona_v2_heuristics_applied: Optional[List[str]]
persona_v2_memory_anchors: Optional[List[str]]
persona_v2_safety_checks: Optional[List[Dict[str, Any]]]
persona_v2_safety_blocked: Optional[bool]
persona_v2_consistency_hash: Optional[str]
persona_v2_processing_time_ms: Optional[int]
```

### 2. Planner Node Integration

Modified `planner_node` in `backend/modules/agent.py` to:

1. **Check Feature Flag**: Determine if 5-Layer should be used
2. **Initialize Integration**: Create `PersonaAgentIntegration` instance
3. **Process Query**: Run 5-Layer engine for evaluation queries
4. **Handle Safety**: Return early if safety boundaries triggered
5. **Update State**: Add v2 state fields to result

```python
# In planner_node:
if should_use_5layer_persona(state):
    used_5layer, v2_result = await maybe_use_5layer_persona(
        state=state,
        user_query=user_query,
        context_data=context_data,
    )
    
    if used_5layer and v2_result:
        # Build state updates
        v2_state_updates = build_persona_v2_state_updates(v2_result.decision_output)
        
        # If safety blocked, return early
        if v2_result.safety_blocked:
            return {
                "planning_output": {...},
                "persona_v2_enabled": True,
                "persona_v2_safety_blocked": True,
                ...
            }
```

### 3. Integration Module

Created `backend/modules/persona_agent_integration.py` with:

| Component | Purpose |
|-----------|---------|
| `should_use_5layer_persona()` | Feature flag check with state/twin overrides |
| `PersonaAgentIntegration` | Main integration class |
| `maybe_use_5layer_persona()` | Async helper for conditional processing |
| `build_persona_v2_state_updates()` | Convert decision output to state updates |
| `get_persona_v2_state_defaults()` | Default state values |

---

## Activation

### Method 1: Environment Variable (Global)

```bash
export PERSONA_5LAYER_ENABLED=true
```

### Method 2: State Override (Per Request)

```python
state["use_5layer_persona"] = True  # Force enable
state["use_5layer_persona"] = False  # Force disable
```

### Method 3: Twin Settings (Per Twin)

```python
# In twin settings JSON
{
  "use_5layer_persona": true
}
```

---

## Data Flow

```
User Query
    ↓
router_node (unchanged)
    ↓
planner_node
    ├── Check: should_use_5layer_persona()? (NO)
    │       └── Continue with existing flow
    │
    └── Check: should_use_5layer_persona()? (YES)
            ↓
    maybe_use_5layer_persona()
            ↓
    ┌───────────────────────────────────────┐
    │ 5-Layer Persona Decision Engine       │
    │                                       │
    │ 1. Safety Check (rule-based)          │
    │ 2. Query Classification               │
    │ 3. Apply Cognitive Heuristics         │
    │ 4. Score Dimensions (1-5)             │
    │ 5. Resolve Value Conflicts            │
    │ 6. Apply Memory Anchors               │
    │ 7. Generate Response                  │
    └───────────────────────────────────────┘
            ↓
    StructuredDecisionOutput
            ↓
    build_persona_v2_state_updates()
            ↓
    Return enhanced planning_output
            ↓
realizer_node (unchanged)
    ↓
Response with persona_v2_* metadata
```

---

## Response Format

### Planning Output (Internal)

```python
{
    "planning_output": {
        "answer_points": ["This looks promising!"],
        "citations": [],
        "confidence": 0.75,
        "telemetry": {
            "persona_v2": True,
            "dimension_count": 5,
            "processing_time_ms": 45,
        },
        "persona_v2_scores": {
            "market": 4,
            "founder": 5,
            "traction": 3,
            "defensibility": 3,
            "speed": 4
        },
    },
    "persona_v2_enabled": True,
    "persona_v2_spec_version": "2.0.0",
    "persona_v2_dimension_scores": {"market": 4, ...},
    "persona_v2_overall_score": 3.8,
    "persona_v2_reasoning_steps": [...],
    "persona_v2_consistency_hash": "abc123...",
}
```

### API Response (to Client)

```json
{
  "response": "This looks promising! The team shows strong expertise...",
  "citations": [],
  "persona_scores": {
    "market": 4,
    "founder": 5,
    "traction": 3,
    "defensibility": 3,
    "speed": 4
  },
  "overall_score": 3.8,
  "persona_version": "2.0.0"
}
```

---

## Query Type Routing

The 5-Layer engine is only activated for evaluation-type queries:

| Query Type | Example | 5-Layer Used? |
|------------|---------|---------------|
| Evaluation | "What do you think of this startup?" | ✅ Yes |
| Assessment | "Evaluate the team" | ✅ Yes |
| Advice | "Should I invest?" | ❌ No (safety block) |
| Factual | "What is the revenue?" | ❌ No (existing RAG) |
| Smalltalk | "Hello" | ❌ No (smalltalk bypass) |

---

## Backward Compatibility

The integration maintains 100% backward compatibility:

1. **Feature Flag**: Off by default (`PERSONA_5LAYER_ENABLED=false`)
2. **Fallback**: If v2 spec not found, uses existing v1 flow
3. **State Fields**: Optional, existing code ignores unknown fields
4. **Response Format**: Existing fields unchanged, v2 fields additive

---

## Testing

### Integration Tests (16 passing)

```bash
pytest backend/tests/test_persona_agent_integration.py -v
```

Test coverage:
- Feature flag behavior
- State management
- Integration initialization
- Query processing
- Safety blocking
- State updates

### Full Test Suite (76 passing)

```bash
pytest backend/tests/test_persona_spec_v2.py \
       backend/tests/test_persona_consistency_harness.py \
       backend/tests/test_persona_agent_integration.py -v
```

---

## Metrics Available

With 5-Layer persona enabled, the following metrics are tracked:

| Metric | Path in State | Description |
|--------|---------------|-------------|
| Processing Time | `persona_v2_processing_time_ms` | Engine execution time |
| Consistency Hash | `persona_v2_consistency_hash` | Determinism validation |
| Dimension Scores | `persona_v2_dimension_scores` | 1-5 per dimension |
| Overall Score | `persona_v2_overall_score` | Weighted average |
| Heuristics Used | `persona_v2_heuristics_applied` | Cognitive rules triggered |
| Value Conflicts | `persona_v2_value_conflicts` | Conflicts encountered |
| Safety Blocks | `persona_v2_safety_blocked` | Refusal count |

---

## Files Added/Modified

### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `persona_agent_integration.py` | 540 | Integration layer |
| `test_persona_agent_integration.py` | 430 | Integration tests |

### Modified Files

| File | Change | Purpose |
|------|--------|---------|
| `agent.py` | Added v2 fields to TwinState | State management |
| `agent.py` | Added 5-Layer check in planner_node | Integration point |

---

## Next Steps (Future Phases)

1. **Metrics Dashboard**: Visualize persona_v2_* fields in Langfuse
2. **A/B Testing**: Compare v1 vs v2 performance
3. **Auto-Migration**: Gradually migrate twins to v2
4. **Memory Integration**: Connect Memory Anchors to RAG
5. **Feedback Loop**: Learn from user corrections

---

## Rollout Strategy

### Phase 4A: Canary (Week 1)
```bash
# Enable for specific twins only
PERSONA_5LAYER_ENABLED=true
# Set twin setting: use_5layer_persona=true
```

### Phase 4B: Gradual Rollout (Week 2-3)
```bash
# Enable globally, monitor metrics
PERSONA_5LAYER_ENABLED=true
# Monitor: consistency scores, safety blocks, processing time
```

### Phase 4C: Full Rollout (Week 4)
```bash
# Default to v2 for all evaluation queries
# Keep v1 fallback for edge cases
```

---

## Success Criteria

| Criteria | Target | Status |
|----------|--------|--------|
| Backward Compatibility | 100% | ✅ Pass |
| Integration Tests | 16/16 | ✅ Pass |
| Total Tests | 76/76 | ✅ Pass |
| Feature Flag Control | Full | ✅ Pass |
| Safety Boundaries | Working | ✅ Pass |
| State Persistence | Working | ✅ Pass |

---

**Status**: ✅ Phase 4 Complete  
**Total Implementation**: ~4,800 lines of code + 76 tests  
**Date**: February 20, 2026
