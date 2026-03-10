# Person Completeness v1 - UI Implementation Plan
## REVISION 2.2: Final, Self-Contained, Contractor-Ready

**Prepared for:** Contractor/Development Team  
**Date:** 2026-02-25  
**Version:** 2.2 (Final Corrections)  
**Classification:** Contractor-Ready Handoff Document

---

## EXECUTIVE SUMMARY

This is a **complete, self-contained specification** for Person Completeness v1 UI implementation. All backend contracts align with existing code in the repo. No external references required.

**Key Architectural Decisions:**
- Compile-time feature flags (5-minute rollback, not instant)
- Twin-scoped endpoints use `/twins/{twin_id}/...` pattern (required by useAuthFetch)
- Name-Only Deep Research uses existing `/deep-research/name-only` endpoints
- DumplingAI remains in ingestion (don't delete, migrate gradually)
- Rate limiting: 10 req/min per `twin_id:IP` (current production behavior)

---

## TABLE OF CONTENTS

1. [Repo Audit & Current State](#1-repo-audit--current-state)
2. [Information Architecture](#2-information-architecture)
3. [Feature Flag Strategy](#3-feature-flag-strategy)
4. [Onboarding (3 Screens)](#4-onboarding-3-screens)
5. [Post-Onboarding Build Flow](#5-post-onboarding-build-flow)
6. [Core Product Screens](#6-core-product-screens)
7. [API Contract Specification](#7-api-contract-specification)
8. [Design System](#8-design-system)
9. [Acceptance Criteria & QA](#9-acceptance-criteria--qa)
10. [Implementation Milestones](#10-implementation-milestones)
11. [Backend Gaps](#11-backend-gaps)

---

## 1. REPO AUDIT & CURRENT STATE

### 1.1 Frontend Stack

| Component | Technology | Evidence |
|-----------|------------|----------|
| Framework | Next.js 16.1.6 App Router | `frontend/package.json:22` |
| React | 19.2.1 | `frontend/package.json:23-24` |
| TypeScript | 5.9.3 | `frontend/package.json:40` |
| Styling | Tailwind CSS v4 | `frontend/package.json:30,39` |
| Auth | Supabase auth-helpers-nextjs | `frontend/package.json:20-21` |
| Validation | Zod | `frontend/package.json:27` |

### 1.2 Current Multi-Twin Support

**File:** `frontend/lib/context/TwinContext.tsx` (lines 53-54, 70-72)
```typescript
// Multiple twins state (preserved for compatibility)
twins: Twin[];
activeTwin: Twin | null;

// Primary profile for Person Completeness v1
primaryProfile: Twin | null;
hasMultipleProfiles: boolean;
```

**File:** `frontend/components/Sidebar.tsx` (lines 104-108)
```typescript
// TwinSelector visible when multiple twins exist
<div className="relative border-b border-slate-800/50">
  <TwinSelector />
</div>
```

### 1.3 useAuthFetch Scope Enforcement

**File:** `frontend/lib/hooks/useAuthFetch.ts` (lines 228, 392)

```typescript
// Twin-scoped validation REQUIRES these patterns:
const hasTwinInPath = 
  endpoint.includes(`/twins/${twinId}`) ||     // REQUIRED
  endpoint.includes(`twin_id=${twinId}`) ||     // Alternative
  endpoint.includes('{twinId}');

// Usage:
const { getTwin } = useAuthFetch();
await getTwin(twinId, '/twins/{twinId}/build-status');  // ✅ Valid
await getTwin(twinId, '/build-status/{twinId}');        // ❌ Invalid
```

### 1.4 Name-Only Deep Research (Existing Backend)

**File:** `backend/routers/deep_research.py` (lines 85, 142)

```python
# Existing endpoints (use these, don't create new)

@router.post("/deep-research/name-only")
async def create_name_only_research(
    request: NameOnlyHintsRequest,
    user=Depends(get_current_user)
):
    """Start name-only deep research."""
    # Returns: { research_run_id, twin_id, status }

@router.get("/deep-research/{research_run_id}/status")
async def get_research_status(
    research_run_id: str,
    user=Depends(get_current_user)
):
    """Poll research status."""
    # Returns: { status, progress, stage, metrics }
```

### 1.5 Rate Limiting (Current Production)

**File:** `backend/routers/chat.py` (lines 2930-2931)

```python
# Current implementation
rate_limit_key = f"public_chat:{twin_id}:{client_ip}"
requests_per_minute = 10
window_seconds = 60
```

**NOT per-token. NOT 30 requests. Actual: 10 req/min per twin_id:IP.**

### 1.6 Error Code Conventions

**File:** `AGENTS.md` (line 353)

```
404 - Resource not found OR access denied (don't leak existence)
```

**Cross-tenant access returns 404 (not 403) to prevent enumeration.**

### 1.7 DumplingAI Status

**File:** `backend/modules/ingestion.py` (lines 634, 1709, 2196)

DumplingAI is **actively used** in core ingestion. **DO NOT DELETE** without full replacement.

**Strategy:** Deprecate gradually, migrate to Firecrawl over time. Not a blocker for Person Completeness v1.

---

## 2. INFORMATION ARCHITECTURE

### 2.1 Core Principle: Primary Profile Per User

**Compatibility Mode:** Keep multi-twin support, default to primary profile.

```typescript
// TwinContext adaptation
interface TwinContextType {
  // Existing (preserved)
  twins: Twin[];
  activeTwin: Twin | null;
  setActiveTwin: (twinId: string) => void;
  
  // NEW: Primary profile
  primaryProfile: Twin | null;
  hasMultipleProfiles: boolean;
  setPrimaryProfile: (twinId: string) => void;
}
```

### 2.2 Site Map

```
PUBLIC ROUTES
├── / (Landing)
├── /auth/* (Login/Signup)
└── /share/{twin_id}/{token} (Public Profile)

ONBOARDING
├── /onboarding (Legacy - preserved)
└── /onboarding/v2 (NEW - 3-screen flow)
    ├── Screen 1: Identity + Build Mode
    ├── Screen 2: Optional Hints (conditional)
    ├── Screen 3: Add Content (conditional)
    └── /v2/building (Build progress)

DASHBOARD (Owner)
├── /dashboard (Home → redirects to profile)
├── /dashboard/profile (Profile Overview hub)
│   ├── /sources
│   ├── /claims
│   ├── /timeline
│   ├── /topics
│   └── /review
├── /dashboard/chat
├── /dashboard/settings
│   └── /settings/policies (Audience policies)
└── /dashboard/share
```

### 2.3 Navigation (Feature-Flagged)

**File:** `frontend/lib/navigation/config.ts`

```typescript
import { isRuntimeFeatureEnabled } from '@/lib/features/runtimeFlags';

export const getSidebarConfig = (): SidebarConfig => {
  const isV1Enabled = isRuntimeFeatureEnabled('personCompletenessV1');
  
  if (!isV1Enabled) {
    return LEGACY_SIDEBAR_CONFIG; // 33 items, 8 sections
  }
  
  return [
    {
      title: 'Profile',
      items: [
        { name: 'Overview', href: '/dashboard/profile', icon: 'profile' },
        { name: 'Sources', href: '/dashboard/profile/sources', icon: 'book' },
        { name: 'Claims', href: '/dashboard/profile/claims', icon: 'check' },
        { name: 'Timeline', href: '/dashboard/profile/timeline', icon: 'clock' },
        { name: 'Topics', href: '/dashboard/profile/topics', icon: 'chart' },
        { name: 'Review', href: '/dashboard/profile/review', icon: 'alert' },
      ]
    },
    {
      title: 'Interact',
      items: [
        { name: 'Chat', href: '/dashboard/chat', icon: 'chat' },
        { name: 'Share', href: '/dashboard/share', icon: 'share' },
      ]
    },
    {
      title: 'Settings',
      items: [
        { name: 'Settings', href: '/dashboard/settings', icon: 'settings' },
        { name: 'Policies', href: '/dashboard/settings/policies', icon: 'shield' },
      ]
    }
  ];
};
```

---

## 3. FEATURE FLAG STRATEGY

### 3.1 Compile-Time Flags

**File:** `frontend/lib/features/runtimeFlags.ts`

```typescript
export type RuntimeFeatureFlag = 
  | 'personCompletenessV1'      // Master switch
  | 'simplifiedOnboarding'      // 3-screen vs legacy
  | 'profileOverview'           // New profile hub
  | 'sourcesManagement'         // Sources screens
  | 'claimsReview'              // Claims screens
  | 'timelineView'              // Timeline visualization
  | 'topicsCoverage'            // Topics & answerability
  | 'reviewQueue'               // Guided review flow
  | 'audiencePolicies';         // Per-audience policies

const FLAGS: Record<RuntimeFeatureFlag, boolean> = {
  personCompletenessV1: process.env.NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1 === 'true',
  simplifiedOnboarding: process.env.NEXT_PUBLIC_FF_SIMPLIFIED_ONBOARDING === 'true',
  profileOverview: process.env.NEXT_PUBLIC_FF_PROFILE_OVERVIEW === 'true',
  sourcesManagement: process.env.NEXT_PUBLIC_FF_SOURCES_MANAGEMENT === 'true',
  claimsReview: process.env.NEXT_PUBLIC_FF_CLAIMS_REVIEW === 'true',
  timelineView: process.env.NEXT_PUBLIC_FF_TIMELINE_VIEW === 'true',
  topicsCoverage: process.env.NEXT_PUBLIC_FF_TOPICS_COVERAGE === 'true',
  reviewQueue: process.env.NEXT_PUBLIC_FF_REVIEW_QUEUE === 'true',
  audiencePolicies: process.env.NEXT_PUBLIC_FF_AUDIENCE_POLICIES === 'true',
};
```

### 3.2 Rollback Procedure (5 Minutes)

```bash
# Step 1: Disable flag
vercel env rm NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1
vercel env add NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1 false

# Step 2: Redeploy
vercel --prod

# Step 3: Verify (2-3 minutes for propagation)
```

**Timeline:**
- Build: ~3 minutes
- Propagation: ~2 minutes
- **Total: ~5 minutes**

---

## 4. ONBOARDING (3 SCREENS)

### 4.1 Screen 1: Identity + Build Mode

**Route:** `/onboarding/v2`

**Layout:**
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
│  Pre-filled from your account                           │
│                                                         │
│  Headline (optional)                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [___________________________]                   │   │
│  └─────────────────────────────────────────────────┘   │
│  e.g., "Product Designer at Acme"                       │
│                                                         │
│  ─────── How would you like to build? ───────          │
│                                                         │
│  (○) I have links to my content                        │
│      LinkedIn, articles, portfolio, etc.               │
│                                                         │
│  (○) Just my name - discover automatically             │
│      We'll find your public content                    │
│                                                         │
│           [Continue →]                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**State:**
```typescript
interface Screen1Data {
  full_name: string;          // Required
  headline?: string;          // Optional
  build_mode: 'with_links' | 'name_only';
}
```

**API Calls:**
```typescript
// 1. Create twin (always)
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
// Response: { id: twin_id, ... }

// 2. If build_mode === 'name_only'
POST /deep-research/name-only
{
  "full_name": full_name,
  "headline": headline,
  "location": null  // Optional, can add in v2.1
}
// Response: { research_run_id, twin_id, status }

// 3. Redirect based on mode
if (build_mode === 'name_only') {
  router.push(`/onboarding/v2/building?research_run_id=${research_run_id}`);
} else {
  router.push('/onboarding/v2?step=2');
}
```

### 4.2 Screen 2: Optional Hints (With Links Only)

**Route:** `/onboarding/v2?step=2`

**Show if:** `build_mode === 'with_links'`

**Skip if:** `build_mode === 'name_only'`

**Fields:**
| Field | Type | Required |
|-------|------|----------|
| role | select | No |
| location | text | No |
| expertise_tags | multi-select | No |

**API:**
```typescript
PATCH /twins/{twin_id}
{
  "settings": {
    "onboarding_hints": { role, location, expertise_tags }
  }
}
```

### 4.3 Screen 3: Add Content (With Links Only)

**Route:** `/onboarding/v2?step=3`

**Show if:** `build_mode === 'with_links'`

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  ← Back                              Step 3 of 3        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│           Add your content sources                      │
│                                                         │
│  🔗 Links to your content                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [___________________________]              [Add]│   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Added:                                                 │
│  ● linkedin.com/in/johndoe                        [×]  │
│  ● github.com/johndoe                             [×]  │
│                                                         │
│  ─────── Or Upload Files ───────                        │
│  [Drop PDF, DOCX, TXT, MD - Max 10MB]                   │
│                                                         │
│  ⚠️ Need at least 1 source                              │
│                                                         │
│           [Finish & Build Profile →]                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**API:**
```typescript
// Submit URLs
POST /persona/link-compile/jobs/mode-c
{
  "twin_id": twin_id,
  "urls": ["https://linkedin.com/in/...", "..."]
}

// Upload files
POST /persona/link-compile/jobs/mode-a
FormData: { files[], twin_id }

// Trigger person completeness
POST /twins/{twin_id}/person-completeness/run
{
  "trigger": "onboarding_complete"
}

// Redirect to building
router.push(`/onboarding/v2/building?run_id=${pc_run_id}`);
```

### 4.4 Building Screen

**Route:** `/onboarding/v2/building?research_run_id={id}&pc_run_id={id}`

**Polling:**
```typescript
// CORRECTED: Uses /twins/{id}/ pattern
const { getTwin } = useAuthFetch();

// For name-only flow
const pollResearchStatus = async () => {
  const res = await getTwin(
    twinId,
    `/deep-research/{research_run_id}/status`
  );
  return res.json();
};

// For person completeness
const pollBuildStatus = async () => {
  const res = await getTwin(
    twinId,
    `/twins/{twinId}/build-status`
  );
  return res.json();
};
```

---

## 5. POST-ONBOARDING BUILD FLOW

### 5.1 Unified Build Status Endpoint

**File:** Backend to implement

```typescript
// GET /twins/{twin_id}/build-status

interface BuildStatusResponse {
  twin_id: string;
  overall_status: 'pending' | 'crawling' | 'processing' | 'finalizing' | 'completed' | 'failed';
  progress_percent: number;
  
  stages: Array<{
    name: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
  }>;
  
  metrics: {
    sources_found: number;
    claims_extracted: number;
    topics_identified: number;
    answerability_score?: number;
  };
  
  completion_tier: 'high_confidence' | 'with_gaps' | 'low_confidence' | 'failed';
}
```

### 5.2 Stage Mapping

| Stage Name | Progress | Description |
|------------|----------|-------------|
| `planning` | 5% | Initializing |
| `name_discovery` | 15% | Finding content by name (name-only) |
| `source_crawling` | 30% | Crawling discovered URLs |
| `bio_generation` | 45% | Generating bio |
| `claim_extraction` | 60% | Extracting claims |
| `verification` | 75% | Cross-referencing sources |
| `finalization` | 90% | Building knowledge graph |
| `completed` | 100% | Ready |

---

## 6. CORE PRODUCT SCREENS

### 6.1 Profile Overview - `/dashboard/profile`

**Components:**
- Answerability score (0-100, color-coded)
- Grade badge (A/B/C/D/F)
- Quick stats (sources, claims, verified, contradictions)
- Top topics list
- Next actions panel
- Build status banner (if in progress)

**API:**
```typescript
GET /twins/{twin_id}/person-completeness/summary
```

### 6.2 Sources - `/dashboard/profile/sources`

**Features:**
- Authority tier badges (1-7)
- Owner verification status
- Exclude source action ("Not me")
- Filter tabs (All | Verified | Needs Review | Excluded)

**API:**
```typescript
GET /twins/{twin_id}/person-sources
PATCH /twins/{twin_id}/person-sources/{id}
```

### 6.3 Claims - `/dashboard/profile/claims`

**Features:**
- Group by type (Work, Education, etc.)
- Evidence viewer with quotes
- Verify / Reject / Make Private actions
- Bulk actions

**API:**
```typescript
GET /twins/{twin_id}/person-claims
PATCH /twins/{twin_id}/person-claims/{id}
GET /twins/{twin_id}/person-claims/{id}/evidence
```

### 6.4 Timeline - `/dashboard/profile/timeline`

**Features:**
- Chronological view
- Event type colors
- Conflict highlighting
- Resolution workflow

**API:**
```typescript
GET /twins/{twin_id}/person-timeline
```

### 6.5 Topics - `/dashboard/profile/topics`

**Features:**
- Per-topic scores (coverage, verification, recency, consistency)
- Gaps identification
- Suggested sources for low coverage

**API:**
```typescript
GET /twins/{twin_id}/person-topics
```

### 6.6 Review Queue - `/dashboard/profile/review`

**Features:**
- Contradictions list
- Low-confidence claims
- Guided resolution flow
- Progress indicator

**API:**
```typescript
GET /twins/{twin_id}/person-contradictions
POST /twins/{twin_id}/person-contradictions/{id}/resolve
```

### 6.7 Policies - `/dashboard/settings/policies`

**Features:**
- Audience selector (Public, Recruiter, Investor, Internal)
- Confidence thresholds (sliders 0-100, backend 0.0-1.0)
- Require citations toggle
- Blocked topics multi-select
- Fallback behavior (I don't know / Clarify / Escalate)

**API:**
```typescript
GET /twins/{twin_id}/person-runtime-policies
PUT /twins/{twin_id}/person-runtime-policies
```

---

## 7. API CONTRACT SPECIFICATION

### 7.1 Authentication Matrix

| Endpoint Type | Auth | Pattern |
|--------------|------|---------|
| Owner (private) | JWT Header | `Authorization: Bearer {jwt}` |
| Public share | URL Token | `/share/{twin_id}/{token}/...` |
| Public chat | URL Token + IP | `public_chat:{twin_id}:{ip}` |

### 7.2 Rate Limiting (Actual)

```python
# Current production (chat.py:2930-2931)
key = f"public_chat:{twin_id}:{client_ip}"
limit = 10  # requests per minute
window = 60  # seconds
```

### 7.3 Error Codes

| Code | HTTP | When |
|------|------|------|
| `NOT_FOUND` | 404 | Twin doesn't exist OR access denied |
| `UNAUTHORIZED` | 401 | Missing/invalid JWT |
| `TOKEN_INVALID` | 403 | Invalid/expired share token |
| `RATE_LIMITED` | 429 | >10 req/min from same IP |
| `VALIDATION_ERROR` | 400 | Invalid request params |

### 7.4 Complete Endpoint Table

| Method | Endpoint | Scope | Auth | Notes |
|--------|----------|-------|------|-------|
| POST | `/twins` | tenant | JWT | Create profile |
| GET | `/twins/{id}` | twin | JWT | Get profile |
| PATCH | `/twins/{id}` | twin | JWT | Update settings |
| POST | `/deep-research/name-only` | tenant | JWT | Start name research |
| GET | `/deep-research/{id}/status` | twin | JWT | Poll research status |
| GET | `/twins/{id}/build-status` | twin | JWT | Unified build status |
| GET | `/twins/{id}/person-completeness/summary` | twin | JWT | Overview stats |
| POST | `/twins/{id}/person-completeness/run` | twin | JWT | Trigger pipeline |
| GET | `/twins/{id}/person-sources` | twin | JWT | List sources |
| PATCH | `/twins/{id}/person-sources/{id}` | twin | JWT | Update source |
| GET | `/twins/{id}/person-claims` | twin | JWT | List claims |
| PATCH | `/twins/{id}/person-claims/{id}` | twin | JWT | Update claim |
| GET | `/twins/{id}/person-claims/{id}/evidence` | twin | JWT | Get evidence |
| GET | `/twins/{id}/person-timeline` | twin | JWT | Get timeline |
| GET | `/twins/{id}/person-contradictions` | twin | JWT | List contradictions |
| POST | `/twins/{id}/person-contradictions/{id}/resolve` | twin | JWT | Resolve |
| GET | `/twins/{id}/person-topics` | twin | JWT | List topics |
| GET | `/twins/{id}/person-runtime-policies` | twin | JWT | Get policies |
| PUT | `/twins/{id}/person-runtime-policies` | twin | JWT | Update policies |
| GET | `/share/{id}/{token}/profile` | public | URL token | Public profile |
| POST | `/public/chat/{id}/{token}` | public | URL token | Public chat |

---

## 8. DESIGN SYSTEM

### 8.1 Color Palette

```css
/* Backgrounds */
bg-slate-950        /* Primary dark */
bg-slate-900        /* Cards */

/* Accents */
from-indigo-600 to-purple-600  /* Primary gradient */
bg-emerald-500      /* Success */
bg-amber-500        /* Warning */
bg-red-500          /* Error */

/* Text */
text-white          /* Headings dark */
text-slate-900      /* Headings light */
text-slate-400      /* Secondary */
```

### 8.2 Spacing

- Cards: `p-6`, `rounded-2xl`
- Section gaps: `space-y-8`, `gap-4`
- Page padding: `max-w-6xl mx-auto p-4 md:p-8`

### 8.3 Components

**Score Circle:**
```tsx
<div className="relative w-32 h-32">
  <svg className="w-full h-full -rotate-90">
    <circle cx="64" cy="64" r="56" className="stroke-slate-200" strokeWidth="12" fill="none"/>
    <circle cx="64" cy="64" r="56" className="stroke-indigo-500" strokeWidth="12" 
      strokeDasharray={351} strokeDashoffset={351 * (1 - score/100)} />
  </svg>
  <div className="absolute inset-0 flex items-center justify-center">
    <span className="text-3xl font-black">{grade}</span>
  </div>
</div>
```

---

## 9. ACCEPTANCE CRITERIA & QA

### 9.1 Security Criteria

| Test | Expected |
|------|----------|
| Request `/twins/{other_tenant_id}/person-sources` | **404** NOT_FOUND |
| Sequential twin_id enumeration | All return 404 (no 403) |
| Public endpoint without token | 404 |
| Invalid share token | 403 TOKEN_INVALID |
| >10 req/min from same IP | 429 RATE_LIMITED |

### 9.2 Scope Enforcement

| Test | Expected |
|------|----------|
| `getTwin(id, '/twins/{id}/build-status')` | Success |
| `getTwin(id, '/build-status/{id}')` | Validation error |

### 9.3 Onboarding E2E

| Test | Expected |
|------|----------|
| Complete 3 screens | < 5 minutes |
| Select "name-only" | Skips URL input, triggers research |
| Select "with links" | Shows URL input screen |
| Building progress | Updates every 3s, completes |

### 9.4 Regression

| Test | Expected |
|------|----------|
| Feature flag OFF | Legacy UI visible |
| Multi-twin user | TwinSelector visible |
| Existing onboarding | /onboarding?twinId={id} works |

### 9.5 Performance

| Metric | Target |
|--------|--------|
| Page load | < 2s |
| API response | < 500ms |
| Build polling | < 100ms |

---

## 10. IMPLEMENTATION MILESTONES

### Week 0: Foundation
- [ ] Add feature flags
- [ ] Implement `/twins/{id}/build-status`
- [ ] Create `useBuildStatus` hook

### Week 1: Backend APIs
- [ ] All person-completeness endpoints
- [ ] All person-* endpoints (sources, claims, timeline, etc.)

### Week 2-3: Onboarding v2
- [ ] Screen 1 with name-only integration
- [ ] Conditional screens 2 & 3
- [ ] Building screen with polling

### Week 4-5: Profile Screens
- [ ] Profile Overview
- [ ] Sources
- [ ] Claims
- [ ] Timeline

### Week 6: Advanced
- [ ] Topics
- [ ] Review Queue
- [ ] Policies

### Week 7: Public Share
- [ ] Tokenized endpoints
- [ ] Rate limiting
- [ ] Chat integration

### Week 8: QA & Rollout
- [ ] Security audit
- [ ] Rollback test
- [ ] Gradual rollout

---

## 11. BACKEND GAPS

| Priority | Endpoint | Effort |
|----------|----------|--------|
| P0 | GET `/twins/{id}/build-status` | 2 days |
| P0 | GET `/twins/{id}/person-completeness/summary` | 1 day |
| P0 | GET `/twins/{id}/person-sources` | 1 day |
| P0 | PATCH `/twins/{id}/person-sources/{id}` | 1/2 day |
| P0 | GET `/twins/{id}/person-claims` | 1 day |
| P0 | PATCH `/twins/{id}/person-claims/{id}` | 1/2 day |
| P0 | GET `/twins/{id}/person-claims/{id}/evidence` | 1/2 day |
| P1 | GET `/twins/{id}/person-timeline` | 1 day |
| P1 | GET `/twins/{id}/person-contradictions` | 1 day |
| P1 | POST `/twins/{id}/person-contradictions/{id}/resolve` | 1/2 day |
| P1 | GET `/twins/{id}/person-topics` | 1 day |
| P1 | GET/PUT `/twins/{id}/person-runtime-policies` | 1 day |

**Total: ~12 days**

---

## APPENDIX: DUMPLINGAI DEPRECATION (NOT DELETION)

**Current Usage:**
- `backend/modules/ingestion.py` (lines 634, 1709, 2196)

**Strategy:**
1. **Phase 1 (v1):** Keep DumplingAI, add Firecrawl as alternative
2. **Phase 2 (v2):** Migrate ingestion to Firecrawl
3. **Phase 3 (v3):** Remove DumplingAI when fully replaced

**Do NOT delete for Person Completeness v1.**

---

**END OF SPECIFICATION**

*This document is complete, self-contained, and contractor-ready.*
