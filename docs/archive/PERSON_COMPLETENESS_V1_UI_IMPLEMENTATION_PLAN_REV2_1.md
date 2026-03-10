# Person Completeness v1 - UI Implementation Plan
## REVISION 2.1: Final Corrections + Name-Only Deep Research Integration

**Prepared for:** Contractor/Development Team  
**Date:** 2026-02-25  
**Version:** 2.1 (Final Corrections)  
**Classification:** Contractor-Ready

---

## REVISION 2.1 SUMMARY

Fixes 4 contradictions identified in review + integrates Name-Only Deep Research + removes DumplingAI.

| Finding | Severity | Fix |
|---------|----------|-----|
| Rollback timing claim incorrect | **High** | Sec I.3 - Clarified compile-time flags require redeploy (~5 min, not 30 sec) |
| `build-status` scope inconsistent | **Medium** | Sec F.4 - Changed to `/twins/{twin_id}/build-status` to match validation |
| Rate-limit statement inaccurate | **Medium** | Sec A.6 - Corrected to `twin_id + client_ip` (not per-token) |
| Cross-tenant status code conflict | **Medium** | Sec H.2 - Aligned with AGENTS.md: `404` for not found/access denied |
| Name-Only Deep Research missing | **N/A** | Sec C.6 - Integrated into onboarding Screen 1 |
| DumplingAI references | **N/A** | Sec A.7 - Removed, replaced with Firecrawl/Name-Only Deep Research |

---

## A) REPO AUDIT & CORRECTIONS

### A.1 Feature Flag Reality (Compile-Time)

**Current Implementation:**
```typescript
// File: frontend/lib/features/runtimeFlags.ts
// Flags are process.env compiled at build time

export function isRuntimeFeatureEnabled(flag: RuntimeFeatureFlag): boolean {
  // Compile-time check - requires rebuild to change
  return FLAGS[flag] === true;
}
```

**Implication:**
- Rollback requires **redeploy** (~5 minutes via Vercel/Render), not instant
- For true instant rollback, flags would need to be:
  - Database-driven (Supabase table)
  - Or environment variables with edge config

**Decision:** Keep compile-time flags (simpler), document redeploy requirement.

### A.2 useAuthFetch Scope Validation (Current)

**File:** `frontend/lib/hooks/useAuthFetch.ts` (lines 228, 392)

```typescript
// Twin-scoped endpoint validation
function validateTwinEndpoint(endpoint: string, twinId: string): void {
  const hasTwinInPath = 
    endpoint.includes(`/twins/${twinId}`) ||     // <-- REQUIRED pattern
    endpoint.includes(`twin_id=${twinId}`) ||    // <-- Alternative
    endpoint.includes('{twinId}');
  
  if (!hasTwinInPath) {
    throw new Error(`Twin-scoped endpoint must include twinId: ${endpoint}`);
  }
}
```

**Correction:** All twin-scoped endpoints MUST use `/twins/{twin_id}/...` or `twin_id=` param.

### A.3 Rate Limiting (Current Production)

**File:** `backend/routers/chat.py` (line ~2930)

```python
# Current implementation
rate_limit_key = f"{twin_id}:{client_ip}"
# NOT per-token
```

**Correction:** Rate limiting is per `twin_id + client_ip`, not per share token.

### A.4 Error Code Conventions (Per AGENTS.md)

**File:** `AGENTS.md` (line 353)

```
- `404` - Resource not found OR access denied (don't leak existence)
```

**Correction:** Use `404` (not `403`) for cross-tenant/not found to prevent enumeration.

### A.5 Name-Only Deep Research Module

**File:** `backend/modules/name_deep_research_service.py`

**Purpose:** Performs deep research using ONLY a person's name (no URLs required).

**Current Usage:**
- Triggered from onboarding when user provides just name
- Discovers URLs automatically
- Generates bio, claims, timeline from discovered sources

**Integration Point:** Should be triggered from Onboarding Screen 1.

### A.6 DumplingAI Removal

**Current References:**
- `backend/modules/dumplingai_client.py` - Client module
- Onboarding flows that mention "DumplingAI-powered research"
- Documentation referencing DumplingAI

**Replacement:**
- **Firecrawl** for web scraping (`backend/modules/firecrawl_client.py`)
- **Name-Only Deep Research** for discovery without URLs
- **Exa** for web verification

---

## B) NAME-ONLY DEEP RESEARCH INTEGRATION

### B.1 Onboarding Screen 1: Identity (Revised)

**New Behavior:** Two paths based on user input.

