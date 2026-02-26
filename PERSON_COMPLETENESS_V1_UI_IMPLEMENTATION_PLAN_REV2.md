# Person Completeness v1 - UI Implementation Plan
## REVISION 2: Production-Ready with Rollout Strategy

**Prepared for:** Contractor/Development Team  
**Date:** 2026-02-25  
**Version:** 2.0 (Post-Review)  
**Classification:** Contractor-Ready with Migration Guards

---

## REVISION SUMMARY

This revision addresses 7 critical gaps identified in review:

| Finding | Severity | Fix in This Revision |
|---------|----------|---------------------|
| Public auth contract inconsistent | **High** | Sec A.6 - Preserves tokenized sharing, no JWT for public |
| "One profile per user" incompatible | **High** | Sec B.4 - Compatibility mode with primary profile selection |
| Navigation hard-cut | **High** | Sec I.3 - Feature-flagged rollout with rollback |
| Build progress mixing pipelines | **Medium** | Sec D.2 - Unified status API contract |
| Endpoint scope underspecified | **Medium** | Sec F.5 - Explicit scope classification per endpoint |
| Onboarding route migration | **Medium** | Sec C.5 - Backward-compatible routing |
| QA thin on security | **Medium** | Sec H.8 - Expanded negative test cases |

---

## A) REPO AUDIT & CONTRACT ALIGNMENT

### A.1 Current System State (Verified)

**Public Sharing (Current Production):**
```typescript
// File: frontend/app/share/[twin_id]/[token]/page.tsx
// Current: Tokenized public access
/share/{twin_id}/{token} → resolves to public chat

// File: backend/routers/chat.py (public routes)
// Current: Token validation + rate limiting
POST /public/chat/{twin_id}/{token}
Headers: None (token in URL)
Validation: share_links table lookup
Rate limiting: Applied per token
```

**Multi-Twin Support (Current Production):**
```typescript
// File: frontend/lib/context/TwinContext.tsx
// Lines 53-54: Multiple twins state
twins: Twin[];
activeTwin: Twin | null;

// File: frontend/components/Sidebar.tsx  
// Lines 104-108: TwinSelector component
<div className="relative border-b border-slate-800/50">
  <TwinSelector />
</div>

// File: backend/routers/auth.py
// Returns all twins per tenant
```

### A.2 Navigation Current State

**File:** `frontend/lib/navigation/config.ts` (Current)
```typescript
export const SIDEBAR_CONFIG: SidebarConfig = [
  { title: 'Build', items: [...] },      // 8 items
  { title: 'Interact', items: [...] },   // 4 items
  { title: 'Test & Review', items: [...] }, // 8 items
  { title: 'Insights', items: [...] },   // 2 items
  { title: 'Share & Access', items: [...] }, // 3 items
  { title: 'Automation', items: [...] }, // 2 items
  { title: 'Settings', items: [...] },   // 5 items
  { title: 'System', items: [...] },     // 1 item
];
// Total: 33 navigation items across 8 sections
```

### A.3 Existing Runtime Flags

**File:** `frontend/lib/features/runtimeFlags.ts`
```typescript
export type RuntimeFeatureFlag = 
  | 'memoryCenter'
  | 'privacyControls' 
  | 'publishControls'
  | 'dashboardChat'
  | 'personCompletenessV1'  // NEW - Add this
  | 'simplifiedOnboarding';  // NEW - Add this
```

### A.4 Backend Tables Verified

| Table | Exists | Person Completeness v1 |
|-------|--------|----------------------|
| `twins` | ✅ | Reused |
| `person_source_registry` | ✅ | Uses |
| `person_claims` | ✅ | Uses |
| `person_claim_evidence_spans` | ✅ | Uses |
| `person_timeline_events` | ✅ | Uses |
| `person_topic_profiles` | ✅ | Uses |
| `person_contradictions` | ✅ | Uses |
| `person_answerability_scores` | ✅ | Uses |
| `person_runtime_policies` | ✅ | Uses |
| `person_completeness_runs` | ✅ | Uses |
| `research_runs` | ✅ | Deep research status |
| `share_links` | ✅ | Public access tokens |

### A.5 Current Onboarding Flow

