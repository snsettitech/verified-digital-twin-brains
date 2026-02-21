# Link-First Architectural Alignment: Backend Summary

## Overview
This document summarizes the backend changes to align twin creation with the Link-First Persona architecture, implementing state machine enforcement and mode selection.

## State Machine

```
draft → ingesting → claims_ready → clarification_pending → persona_built → active
```

| Status | Description | Chat Allowed? |
|--------|-------------|---------------|
| `draft` | Twin created, awaiting content ingestion | ❌ No |
| `ingesting` | Content being processed, claims extracted | ❌ No |
| `claims_ready` | Claims extracted, awaiting review | ❌ No |
| `clarification_pending` | User clarification interview in progress | ❌ No |
| `persona_built` | Persona spec generated, awaiting activation | ❌ No |
| `active` | Persona active, ready for chat | ✅ Yes |

## Backend Changes Implemented

### 1. Twin Creation API (`backend/routers/twins.py`)

**Modified `TwinCreateRequest` schema:**
```python
class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None
    persona_v2_data: Optional[Dict[str, Any]] = None
    # NEW FIELDS:
    mode: Optional[str] = None  # "link_first" | "manual"
    links: Optional[List[str]] = None  # URLs for link-first mode
```

**Modified `POST /twins` logic:**

#### Manual Mode (Default)
- Status: `active`
- Persona: Auto-bootstrapped from `persona_v2_data`
- Source: `onboarding_v2`
- Chat: Enabled immediately

#### Link-First Mode (`mode="link_first"`)
- Status: `draft`
- Persona: NOT created (will be built from claims)
- Source: `link-compile` (set later)
- Chat: Blocked until status → `active`
- Links: Stored in `settings.link_first_urls`

### 2. Chat Blocking (`backend/modules/auth_guard.py`)

Already implemented - `ensure_twin_active()` checks:
1. Twin exists
2. `status` column value
3. Blocks with 403 if status not in `["active", "live", None]`
4. Backward compatible (treats missing status as active for legacy twins)

**Applied to all chat endpoints:**
- `POST /chat/{twin_id}` ✅
- `POST /chat-widget/{twin_id}` ✅
- `POST /public/chat/{twin_id}/{token}` ✅

### 3. Citation Enforcement (`backend/modules/agent.py`)

Already implemented in `_build_prompt_from_v2_persona()`:

When `source` indicates link-first persona:
```python
is_link_first = "link" in source.lower() or source == "link-compile"
```

**Inferred heuristics require verification:**
```
INFERENCE HONESTY (Layer 2 - Cognitive Heuristics):
The following heuristics REQUIRE source verification:
- Framework Name: Cite claims when applying
```

**Value claims require evidence:**
```
INFERENCE HONESTY (Layer 3 - Values):
Value-based claims REQUIRE documented evidence:
- Value Name: Link to source claims
```

**Citation rules injected:**
```
CITATION RULES (Link-First Persona):
1. Every owner-specific factual claim MUST cite [claim_id]
2. If no claim supports a statement, ask a clarification question
3. Do NOT make assumptions beyond the documented claims
4. Uncertainty is preferred to unsupported assertions

CITATION FORMAT: 'I prefer B2B investments [claim_abc123]'
```

## API Contract: Twin Creation

### Manual Mode Request
```json
POST /twins
{
  "name": "My Twin",
  "specialization": "investment",
  "mode": "manual",  // or omitted (default)
  "persona_v2_data": {
    "identity": {...},
    "cognitive": {...},
    "values": {...},
    "communication": {...},
    "memory": {...}
  }
}
```

**Response:**
```json
{
  "id": "twin_abc123",
  "status": "active",
  "persona_v2": {
    "id": "spec_xyz789",
    "version": "2.0.0",
    "status": "active"
  }
}
```

### Link-First Mode Request
```json
POST /twins
{
  "name": "My Twin",
  "specialization": "investment",
  "mode": "link_first",
  "links": [
    "https://linkedin.com/in/username",
    "https://twitter.com/username"
  ]
}
```

**Response:**
```json
{
  "id": "twin_abc123",
  "status": "draft",
  "link_first": {
    "status": "draft",
    "links": [...],
    "next_step": "POST /persona/link-compile/jobs/mode-c"
  }
}
```

## Feature Flag

Environment variable controls UI visibility:
```
LINK_FIRST_ENABLED=true  # Show link-first mode option
LINK_FIRST_ENABLED=false # Hide link-first mode option (default)
```

## Migration Safety