```
┌─────────────────────────────────────────────────────────┐
│  ← Back                              Step 1 of 3        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│              Let's create your profile                  │
│                                                         │
│  Full Name *                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [___________________________]                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Headline (optional)                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [___________________________]                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ─────── How would you like to build? ───────          │
│                                                         │
│  [○] I have links (LinkedIn, articles, etc.)           │
│      → Go to Screen 3 to add URLs                      │
│                                                         │
│  [○] Just my name - auto-discover my content           │
│      → Trigger Name-Only Deep Research                 │
│                                                         │
│           [Continue →]                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Path A: User Has Links**
- Collect name + headline
- Proceed to Screen 3 (Add Content)
- User provides URLs manually
- Standard link-compile pipeline

**Path B: Name-Only Discovery**
- Collect name + headline + location (optional)
- Trigger Name-Only Deep Research immediately
- Skip Screen 3 (URLs auto-discovered)
- Go directly to Building screen

### B.2 Name-Only Deep Research API

**Trigger:**
```typescript
// On Continue with "name-only" selected
POST /name-deep-research/start
{
  "full_name": "John Doe",
  "headline": "VC at Acme",
  "location": "San Francisco, CA",  // Optional hint
  "twin_id": "..."  // Created before research starts
}

// Response
{
  "research_run_id": "uuid",
  "status": "started",
  "estimated_duration_seconds": 120
}
```

**Polling:**
```typescript
// Same unified status endpoint
GET /twins/{twin_id}/build-status
// Includes name_research stage

{
  "stages": [
    { "name": "name_discovery", "status": "completed", "progress": 100 },
    { "name": "source_crawling", "status": "running", "progress": 45 },
    // ... continues to person completeness
  ]
}
```

### B.3 Name-Only Research Stages

| Stage | Description | Duration |
|-------|-------------|----------|
| `name_discovery` | Search for person by name | 10-20s |
| `url_candidates` | Rank discovered URLs | 5s |
| `source_crawling` | Crawl top URLs (Firecrawl) | 30-60s |
| `bio_generation` | Generate bio from sources | 10s |
| `claim_extraction` | Extract structured claims | 15s |
| (continues) | → Person Completeness pipeline | - |

**Backend Integration:**
```python
# File: backend/modules/name_deep_research_service.py
# Already exists - integrate with onboarding

async def start_name_only_research(
    twin_id: str,
    full_name: str,
    headline: Optional[str],
    location: Optional[str]
) -> ResearchRun:
    """
    1. Search for person using Exa/Tavily
    2. Score and rank URL candidates
    3. Trigger crawl + ingestion
    4. Return research_run_id for polling
    """
```

### B.4 DumplingAI Removal Checklist

| Location | Action | Replacement |
|----------|--------|-------------|
| `backend/modules/dumplingai_client.py` | Delete | Use Firecrawl |
| Onboarding copy | Remove "DumplingAI-powered" | "AI-powered research" |
| API calls to DumplingAI | Migrate | Firecrawl client |
| Documentation | Remove references | Update to Firecrawl + Name-Only |

---

## C) ONBOARDING (3 SCREENS) - FINAL

### C.1 Screen 1: Identity + Build Mode Selection

**Route:** `/onboarding/v2`

**State:**
```typescript
interface Screen1Data {
  full_name: string;
  headline?: string;
  build_mode: 'with_links' | 'name_only';
}
```

**Validation:**
- Full name required
- Build mode required

**API Calls:**
```typescript
// Always create twin first
POST /twins
{
  "name": full_name,
  "mode": "link_first",
  "specialization": "vanilla",
  "settings": {
    "headline": headline,
    "build_mode": build_mode
  }
}

// If build_mode === 'name_only'
POST /name-deep-research/start
{ twin_id, full_name, headline }

// Redirect to /onboarding/v2/building
```

### C.2 Screen 2: Optional Hints (Conditional)

**Show if:** `build_mode === 'with_links'`

**Skip if:** `build_mode === 'name_only'` (research already running)

### C.3 Screen 3: Add Content (Conditional)

**Show if:** `build_mode === 'with_links'`

**Skip if:** `build_mode === 'name_only'`

### C.4 Building Screen (Unified)

**Route:** `/onboarding/v2/building`

**Polling:**
```typescript
// CORRECTED endpoint pattern
GET /twins/{twin_id}/build-status
// NOT: /build-status/{twin_id}

