# 5-Layer Persona: Default & Primary Implementation Summary

**Date:** 2026-02-21  
**Status:** Implementation Complete  
**Scope:** Full-stack implementation for new twin creation

---

## Executive Summary

This implementation makes 5-Layer Persona the **default and only path** for all new digital twins created through onboarding. The legacy flattened `system_prompt` approach is deprecated for new twins.

### Key Changes

| Component | Before | After |
|-----------|--------|-------|
| Onboarding | 3 steps, text-based | 6 steps, structured 5-Layer |
| Twin Creation | Flattened `system_prompt` text | Structured `persona_v2_data` JSON |
| Persona Spec | v1 (optional, manual) | v2 (auto-created, ACTIVE) |
| Feature Flag | Global OFF by default | Bypassed for v2-enabled twins |
| Chat Runtime | Legacy prompt building | Auto-detects v2, uses structured persona |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         NEW ONBOARDING FLOW (6 STEPS)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STEP 1: Layer 1 - Identity Frame                                               │
│  ├── Twin name, tagline, handle                                                 │
│  ├── Specialization selection (founder/creator/technical/vanilla)               │
│  ├── Expertise domains (selected + custom)                                      │
│  ├── Goals (90-day)                                                             │
│  └── Boundaries & privacy constraints                                           │
│                              ↓                                                  │
│  STEP 2: Layer 2 - Thinking Style                                               │
│  ├── Decision framework (evidence/intuitive/analytical/first-principles)        │
│  ├── Cognitive heuristics selection                                             │
│  ├── Clarifying behavior (ask vs infer)                                         │
│  └── Evidence evaluation criteria                                               │
│                              ↓                                                  │
│  STEP 3: Layer 3 - Values & Priorities                                          │
│  ├── Drag-to-rank value hierarchy                                               │
│  ├── Default values by specialization                                           │
│  ├── Custom value addition                                                      │
│  └── Tradeoff notes                                                             │
│                              ↓                                                  │
│  STEP 4: Layer 4 - Communication Patterns                                       │
│  ├── Tone selection (professional/friendly/casual/technical)                    │
│  ├── Response length (concise/balanced/detailed)                                │
│  ├── First/third person preference                                              │
│  └── Signature phrases                                                          │
│                              ↓                                                  │
│  STEP 5: Layer 5 - Memory Anchors                                               │
│  ├── Key experiences                                                            │
│  ├── Lessons learned                                                            │
│  └── Recurring patterns                                                         │
│                              ↓                                                  │
│  STEP 6: Review & Launch                                                        │
│  ├── Summary of all 5 layers                                                    │
│  ├── Test sandbox preview                                                       │
│  └── Launch button (creates twin + auto-publishes persona)                      │
│                              ↓                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  BACKEND: POST /twins with persona_v2_data                              │   │
│  │  ├── Creates twin record                                                │   │
│  │  ├── Bootstraps PersonaSpecV2 (bootstrap_persona_from_onboarding)       │   │
│  │  ├── Auto-publishes as ACTIVE                                           │   │
│  │  └── Sets use_5layer_persona = true in settings                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              ↓                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CHAT: First message triggers 5-Layer Persona                           │   │
│  │  ├── build_system_prompt_with_trace() detects v2 persona                │   │
│  │  ├── should_use_5layer_persona() returns TRUE (twin setting)            │   │
│  │  ├── PersonaDecisionEngine runs scoring (1-5 per dimension)             │   │
│  │  └── Structured output with dimension_scores, reasoning, consistency    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Backend Changes

### 1. New Module: `backend/modules/persona_bootstrap.py`

**Purpose:** Convert onboarding form data → structured 5-Layer Persona Spec v2

**Key Functions:**
```python
bootstrap_persona_from_onboarding(onboarding_data: Dict) -> PersonaSpecV2
├── _build_identity_frame()      # Layer 1
├── _build_cognitive_heuristics() # Layer 2
├── _build_value_hierarchy()      # Layer 3
├── _build_communication_patterns() # Layer 4
├── _build_memory_anchors()       # Layer 5
└── _build_safety_boundaries()    # Safety (always included)
```

