# Person Completeness v1 - UI Implementation Plan
## REVISION 2.3: Exact Backend Routes, Explicit Gaps, Contractor-Ready

**Prepared for:** Contractor/Development Team  
**Date:** 2026-02-25  
**Version:** 2.3 (Final Corrections)  
**Classification:** Contractor-Ready Handoff Document

---

## CRITICAL CORRECTIONS IN THIS REVISION

| Finding | Severity | Fix |
|---------|----------|-----|
| Deep research routes wrong | **High** | Use actual routes: `/deep-research/runs` and `/deep-research/runs/{run_id}` |
| Public profile endpoint doesn't exist | **High** | Marked as **NEW endpoint to implement** in backend gaps |
| TwinContext state inaccurate | **Medium** | Clarified: `primaryProfile` is PROPOSED, not current |
| Feature flags not in code | **Medium** | Clarified: All new flags are PROPOSED additions |
| Deep research scope wrong | **Medium** | Corrected: Tenant-scoped (not twin-scoped) |

---

## 1. REPO AUDIT: CURRENT VS PROPOSED

### 1.1 Current Frontend State (Verified)

**File:** `frontend/lib/context/TwinContext.tsx` (lines 53-54)
```typescript
// CURRENT STATE (verified in repo)
interface TwinContextType {
  twins: Twin[];
  activeTwin: Twin | null;
  setActiveTwin: (twinId: string) => void;
  // ... other existing methods
}

// PROPOSED ADDITIONS for Person Completeness v1:
primaryProfile: Twin | null;         // NEW - Add this
hasMultipleProfiles: boolean;        // NEW - Add this
setPrimaryProfile: (twinId: string) => void;  // NEW - Add this
```

### 1.2 Current Feature Flags (Verified)

**File:** `frontend/lib/features/runtimeFlags.ts` (current)
```typescript
// CURRENT FLAGS (verified in repo)
export type RuntimeFeatureFlag = 
  | 'memoryCenter'
  | 'privacyControls' 
  | 'publishControls'
  | 'dashboardChat';

// PROPOSED NEW FLAGS to add:
| 'personCompletenessV1'
| 'simplifiedOnboarding'
| 'profileOverview'
| 'sourcesManagement'
| 'claimsReview'
| 'timelineView'
| 'topicsCoverage'
| 'reviewQueue'
| 'audiencePolicies';
```

### 1.3 Deep Research: Actual Backend Routes

**File:** `backend/routers/deep_research.py` (lines 86, 143)

```python
# ACTUAL CURRENT ENDPOINTS (verified in repo)

@router.post("/deep-research/runs")
async def create_deep_research_run(
    request: CreateDeepResearchRunRequest,
    user=Depends(get_current_user)
):
    """Start name-only deep research."""
    # Returns: { research_run_id, twin_id, status, estimated_duration }

@router.get("/deep-research/runs/{research_run_id}")
async def get_deep_research_status(
    research_run_id: str,
    user=Depends(get_current_user)
):
    """Poll research status."""
    # Returns: { research_run_id, twin_id, status, progress, stage, metrics }
```

**Auth:** Tenant-scoped (`require_tenant`), NOT twin-scoped.

### 1.4 Public Share: Actual Current Routes

**File:** `backend/routers/chat.py` (lines 1138, 2860), `auth.py` (line 666)

```python
# ACTUAL CURRENT ENDPOINTS (verified in repo)

# Share resolution (public, no auth)
GET /share/resolve/{handle}

# Share validation (public, token in path)
GET /public/validate-share/{twin_id}/{token}

# Public chat (public, token in path, rate limited)
POST /public/chat/{twin_id}/{token}

# MISSING (needs implementation):
GET /share/{twin_id}/{token}/profile    # <-- DOES NOT EXIST
```

### 1.5 Rate Limiting (Current)

**File:** `backend/routers/chat.py` (lines 2930-2931)
```python
# CURRENT BEHAVIOR (verified in repo)
rate_limit_key = f"public_chat:{twin_id}:{client_ip}"
requests_per_minute = 10
window_seconds = 60
```

### 1.6 useAuthFetch Scope Validation (Current)

**File:** `frontend/lib/hooks/useAuthFetch.ts` (lines 228, 392)

```typescript
// Twin-scoped endpoints MUST include:
endpoint.includes(`/twins/${twinId}`) ||
endpoint.includes(`twin_id=${twinId}`)

// Tenant-scoped endpoints:
// - No /twins/ path
// - No twin_id query param (unless allowlisted)
```

---

## 2. CORRECTED API CONTRACT

### 2.1 Scope Classification Table