// Using scope-enforced fetch
const { getTwin } = useAuthFetch();
const response = await getTwin(
  twinId, 
  `/twins/{twinId}/build-status`
);
```

---

## D) API CONTRACT SPECIFICATION (CORRECTED)

### D.1 Authentication by Endpoint Type

| Endpoint Type | Auth Method | Pattern |
|--------------|-------------|---------|
| **Owner** | JWT Header | `Authorization: Bearer {jwt}` |
| **Public** | URL Token | `/share/{twin_id}/{token}/...` |
| **Public Chat** | URL Token + IP Rate Limit | `/public/chat/{twin_id}/{token}` |

### D.2 Rate Limiting (Corrected)

**Current Production:**
```python
# backend/routers/chat.py
rate_limit_key = f"{twin_id}:{client_ip}"
max_requests = 30  # per window
window_seconds = 60
```

**Per-token limiting NOT implemented.**

### D.3 Error Codes (Aligned with AGENTS.md)

| Scenario | Status | Code | Message |
|----------|--------|------|---------|
| Twin not found | 404 | NOT_FOUND | "Profile not found" |
| Cross-tenant access | 404 | NOT_FOUND | "Profile not found" |
| Invalid share token | 403 | TOKEN_INVALID | "Invalid or expired share link" |
| Rate limit exceeded | 429 | RATE_LIMITED | "Too many requests" |
| Unauthorized | 401 | UNAUTHORIZED | "Authentication required" |

**Note:** Use `404` (not `403`) for cross-tenant to prevent enumeration.

### D.4 Corrected Endpoint List

#### Build Status (Scope-Corrected)

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/build-status` | twin | `/twins/{id}/...` | JWT |

**Usage:**
```typescript
// CORRECT - uses twin-scoped fetch
const { getTwin } = useAuthFetch();
await getTwin(twinId, `/twins/{twinId}/build-status`);

// INCORRECT - bypasses scope enforcement
await authFetchStandalone(`/build-status/${twinId}`);
```

#### Name-Only Deep Research (NEW)

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| POST | `/name-deep-research/start` | twin | JWT | `{ twin_id, full_name, location? }` | `{ research_run_id }` |
| GET | `/name-deep-research/{run_id}/status` | twin | JWT | - | `{ status, progress, urls_found }` |

#### Person Completeness

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/person-completeness/summary` | twin | `/twins/{id}/...` | JWT |
| POST | `/twins/{twin_id}/person-completeness/run` | twin | `/twins/{id}/...` | JWT |

#### Sources

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/person-sources` | twin | `/twins/{id}/...` | JWT |
| PATCH | `/twins/{twin_id}/person-sources/{id}` | twin | `/twins/{id}/...` | JWT |

#### Claims

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/person-claims` | twin | `/twins/{id}/...` | JWT |
| PATCH | `/twins/{twin_id}/person-claims/{id}` | twin | `/twins/{id}/...` | JWT |

#### Timeline

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/person-timeline` | twin | `/twins/{id}/...` | JWT |

#### Contradictions

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/person-contradictions` | twin | `/twins/{id}/...` | JWT |

#### Topics

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/person-topics` | twin | `/twins/{id}/...` | JWT |

#### Policies

| Method | Endpoint | Scope | Pattern | Auth |
|--------|----------|-------|---------|------|
| GET | `/twins/{twin_id}/person-runtime-policies` | twin | `/twins/{id}/...` | JWT |
| PUT | `/twins/{twin_id}/person-runtime-policies` | twin | `/twins/{id}/...` | JWT |

#### Public (Tokenized)

| Method | Endpoint | Scope | Auth | Rate Limit |
|--------|----------|-------|------|------------|
| GET | `/share/{twin_id}/{token}/profile` | public | URL token | twin_id + IP |
| POST | `/public/chat/{twin_id}/{token}` | public | URL token | twin_id + IP |

---

## E) ROLLBACK STRATEGY (CORRECTED)

### E.1 Compile-Time Flag Reality

**File:** `frontend/lib/features/runtimeFlags.ts`

```typescript
// These are COMPILE-TIME constants
const FLAGS = {
  personCompletenessV1: process.env.NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1 === 'true',
  // ...
};
```

**Implication:** Changing flags requires rebuild + redeploy.

### E.2 Rollback Procedure (5-10 minutes)

```bash
# Step 1: Set environment variable
# Vercel Dashboard or CLI
vercel env rm NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1
vercel env add NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1 false

# Step 2: Trigger redeploy
vercel --prod

# Step 3: Verify (2 minutes)
# - Check /onboarding redirects to legacy
# - Check TwinSelector visible
# - Check existing twins accessible
```