**File:** `frontend/app/onboarding/page.tsx` (Lines 1-859)
- Single state-machine page
- Resume via `?twinId={id}` parameter
- Internal steps: `welcome → link_suggestions → add_sources → source_review → research → building → profile`

### A.6 Public API Contract (CORRECTED)

**❌ INCORRECT (from Rev 1):**
```typescript
// DO NOT IMPLEMENT - Breaks security
GET /public-profiles/{twin_id}      // No token!
POST /public-chat/{twin_id}         // No token!
```

**✅ CORRECT (Preserves Current Security):**
```typescript
// Public endpoints use tokenized URLs (existing pattern)
// File: backend/routers/chat.py pattern

// Profile resolution (existing)
GET /share/resolve/{handle}
Response: { twin_id, share_token }

// Public profile data (tokenized)
GET /share/{twin_id}/{token}/profile
Auth: Token in URL, validated against share_links table

// Public chat (tokenized)
POST /public/chat/{twin_id}/{token}
Auth: Token in URL + optional session
Rate limiting: Per-token limits enforced

// Public profile config (what visitor sees)
GET /share/{twin_id}/{token}/config
Response: { 
  profile_name,
  headline,
  answerability_score,
  allowed_topics[],
  citations_enabled,
  require_citation
}
```

**Security Preservation:**
- No JWT required for public (existing behavior)
- Token validation against `share_links` table
- Rate limiting per token
- Publish controls respected

---

## B) INFORMATION ARCHITECTURE (REVISED)

### B.1 Core Principle: Primary Profile Per User (Compatibility Mode)

**Problem:** Complete removal of multi-twin breaks existing tenants.

**Solution:** "Primary Profile" Pattern

```typescript
// File: frontend/lib/context/TwinContext.tsx (Adapted)
interface TwinContextType {
  // Existing (preserved for backward compatibility)
  twins: Twin[];
  activeTwin: Twin | null;
  setActiveTwin: (twinId: string) => void;
  
  // NEW: Primary profile for Person Completeness v1
  primaryProfile: Twin | null;
  hasMultipleProfiles: boolean;
  
  // Actions
  setPrimaryProfile: (twinId: string) => void; // Sets both activeTwin and persists
}

// NEW: Profile context for Person Completeness v1 screens
// Uses activeTwin internally but provides profile-centric naming
interface ProfileContextType {
  profile: Twin | null;  // Alias for activeTwin
  profileId: string | null;
  isLoading: boolean;
  refreshProfile: () => Promise<void>;
}
```

**User Experience:**
| Scenario | UX |
|----------|-----|
| User has 1 twin | Auto-select as primary, hide selector |
| User has 2+ twins | Show primary profile, "Switch Profile" in settings |
| First-time user | Create profile (twin) in onboarding |

### B.2 Compatibility: When to Show TwinSelector

**Keep TwinSelector in Sidebar IF:**
- Feature flag `personCompletenessV1` is OFF, OR
- User has `role === 'admin'` and multiple twins, OR
- Explicit query param `?showSelector=true`

**Hide TwinSelector (Default for Person Completeness v1):**
- Feature flag ON, AND
- User has single primary profile selected

### B.3 Site Map (Preserving Existing Routes)

```
EXISTING ROUTES (Preserved)
├── /dashboard/* (existing 33 routes)
├── /share/{twin_id} → redirects to /share/{twin_id}/{token}
├── /share/{twin_id}/{token} (existing public share)
├── /onboarding (existing state-machine)
└── /onboarding?twinId={id} (existing resume)

NEW ROUTES (Person Completeness v1)
├── /dashboard/profile (NEW - Profile Overview hub)
│   ├── /sources
│   ├── /claims  
│   ├── /timeline
│   ├── /topics
│   └── /review
├── /onboarding/v2 (NEW - 3-screen flow)
│   └── /v2/building (NEW - build progress)
└── /settings/policies (NEW - audience policies)

DEPRECATED (Redirect to new)
├── /dashboard/twins/{id} → /dashboard/profile
└── /dashboard/brain → /dashboard/profile
```

### B.4 Feature Flag Strategy

