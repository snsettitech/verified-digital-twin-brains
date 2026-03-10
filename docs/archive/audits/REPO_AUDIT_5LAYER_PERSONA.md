# Repo Audit: 5-Layer Persona Integration

**Date:** 2026-02-21  
**Auditor:** Principal Engineer  
**Scope:** Onboarding → Twin → Persona → Chat call chain

---

## Executive Summary

**CRITICAL FINDING:** The 5-Layer Persona system exists in codebase but is completely bypassed for new twins. All rich onboarding data is flattened to a text string and the structured persona spec is never created.

---

## Call Chain Analysis

### 1. Frontend Onboarding

**File:** `frontend/app/onboarding/page.tsx`

**Current Flow (LINES 171-202):**
```typescript
// Line 171-180: FLATTENING TO TEXT
const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
...`;

// Line 182-202: SENDING FLATTENED TEXT
const response = await authFetchStandalone('/twins', {
  method: 'POST',
  body: JSON.stringify({
    name: twinName,
    description: tagline,
    settings: {
      system_prompt: systemInstructions,  // ← FLAT TEXT
      handle,
      tagline,
      expertise: [...],
      personality,
      intent_profile: { goals_90_days, boundaries, ... }
    }
  })
});
```

**ISSUE:** All structured persona data is converted to a single text string. No `persona_v2_data` structure is sent.

---

### 2. Backend Twin Creation

**File:** `backend/routers/twins.py`

**Current Flow (LINES 94-186):**
```python
@router.post("/twins")
async def create_twin(request: TwinCreateRequest, user=Depends(get_current_user)):
    # ... validation ...
    
    # LINE 143-152: JUST STORES SETTINGS AS-IS
    data = {
        "name": requested_name,
        "tenant_id": tenant_id,
        "description": request.description,
        "specialization": request.specialization,
        "settings": request.settings or {}  // ← Contains flattened system_prompt
    }
    
    # LINE 156: Insert to DB
    response = supabase.table("twins").insert(data).execute()
    
    # LINE 174-184: Creates default group
    await create_group(...)
    
    # MISSING: No persona spec creation!
    # MISSING: No 5-Layer bootstrap!
    return twin
```

**ISSUE:** No PersonaSpecV2 is created. The `settings.system_prompt` text is stored but never used for structured decision-making.

---

### 3. Persona Spec Storage

**File:** `backend/modules/persona_spec_store.py`

**Existing Functions:**
- `bootstrap_persona_spec_from_user_data(twin_id)` - Creates v1 spec from twin settings
- `create_persona_spec(twin_id, tenant_id, created_by, spec, ...)` - Creates v1 spec
- `get_active_persona_spec(twin_id)` - Returns v1 spec or None

**File:** `backend/modules/persona_spec_store_v2.py`

**Existing Functions:**
- `create_persona_spec_v2(...)` - Creates v2 spec
- `get_active_persona_spec_v2(twin_id)` - Returns v2 spec or None
- `PERSONA_5LAYER_ENABLED = os.getenv("PERSONA_5LAYER_ENABLED", "false")` ← DEFAULT FALSE

**ISSUE:** v2 store exists but is never called during onboarding.

---

### 4. Chat Runtime Persona Selection

**File:** `backend/modules/agent.py`

**Current Flow (LINES 293-377):**
```python
def build_system_prompt_with_trace(state: TwinState) -> tuple[str, Dict[str, Any]]:
    full_settings = state.get("full_settings") or {}
    
    # LINE 314-315: USES FLATTENED system_prompt
    default_system_prompt = (full_settings.get("system_prompt") or "").strip()
    custom_instructions = system_prompt_override or default_system_prompt
    
    # LINE 351: Tries to get persona spec (but none exists for new twins)
    active_persona_row = get_active_persona_spec(twin_id=twin_id)
    if active_persona_row and active_persona_row.get("spec"):
        parsed = PersonaSpec.model_validate(active_persona_row["spec"])
        # Uses v1 spec only if manually created
```

**Current Flow - 5-Layer Check (LINES 2002-2050):**
```python
# LINE 2002: Check if 5-Layer should be used
if should_use_5layer_persona(state):
    used_5layer, v2_result = await maybe_use_5layer_persona(...)
```

**File:** `backend/modules/persona_agent_integration.py` (LINE 42)
```python
def should_use_5layer_persona(state: Dict[str, Any]) -> bool:
    # LINE 52: CHECKS GLOBAL FLAG
    if not PERSONA_5LAYER_ENABLED:  # ← FALSE by default
        return False
    
    # Can be overridden by state
    if state.get("use_5layer_persona") is True:
        return True