**Timeline:**
- Vercel build: ~3 minutes
- Propagation: ~2 minutes
- **Total: ~5 minutes** (not 30 seconds)

### E.3 Emergency Database-Driven Flags (Future)

If instant rollback (<30s) required, implement:

```typescript
// Future enhancement - NOT in this plan
async function isFeatureEnabled(flag: string): Promise<boolean> {
  // Check Supabase feature_flags table
  const { data } = await supabase
    .from('feature_flags')
    .select('enabled')
    .eq('flag', flag)
    .single();
  return data?.enabled ?? false;
}
```

**Decision:** Use compile-time for v1. Document 5-minute rollback.

---

## F) ACCEPTANCE CRITERIA (CORRECTED)

### F.1 Security Criteria (Corrected)

| Criteria | Test | Expected |
|----------|------|----------|
| Cross-tenant twin | Request `/twins/{other_tenant_twin}/person-sources` | **404** (not 403) with "Profile not found" |
| Cross-tenant enumeration | Attempt sequential twin_id access | All return 404 (no distinction) |
| Public auth | Request `/share/{id}/profile` without token | 404 |
| Invalid token | Request with expired token | 403 TOKEN_INVALID |
| Rate limit | 100 requests from same IP | 429 RATE_LIMITED |

### F.2 Scope Enforcement Criteria

| Criteria | Test | Expected |
|----------|------|----------|
| Valid twin endpoint | `getTwin(twinId, '/twins/{twinId}/build-status')` | Success |
| Invalid pattern | `getTwin(twinId, '/build-status/{twinId}')` | Scope validation error |
| Standalone bypass | `authFetchStandalone('/build-status/{twinId}')` | Works (no enforcement) |

### F.3 Name-Only Deep Research Criteria

| Criteria | Test | Expected |
|----------|------|----------|
| Name-only path | Select "Just my name", continue | Triggers research, skips URL input |
| With-links path | Select "I have links", continue | Goes to URL input screen |
| Research progress | Poll `/twins/{id}/build-status` | Shows name_discovery stage |
| URL discovery | Complete name-only research | Auto-discovered URLs appear in Sources |

---

## G) IMPLEMENTATION MILESTONES (FINAL)

### G.1 Pre-Work: DumplingAI Removal

**Tasks:**
- [ ] Delete `backend/modules/dumplingai_client.py`
- [ ] Remove DumplingAI references from onboarding copy
- [ ] Migrate any DumplingAI calls to Firecrawl
- [ ] Update documentation

### G.2 Phase 0: Foundation
- [ ] Add feature flags to runtimeFlags.ts
- [ ] Create `/twins/{twin_id}/build-status` endpoint (unified)
- [ ] Create `useBuildStatus` hook with scope enforcement
- [ ] Add Name-Only Deep Research trigger endpoint

### G.3 Phase 1: Onboarding v2
- [ ] Screen 1: Identity + build mode selection
- [ ] Name-Only Deep Research integration
- [ ] Screen 3: Add Content (conditional)
- [ ] Building screen with unified status

### G.4 Phase 2-5: Profile Screens
(Unchanged from Rev 2)

### G.5 Phase 6: Public Share
- [ ] Tokenized endpoints (`/share/{id}/{token}/...`)
- [ ] Rate limiting (twin_id + IP)
- [ ] Chat integration

### G.6 Phase 7: QA & Rollout
- [ ] Security audit (404 for cross-tenant)
- [ ] Rate limit testing
- [ ] 5-minute rollback test
- [ ] Gradual rollout (10% → 50% → 100%)

---

## H) DEPLOYMENT READINESS CHECKLIST

**Before Contractor Handoff:**
- [x] Rollback timing corrected (5 min, not 30 sec)
- [x] Endpoint scopes aligned with useAuthFetch (`/twins/{id}/...`)
- [x] Rate limiting corrected (twin_id + IP)
- [x] Error codes aligned (404 for cross-tenant)
- [x] Name-Only Deep Research integrated
- [x] DumplingAI removal specified
- [x] All 7 previous findings fixed

**Before Production:**
- [ ] DumplingAI fully removed
- [ ] Name-Only Deep Research endpoints implemented
- [ ] All endpoints use `/twins/{id}/...` pattern
- [ ] 404 returned for cross-tenant (not 403)
- [ ] Rate limiting verified (twin_id + IP)
- [ ] Rollback procedure tested (5 min)

---

**END OF REVISION 2.1**

*Final corrections applied. Contractor-ready.*