**File:** `frontend/lib/features/runtimeFlags.ts`
```typescript
export const PERSON_COMPLETENESS_FLAGS = {
  // Master switch - gates all Person Completeness v1 features
  personCompletenessV1: {
    default: false,
    description: 'Enable Person Completeness v1 UI and APIs'
  },
  
  // Sub-features for gradual rollout
  simplifiedOnboarding: {
    default: false,
    description: 'Enable 3-screen onboarding (vs legacy multi-step)',
    dependsOn: ['personCompletenessV1']
  },
  
  profileOverview: {
    default: false,
    description: 'Enable new Profile Overview hub',
    dependsOn: ['personCompletenessV1']
  },
  
  sourcesManagement: {
    default: false,
    description: 'Enable Sources management screens',
    dependsOn: ['personCompletenessV1']
  },
  
  claimsReview: {
    default: false,
    description: 'Enable Claims review screens',
    dependsOn: ['personCompletenessV1']
  },
  
  timelineView: {
    default: false,
    description: 'Enable Timeline visualization',
    dependsOn: ['personCompletenessV1']
  },
  
  topicsCoverage: {
    default: false,
    description: 'Enable Topics & Answerability screens',
    dependsOn: ['personCompletenessV1']
  },
  
  reviewQueue: {
    default: false,
    description: 'Enable Review Queue workflow',
    dependsOn: ['personCompletenessV1', 'claimsReview']
  },
  
  audiencePolicies: {
    default: false,
    description: 'Enable audience-based policies (replaces multi-twin)',
    dependsOn: ['personCompletenessV1']
  }
};
```

**Environment Override:**
```bash
# In Vercel/Render env
NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1=true
NEXT_PUBLIC_FF_SIMPLIFIED_ONBOARDING=true
```

### B.5 Navigation (Feature-Flagged)

**File:** `frontend/lib/navigation/config.ts` (Revised)
```typescript
import { isRuntimeFeatureEnabled } from '@/lib/features/runtimeFlags';

export const getSidebarConfig = (): SidebarConfig => {
  const isPersonCompletenessEnabled = isRuntimeFeatureEnabled('personCompletenessV1');
  
  if (!isPersonCompletenessEnabled) {
    // Return LEGACY config (current 33 items)
    return LEGACY_SIDEBAR_CONFIG;
  }
  
  // Return SIMPLIFIED config (Person Completeness v1)
  return [
    {
      title: 'Profile',
      items: [
        { name: 'Overview', href: '/dashboard/profile', icon: 'profile', featureFlag: 'profileOverview' },
        { name: 'Sources', href: '/dashboard/profile/sources', icon: 'book', featureFlag: 'sourcesManagement' },
        { name: 'Claims', href: '/dashboard/profile/claims', icon: 'check', featureFlag: 'claimsReview' },
        { name: 'Timeline', href: '/dashboard/profile/timeline', icon: 'clock', featureFlag: 'timelineView' },
        { name: 'Topics', href: '/dashboard/profile/topics', icon: 'chart', featureFlag: 'topicsCoverage' },
        { name: 'Review', href: '/dashboard/profile/review', icon: 'alert', featureFlag: 'reviewQueue' },
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
        { name: 'Policies', href: '/dashboard/settings/policies', icon: 'shield', featureFlag: 'audiencePolicies' },
      ]
    },
    // Keep essential operational items for admins
    {
      title: 'Advanced',
      items: [
        { name: 'Knowledge', href: '/dashboard/knowledge', icon: 'book' },
        { name: 'Memory Center', href: '/dashboard/memory', icon: 'memory', featureFlag: 'memoryCenter' },
      ]
    }
  ];
};
```

---

## C) ONBOARDING (3 SCREENS) - WITH BACKWARD COMPATIBILITY

### C.1 Route Strategy

**New 3-screen flow:** `/onboarding/v2/*`
**Legacy flow:** `/onboarding` (preserved)

**Migration:**
```typescript
// middleware.ts or page logic
if (isRuntimeFeatureEnabled('simplifiedOnboarding')) {
  // New users go to v2
  if (pathname === '/onboarding' && !searchParams.has('legacy')) {
    redirect('/onboarding/v2');
  }
} else {
  // All users go to legacy
  if (pathname === '/onboarding/v2') {
    redirect('/onboarding');
  }
}

// Resume compatibility
// Old: /onboarding?twinId={id}
// New: /onboarding/v2?profileId={id} (same twin_id, renamed param)
```