| Endpoint | Current/Proposed | Scope | Auth Pattern | Notes |
|----------|------------------|-------|--------------|-------|
| `POST /deep-research/runs` | Current | **Tenant** | JWT header | No twin_id in path |
| `GET /deep-research/runs/{id}` | Current | **Tenant** | JWT header | Uses research_run_id |
| `POST /twins` | Current | Tenant | JWT header | Creates twin |
| `GET /twins/{id}` | Current | **Twin** | JWT header | /twins/{id} pattern ✅ |
| `GET /twins/{id}/build-status` | **PROPOSED** | **Twin** | JWT header | NEW - Must use /twins/{id}/ |
| `GET /twins/{id}/person-sources` | **PROPOSED** | **Twin** | JWT header | NEW - Must use /twins/{id}/ |
| `GET /share/{id}/{token}/profile` | **PROPOSED** | **Public** | URL token | NEW - Implement |
| `POST /public/chat/{id}/{token}` | Current | **Public** | URL token | Existing |

### 2.2 Corrected Endpoint Usage

```typescript
// DEEP RESEARCH (Tenant-scoped, NOT twin-scoped)
const { post, get } = useAuthFetch();

// Correct - no twin_id in path, uses tenant auth
const response = await post('/deep-research/runs', {
  full_name: "John Doe",
  headline: "VC at Acme"
});

// Correct - uses research_run_id, not twin_id
const status = await get(`/deep-research/runs/${researchRunId}`);

// TWIN-SCOPED (Must use /twins/{id}/ pattern)
const { getTwin } = useAuthFetch();

// Correct
const sources = await getTwin(
  twinId, 
  '/twins/{twinId}/person-sources'
);

// Incorrect - would fail scope validation
const sources = await getTwin(
  twinId, 
  '/person-sources?twin_id={twinId}'  // ❌ Not /twins/{id}/
);
```

### 2.3 Complete Endpoint Specification

#### Existing Backend (Use As-Is)

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| POST | `/deep-research/runs` | Tenant | JWT | `{ full_name, headline?, location?, mode: "name_only" }` | `{ research_run_id, twin_id, status }` |
| GET | `/deep-research/runs/{id}` | Tenant | JWT | - | `{ research_run_id, twin_id, status, progress, stage, metrics }` |
| GET | `/share/resolve/{handle}` | Public | None | - | `{ twin_id, share_token }` |
| GET | `/public/validate-share/{twin_id}/{token}` | Public | URL token | - | `{ valid, twin_id, settings }` |
| POST | `/public/chat/{twin_id}/{token}` | Public | URL token | `{ message }` | `{ response, citations? }` |

#### New Backend (To Implement)

| Method | Endpoint | Scope | Priority | Notes |
|--------|----------|-------|----------|-------|
| GET | `/twins/{twin_id}/build-status` | Twin | P0 | Unified status polling |
| GET | `/twins/{twin_id}/person-completeness/summary` | Twin | P0 | Overview stats |
| POST | `/twins/{twin_id}/person-completeness/run` | Twin | P0 | Trigger pipeline |
| GET | `/twins/{twin_id}/person-sources` | Twin | P0 | List sources |
| PATCH | `/twins/{twin_id}/person-sources/{id}` | Twin | P0 | Update source |
| GET | `/twins/{twin_id}/person-claims` | Twin | P0 | List claims |
| PATCH | `/twins/{twin_id}/person-claims/{id}` | Twin | P0 | Update claim |
| GET | `/twins/{twin_id}/person-claims/{id}/evidence` | Twin | P0 | Get evidence |
| GET | `/twins/{twin_id}/person-timeline` | Twin | P1 | Timeline |
| GET | `/twins/{twin_id}/person-contradictions` | Twin | P1 | Contradictions |
| POST | `/twins/{twin_id}/person-contradictions/{id}/resolve` | Twin | P1 | Resolve |
| GET | `/twins/{twin_id}/person-topics` | Twin | P1 | Topics |
| GET | `/twins/{twin_id}/person-runtime-policies` | Twin | P1 | Get policies |
| PUT | `/twins/{twin_id}/person-runtime-policies` | Twin | P1 | Update policies |
| GET | `/share/{twin_id}/{token}/profile` | Public | P1 | **NEW** - Public profile data |

---

## 3. ONBOARDING FLOW (CORRECTED)

### 3.1 Screen 1: Identity + Build Mode

**Route:** `/onboarding/v2`

**API Integration:**
```typescript
// 1. Create twin (same for both modes)
POST /twins
{
  "name": full_name,
  "mode": "link_first",
  "specialization": "vanilla",
  "settings": {
    "headline": headline,
    "build_mode": build_mode  // 'with_links' | 'name_only'
  }
}

// 2. If build_mode === 'name_only'
// CORRECTED: Use /deep-research/runs (NOT /name-deep-research/start)
POST /deep-research/runs
{
  "full_name": full_name,
  "headline": headline,
  "location": location,  // optional
  "mode": "name_only"
}
// Response: { research_run_id, twin_id, status }

// 3. Redirect
if (build_mode === 'name_only') {
  router.push(`/onboarding/v2/building?research_run_id=${research_run_id}`);
} else {
  router.push('/onboarding/v2?step=2');
}
```

### 3.2 Building Screen: Polling

**Route:** `/onboarding/v2/building?research_run_id={id}`