**Features:**
- Infers heuristics from specialization when not explicitly provided
- Maps tone to linguistic markers and formality levels
- Auto-adds default values based on specialization
- Always includes investment/legal/medical advice safety boundaries
- Supports custom heuristics, values, and memory anchors

### 2. Updated: `backend/routers/twins.py`

**Changes:**
- Added `persona_v2_data` field to `TwinCreateRequest`
- Modified `create_twin()` to:
  1. Set `settings.use_5layer_persona = true` for all new twins
  2. Set `settings.persona_v2_version = "2.0.0"`
  3. Call `bootstrap_persona_from_onboarding()` with form data
  4. Create and publish PersonaSpecV2 via `create_persona_spec_v2()`
  5. Include persona info in response

**Key Code:**
```python
# Enhanced settings with 5-Layer Persona configuration
settings = request.settings or {}
settings["use_5layer_persona"] = True  # NEW: Always true for new twins
settings["persona_v2_version"] = "2.0.0"  # NEW: Track persona version

# Bootstrap and create persona spec
persona_spec = bootstrap_persona_from_onboarding(onboarding_data)
persona_record = create_persona_spec_v2(
    twin_id=twin_id,
    tenant_id=tenant_id,
    spec=persona_spec.model_dump(mode="json"),
    status="active",  # Auto-publish
    source="onboarding_v2",
)
```

### 3. Updated: `backend/modules/persona_agent_integration.py`

**Changes:**
- Modified `should_use_5layer_persona()` to check twin settings BEFORE global flag
- Priority: State override → Twin setting → Global flag
- New twins with `use_5layer_persona = true` bypass feature flag entirely

**Key Code:**
```python
def should_use_5layer_persona(state: Dict[str, Any]) -> bool:
    # Check twin settings FIRST (new twins have use_5layer_persona = True)
    full_settings = state.get("full_settings") or {}
    twin_flag = full_settings.get("use_5layer_persona")
    
    # NEW TWINS: Always use 5-Layer if explicitly enabled
    if twin_flag is True:
        return True
    
    # LEGACY TWINS: Fall back to global feature flag
    return PERSONA_5LAYER_ENABLED
```

### 4. Updated: `backend/modules/agent.py`

**Changes:**
- Added `_build_prompt_from_v2_persona()` helper function
- Modified `build_system_prompt_with_trace()` to:
  1. Check for v2 persona spec in database
  2. If found, build prompt from structured spec
  3. Fall back to v1 spec, then legacy system_prompt
- Modified planner_node to auto-use 5-Layer when available

**Prompt Building Priority:**
1. Explicit system_prompt_override (for testing)
2. 5-Layer Persona v2 (if active and use_5layer_persona = true)
3. Legacy PersonaSpec v1 (if exists)
4. Flattened system_prompt text (legacy fallback)

---

## Frontend Changes

### New Files

#### `frontend/components/onboarding/StepIndicator.tsx`
- Visual progress indicator for 6-step onboarding
- Progress bar + step circles with titles
- Responsive design (titles hidden on mobile)

#### `frontend/components/onboarding/steps/Step2ThinkingStyle.tsx`
- Layer 2: Cognitive Heuristics
- Decision framework selection
- Heuristic checkboxes with descriptions
- Clarifying behavior radio buttons
- Evidence standards multi-select

#### `frontend/components/onboarding/steps/Step3Values.tsx`
- Layer 3: Value Hierarchy
- Drag-to-rank interface (up/down buttons)
- Default values by specialization
- Custom value addition
- Tradeoff notes textarea

#### `frontend/components/onboarding/steps/Step5Memory.tsx`
- Layer 5: Memory Anchors
- Tabbed interface: Experiences / Lessons / Patterns
- Add/remove memory items with tags
- Summary counter

#### `frontend/components/onboarding/steps/Step6Review.tsx`
- Layer 6: Review & Launch
- Collapsible sections for all 5 layers
- Summary badges
- Test sandbox preview
- Launch button with loading state
- "What's Different" explainer