### C.2 Screen 1: Identity

**Route:** `/onboarding/v2`

**Changes from Rev 1:**
- Pre-fill from Supabase `user.user_metadata.full_name`
- If user has existing twin(s), offer "Use existing profile" vs "Create new"

**Existing Twin Detection:**
```typescript
// Check for existing twins on mount
const { twins, activeTwin } = useTwin();

useEffect(() => {
  if (twins.length === 1) {
    // Auto-select single twin as profile
    setProfileId(twins[0].id);
  } else if (twins.length > 1) {
    // Show selector: "Which profile to enhance?"
    setShowExistingProfileSelector(true);
  }
}, [twins]);
```

### C.3 Screen 2: Optional Hints

**Route:** `/onboarding/v2?step=2`

Unchanged from Rev 1.

### C.4 Screen 3: Add Content

**Route:** `/onboarding/v2?step=3`

**API Integration:**
```typescript
// Reuse existing endpoints
POST /persona/link-compile/jobs/mode-c  // URLs
POST /persona/link-compile/jobs/mode-a  // Files

// Trigger deep research (existing)
POST /twins/{twin_id}/research/{research_run_id}/continue-claims

// Trigger person completeness (new)
POST /person-completeness/run
```

### C.5 Building Screen - Unified Status API

**Route:** `/onboarding/v2/building?run_id={run_id}&research_run_id={research_run_id}`

**Problem (Rev 1):** Mixed two different status APIs.

**Solution:** Unified status endpoint.

**Backend Unified Status API:**
```typescript
// NEW ENDPOINT: GET /build-status/{twin_id}
// Combines research_runs + person_completeness_runs

interface UnifiedBuildStatusResponse {
  twin_id: string;
  research_run_id?: string;
  person_completeness_run_id?: string;
  
  overall_status: 'pending' | 'crawling' | 'ingesting' | 'processing' | 'finalizing' | 'completed' | 'failed';
  progress_percent: number;  // 0-100
  
  stages: Array<{
    name: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
    started_at?: string;
    completed_at?: string;
  }>;
  
  metrics: {
    sources_found: number;
    claims_extracted: number;
    topics_identified: number;
    answerability_score?: number;
  };
  
  // For completion handling
  completion_tier: 'high_confidence' | 'with_gaps' | 'low_confidence' | 'failed';
  next_actions: Array<{
    type: string;
    description: string;
    link: string;
  }>;
}
```

**Stage Mapping (Unified):**
```
Research Stage → UI Stage → Progress
PLANNING → planning → 5%
CRAWLING → discovering → 15%
INGESTING → processing → 30%
BIO_GENERATED → analyzing → 40%
CLAIMS_ENRICHMENT → extracting → 55%
WEB_VERIFICATION → verifying → 70%
CLAIMS_FINALIZED → finalizing → 85%
RUNTIME_PUBLISHED → publishing → 95%
COMPLETED → completed → 100%

Person Completeness (parallel/sequential):
SOURCE_REGISTRY_BUILT → processing
CLAIMS_EXTRACTED → extracting
TIMELINE_BUILT → analyzing
TOPIC_GRAPH_BUILT → finalizing
ANSWERABILITY_SCORED → completed
```

---

## D) POST-ONBOARDING BUILD FLOW (REVISED)

### D.1 Unified Progress Polling

```typescript
// File: frontend/lib/hooks/useBuildStatus.ts

interface UseBuildStatusOptions {
  twinId: string;
  researchRunId?: string;
  personCompletenessRunId?: string;
  pollingInterval?: number;
}

export function useBuildStatus(options: UseBuildStatusOptions) {
  const { twinId, pollingInterval = 3000 } = options;
  
  const fetchStatus = async (): Promise<UnifiedBuildStatusResponse> => {
    const response = await authFetchStandalone(
      `/build-status/${twinId}`
    );
    return response.json();
  };
  
  // React Query or SWR for polling
  const { data, isLoading, error } = useQuery({
    queryKey: ['build-status', twinId],
    queryFn: fetchStatus,
    refetchInterval: (data) => {
      // Dynamic polling based on status
      if (data?.overall_status === 'completed') return false;
      if (data?.overall_status === 'failed') return false;
      if (data?.progress_percent > 80) return 10000; // Slow down near end
      return pollingInterval;
    }
  });
  
  return { status: data, isLoading, error };
}
```