### Legacy Twins (Pre-Link-First)
- No `status` column → treated as `active`
- Persona source is `onboarding_v2`
- Chat works unchanged

### New Twins - Manual Mode
- Status: `active` (immediate)
- Source: `onboarding_v2`
- Chat: Enabled

### New Twins - Link-First Mode
- Status: `draft` → `ingesting` → `claims_ready` → `clarification_pending` → `persona_built` → `active`
- Source: `link-compile`
- Chat: Blocked until `active`

## Frontend Requirements

### 1. Mode Selector Component
Add to onboarding flow (Step 0 or integrated):
```typescript
type Mode = "manual" | "link_first";

// Feature flag check
const linkFirstEnabled = process.env.LINK_FIRST_ENABLED === "true";
```

### 2. Link-First Onboarding Steps
When `mode === "link_first"`:
- Skip steps 1-6 (manual persona builder)
- Show new steps:
  1. **LinkSubmission** - Accept URLs/uploads
  2. **IngestionProgress** - Poll `/twins/{id}` for status changes
  3. **ClaimReview** - Display extracted claims
  4. **Clarification** - Ask inference questions
  5. **PersonaPreview** - Review generated persona
  6. **Activation** - Set status → `active`

### 3. Chat Access Control
Before entering chat:
```typescript
if (twin.status !== "active") {
  redirect(`/onboarding?twinId=${twin.id}&status=${twin.status}`);
}
```

### 4. Status Polling
During ingestion:
```typescript
const pollStatus = async () => {
  const res = await fetch(`/api/twins/${twinId}`);
  const twin = await res.json();
  
  switch (twin.status) {
    case "ingesting":
      showProgress("Processing content...");
      break;
    case "claims_ready":
      redirectToClaimReview();
      break;
    case "active":
      redirectToChat();
      break;
  }
};
```

## Database Schema

### twins Table
```sql
status VARCHAR(50) DEFAULT 'active' CHECK (
  status IN ('draft', 'ingesting', 'claims_ready', 
             'clarification_pending', 'persona_built', 'active')
)
```

### persona_specs Table
```sql
source VARCHAR(100)  -- 'onboarding_v2' | 'link-compile' | 'manual'
```

### Link-First Tables (Already Created)
- `persona_claims` - Atomic statements with provenance
- `persona_claim_links` - Claims ↔ Persona layer mappings
- `citation_snapshots` - Stable citation records
- `twin_status_log` - Audit trail

## Files Modified

| File | Changes |
|------|---------|
| `backend/routers/twins.py` | Added `mode` and `links` fields; conditional bootstrap; status setting |
| `backend/modules/auth_guard.py` | Already had status check in `ensure_twin_active()` |
| `backend/modules/agent.py` | Already had citation enforcement in `_build_prompt_from_v2_persona()` |

## Files Already Existing (Phase 1-6)

| File | Purpose |
|------|---------|
| `backend/migrations/20260220_add_persona_claims.sql` | Database schema for Link-First |
| `backend/routers/persona_link_compile.py` | 10 API endpoints for link compilation |
| `backend/modules/persona_claim_extractor.py` | Chunk → Atomic claims |
| `backend/modules/persona_claim_inference.py` | Claims → PersonaSpecV2 |
| `backend/modules/persona_bio_generator.py` | Claims → Bio with citations |
| `backend/modules/robots_checker.py` | robots.txt validation |
| `backend/modules/export_parsers.py` | LinkedIn/Twitter export parsers |

## Testing Checklist

### Backend
- [ ] `POST /twins` with `mode: "manual"` creates active twin with persona
- [ ] `POST /twins` with `mode: "link_first"` creates draft twin, no persona
- [ ] Chat returns 403 for non-active twins
- [ ] Legacy twins (no status) can still chat
- [ ] Link-first persona includes citation rules in system prompt

### Frontend (To Be Implemented)
- [ ] Mode selector visible when `LINK_FIRST_ENABLED=true`
- [ ] Manual mode shows steps 1-6
- [ ] Link-first mode shows new flow
- [ ] Chat blocked with redirect for non-active twins
- [ ] Status polling works during ingestion

## Summary

The backend is now architecturally aligned for Link-First Persona:

1. ✅ **State machine enforced** - Chat blocked unless `status === "active"`
2. ✅ **Mode selection supported** - `mode` field in twin creation
3. ✅ **Citation enforcement** - Prompt includes citation rules for link-first
4. ✅ **No breaking changes** - Legacy twins work unchanged

**Next: Frontend implementation** of mode selector and Link-First onboarding flow.
