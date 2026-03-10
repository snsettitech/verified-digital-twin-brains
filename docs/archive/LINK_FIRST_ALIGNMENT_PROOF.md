# Link-First Architectural Alignment Proof

## Overview

This document proves that the frontend onboarding now matches the Link-First backend state machine and APIs end-to-end.

## State Machine Alignment

### Backend State Machine
```
draft → ingesting → claims_ready → clarification_pending → persona_built → active
```

### Frontend Implementation
- ✅ `TwinStatus` type defined in `frontend/lib/context/TwinContext.tsx`
- ✅ Each state has corresponding UI screen
- ✅ State transitions via API calls

| Backend State | Frontend Screen | API Endpoint |
|--------------|-----------------|--------------|
| `draft` | LinkSubmission | POST /twins (mode=link_first) |
| `ingesting` | IngestionProgress | GET /persona/link-compile/twins/{id}/job |
| `claims_ready` | ClaimReview | GET /persona/link-compile/twins/{id}/claims |
| `clarification_pending` | Clarification | GET /persona/link-compile/twins/{id}/clarification-questions |
| `persona_built` | PersonaPreview | GET /persona/link-compile/twins/{id}/bios |
| `active` | Chat | POST /twins/{id}/activate |

## Code Verification

### 1. Backend Mode/Links Handling

**File**: `backend/routers/twins.py` (lines 68-78, 167-182)

```python
class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None
    persona_v2_data: Optional[Dict[str, Any]] = None
    # NEW: Mode selector for Link-First vs Manual onboarding
    mode: Optional[str] = None  # "link_first" | "manual" (default: "manual")
    links: Optional[List[str]] = None  # URLs for link-first mode (Mode C)
```

**Twin creation logic** (lines 167-182):
```python
# Determine mode: link_first vs manual (default: manual)
is_link_first = request.mode == "link_first"

# Status based on mode:
# - manual: active (ready to chat immediately)
# - link_first: draft (requires ingestion → claims → clarification → active)
twin_status = "draft" if is_link_first else "active"
```

### 2. Backend Link-Compile Endpoints

**File**: `backend/routers/persona_link_compile.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/persona/link-compile/jobs/mode-a` | POST | Export upload (files) |
| `/persona/link-compile/jobs/mode-b` | POST | Paste/import (text) |
| `/persona/link-compile/jobs/mode-c` | POST | Web fetch (URLs) |
| `/persona/link-compile/jobs/{job_id}` | GET | Job status |
| `/persona/link-compile/twins/{id}/job` | GET | Latest job for twin (NEW) |
| `/persona/link-compile/twins/{id}/claims` | GET | Get claims |
| `/persona/link-compile/twins/{id}/clarification-questions` | GET | Get questions |
| `/persona/link-compile/twins/{id}/clarification-answers` | POST | Submit answers |
| `/persona/link-compile/twins/{id}/bios` | GET | Get bio variants |
| `/persona/link-compile/validate-url` | POST | Validate URL |

**NEW State Transition Endpoints** (lines 484-600):
```python
@router.post("/twins/{twin_id}/transition/clarification-pending")
async def transition_to_clarification_pending(...)

@router.post("/twins/{twin_id}/transition/persona-built")
async def transition_to_persona_built(...)

@router.post("/twins/{twin_id}/activate")
async def activate_twin(...)
```

### 3. Backend Chat Gating

**File**: `backend/modules/auth_guard.py` (lines 814-883)

```python
def ensure_twin_active(twin_id: str) -> bool:
    # Check if twin is active (only when status field is present)
    twin_status = result.data.get("status")
    if twin_status and twin_status not in ["active", "live", None]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Twin {twin_id} is not active (status: {twin_status})"
        )
```

Applied to all chat endpoints in `backend/routers/chat.py`:
- `POST /chat/{twin_id}` (line 1505)
- `POST /chat-widget/{twin_id}` (line 2233)
- `POST /public/chat/{twin_id}/{token}` (line 2695)

### 4. Frontend Mode Selection

**File**: `frontend/app/onboarding/page.tsx`

Mode selector (lines 125-140):
```typescript
const handleModeSelect = (selectedMode: 'manual' | 'link_first') => {
  setMode(selectedMode);
  trackEvent('link_first_onboarding_started', { mode: selectedMode });
  
  if (selectedMode === 'link_first') {
    setLinkFirstStep('link-submission');
    createDraftTwin();  // Creates twin with status='draft'
  }
};
```

### 5. Frontend Link-First Flow Components

All components in `frontend/components/onboarding/steps/`:

| Component | Purpose | Lines |
|-----------|---------|-------|
| `StepModeSelect.tsx` | Mode selection UI | 60 |
| `StepLinkSubmission.tsx` | URL/file submission | 174 |
| `StepIngestionProgress.tsx` | Job polling | 140 |
| `StepClaimReview.tsx` | Claims approval | 178 |
| `StepClarification.tsx` | Q&A form | 171 |
| `StepPersonaPreview.tsx` | Bio selection + activation | 189 |

### 6. Frontend Resume Onboarding

**File**: `frontend/app/onboarding/page.tsx` (lines 85-125)

```typescript
useEffect(() => {
  if (resumeTwinId) {
    fetchTwin(resumeTwinId).then((twinData) => {
      if (twinData) {
        setTwin(twinData);
        // Determine where to resume based on status
        if (twinData.status === 'draft') {
          setMode('link_first');
          setLinkFirstStep('link-submission');
        } else if (twinData.status === 'ingesting') {
          setMode('link_first');
          setLinkFirstStep('ingestion');
        }
        // ... etc
      }
    });
  }
}, [resumeTwinId]);
```