### D.2 Completion Handling

```typescript
// On completion, redirect based on tier
const handleComplete = (status: UnifiedBuildStatusResponse) => {
  switch (status.completion_tier) {
    case 'high_confidence':
      router.push('/dashboard/profile?onboarding=complete&grade=A');
      break;
    case 'with_gaps':
      router.push('/dashboard/profile?onboarding=complete&grade=B&gaps=true');
      break;
    case 'low_confidence':
      router.push('/dashboard/profile/sources?onboarding=complete&needs_sources=true');
      break;
    case 'failed':
      router.push('/onboarding/v2/building?failed=true');
      break;
  }
};
```

---

## E) CORE PRODUCT SCREENS

Unchanged from Rev 1 except:

1. **Twin terminology** → "Profile" in all UI copy
2. **Navigation** controlled by feature flags
3. **Back button** in profile screens returns to `/dashboard/profile`

---

## F) API CONTRACT SPECIFICATION (REVISED)

### F.1 Authentication by Endpoint Type

| Endpoint Type | Auth Method | Example |
|--------------|-------------|---------|
| **Owner (Private)** | Supabase JWT in header | `Authorization: Bearer {jwt}` |
| **Public Share** | Token in URL path | `/share/{twin_id}/{token}` |
| **Public Chat** | Token in URL path + optional session | `/public/chat/{twin_id}/{token}` |
| **Tenant-scoped** | Supabase JWT + tenant resolution | Same as Owner |

### F.2 Error Format (Standardized)

```typescript
interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  status: number;
}

// Common error codes
const ERROR_CODES = {
  // Auth errors
  UNAUTHORIZED: 'Authentication required',
  FORBIDDEN: 'Access denied to this resource',
  TOKEN_EXPIRED: 'Share token has expired',
  
  // Tenant/Twin errors
  TWIN_NOT_FOUND: 'Profile not found',
  NOT_OWNER: 'You do not own this profile',
  
  // Validation errors
  VALIDATION_ERROR: 'Invalid request parameters',
  MISSING_SOURCE: 'At least one source is required',
  
  // Pipeline errors
  PIPELINE_RUNNING: 'Build already in progress',
  PIPELINE_FAILED: 'Profile build failed'
};
```

### F.3 Pagination & Filtering

```typescript
// Standard pagination
?page=1&per_page=20&sort=-created_at

// Standard filters
?status=verified&claim_type=work_experience
?min_confidence=0.7
?search=keyword
```

### F.4 Complete Endpoint Specification

#### Build Status (NEW - Unified)

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/build-status/{twin_id}` | twin | JWT | - | `UnifiedBuildStatusResponse` |

#### Person Completeness

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/person-completeness/summary/{twin_id}` | twin | JWT | - | `CompletenessSummaryResponse` |
| POST | `/person-completeness/run` | twin | JWT | `{ twin_id, trigger }` | `{ run_id }` |

#### Sources

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/person-sources?twin_id={id}&filter={}` | twin | JWT | - | `ListSourcesResponse` |
| PATCH | `/person-sources/{id}` | twin | JWT | `{ owner_verified_status, is_active }` | `SourceResponse` |

#### Claims

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/person-claims?twin_id={id}&type={}` | twin | JWT | - | `ListClaimsResponse` |
| PATCH | `/person-claims/{id}` | twin | JWT | `{ owner_approval_status, public_visibility }` | `ClaimResponse` |
| GET | `/person-claims/{id}/evidence` | twin | JWT | - | `ClaimEvidenceResponse` |

#### Timeline

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/person-timeline?twin_id={id}` | twin | JWT | - | `TimelineResponse` |
| POST | `/person-timeline/resolve-conflict` | twin | JWT | `{ event_ids, resolution }` | `{ success }` |

#### Contradictions

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/person-contradictions?twin_id={id}` | twin | JWT | - | `ContradictionsResponse` |
| POST | `/person-contradictions/{id}/resolve` | twin | JWT | `{ resolution, notes }` | `ResolutionResponse` |