```

**ISSUE:** 
1. `PERSONA_5LAYER_ENABLED = "false"` by default
2. New twins don't have `use_5layer_persona = true` in settings
3. No active v2 persona spec exists
4. Falls back to flattened system_prompt (text-based responses)

---

### 5. Feature Flag Configuration

**File:** `backend/modules/persona_spec_store_v2.py` (LINE 33)
```python
PERSONA_5LAYER_ENABLED = os.getenv("PERSONA_5LAYER_ENABLED", "false").strip().lower() == "true"
```

**Status:** Defaults to `false`. Even if set to `true`, new twins still need:
1. An active v2 persona spec
2. `use_5layer_persona = true` in twin settings (or remove this check)

---

## Data Flow Diagram (Current - BROKEN)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT FLOW (BROKEN)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FRONTEND (onboarding/page.tsx)                                             │
│  ├── Collects: name, expertise, goals, boundaries, personality            │
│  ├── LINE 171-180: Flattens to systemInstructions TEXT                    │
│  └── LINE 182-202: POST /twins {settings: {system_prompt: TEXT}}          │
│                              ↓                                              │
│  BACKEND (routers/twins.py)                                                 │
│  ├── LINE 143-152: Stores settings as-is (contains flattened text)        │
│  ├── LINE 156: Insert to twins table                                      │
│  └── MISSING: No persona spec v2 creation                                 │
│                              ↓                                              │
│  CHAT (modules/agent.py)                                                    │
│  ├── LINE 2002: should_use_5layer_persona(state)?                         │
│  │   ├── Check 1: PERSONA_5LAYER_ENABLED? → false (default)              │
│  │   ├── Check 2: state.use_5layer_persona? → undefined                  │
│  │   └── Result: RETURN FALSE                                             │
│  │                                                                          │
│  ├── LINE 314-315: Uses settings.system_prompt (flat text)                │
│  └── Result: Random, unstructured responses                               │
│                                                                             │
│  ❌ 5-Layer Persona NEVER ACTIVATED                                       │
│  ❌ Structured scoring NEVER USED                                         │
│  ❌ All onboarding data lost in text flattening                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Files to Modify

### Frontend
| File | Lines | Change |
|------|-------|--------|
| `frontend/app/onboarding/page.tsx` | 1-400 | Restructure to send `persona_v2_data` |
| `frontend/components/onboarding/steps/Step1Identity.tsx` | All | Add Layer 1 fields |
| `frontend/components/onboarding/steps/Step2ThinkingStyle.tsx` | New | Layer 2 - Cognitive Heuristics |
| `frontend/components/onboarding/steps/Step3Values.tsx` | New | Layer 3 - Value Hierarchy |
| `frontend/components/onboarding/steps/Step4Communication.tsx` | New | Layer 4 - Communication Patterns |
| `frontend/components/onboarding/steps/Step5Memory.tsx` | New | Layer 5 - Memory Anchors |
| `frontend/components/onboarding/steps/Step6Review.tsx` | New | Persona Preview & Test |

### Backend
| File | Lines | Change |
|------|-------|--------|
| `backend/routers/twins.py` | 94-186 | Add auto-bootstrap of PersonaSpecV2 |
| `backend/modules/persona_bootstrap.py` | New | `bootstrap_persona_from_onboarding()` |
| `backend/modules/persona_spec_v2.py` | All | Ensure schema completeness |
| `backend/modules/persona_agent_integration.py` | 42 | Default to true for new twins |
| `backend/modules/agent.py` | 2002 | Auto-detect v2 spec availability |

### Tests
| File | Purpose |
|------|---------|
| `backend/tests/test_persona_bootstrap.py` | Bootstrap mapping tests |
| `backend/tests/test_onboarding_integration.py` | End-to-end flow tests |
| `backend/tests/test_scoring_determinism.py` | Consistency harness |

---

## Required Schema Changes

### Database: twins table
No schema change needed. Use `settings` JSONB field to store:
```json
{
  "system_prompt": "legacy text for backwards compat",
  "use_5layer_persona": true,  // NEW
  "persona_v2_version": "2.0.0"  // NEW
}
```

### Database: persona_specs table
Existing table supports v2 via `spec` JSONB:
```json
{
  "version": "2.0.0",
  "identity_frame": {...},
  "cognitive_heuristics": {...},
  "value_hierarchy": {...},
  "communication_patterns": {...},
  "memory_anchors": {...}
}
```

---

## Key Decisions

### 1. Eliminate Feature Flag for New Twins
**Decision:** Remove `PERSONA_5LAYER_ENABLED` check for twins created via new onboarding.

**Rationale:**
- Quality over backwards compatibility (per requirements)
- New twins should always use best available system
- Existing twins unaffected (no migration)

### 2. Strict Layer Separation
**Decision:** Enforce architectural boundaries in code.

**Implementation:**
- Layers 1-3 produce scoring decisions
- Layer 4 only transforms output text
- Layer 5 provides context but doesn't override scores

### 3. Auto-Publish on Creation
**Decision:** Persona specs created during onboarding are immediately ACTIVE.

**Rationale:**
- No manual steps for users
- Immediate availability
- Version can be updated later via Persona Studio

### 4. No Migration Path
**Decision:** Existing twins remain on legacy system.

**Rationale:**
- Explicit requirement
- Avoid breaking changes to production twins
- New twins get new system

---

## Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| 100% of new twins have v2 persona | Check `persona_specs` table after onboarding |
| 100% of new twin chats use v2 | Log `chat_used_persona_v2` event |
| Structured scoring available | Evaluation queries return dimension scores |
| Determinism | N=5 runs show ≤10% decision variance |
| No hallucination | Missing info triggers clarification, not fake scores |

---

## Audit Conclusion

**Current State:** 5-Layer Persona exists but is completely bypassed
**Root Cause:** Onboarding flattens data to text; no v2 spec created; feature flag off
**Solution:** Restructure onboarding to send structured data; auto-create v2 spec; eliminate flag for new twins
**Effort Estimate:** 3-4 weeks (1 BE, 1 FE, full-time)
**Impact:** Critical - Unlocks core product differentiation