### 7. Frontend Chat Gating

**File**: `frontend/lib/hooks/useChatGating.ts`

```typescript
export function useChatGating(): ChatGateResult {
  const checkAndRedirect = useCallback((twinId?: string): boolean => {
    const twin = twins.find(t => t.id === targetTwinId) || activeTwin;
    const canChat = twin.status === 'active' || twin.is_active;
    
    if (!canChat) {
      router.push(getOnboardingResumeUrl(targetTwinId));
      return false;
    }
    return true;
  }, [...]);
}
```

### 8. Dashboard "Continue Setup" Section

**File**: `frontend/app/dashboard/page.tsx` (lines 55-58, 192-210)

```typescript
const nonActiveTwins = twins.filter(t => t.status && t.status !== 'active');

{nonActiveTwins.length > 0 && (
  <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6">
    <h2 className="text-lg font-bold text-amber-900 mb-4">
      Continue Setup ({nonActiveTwins.length})
    </h2>
    {nonActiveTwins.map((twin) => (
      <Link href={getOnboardingResumeUrl(twin.id)}>
        Continue Setup →
      </Link>
    ))}
  </div>
)}
```

### 9. Shared Types

**File**: `frontend/lib/types/link-first.ts`

Defines TypeScript types matching backend schema:
- `TwinStatus`
- `TwinCreateRequest/Response`
- `LinkCompileJob`
- `Claim`
- `ClarificationQuestion`
- `BioVariant`
- etc.

## Test Coverage

**File**: `frontend/tests/link-first-onboarding.e2e.test.ts`

- ✅ Contract tests (schema validation)
- ✅ Link-First onboarding flow (6 steps)
- ✅ Manual onboarding regression
- ✅ Chat gating (403 handling)
- ✅ State machine transitions
- ✅ API rate limiting

## Sample Payloads

### Create Link-First Twin
```json
POST /api/twins
{
  "name": "My Link-First Twin",
  "mode": "link_first",
  "specialization": "investment"
}
```

**Response**:
```json
{
  "id": "twin_abc123",
  "name": "My Link-First Twin",
  "status": "draft",
  "link_first": {
    "status": "draft",
    "links": [],
    "next_step": "POST /persona/link-compile/jobs/mode-c"
  }
}
```

### Submit URLs (Mode C)
```json
POST /api/persona/link-compile/jobs/mode-c
{
  "twin_id": "twin_abc123",
  "urls": ["https://example.com/article"]
}
```

### Poll Job Status
```json
GET /api/persona/link-compile/twins/twin_abc123/job

Response:
{
  "job_id": "job_xyz789",
  "status": "processing",
  "total_sources": 1,
  "processed_sources": 1,
  "extracted_claims": 5
}
```

### Activate Twin
```json
POST /api/twins/twin_abc123/activate
{
  "final_name": "Investment Advisor Sarah"
}

Response:
{
  "twin_id": "twin_abc123",
  "status": "active",
  "name": "Investment Advisor Sarah",
  "persona_spec_id": "spec_def456"
}
```

## Verification Steps

1. **Manual mode still works**:
   ```bash
   curl -X POST /api/twins \
     -d '{"name": "Manual Twin", "mode": "manual", "persona_v2_data": {...}}'
   # Returns: status="active", chat works immediately
   ```

2. **Link-first mode creates draft**:
   ```bash
   curl -X POST /api/twins \
     -d '{"name": "Link Twin", "mode": "link_first"}'
   # Returns: status="draft", no persona_v2
   ```

3. **Chat blocked for non-active**:
   ```bash
   curl -X POST /api/chat/draft_twin_id \
     -d '{"query": "Hello"}'
   # Returns: 403 Forbidden
   ```

4. **Resume URL works**:
   ```
   /onboarding?twinId=twin_abc123
   # Redirects to correct step based on status
   ```

## File Change Summary

| File | Changes | Lines |
|------|---------|-------|
| `backend/routers/twins.py` | Add mode/links fields, conditional bootstrap | +75 |
| `backend/routers/persona_link_compile.py` | Add transition endpoints, job polling | +120 |
| `frontend/app/onboarding/page.tsx` | Complete rewrite with mode selection | +269 |
| `frontend/lib/context/TwinContext.tsx` | Add TwinStatus type, helpers | +20 |
| `frontend/lib/hooks/useChatGating.ts` | New hook for chat access control | +65 |
| `frontend/lib/types/link-first.ts` | Shared TypeScript types | +150 |
| `frontend/app/dashboard/page.tsx` | Add "Continue Setup" section | +25 |
| `frontend/tests/link-first-onboarding.e2e.test.ts` | Comprehensive E2E tests | +350 |

## Telemetry Events

- `link_first_onboarding_started` - User selects link-first mode
- `link_first_twin_created` - Draft twin created
- `ingestion_started` - URLs/files submitted
- `claims_ready` - Claims extracted
- `clarification_completed` - Q&A finished
- `persona_activated` - Twin activated

## Conclusion

✅ **Backend**: Mode/links handling implemented, state machine enforced
✅ **Frontend**: Mode selector, state-driven flow, resume capability
✅ **Chat Gating**: UI and backend 403 handling with redirects
✅ **Tests**: Contract, E2E, regression coverage
✅ **Types**: Shared schema between frontend and backend

The Link-First Persona architecture is now fully aligned end-to-end.