#### Topics

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/person-topics?twin_id={id}` | twin | JWT | - | `TopicsResponse` |

#### Policies

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/person-runtime-policies/{twin_id}` | twin | JWT | - | `PoliciesResponse` |
| PUT | `/person-runtime-policies/{twin_id}` | twin | JWT | `PoliciesFormData` | `PoliciesResponse` |

#### Public (Tokenized - Preserves Current Security)

| Method | Endpoint | Scope | Auth | Request | Response |
|--------|----------|-------|------|---------|----------|
| GET | `/share/{twin_id}/{token}/profile` | public | URL token | - | `PublicProfileResponse` |
| POST | `/public/chat/{twin_id}/{token}` | public | URL token | `{ message }` | `ChatResponse` |
| GET | `/share/{twin_id}/{token}/config` | public | URL token | - | `PublicConfigResponse` |

### F.5 Scope Enforcement (useAuthFetch)

**File:** `frontend/lib/hooks/useAuthFetch.ts`

```typescript
// Endpoint classification
const ENDPOINT_SCOPES = {
  // Tenant endpoints (no twin_id in path/param)
  '/api-keys': 'tenant',
  '/access-groups': 'tenant',
  
  // Twin endpoints (require twin_id)
  '/person-completeness': 'twin',
  '/person-sources': 'twin',
  '/person-claims': 'twin',
  '/person-timeline': 'twin',
  '/person-contradictions': 'twin',
  '/person-topics': 'twin',
  '/person-runtime-policies': 'twin',
  '/build-status': 'twin',
  
  // Public endpoints (token in URL)
  '/share': 'public',
  '/public/chat': 'public'
};

// Usage in components
const { getTwin, postTwin, getPublic } = useAuthFetch();

// Correct - twin-scoped
const response = await getTwin(twinId, `/person-sources?twin_id={twinId}`);

// Correct - public (no JWT)
const response = await getPublic(`/share/${twinId}/${token}/profile`);
```

---

## G) DESIGN SYSTEM

Unchanged from Rev 1.

---

## H) ACCEPTANCE CRITERIA & QA (REVISED)

### H.1 Onboarding Acceptance Criteria

| Criteria | Test | Expected |
|----------|------|----------|
| Legacy preserved | Visit /onboarding?legacy=true | Shows legacy flow |
| New flow | Visit /onboarding/v2 | Shows 3-screen flow |
| Feature flag off | FF simplifiedOnboarding=false | Redirects /onboarding/v2 → /onboarding |
| Existing twin | User with 1 twin | Auto-selects, skips creation |
| Existing twins | User with 2+ twins | Shows "Select profile to enhance" |

### H.2 Security Acceptance Criteria (NEW)

| Criteria | Test | Expected |
|----------|------|----------|
| Public auth | Request /share/{id}/profile without token | 404/403 |
| Token validation | Request with invalid token | 403 + error code TOKEN_EXPIRED |
| Rate limiting | 100 requests to /public/chat/{token} | Rate limited after threshold |
| JWT on public | Request public endpoint with JWT header | Ignores JWT, validates URL token only |
| Owner access | Request owner endpoint without JWT | 401 UNAUTHORIZED |
| Cross-tenant | Request /person-claims with other tenant's twin_id | 403 NOT_OWNER |

### H.3 Tenant Isolation Criteria (NEW)

| Criteria | Test | Expected |
|----------|------|----------|
| Data isolation | Tenant A requests Tenant B's sources | 403 + error code NOT_OWNER |
| URL param block | Request /person-sources (no twin_id) | 400 VALIDATION_ERROR |
| Twin ownership | User requests twin they don't own | 403 NOT_OWNER |
| Public share isolation | Share token for Tenant A works only for that twin | Validated against share_links table |

### H.4 Regression Criteria (NEW)