#### `frontend/components/onboarding/steps/Step4Communication.tsx`
- Layer 4: Communication Patterns
- Tone selection grid
- Response length options
- First/third person toggle
- Signature phrases
- Custom instructions textarea

### Updated Files

#### `frontend/components/onboarding/steps/Step1Identity.tsx`
- Refactored to use `data/onChange` pattern
- Now explicitly exports `IdentityFormData` interface
- Maintains backwards compatibility with legacy props
- Wrapped in motion.div for animations
- Added layer header with "Layer 1: Identity Frame" title

#### `frontend/app/onboarding/page.tsx` (NEW - Complete Rewrite)
- Complete rewrite for 6-step flow
- State management for all 5 layers
- `buildPersonaV2Data()` function to structure form data
- `createTwin()` function sending `persona_v2_data` to backend
- Step validation and navigation
- Launch handling with redirects

---

## API Changes

### POST /twins

**Request Body (NEW):**
```json
{
  "name": "FounderTwin",
  "description": "Startup advisor and operator",
  "specialization": "founder",
  "settings": {
    "system_prompt": "[LEGACY - backwards compat]",
    "use_5layer_persona": true,
    "persona_v2_version": "2.0.0"
  },
  "persona_v2_data": {
    "twin_name": "FounderTwin",
    "specialization": "founder",
    "decision_framework": "evidence_based",
    "prioritized_values": [
      {"name": "team_quality", "description": "..."},
      {"name": "traction", "description": "..."}
    ],
    "personality": {
      "tone": "professional",
      "response_length": "concise"
    },
    "key_experiences": [...],
    "lessons_learned": [...],
    "safety_boundaries": [...]
  }
}
```

**Response (NEW fields):**
```json
{
  "id": "twin_uuid",
  "name": "FounderTwin",
  "persona_v2": {
    "id": "persona_uuid",
    "version": "2.0.0",
    "status": "active",
    "auto_created": true
  }
}
```

---

## Database Changes

No schema migrations required. Uses existing tables:

### `twins` table
- `settings` JSONB: Now includes `use_5layer_persona: true` and `persona_v2_version: "2.0.0"`

### `persona_specs` table
- New records created with:
  - `version`: "2.0.0"
  - `spec`: Full PersonaSpecV2 JSON
  - `status`: "active" (auto-published)
  - `source`: "onboarding_v2"

---

## Testing

### Backend Tests: `backend/tests/test_persona_bootstrap.py`

**Test Coverage:**
- ✅ Full bootstrap integration (minimal and founder data)
- ✅ All 5 layers populated correctly
- ✅ Default safety boundaries always added
- ✅ Specialization-inferred heuristics
- ✅ Explicit heuristics used when provided
- ✅ Value hierarchy order preserved
- ✅ Tone mapping to linguistic markers
- ✅ Memory anchors conversion
- ✅ Edge cases (empty data, missing optional fields)
- ✅ JSON serialization/deserialization roundtrip

**Run Tests:**
```bash
cd backend
python -m pytest tests/test_persona_bootstrap.py -v
```

### Integration Tests Needed (Future)

- End-to-end: Onboarding → Twin Creation → Chat with v2
- Determinism harness: N=5 runs with same input → variance < 10%
- Safety boundary tests: Ensure refusal for investment/legal/medical queries

---

## Rollout Strategy

### Phase 1: Deploy Backend (Safe)
- ✅ New modules added (no breaking changes)
- ✅ Twin creation enhanced (backwards compatible)
- ✅ Feature flag check updated (preserves existing behavior)

### Phase 2: Deploy Frontend (User-Facing)
- ✅ New onboarding flow (6 steps)
- ✅ Old onboarding still accessible via different route (if needed)

### Phase 3: Monitor
- Track `persona_bootstrap_created` events
- Monitor `chat_used_persona_v2` adoption
- Watch for errors in persona spec creation

### Backwards Compatibility

| Scenario | Behavior |
|----------|----------|
| New twins | Always use 5-Layer Persona v2 |
| Existing twins | Continue using existing system (v1 or legacy) |
| API clients sending old format | Legacy system_prompt still accepted, stored but not used if v2 created |
| Feature flag OFF | New twins still use v2 (bypass flag), legacy twins unaffected |