**Polling Logic:**
```typescript
// For name-only flow: Poll deep research status
const pollResearchStatus = async () => {
  // CORRECTED: Tenant-scoped, NOT twin-scoped
  const { get } = useAuthFetch();
  const res = await get(`/deep-research/runs/${researchRunId}`);
  return res.json();
};

// When research completes, trigger person completeness
// Then poll unified build status
const pollBuildStatus = async () => {
  // CORRECTED: Twin-scoped, must use /twins/{id}/
  const { getTwin } = useAuthFetch();
  const res = await getTwin(
    twinId,
    '/twins/{twinId}/build-status'
  );
  return res.json();
};
```

---

## 4. BACKEND GAPS (CORRECTED & EXPANDED)

### 4.1 Critical New Endpoints

| Priority | Endpoint | Scope | Effort | Dependencies |
|----------|----------|-------|--------|--------------|
| **P0** | `GET /twins/{id}/build-status` | Twin | 2 days | Combines research + PC status |
| **P0** | `GET /share/{twin_id}/{token}/profile` | Public | 1 day | **Previously missed** - Public profile data |
| P0 | `GET /twins/{id}/person-completeness/summary` | Twin | 1 day | Aggregates all tables |
| P0 | `GET /twins/{id}/person-sources` | Twin | 1 day | List sources |
| P0 | `PATCH /twins/{id}/person-sources/{id}` | Twin | 1/2 day | Update verification |
| P0 | `GET /twins/{id}/person-claims` | Twin | 1 day | List claims |
| P0 | `PATCH /twins/{id}/person-claims/{id}` | Twin | 1/2 day | Approve/reject |
| P1 | `GET /twins/{id}/person-timeline` | Twin | 1 day | Timeline events |
| P1 | `GET /twins/{id}/person-contradictions` | Twin | 1 day | Contradictions |
| P1 | `GET /twins/{id}/person-topics` | Twin | 1 day | Topic profiles |
| P1 | `GET/PUT /twins/{id}/person-runtime-policies` | Twin | 1 day | Audience policies |

### 4.2 Public Profile Endpoint Specification

**NEW ENDPOINT TO IMPLEMENT:**

```python
@router.get("/share/{twin_id}/{token}/profile")
async def get_public_profile(
    twin_id: str,
    token: str,
):
    """
    Return public-safe profile data.
    Validates token against share_links table.
    """
    # 1. Validate token
    share = await validate_share_token(twin_id, token)
    if not share:
        raise HTTPException(403, "Invalid share token")
    
    # 2. Get public-safe data
    return {
        "twin_id": twin_id,
        "name": twin.name,
        "headline": twin.settings.get("headline"),
        "answerability_score": get_public_answerability(twin_id),
        "public_topics": get_public_topics(twin_id),
        "citations_enabled": policies.require_citation,
    }
```

**Frontend Usage:**
```typescript
// Public page (no JWT)
const response = await fetch(
  `/share/${twinId}/${token}/profile`
);
const profile = await response.json();
```

---

## 5. IMPLEMENTATION MILESTONES (CORRECTED)

### Week 0: Foundation
- [ ] Add **PROPOSED** flags to `runtimeFlags.ts`
- [ ] Add **PROPOSED** `primaryProfile` state to `TwinContext`
- [ ] Implement `GET /twins/{id}/build-status`
- [ ] Implement `GET /share/{id}/{token}/profile` **(previously missed)**
- [ ] Create `useBuildStatus` hook

### Week 1: Backend APIs
- [ ] All `/twins/{id}/person-*` endpoints
- [ ] Scope validation tests

### Week 2-3: Onboarding v2
- [ ] Screen 1 with CORRECTED deep research integration (`/deep-research/runs`)
- [ ] Building screen with CORRECTED polling

### Week 4-8: Profile, QA, Rollout
(Unchanged from previous)

---

## 6. VERIFICATION CHECKLIST

**Before Handoff:**
- [x] Deep research routes: `/deep-research/runs` and `/deep-research/runs/{id}`
- [x] Deep research scope: Tenant (NOT twin)
- [x] Public profile endpoint: Added to gaps as NEW
- [x] TwinContext: Clarified current vs proposed
- [x] Feature flags: Clarified current vs proposed
- [x] All twin-scoped endpoints: Use `/twins/{id}/` pattern
- [x] DumplingAI: Deprecation (not deletion)
- [x] Rate limits: 10/min per twin_id:IP
- [x] Error codes: 404 for cross-tenant

**Contractor Verification Commands:**
```bash
# Verify deep research routes exist
grep -n "@router.post.*runs" backend/routers/deep_research.py
grep -n "@router.get.*runs" backend/routers/deep_research.py

# Verify public share endpoints exist
grep -n "@router.*share" backend/routers/chat.py

# Verify TwinContext current state
grep -n "twins: Twin\[\]" frontend/lib/context/TwinContext.tsx
grep -n "activeTwin: Twin" frontend/lib/context/TwinContext.tsx

# Verify useAuthFetch patterns
grep -n "/twins/" frontend/lib/hooks/useAuthFetch.ts
```

---

**END OF REVISION 2.3**

*All backend routes verified. All gaps explicitly listed. Contractor-ready.*