| Criteria | Test | Expected |
|----------|------|----------|
| Multi-twin preserved | FF off, user with 2 twins | TwinSelector visible, both twins accessible |
| Resume legacy | /onboarding?twinId={id} with legacy twin | Resumes at correct step |
| Resume v2 | /onboarding/v2?profileId={id} | Resumes at building or profile |
| Nav fallback | FF off | Shows all 33 legacy nav items |
| Nav v2 | FF on | Shows simplified nav |

### H.5 End-to-End QA Checklist

#### Critical Security Tests
- [ ] Public endpoints reject requests without valid share token
- [ ] Public endpoints ignore JWT headers (don't leak based on session)
- [ ] Rate limiting enforced on public chat
- [ ] Cross-tenant requests return 403 (not 404, to prevent enumeration)
- [ ] Expired share tokens return 403 with clear error
- [ ] Owner endpoints reject unauthenticated requests
- [ ] Owner endpoints reject requests for other users' profiles

#### Critical Regression Tests
- [ ] Existing tenants with multiple twins can still access all twins
- [ ] Legacy onboarding flows continue to work
- [ ] Feature flag OFF = no UI changes visible
- [ ] Feature flag ON = new UI available
- [ ] Rollback (flag OFF after ON) restores previous behavior

#### Person Completeness Tests
- [ ] Onboarding creates new profile (twin) correctly
- [ ] Build progress polling works end-to-end
- [ ] Unified status API returns consistent data
- [ ] Sources display with authority tiers
- [ ] Claims can be verified/rejected
- [ ] Timeline shows conflicts
- [ ] Review queue guides through resolutions
- [ ] Policies save per audience

#### Public Share Tests
- [ ] Share page shows only public-safe data
- [ ] Private claims not visible in public profile
- [ ] Chat respects confidence thresholds
- [ ] Citations display when required
- [ ] Fallback messages appear appropriately

### H.6 Performance Criteria

| Metric | Target | Test |
|--------|--------|------|
| Page load | < 2s | Lighthouse performance audit |
| API response | < 500ms | 95th percentile of GET /person-completeness/summary |
| Build polling | < 100ms | Response time for /build-status |
| Chat response | < 2s | Time to first token in chat |

### H.7 Rollback Plan

**Emergency Rollback (if issues in production):**

1. **Immediate (30 seconds):**
   ```bash
   # Disable all Person Completeness v1 features
   vercel env add NEXT_PUBLIC_FF_PERSON_COMPLETENESS_V1 false
   # Or in Render dashboard
   FF_PERSON_COMPLETENESS_V1=false
   ```

2. **Verify (2 minutes):**
   - Confirm /onboarding redirects to legacy
   - Confirm TwinSelector visible for multi-twin users
   - Confirm existing twins accessible

3. **Root cause analysis:**
   - Review error logs
   - Identify failing component
   - Fix and re-deploy with flag OFF

4. **Re-enable:**
   - Set flag to true in staging
   - Verify fix
   - Gradual rollout (10% → 50% → 100%)

---

## I) IMPLEMENTATION MILESTONES (REVISED)

### I.1 Phase 0: Foundation (Week 0)
**Goal:** Safe infrastructure for gradual rollout

**Tasks:**
- [ ] Add feature flag framework entries
- [ ] Create `useBuildStatus` hook with unified polling
- [ ] Add scope enforcement to useAuthFetch
- [ ] Create backward-compatible navigation getter
- [ ] Add legacy route redirects

**Done Criteria:**
- All flags default to false
- No visible UI changes when flags off
- All existing tests pass

### I.2 Phase 1: Backend APIs (Week 1)
**Goal:** Complete backend endpoint gaps

**Tasks:**
- [ ] Implement GET /build-status/{twin_id} (unified status)
- [ ] Implement /person-completeness endpoints
- [ ] Implement /person-sources endpoints
- [ ] Implement /person-claims endpoints
- [ ] Implement /person-topics endpoint
- [ ] Implement /person-runtime-policies endpoints

**Done Criteria:**
- All endpoints return correct schemas
- Security tests pass
- Tenant isolation verified

### I.3 Phase 2: Onboarding v2 (Week 2-3)
**Goal:** 3-screen onboarding behind feature flag

**Tasks:**
- [ ] Create /onboarding/v2 route
- [ ] Implement Screen 1: Identity
- [ ] Implement Screen 2: Optional Hints
- [ ] Implement Screen 3: Add Content
- [ ] Implement /v2/building with unified status
- [ ] Add resume from legacy flow

**Done Criteria:**
- User can complete onboarding in < 5 minutes
- Progress displays correctly
- Pipeline triggers automatically
- Rollback to legacy works

### I.4 Phase 4: Profile Screens (Week 4-5)
**Goal:** Core profile management screens

**Tasks:**
- [ ] Profile Overview hub
- [ ] Sources management
- [ ] Claims review
- [ ] Timeline view
- [ ] Topics & coverage

**Done Criteria:**
- All screens behind feature flags
- Data loads correctly from new APIs
- Navigation between screens works

### I.5 Phase 5: Advanced Features (Week 6)
**Goal:** Review queue and policies

**Tasks:**
- [ ] Review Queue workflow
- [ ] Contradiction resolution
- [ ] Audience-based policies

**Done Criteria:**
- Guided review flow works
- Policies save correctly
- Public share respects policies

### I.6 Phase 6: Public Share Updates (Week 7)
**Goal:** Tokenized public sharing (preserves security)

**Tasks:**
- [ ] Update public share endpoints
- [ ] Implement /share/{twin_id}/{token}/profile
- [ ] Update chat integration
- [ ] Add confidence indicators to chat

**Done Criteria:**
- Public endpoints use tokenized URLs
- No JWT required for public access
- Rate limiting enforced

### I.7 Phase 7: QA & Rollout (Week 8)
**Goal:** Production readiness

**Tasks:**
- [ ] Security audit
- [ ] Performance optimization
- [ ] Cross-browser testing
- [ ] Gradual rollout (10% → 50% → 100%)

**Done Criteria:**
- All acceptance criteria pass
- Security review approved
- Rollback tested

---

## J) BACKEND GAPS (REVISED)

| Priority | Endpoint | Effort | Notes |
|----------|----------|--------|-------|
| **P0** | GET /build-status/{twin_id} | 2 days | Unified status - combines research + PC |
| **P0** | GET /person-completeness/summary/{twin_id} | 1 day | Aggregates all tables |
| **P0** | POST /person-completeness/run | 1/2 day | Trigger pipeline |
| **P0** | GET /person-sources | 1 day | Query person_source_registry |
| **P0** | PATCH /person-sources/{id} | 1/2 day | Update verification |
| **P0** | GET /person-claims | 1 day | Query person_claims |
| **P0** | PATCH /person-claims/{id} | 1/2 day | Update approval |
| **P0** | GET /person-claims/{id}/evidence | 1/2 day | Join evidence_spans |
| **P0** | GET /person-topics | 1 day | Query person_topic_profiles |
| **P1** | GET /person-timeline | 1 day | Query person_timeline_events |
| **P1** | POST /person-timeline/resolve-conflict | 1/2 day | Resolution logic |
| **P1** | GET /person-contradictions | 1 day | Query person_contradictions |
| **P1** | POST /person-contradictions/{id}/resolve | 1/2 day | Resolution logic |
| **P1** | GET/PUT /person-runtime-policies/{twin_id} | 1 day | CRUD policies |
| **P1** | GET /share/{twin_id}/{token}/profile | 1 day | Public-safe data (preserves token pattern) |
| **P1** | GET /share/{twin_id}/{token}/config | 1/2 day | Public config |

**Total Backend Effort:** ~14 days

---

## K) DEPLOYMENT READINESS CHECKLIST

**Before Contractor Handoff:**
- [x] All security gaps addressed (tokenized public, JWT for private)
- [x] Compatibility mode specified (primary profile, multi-twin preserved)
- [x] Feature flag strategy defined
- [x] Rollback plan documented
- [x] Endpoint scope enforcement specified
- [x] Unified status API defined
- [x] Backward-compatible routing specified
- [x] Expanded QA/security tests added

**Before Production Deploy:**
- [ ] All backend endpoints implemented
- [ ] All feature flags default to false
- [ ] Security audit passed
- [ ] Rollback procedure tested
- [ ] Gradual rollout plan approved
- [ ] Monitoring and alerting configured

---

**END OF REVISION 2**

*This document is production-ready with migration guards, rollback strategy, and security fixes.*