---

## Telemetry Events

### To Add (Recommended)

```javascript
// Frontend
- persona_bootstrap_started    // User begins onboarding
- persona_step_completed       // Each step completion
- persona_bootstrap_created    // Twin + persona created successfully
- persona_bootstrap_failed     // Creation error

// Backend
- persona_spec_created         // PersonaSpecV2 record created
- persona_active_on_launch     // Spec published as ACTIVE
- chat_used_persona_v2         // Chat runtime used v2 engine
- scoring_attempted            // Dimension scoring executed
- refusal_triggered            // Safety boundary blocked request
```

---

## Success Criteria Verification

| Criterion | Implementation | Verification |
|-----------|----------------|--------------|
| 100% new twins have v2 persona | `create_twin()` auto-creates | Check `persona_specs` table |
| 100% new twin chats use v2 | `should_use_5layer_persona()` returns true | Log events |
| Structured scoring | `PersonaDecisionEngine.decide()` outputs dimension scores | Check response metadata |
| Determinism | Consistency hashing in output | Run harness test |
| No hallucination | "Clarify before evaluating" heuristic + safety boundaries | Test with insufficient info |

---

## Documentation

### User-Facing
- Onboarding UI includes explanations for each layer
- Step 6 includes "What's Different" explainer
- Help tooltips (?) throughout forms

### Developer
- `REPO_AUDIT_5LAYER_PERSONA.md` - Complete call chain analysis
- `5LAYER_PERSONA_IMPLEMENTATION_SUMMARY.md` - This document
- Inline code comments in bootstrap module

---

## Known Limitations & Future Work

### Current Limitations
1. **No drag-and-drop in Step 3:** Uses up/down buttons instead of true DnD
2. **Test sandbox is mocked:** Step 6 preview doesn't make actual LLM calls
3. **No persona migration:** Existing twins remain on legacy system
4. **Limited heuristic customization:** Can't create fully custom heuristics in UI

### Future Enhancements
1. True drag-and-drop for value ranking
2. Live test chat in preview step
3. Persona Studio v2 for editing created personas
4. Import/export persona specs
5. Template library (pre-built personas for common roles)

---

## Files Modified/Created

### Backend (5 files)
1. `backend/modules/persona_bootstrap.py` - NEW
2. `backend/routers/twins.py` - MODIFIED
3. `backend/modules/persona_agent_integration.py` - MODIFIED
4. `backend/modules/agent.py` - MODIFIED
5. `backend/tests/test_persona_bootstrap.py` - NEW

### Frontend (7 files)
1. `frontend/app/onboarding/page.tsx` - REWRITTEN
2. `frontend/components/onboarding/StepIndicator.tsx` - NEW
3. `frontend/components/onboarding/steps/Step1Identity.tsx` - REFACTORED
4. `frontend/components/onboarding/steps/Step2ThinkingStyle.tsx` - NEW
5. `frontend/components/onboarding/steps/Step3Values.tsx` - NEW
6. `frontend/components/onboarding/steps/Step4Communication.tsx` - NEW
7. `frontend/components/onboarding/steps/Step5Memory.tsx` - NEW
8. `frontend/components/onboarding/steps/Step6Review.tsx` - NEW

### Documentation (2 files)
1. `REPO_AUDIT_5LAYER_PERSONA.md` - Call chain analysis
2. `5LAYER_PERSONA_IMPLEMENTATION_SUMMARY.md` - This file

---

## Summary

This implementation delivers a complete 5-Layer Persona system as the default for new twins:

✅ **6-step onboarding** capturing all persona layers  
✅ **Structured data flow** from frontend to backend  
✅ **Auto-bootstrap** of PersonaSpecV2 on twin creation  
✅ **Auto-publish** as ACTIVE (no manual steps)  
✅ **Bypass feature flag** for v2-enabled twins  
✅ **Chat runtime integration** with auto-detection  
✅ **Backwards compatibility** for existing twins  
✅ **Comprehensive tests** for bootstrap logic  

**Ready for deployment and testing.**
