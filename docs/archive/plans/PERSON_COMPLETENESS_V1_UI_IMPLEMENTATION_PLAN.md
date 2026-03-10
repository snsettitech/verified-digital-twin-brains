# Person Completeness v1 - UI Implementation Plan

**Prepared for:** Contractor/Development Team  
**Date:** 2026-02-25  
**Version:** 1.0  
**Classification:** Contractor-Ready Specification

---

## A) REPO AUDIT SUMMARY (with File/Line Evidence)

### A.1 Frontend Stack

| Component | Technology | Evidence |
|-----------|------------|----------|
| **Framework** | Next.js 16.1.6 App Router | `frontend/package.json` lines 22 |
| **React** | 19.2.1 | `frontend/package.json` lines 23-24 |
| **Language** | TypeScript 5.9.3 | `frontend/package.json` line 40 |
| **Styling** | Tailwind CSS v4 | `frontend/package.json` lines 30, 39 |
| **Auth** | Supabase auth-helpers-nextjs | `frontend/package.json` lines 20-21 |
| **Validation** | Zod | `frontend/package.json` line 27 |
| **UI Kit** | Custom (NO shadcn/MUI) | `frontend/components/ui/` directory |

### A.2 Existing UI Components (`frontend/components/ui/`)

| Component | File Path | Purpose |
|-----------|-----------|---------|
| Badge | `frontend/components/ui/Badge.tsx` | Status badges |
| Card | `frontend/components/ui/Card.tsx` | Card containers |
| EmptyState | `frontend/components/ui/EmptyState.tsx` | Empty state illustrations |
| Modal | `frontend/components/ui/Modal.tsx` | Dialog modals |
| Skeleton | `frontend/components/ui/Skeleton.tsx` | Loading skeletons |
| StatCard | `frontend/components/ui/StatCard.tsx` | Dashboard stat cards |
| Toast | `frontend/components/ui/Toast.tsx` | Notification system |
| Toggle | `frontend/components/ui/Toggle.tsx` | Toggle switches |
| VerificationBadge | `frontend/components/ui/VerificationBadge.tsx` | Verification status |

### A.3 Current Navigation Structure

**File:** `frontend/lib/navigation/config.ts` (lines 1-100)

Current sections:
- **Build:** Dashboard, Deep Research, Profile, Knowledge, Memory Center, Studio, Ingestion Jobs, Brain Graph
- **Interact:** Chat, Actions, Products, Share
- **Test & Review:** Simulator Hub, Simulator Owner/Training/Public/Workflow, Retrieval Debug, Escalations, Verified QnA
- **Insights:** Metrics, Insights
- **Share & Access:** Access Groups, Widget, API Keys
- **Settings:** Settings, Privacy & Data, Publish Controls, Users, Governance

**File:** `frontend/components/Sidebar.tsx` (lines 1-192)
- Uses `TwinSelector` component (line 6, 104-108) - **TO BE REMOVED for single-profile**
- Static navigation config from `SIDEBAR_CONFIG`
- Collapsible sidebar with gradient styling

### A.4 Existing Onboarding Flow (TO BE REPLACED)

**File:** `frontend/app/onboarding/page.tsx` (lines 1-859)

**Current Problems:**
- 12+ steps in link-first flow (lines 28-44)
- 6+ steps in manual flow (lines 169-176)
- Creates "twin" with `twinName` field (line 123) - **TO BE REMOVED**
- Complex state machine (lines 46-54, 198-232)

**Current Flow States:**
```typescript
type OnboardingStep = 
  | 'welcome'
  | 'link_suggestions'
  | 'add_sources'
  | 'source_review'
  | 'research'
  | 'building'
  | 'profile'
  | 'claim_review'
  | 'clarification'
  | 'manual_identity'
  | 'manual_thinking'
  | 'manual_values'
  | 'manual_communication'
  | 'manual_memory'
  | 'manual_review';
```

### A.5 API Client Patterns

**File:** `frontend/lib/api.ts` (lines 1-146)
- `resolveApiBaseUrl()` - Environment-based backend URL resolution (lines 8-26)
- `getChatAuthToken()` - Supabase session token retrieval (lines 137-145)
- `ingestionJobsApi` - Typed API pattern example (lines 75-125)

**File:** `frontend/lib/hooks/useAuthFetch.ts` (lines 1-430)
- `useAuthFetch()` hook - Primary authenticated fetch pattern (lines 12-287)
- `authFetchStandalone()` - Standalone function for non-hook contexts (lines 306-327)
- Scope enforcement: `getTwin()`, `postTwin()`, `getTenant()` (lines 224-268)

### A.6 State Management

**File:** `frontend/lib/context/TwinContext.tsx` (lines 1-773)

**Current twin-centric patterns (TO BE ADAPTED):**
```typescript
// Lines 12-26: Twin type definition
export interface Twin {
  id: string;
  name: string;  // This is currently "twin name", will become "profile name"
  owner_id: string;
  tenant_id: string;
  specialization: string;
  status: TwinStatus;
  is_active: boolean;
  settings?: Record<string, unknown>;
}

// Lines 53-54: Multiple twins state
 twins: Twin[];
 activeTwin: Twin | null;

// Lines 56-60: Twin actions
 setActiveTwin: (twinId: string) => void;
 refreshTwins: (...) => Promise<void>;
```

**Adaptation Strategy:**
- Keep `activeTwin` internally (maps to single profile)
- `twins` array will contain exactly one item for most users
- UI will not expose "twin" terminology - always "Profile"

### A.7 Backend Person Completeness Pipeline

**File:** `backend/modules/person_completeness_pipeline.py` (lines 1-479)

**Pipeline Stages (lines 31-39):**
```python
class PipelineStage(str, Enum):
    SOURCE_REGISTRY_BUILT = "source_registry_built"
    CLAIMS_EXTRACTED = "claims_extracted"
    TIMELINE_BUILT = "timeline_built"
    TOPIC_GRAPH_BUILT = "topic_graph_built"
    STYLE_PROFILE_BUILT = "style_profile_built"
    CONTRADICTIONS_DETECTED = "contradictions_detected"
    ANSWERABILITY_SCORED = "answerability_scored"
```

**Run Status Tracking (lines 91-170):**
- `person_completeness_runs` table operations
- Status values: `pending`, `running`, `completed`, `failed`, `partial`
- Tracks: `current_stage`, `completed_stages`, `metrics`

### A.8 Backend Runtime Confidence Gate

**File:** `backend/modules/runtime_confidence_gate.py` (lines 1-275)

**Gate Decisions (lines 22-26):**
```python
class GateDecision(str, Enum):
    ALLOW = "allow"
    PARTIAL = "partial"
    BLOCK = "block"
```

**Policy Structure (lines 156-160):**
```python
{
    "confidence_threshold_answer": 0.5,  # 0-1 scale
    "confidence_threshold_style": 0.6,
    "fallback_behavior": "i_dont_know",  # | "clarify" | "escalate"
    "require_citation": True,
}
```

### A.9 Existing Backend Endpoints (Reusable)

**File:** `backend/routers/research_claims.py` (lines 1+)

| Endpoint | Method | Purpose | Lines |
|----------|--------|---------|-------|
| `/twins/{twin_id}/research/{research_run_id}/continue-claims` | POST | Trigger claim enrichment | 197-270 |
| `/twins/{twin_id}/research/{research_run_id}/claims-status` | GET | Get enrichment status | 273-300 |
| `/twins/{twin_id}/research/{research_run_id}/claims` | GET | List claims | 300+ |
| `/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}` | PATCH | Update claim | 400+ |
| `/twins/{twin_id}/review-queue` | GET | Get review queue | 1660+ |
| `/twins/{twin_id}/review-queue/{item_id}/resolve` | POST | Resolve review item | 1700+ |

**File:** `backend/routers/twins.py` (lines 1+)

| Endpoint | Method | Purpose | Lines |
|----------|--------|---------|-------|
| `/twins` | POST | Create twin | 225-447 |
| `/twins` | GET | List twins | 450-477 |
| `/twins/{twin_id}` | GET | Get twin | 479-548 |
| `/twins/{twin_id}` | PATCH | Update twin | 660-761 |
| `/twins/{twin_id}/settings` | GET/POST | Twin settings | 801-866 |

### A.10 Backend Gaps (Endpoints to Implement)

| Endpoint | Method | Purpose | Priority |
|----------|--------|---------|----------|
| `/person-completeness/summary/{twin_id}` | GET | Overview stats | P0 |
| `/person-sources` | GET | List sources with filtering | P0 |
| `/person-sources/{id}` | PATCH | Update source verification | P0 |
| `/person-claims` | GET | List claims with pagination | P0 |
| `/person-claims/{id}/evidence` | GET | Get evidence spans | P0 |
| `/person-claims/{id}` | PATCH | Approve/reject claim | P0 |
| `/person-timeline` | GET | Get timeline events | P1 |
| `/person-contradictions` | GET | List contradictions | P1 |
| `/person-contradictions/{id}/resolve` | POST | Resolve contradiction | P1 |
| `/person-topics` | GET | List topic profiles | P0 |
| `/person-runtime-policies/{twin_id}` | GET/PUT | Get/update policies | P1 |
| `/public-profiles/{twin_id}` | GET | Public profile data | P0 |
| `/person-completeness-runs/{id}/status` | GET | Poll pipeline status | P0 |

---

## B) INFORMATION ARCHITECTURE (IA)

### B.1 Core Principle: One Profile Per User

**User Model Change:**
- Remove twin selector from sidebar
- Single `activeTwin` state internally (keeps `twin_id` for backend compatibility)
- Profile name = User's full name (from Supabase auth or onboarding)
- No "twin name" field exposed in UI

### B.2 Site Map

```
PUBLIC ROUTES (Unauthenticated)
├── / (Landing Page)
├── /auth/login
├── /auth/signup
├── /auth/forgot-password
└── /share/{profile_id} (Public Profile - Visitor View)
    └── /share/{profile_id}/{token} (Secured Share Link)

ONBOARDING (Max 3 Screens)
├── /onboarding
    ├── Screen 1: Identity (full name, headline)
    ├── Screen 2: Optional Hints (role, location, expertise - skippable)
    └── Screen 3: Add Content (URLs, social connect, uploads)
    └── /onboarding/building (Auto-build progress)

DASHBOARD (Authenticated - Owner View)
├── /dashboard (Home - Redirects to Profile Overview)
├── /dashboard/profile (Profile Overview - THE HUB)
│   ├── /sources
│   ├── /claims
│   ├── /timeline
│   ├── /topics
│   └── /review
├── /dashboard/chat (Chat with own profile)
├── /dashboard/settings
│   └── /settings/policies (Audience-based policies)
└── /dashboard/share (Share controls)
```

### B.3 Navigation (Simplified)

**New Sidebar Structure (replaces `frontend/lib/navigation/config.ts`):**

```typescript
export const SIDEBAR_CONFIG: SidebarConfig = [
  {
    title: 'Profile',
    items: [
      { name: 'Overview', href: '/dashboard/profile', icon: 'profile' },
      { name: 'Sources', href: '/dashboard/profile/sources', icon: 'book' },
      { name: 'Claims', href: '/dashboard/profile/claims', icon: 'check' },
      { name: 'Timeline', href: '/dashboard/profile/timeline', icon: 'clock' },
      { name: 'Topics', href: '/dashboard/profile/topics', icon: 'chart' },
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
```

### B.4 Visibility Matrix

| Screen | Owner | Public Visitor | Notes |
|--------|-------|----------------|-------|
| Profile Overview | ✅ Full | ✅ Limited | Public sees only public-safe summary |
| Sources | ✅ Full | ❌ Hidden | Owner verification required |
| Claims | ✅ Full | ❌ Hidden | Owner approval required |
| Timeline | ✅ Full | ✅ Public events only | Filtered by public_visibility |
| Topics | ✅ Full | ✅ High-confidence only | Score threshold filter |
| Review Queue | ✅ Full | ❌ Hidden | Owner-only |
| Policies | ✅ Full | ❌ Hidden | Owner-only |
| Chat (Owner) | ✅ Full | ❌ Hidden | Full capabilities |
| Chat (Public) | ❌ Hidden | ✅ Limited | Runtime policies enforced |

---

## C) ONBOARDING (3 SCREENS MAX)

### Design Principles
- **Total time < 5 minutes**
- **Zero required typing except full name**
- **Smart defaults from Supabase auth**
- **Backend does the heavy lifting**

---

### C.1 Screen 1: Identity

**Route:** `/onboarding`

**Purpose:** Set profile identity - full name becomes profile display name

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  ← Back                              Step 1 of 3        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│              Let's create your profile                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  │     [Profile Avatar Placeholder]                │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Full Name *                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [___________________________]                   │   │
│  └─────────────────────────────────────────────────┘   │
│  This is how you'll appear to others                    │
│                                                         │
│  Headline (optional)                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [___________________________]                   │   │
│  └─────────────────────────────────────────────────┘   │
│  e.g., "Product Designer at Acme"                       │
│                                                         │
│           [Continue →]                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Fields:**

| Field | Type | Required | Source/Validation |
|-------|------|----------|-------------------|
| full_name | text | ✅ | Pre-fill from Supabase auth `user.user_metadata.full_name` |
| headline | text | ❌ | Max 140 chars |

**API Calls:**
```typescript
// On mount - get user from Supabase
const { data: { user } } = await supabase.auth.getUser();
// Pre-fill: user.user_metadata.full_name || user.email

// On Continue
POST /twins
{
  "name": "{full_name}",  // User's full name becomes "twin" name
  "mode": "link_first",
  "specialization": "vanilla",
  "settings": {
    "headline": "...",
    "owner_name": "...",
    "use_person_completeness": true
  }
}
// Response: { id: twin_id, ... }
// Store twin_id in TwinContext (activeTwin)
```

**Analytics:**
- `onboarding_started`
- `onboarding_step1_completed` (with has_headline)

**Error States:**
- Empty full name: "Please enter your full name"
- Backend error: "Something went wrong. Please try again."

**Accessibility:**
- Focus trap on modal
- Enter key submits
- ARIA labels on all inputs

---

### C.2 Screen 2: Optional Hints

**Route:** `/onboarding?step=2`

**Purpose:** Optional context to improve source discovery and claim extraction

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  ← Back                              Step 2 of 3        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│         Help us find your best content                  │
│     (Optional - you can skip this step)                 │
│                                                         │
│  What's your primary role?                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │Founder │ │Investor│ │Executive│ │Creator │           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
│  ┌────────┐ ┌────────┐                                  │
│  │Research│ │ Other  │                                  │
│  └────────┘ └────────┘                                  │
│                                                         │
│  Location (optional)                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [___________________________]                   │   │
│  └─────────────────────────────────────────────────┘   │
│  Helps find local content and events                    │
│                                                         │
│  Areas of Expertise                                     │
│  [Venture Capital] [x]  [Startups] [x]  [AI/ML] [+]     │
│  [Product] [+]  [Engineering] [+]                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │ + Add custom tag                                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [Skip for now]              [Continue →]               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Fields:**

| Field | Type | Required | Options |
|-------|------|----------|---------|
| role | select | ❌ | Founder, Investor, Executive, Creator, Researcher, Other |
| location | text | ❌ | Free text, geocoded on backend |
| expertise_tags | multi-select | ❌ | Predefined + custom |

**Expertise Tag Options:**
```typescript
const EXPERTISE_TAGS = [
  'Venture Capital', 'Startups', 'AI/ML', 'Product Management',
  'Engineering', 'Design', 'Marketing', 'Sales', 'Operations',
  'Finance', 'Healthcare', 'Climate', 'Education', 'Policy',
  'Research', 'Writing', 'Speaking', 'Other'
];
```

**API Calls:**
```typescript
// Update twin settings with hints
PATCH /twins/{twin_id}
{
  "settings": {
    "onboarding_hints": {
      "role": "founder",
      "location": "San Francisco, CA",
      "expertise_tags": ["Venture Capital", "Startups", "AI/ML"]
    }
  }
}
```

**Analytics:**
- `onboarding_step2_started`
- `onboarding_step2_completed` (with tags_count, role)
- `onboarding_step2_skipped`

---

### C.3 Screen 3: Add Content

**Route:** `/onboarding?step=3`

**Purpose:** Collect initial sources - URLs, social profiles, file uploads

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
│  │ [___________________________]              [+Add]│   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Added:                                                 │
│  ● linkedin.com/in/johndoe                        [x]  │
│  ● twitter.com/johndoe                            [x]  │
│  ● substack.com/johndoe                           [x]  │
│                                                         │
│  ──────── Quick Connect ────────                        │
│  [Connect LinkedIn]  [Connect Twitter]  [Connect GitHub]│
│                                                         │
│  ──────── Or Upload Files ────────                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  │    [Drop files here or click to upload]         │   │
│  │                                                 │   │
│  │    PDF, DOCX, TXT, MD (max 10MB each)           │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│  resume.pdf [uploading... ████░░░░░░]             [x]  │
│                                                         │
│  ⚠️ Need at least 1 source to build your profile        │
│                                                         │
│           [Finish & Build Profile →]                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Validation Rules:**

| Rule | Validation | Error Message |
|------|------------|---------------|
| Minimum sources | ≥1 URL or file | "Please add at least one source" |
| URL format | Valid URL scheme | "Please enter a valid URL" |
| Duplicate URLs | Dedupe check | "This URL was already added" |
| File size | ≤10MB per file | "Files must be under 10MB" |
| File types | PDF, DOCX, TXT, MD | "Unsupported file type" |
| Max files | ≤10 files | "Maximum 10 files per upload" |

**Supported URL Types (auto-detected):**
```typescript
const URL_PATTERNS = {
  linkedin: /linkedin\.com\/in\//,
  twitter: /(twitter|x)\.com\//,
  github: /github\.com\//,
  substack: /substack\.com\//,
  medium: /medium\.com\/@/,
  youtube: /youtube\.com\/(@|channel|c\/)/,
  personal: /\.com|\.io|\.dev|\.net/,
};
```

**API Calls:**
```typescript
// Trigger deep research and ingestion
// 1. Submit URLs (Mode C)
POST /persona/link-compile/jobs/mode-c
{
  "twin_id": "...",
  "urls": ["https://linkedin.com/in/...", "https://twitter.com/..."]
}

// 2. Upload files (Mode A) - if any
POST /persona/link-compile/jobs/mode-a
FormData: { files[], twin_id }

// 3. Trigger person completeness pipeline
POST /person-completeness/run
{
  "twin_id": "...",
  "trigger": "onboarding_complete"
}

// 4. Response: { run_id: "..." }
// Redirect to /onboarding/building?run_id=...
```

**Analytics:**
- `onboarding_step3_started`
- `onboarding_sources_submitted` (url_count, file_count, has_social_connect)
- `onboarding_complete` (duration_seconds)

---

## D) POST-ONBOARDING AUTO BUILD FLOW

### D.1 Building Screen

**Route:** `/onboarding/building?run_id={run_id}`

**Purpose:** Show progress while backend pipeline runs automatically

**Backend Stage → UI State Mapping:**

| Research Stage | Person Completeness Stage | UI Progress | User-Facing Text |
|----------------|---------------------------|-------------|------------------|
| PLANNING | - | 5% | "Planning your profile build..." |
| CRAWLING | SOURCE_REGISTRY_BUILT | 15% | "Discovering your content across the web..." |
| INGESTING | - | 25% | "Reading and processing your sources..." |
| BIO_GENERATED | - | 35% | "Understanding your background..." |
| CLAIMS_EXTRACTED | CLAIMS_EXTRACTED | 50% | "Extracting key facts and experiences..." |
| CLAIMS_ENRICHMENT | - | 60% | "Deep analysis of your expertise areas..." |
| WEB_VERIFICATION | - | 70% | "Cross-referencing public sources..." |
| CLAIMS_FINALIZED | TOPIC_GRAPH_BUILT | 80% | "Building your knowledge graph..." |
| TIMELINE_BUILT | TIMELINE_BUILT | 85% | "Organizing your timeline..." |
| STYLE_PROFILE_BUILT | STYLE_PROFILE_BUILT | 90% | "Capturing your communication style..." |
| CONTRADICTIONS_DETECTED | CONTRADICTIONS_DETECTED | 92% | "Checking for conflicts..." |
| ANSWERABILITY_SCORED | ANSWERABILITY_SCORED | 95% | "Calculating your readiness score..." |
| RUNTIME_PUBLISHED | - | 98% | "Finalizing your profile..." |
| COMPLETED | - | 100% | "Your profile is ready!" |

**Polling Strategy:**
```typescript
// Poll every 3 seconds during active processing
// Poll every 10 seconds during slower stages
// Exponential backoff if no progress for 30s

const POLL_INTERVALS = {
  active: 3000,
  slow: 10000,
  stalled: 30000
};

// API call
GET /person-completeness-runs/{run_id}/status
// Response: { status, current_stage, completed_stages, progress_pct, metrics }
```

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│              Building Your Profile                      │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  │     [Animated Icon: Pulse/Sparkle]              │   │
│  │                                                 │   │
│  │        "Deep analysis of your                   │   │
│  │         expertise areas..."                     │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ████████████████████████████████████░░░░  67%         │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Stats:                                         │   │
│  │  • Sources found: 12                            │   │
│  │  • Claims extracted: 47                         │   │
│  │  • Topics identified: 6                         │   │
│  │  • Timeline events: 8                           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [Continue in Background]                               │
│  → We'll email you when ready                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### D.2 Completion Tiers

**Backend → UI Mapping:**

| Answerability Score | Tier | UI State | Primary CTA |
|--------------------|------|----------|-------------|
| ≥75 | completed_high_confidence | 🟢 Ready | "View Your Profile →" |
| 50-74 | completed_with_gaps | 🟡 Ready with gaps | "View Profile & Add Sources →" |
| <50 | completed_low_confidence | 🟠 Needs more content | "Add More Sources →" |
| Failed | completed_with_fallback | 🔴 Build failed | "Try Again →" |

**Tier Components:**
```typescript
interface CompletionTier {
  tier: 'high_confidence' | 'with_gaps' | 'low_confidence' | 'fallback';
  score: number;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  headline: string;
  description: string;
  primaryAction: string;
  secondaryAction?: string;
}

const TIERS: Record<string, CompletionTier> = {
  high_confidence: {
    tier: 'high_confidence',
    score: 82,
    grade: 'A',
    headline: "Your profile is ready!",
    description: "Your Digital Brain can confidently answer questions across {topic_count} topic areas.",
    primaryAction: "View Your Profile →",
    secondaryAction: "Start Chatting"
  },
  with_gaps: {
    tier: 'with_gaps',
    score: 62,
    grade: 'B',
    headline: "Your profile is ready with some gaps",
    description: "Your Digital Brain can answer most questions, but adding more sources will improve coverage in: {gaps_list}",
    primaryAction: "View Profile →",
    secondaryAction: "Add Sources"
  },
  low_confidence: {
    tier: 'low_confidence',
    score: 35,
    grade: 'C',
    headline: "Your profile needs more content",
    description: "Add more sources so your Digital Brain can answer confidently. We recommend adding LinkedIn, articles, or presentations.",
    primaryAction: "Add Sources →",
    secondaryAction: "View Anyway"
  }
};
```

---

## E) CORE PRODUCT SCREENS

### E.1 Profile Overview (Owner) - `/dashboard/profile`

**Purpose:** Central hub showing profile completeness and next actions

**Component Structure:**
```typescript
interface ProfileOverviewProps {
  twinId: string;  // Internal, not shown in UI
}

// Components
├── ProfileHeader
│   ├── Avatar (generated from initials)
│   ├── Full Name (from user)
│   ├── Headline (from settings)
│   └── Answerability Score Badge
├── CompletenessCard
│   ├── CircularProgress (score 0-100)
│   ├── Grade Label (A/B/C/D/F)
│   └── Status Badge (Ready/Building/Needs Attention)
├── QuickStatsGrid
│   ├── SourcesCount
│   ├── ClaimsCount
│   ├── VerifiedCount
│   └── OpenContradictionsCount
├── TopTopicsList
│   └── TopicItem[] (name + score)
├── NextActionsPanel
│   └── ActionItem[] (priority ordered)
└── BuildStatusBanner (if pipeline running)
```

**API Contract:**
```typescript
// GET /person-completeness/summary/{twin_id}
interface CompletenessSummaryResponse {
  twin_id: string;
  answerability_score: number;  // 0-100
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  status: 'building' | 'ready' | 'needs_attention' | 'incomplete';
  
  stats: {
    sources_count: number;
    claims_count: number;
    verified_claims: number;
    contradictions_open: number;
    timeline_events: number;
    topics_count: number;
  };
  
  top_topics: Array<{
    slug: string;
    name: string;
    answerability_score: number;
  }>;
  
  next_actions: Array<{
    type: 'verify_claims' | 'resolve_conflicts' | 'add_sources';
    priority: 'high' | 'medium' | 'low';
    description: string;
    count?: number;
    link: string;
  }>;
}

// Response 200
{
  "twin_id": "uuid",
  "answerability_score": 82,
  "grade": "B+",
  "status": "ready",
  "stats": {
    "sources_count": 12,
    "claims_count": 47,
    "verified_claims": 32,
    "contradictions_open": 2,
    "timeline_events": 8,
    "topics_count": 6
  },
  "top_topics": [
    { "slug": "venture_capital", "name": "Venture Capital", "answerability_score": 95 }
  ],
  "next_actions": [
    { 
      "type": "resolve_conflicts", 
      "priority": "high", 
      "description": "2 timeline conflicts need resolution",
      "count": 2,
      "link": "/dashboard/profile/review" 
    }
  ]
}
```

**Empty State:**
```
Your profile is just getting started.

[Illustration]

Add your first sources to start building your Digital Brain.

[Add Sources →]
```

**Acceptance Criteria:**
- [ ] Score displays as 0-100 with color coding (red <50, yellow 50-75, green >75)
- [ ] Grade displays alongside score
- [ ] Stats cards are clickable and navigate to respective sections
- [ ] Next actions sorted by priority
- [ ] Build status banner shows when pipeline is running
- [ ] Page loads in < 2 seconds

---

### E.2 Sources - `/dashboard/profile/sources`

**Purpose:** Manage ingested sources with authority tiers and verification

**Component Structure:**
```typescript
interface SourcesScreenProps {
  twinId: string;
}

├── SourcesHeader
│   ├── Title + Count
│   ├── FilterTabs (All | Verified | Needs Review | Excluded)
│   └── AddSourceButton
├── SourcesList
│   └── SourceCard[]
└── SourceDetailDrawer

interface SourceCardProps {
  source: {
    id: string;
    url: string;
    title: string;
    source_type: string;
    authority_tier: 1-7;
    owner_verified_status: 'verified' | 'unverified' | 'inferred';
    quality_score: number;
    crawl_status: string;
    is_active: boolean;
  };
}
```

**Authority Tier Badges:**
| Tier | Badge | Description |
|------|-------|-------------|
| 1 | 🏛️ Institutional | .edu, .gov, major news outlets |
| 2 | 💼 Professional | LinkedIn, GitHub, established publications |
| 3 | 📝 Published | Medium, Substack, research papers |
| 4 | 🌐 Professional Sites | Personal sites, portfolios |
| 5 | 💬 Social | Twitter/X, professional networks |
| 6 | 📱 Social Media | Instagram, TikTok (limited use) |
| 7 | ❓ Unknown | Unclassified sources |

**API Contract:**
```typescript
// GET /person-sources?twin_id={id}&filter={}&sort={}
interface ListSourcesResponse {
  sources: Array<{
    id: string;
    url: string;
    normalized_url: string;
    title: string;
    source_type: string;
    platform: string;
    authority_tier: number;
    owner_verified_status: string;
    quality_score: number;
    content_length_words: number;
    crawl_status: string;
    is_active: boolean;
    discovered_at: string;
    claims_count: number;
  }>;
  total: number;
  verified_count: number;
  unverified_count: number;
}

// PATCH /person-sources/{source_id}
{
  "owner_verified_status": "verified" | "rejected",
  "is_active": false  // exclude this source
}

// Error: 403 if not owner, 404 if source not found
```

**Exclude Action (Identity Disambiguation):**
```
⚠️ Not you?

This source doesn't appear to be about you.

[This is me] [This is NOT me - Exclude]

Excluding a source removes it from your profile permanently.
```

**Acceptance Criteria:**
- [ ] Authority tier badges display correctly
- [ ] Can filter by verification status
- [ ] Can exclude sources with confirmation
- [ ] Detail drawer shows full metadata
- [ ] "Needs Login" badge for sources requiring auth
- [ ] Empty state when no sources

---

### E.3 Claims - `/dashboard/profile/claims`

**Purpose:** Review and verify extracted claims with evidence

**Component Structure:**
```typescript
├── ClaimsHeader
│   ├── Title + Search
│   ├── CategoryFilter (Work | Education | Projects | Preferences | Beliefs | All)
│   └── VerificationFilter (All | Verified | Pending | Rejected)
├── ClaimsList
│   └── ClaimCard[]
└── ClaimDetailModal

interface ClaimCardProps {
  claim: {
    id: string;
    claim_text: string;
    claim_type: string;
    verification_status: string;
    confidence: number;
    evidence_count: number;
    first_seen_at: string;
  };
}
```

**Claim Type Icons:**
```typescript
const CLAIM_TYPE_ICONS = {
  work_experience: '💼',
  education: '🎓',
  project: '🚀',
  achievement: '🏆',
  preference: '👍',
  belief: '💭',
  skill: '⚡',
  media_appearance: '📺',
  bio_fact: 'ℹ️',
};
```

**API Contract:**
```typescript
// GET /person-claims?twin_id={}&type={}&status={}
interface ListClaimsResponse {
  claims: Array<{
    id: string;
    claim_text: string;
    claim_type: string;
    subject?: string;
    predicate?: string;
    object?: string;
    verification_status: string;
    owner_approval_status: string;
    extraction_confidence: number;
    evidence_count: number;
    public_visibility: 'public' | 'private';
  }>;
  total: number;
  by_type: Record<string, number>;
}

// GET /person-claims/{claim_id}/evidence
interface ClaimEvidenceResponse {
  claim_id: string;
  evidence_spans: Array<{
    id: string;
    evidence_text: string;
    evidence_type: string;
    source_url: string;
    source_title: string;
    quote: string;
    timestamp?: string;
  }>;
}

// PATCH /person-claims/{claim_id}
{
  "owner_approval_status": "approved" | "rejected",
  "public_visibility": "public" | "private"
}
```

**Evidence Viewer UI:**
```
┌─────────────────────────────────────────────────────────┐
│ Claim                                                   │
│ "Led engineering team of 15 at Google"                  │
│                                                         │
│ Evidence Sources (3)                                    │
│ ─────────────────                                       │
│                                                         │
│ 📄 LinkedIn Profile                                     │
│ "Led a team of 15 engineers working on..."              │
│ [View Source →]                                         │
│                                                         │
│ 📝 Blog Post: "My time at Google"                       │
│ "When I joined Google, I inherited a team of 15..."     │
│ [View Source →]                                         │
│                                                         │
│ [✓ Verify]  [✗ Reject]  [🔒 Make Private]               │
└─────────────────────────────────────────────────────────┘
```

---

### E.4 Timeline - `/dashboard/profile/timeline`

**Purpose:** Visual timeline of career/experience with conflict detection

**Component Structure:**
```typescript
├── TimelineHeader
│   ├── Title
│   ├── ZoomControls (Year | Month | All)
│   └── ShowConflictsToggle
├── TimelineVisualization
│   └── TimelineEvent[]
└── ConflictAlertBanner

interface TimelineEventProps {
  event: {
    id: string;
    event_type: string;
    title: string;
    description: string;
    start_date: string;
    end_date?: string;
    date_precision: 'day' | 'month' | 'year' | 'approximate';
    organization?: string;
    role_title?: string;
    confidence: number;
    has_conflict: boolean;
  };
}
```

**Event Type Colors:**
```typescript
const EVENT_COLORS = {
  job_start: 'bg-blue-500',
  job_end: 'bg-blue-300',
  education_start: 'bg-green-500',
  education_end: 'bg-green-300',
  founded_company: 'bg-orange-500',
  award: 'bg-yellow-500',
  publication: 'bg-purple-500',
  media_appearance: 'bg-red-500',
};
```

**Conflict Resolution UI:**
```
⚠️ Timeline Overlap Detected

"Senior Engineer at Google" (Jan 2020 - Dec 2021)
overlaps with
"CTO at StartupX" (Jun 2021 - Present)

How would you like to resolve this?

[✓ This is correct - I worked both] 
[✗ Fix dates - Google ended Jun 2021]
[✗ Fix dates - StartupX started Jan 2022]
[? Needs clarification]
```

---

### E.5 Topics & Answerability - `/dashboard/profile/topics`

**Purpose:** Topic coverage analysis with gap identification

**Component Structure:**
```typescript
├── TopicsHeader
│   ├── Title
│   ├── OverallScore
│   └── SortDropdown
├── TopicsGrid
│   └── TopicCard[]
├── GapsSection
│   └── GapItem[]
└── SuggestionsPanel

interface TopicCardProps {
  topic: {
    slug: string;
    name: string;
    answerability_score: number;
    coverage_score: number;
    verification_score: number;
    recency_score: number;
    consistency_score: number;
    evidence_count: number;
  };
}
```

**Score Visualization:**
```
┌────────────────────────────────────────────┐
│ Venture Capital                     95/100 │
│ ████████████████████████████████████       │
│                                            │
│ Coverage:      ████████████░░░░  90%       │
│ Verification:  ████████████████  95%       │
│ Recency:       ██████████░░░░░░  80%       │
│ Consistency:   ████████████████  95%       │
│                                            │
│ Evidence: 24 claims (18 first-party)       │
│ [View Claims →]                            │
└────────────────────────────────────────────┘
```

**Gaps Section:**
```
Topics with Low Coverage

Healthcare Policy                    23/100
Your Digital Brain can't confidently answer 
questions about this topic yet.

[Add sources about Healthcare →]
```

---

### E.6 Review Queue - `/dashboard/profile/review`

**Purpose:** Guided workflow for resolving issues

**Issues Tracked:**
1. Contradictions between claims
2. Low confidence claims
3. Unverified high-impact claims

**Component Structure:**
```typescript
├── ReviewQueueHeader
│   ├── Title + Total Count
│   ├── TabNavigation
│   └── ProgressIndicator
├── ContradictionsTab
│   └── ContradictionCard[]
├── LowConfidenceTab
│   └── LowConfidenceClaim[]
├── UnverifiedTab
│   └── UnverifiedClaim[]
└── GuidedReviewFlow
```

**Guided Flow:**
```
Step 1 of 3: Resolve Timeline Conflicts

┌────────────────────────────────────────────┐
│                                            │
│  Conflict 1 of 2                           │
│                                            │
│  ┌──────────┐  ┌──────────┐               │
│  │ Claim A  │  │ Claim B  │               │
│  └──────────┘  └──────────┘               │
│                                            │
│  Suggested: These are sequential           │
│                                            │
│  [✓ Correct] [✗ Incorrect] [→ Skip]       │
│                                            │
│  [← Back]              [Next →]           │
│                                            │
└────────────────────────────────────────────┘
```

---

### E.7 Policies & Safety - `/dashboard/settings/policies`

**Purpose:** Configure runtime behavior per audience (replaces multi-twin)

**Key Concept:** One profile, multiple audience policies

**Component Structure:**
```typescript
interface PoliciesFormData {
  audience: 'public' | 'recruiter' | 'investor' | 'internal';
  confidence_threshold_answer: number;  // UI: 0-100, Backend: 0.0-1.0
  confidence_threshold_style: number;   // UI: 0-100, Backend: 0.0-1.0
  require_citation: boolean;
  blocked_topics: string[];
  allow_sensitive_topics: Record<string, boolean>;
  fallback_behavior: 'i_dont_know' | 'clarify' | 'escalate';
}
```

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Profile Policies                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Audience                                                │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│ │  Public  │ │ Recruiter│ │ Investor │ │ Internal │    │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│                                                         │
│ Confidence Settings                                     │
│ ─────────────────                                       │
│ Minimum confidence to answer: [━━━●────] 60%            │
│ "I don't know" threshold:     [━━━━━●──] 70%            │
│                                                         │
│ Content Controls                                        │
│ ─────────────────                                       │
│ ☑ Require citations on all answers                      │
│                                                         │
│ Blocked Topics                                          │
│ [Compensation] [x] [Politics] [x] [+ Add]               │
│                                                         │
│ Fallback Behavior                                       │
│ (○) "I don't have enough information"                  │
│ ( ) "Can you clarify?"                                  │
│ ( ) Escalate to me                                      │
│                                                         │
│              [Save Changes]                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Unit Conversion:**
```typescript
// UI uses 0-100, backend uses 0.0-1.0
const uiToBackend = (uiValue: number): number => uiValue / 100;
const backendToUi = (backendValue: number): number => Math.round(backendValue * 100);
```

---

### E.8 Public Share Page (Visitor) - `/share/{profile_id}`

**Purpose:** Public-facing profile with chat

**Visibility Rules:**
- Only `public_visibility='public'` claims
- Only `verification_status='verified'` claims
- Citations shown if `require_citation=true`
- Confidence tag shown if `answerability_score < 80`

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  [Logo]                                       [Sign In] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  │              [Avatar]                           │   │
│  │                                                 │   │
│  │           John Doe's Profile                    │   │
│  │        VC & Startup Advisor                     │   │
│  │                                                 │   │
│  │     Ask me about startups,                      │   │
│  │     venture capital, and scaling teams          │   │
│  │                                                 │   │
│  │     Confidence Score: 82/100 ⭐⭐⭐⭐☆          │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  💬 Ask a question                                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [What do you look for in startups?          ]   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Popular Topics:                                        │
│  [Venture Capital] [Startups] [Team Building]           │
│                                                         │
│  ───── Powered by Digital Brains ─────                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**API Contract:**
```typescript
// GET /public-profiles/{twin_id}
interface PublicProfileResponse {
  twin_id: string;
  name: string;
  headline?: string;
  avatar_url?: string;
  answerability_score: number;
  verified_claims_count: number;
  public_topics: Array<{
    name: string;
    slug: string;
    answerability_score: number;
  }>;
  citations_enabled: boolean;
}

// POST /public-chat/{twin_id}
{
  "message": "What do you look for in startups?",
  "session_id?": "..."
}
// Response includes confidence tag and citations
```

---

### E.9 Chat Integration

**Runtime Confidence Gate Integration:**

```typescript
interface MessageBubbleProps {
  message: {
    content: string;
    role: 'user' | 'assistant';
    confidence?: number;
    citations?: Array<{
      source: string;
      quote: string;
      url?: string;
    }>;
    gated?: boolean;
    fallback_message?: string;
  };
}
```

**Confidence Indicators:**
| Score | Indicator | Behavior |
|-------|-----------|----------|
| ≥80 | None | Normal response |
| 50-79 | 🟡 Moderate confidence | Show tag |
| <50 | 🔴 Low confidence | Show tag + suggestion |
| Gated | "I don't know" | Fallback message |

**Citation UI:**
```
Response content...

[Sources]
├─ LinkedIn Profile
│  "I look for founders who are deeply passionate..."
├─ Blog Post (2023)
│  "My investment thesis focuses on..."
└─ Podcast Interview
   "When evaluating startups, I always ask..."
```

---

## F) API CONTRACT SPECIFICATION

### F.1 Authentication
All endpoints require Supabase JWT:
```
Authorization: Bearer {supabase_access_token}
```

### F.2 Error Format
```typescript
interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  status: number;
}

// Example 400
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "confidence_threshold",
      "issue": "must be between 0 and 1"
    }
  },
  "status": 400
}
```

### F.3 Pagination
```typescript
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

// Query: ?page=1&per_page=20&sort=-created_at
```

### F.4 Complete Endpoint Specification

#### Person Completeness

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/person-completeness/summary/{twin_id}` | Owner | - | `CompletenessSummaryResponse` |
| POST | `/person-completeness/run` | Owner | `{ twin_id, trigger }` | `{ run_id }` |
| GET | `/person-completeness-runs/{id}/status` | Owner | - | `{ status, stage, progress }` |

#### Sources

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/person-sources?twin_id={id}&filter={}&sort={}` | Owner | - | `ListSourcesResponse` |
| GET | `/person-sources/{id}` | Owner | - | `SourceDetailResponse` |
| PATCH | `/person-sources/{id}` | Owner | `{ owner_verified_status, is_active }` | `SourceResponse` |

#### Claims

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/person-claims?twin_id={id}&type={}&status={}` | Owner | - | `ListClaimsResponse` |
| GET | `/person-claims/{id}` | Owner | - | `ClaimResponse` |
| PATCH | `/person-claims/{id}` | Owner | `{ owner_approval_status, public_visibility }` | `ClaimResponse` |
| GET | `/person-claims/{id}/evidence` | Owner | - | `ClaimEvidenceResponse` |

#### Timeline

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/person-timeline?twin_id={id}&conflicts_only={bool}` | Owner | - | `TimelineResponse` |
| POST | `/person-timeline/resolve-conflict` | Owner | `{ event_a_id, event_b_id, resolution }` | `{ success }` |

#### Contradictions

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/person-contradictions?twin_id={id}&status=open` | Owner | - | `ContradictionsResponse` |
| POST | `/person-contradictions/{id}/resolve` | Owner | `{ resolution, notes }` | `ResolutionResponse` |

#### Topics

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/person-topics?twin_id={id}&min_score={}` | Owner | - | `TopicsResponse` |

#### Policies

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/person-runtime-policies/{twin_id}` | Owner | - | `PoliciesResponse` |
| PUT | `/person-runtime-policies/{twin_id}` | Owner | `PoliciesFormData` | `PoliciesResponse` |

#### Public

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| GET | `/public-profiles/{twin_id}` | Public | - | `PublicProfileResponse` |
| POST | `/public-chat/{twin_id}` | Public | `{ message, session_id? }` | `ChatResponse` |

---

## G) DESIGN SYSTEM GUIDANCE

### G.1 Existing Patterns (MUST Follow)

**Color Palette** (from `frontend/components/Sidebar.tsx`, `frontend/app/onboarding/page.tsx`):
```css
/* Backgrounds */
bg-slate-950      /* Primary dark bg */
bg-slate-900      /* Secondary/cards */
bg-[#F8FAFC]      /* Light mode bg */

/* Accents */
from-indigo-600 to-purple-600  /* Primary gradient */
bg-emerald-500    /* Success */
bg-amber-500      /* Warning */
bg-red-500        /* Error */

/* Text */
text-white        /* Headings on dark */
text-slate-900    /* Headings on light */
text-slate-400    /* Secondary text */
text-slate-500    /* Tertiary/muted */
```

**Typography:**
- Headings: `font-black tracking-tight` (existing pattern)
- Body: Default sans
- Labels: `text-xs font-medium uppercase tracking-wider`

**Spacing:**
- Cards: `p-6`, `rounded-2xl`
- Section gaps: `space-y-8`, `gap-4`
- Page padding: `max-w-6xl mx-auto p-4 md:p-8`

### G.2 Premium Design Guidelines

**Card Patterns:**
```tsx
// Primary card
<div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">

// Elevated card (for emphasis)
<div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl 
                border border-slate-700/50 p-6 shadow-xl">

// Stats card
<div className="bg-white/5 rounded-xl border border-white/10 p-4 
                hover:bg-white/10 transition-colors">
```

**Progressive Disclosure:**
1. Show summary card first
2. "View Details →" expands to drawer
3. "Edit" opens modal for full control

**Empty States:**
- Friendly illustration
- Clear explanation
- Single primary CTA
- No "twin" terminology

**Loading States:**
- Skeleton screens for cards
- Pulsing dots for inline loading
- Progress bar for long operations (building)

---

## H) ACCEPTANCE CRITERIA & QA CHECKLIST

### H.1 Onboarding Acceptance Criteria

| Criteria | Test | Expected Result |
|----------|------|-----------------|
| Screen 1 loads | Navigate to /onboarding | Shows full name field, pre-filled from auth |
| Screen 1 validation | Click Continue with empty name | Shows validation error |
| Screen 1 completion | Enter name, click Continue | Creates twin, advances to screen 2 |
| Screen 2 skip | Click Skip | Advances to screen 3 |
| Screen 3 validation | Click Finish with no sources | Shows "need at least 1 source" error |
| Screen 3 completion | Add URL, click Finish | Submits sources, redirects to building |
| Total time | Complete all 3 screens | < 5 minutes |
| Backend trigger | Complete screen 3 | Pipeline run created, status=pending |

### H.2 Building Flow Acceptance Criteria

| Criteria | Test | Expected Result |
|----------|------|-----------------|
| Progress display | View building screen | Shows progress bar, current stage text |
| Polling | Wait on building screen | Updates every 3-10 seconds |
| Completion | Pipeline completes | Redirects to profile with appropriate tier UI |
| Gaps handling | Complete with score 60 | Shows "with_gaps" tier, suggests adding sources |

### H.3 Profile Overview Acceptance Criteria

| Criteria | Test | Expected Result |
|----------|------|-----------------|
| Score display | View profile | Shows 0-100 score with color coding |
| Stats accuracy | Compare to backend | Source/claim counts match database |
| Navigation | Click source count | Navigates to sources page |
| Next actions | View with open contradictions | Shows "resolve conflicts" as priority action |

### H.4 Sources Acceptance Criteria

| Criteria | Test | Expected Result |
|----------|------|-----------------|
| List display | View sources page | Shows all sources with authority badges |
| Filtering | Click "Needs Review" tab | Filters to unverified sources only |
| Exclude action | Click "Not me" on source | Shows confirmation, excludes on confirm |
| Detail drawer | Click source card | Opens drawer with full metadata |

### H.5 Claims Acceptance Criteria

| Criteria | Test | Expected Result |
|----------|------|-----------------|
| Grouping | View claims page | Claims grouped by type (Work, Education, etc.) |
| Evidence viewer | Click claim | Shows evidence spans with quotes |
| Verify action | Click Verify on claim | Updates status, increments verified count |
| Bulk actions | Select multiple claims | Shows bulk action toolbar |

### H.6 Public Share Acceptance Criteria

| Criteria | Test | Expected Result |
|----------|------|-----------------|
| No private data | View public profile as visitor | No private claims visible |
| Score display | View public profile | Shows answerability score |
| Chat works | Send message as visitor | Returns response with citations |
| Policy enforcement | Set high confidence threshold | Low-confidence queries get fallback |

### H.7 Accessibility Acceptance Criteria

| Criteria | Test | Expected Result |
|----------|------|-----------------|
| Keyboard nav | Tab through onboarding | All interactive elements reachable |
| Screen reader | Enable VoiceOver/TalkBack | Labels read correctly, no "twin" references |
| Color independence | View in grayscale | Grade labels visible, not just color |
| Focus states | Tab to buttons | Visible focus ring on all elements |

### H.8 End-to-End QA Checklist

#### Onboarding E2E
- [ ] User can complete onboarding in < 5 minutes
- [ ] User can skip optional step 2
- [ ] User must provide at least 1 source
- [ ] Pipeline triggers automatically on completion
- [ ] Progress updates in real-time

#### Profile Management E2E
- [ ] User can view profile overview
- [ ] User can add new sources
- [ ] User can verify/reject claims
- [ ] User can resolve timeline conflicts
- [ ] User can configure policies

#### Public Sharing E2E
- [ ] Visitor can view public profile
- [ ] Visitor can ask questions
- [ ] Citations display when required
- [ ] Private data never leaks
- [ ] Confidence gating works correctly

#### Chat E2E
- [ ] Owner chat uses full capabilities
- [ ] Public chat respects policies
- [ ] Fallback messages appear appropriately
- [ ] Citations render correctly
- [ ] No "twin" terminology in UI copy

### H.9 Performance Criteria

| Metric | Target |
|--------|--------|
| Onboarding screen load | < 1s |
| Profile overview load | < 2s |
| Sources list load (50 items) | < 1s |
| Claims list load (100 items) | < 1.5s |
| Chat response start | < 2s |
| Pipeline progress polling | Every 3-10s |

### H.10 Browser/Device Support

| Browser | Minimum Version |
|---------|-----------------|
| Chrome | 120+ |
| Firefox | 120+ |
| Safari | 17+ |
| Edge | 120+ |

| Device | Support |
|--------|---------|
| Desktop | Full |
| Tablet | Full |
| Mobile | Responsive, touch-optimized |

---

## I) IMPLEMENTATION MILESTONES

### Week 1: Foundation & Onboarding
**Focus:** New 3-screen onboarding, API client, shared components

**Tasks:**
- [ ] Create `usePersonCompleteness()` hook
- [ ] Build shared components: ScoreCircle, AuthorityBadge, EvidencePopover
- [ ] Implement Screen 1: Identity
- [ ] Implement Screen 2: Optional Hints
- [ ] Implement Screen 3: Add Content
- [ ] Implement Building screen with polling

**Done Criteria:**
- User can complete new onboarding flow
- Pipeline triggers correctly
- Progress displays accurately

### Week 2: Profile Overview & Sources
**Focus:** Main hub screen and source management

**Tasks:**
- [ ] Build Profile Overview page
- [ ] Implement Sources list with filtering
- [ ] Implement Source detail drawer
- [ ] Build authority tier badges
- [ ] Implement exclude source flow

**Done Criteria:**
- Profile Overview displays real data
- Sources can be filtered and viewed
- Exclude action works with confirmation

### Week 3: Claims & Timeline
**Focus:** Claim verification and timeline visualization

**Tasks:**
- [ ] Build Claims list with grouping
- [ ] Implement Claim detail modal
- [ ] Build Evidence viewer
- [ ] Implement verify/reject actions
- [ ] Build Timeline visualization
- [ ] Implement conflict detection UI

**Done Criteria:**
- Claims display with evidence
- Timeline shows events chronologically
- Conflicts can be resolved

### Week 4: Topics, Review Queue & Policies
**Focus:** Coverage analysis, guided review, audience policies

**Tasks:**
- [ ] Build Topics grid with scores
- [ ] Implement Gaps section
- [ ] Build Review Queue with guided flow
- [ ] Implement Policies screen
- [ ] Build audience selector

**Done Criteria:**
- Topics show score breakdowns
- Review Queue guides through issues
- Policies save per audience

### Week 5: Public Share & Chat Integration
**Focus:** Visitor experience and runtime confidence

**Tasks:**
- [ ] Build Public Share page
- [ ] Implement public chat with gating
- [ ] Add confidence indicators to chat
- [ ] Implement citations UI
- [ ] Add fallback message display

**Done Criteria:**
- Public profile shows correct data
- Chat respects policies
- Confidence gating works

### Week 6: Polish, Testing & QA
**Focus:** Testing, accessibility, performance

**Tasks:**
- [ ] Write E2E tests for critical flows
- [ ] Conduct accessibility audit
- [ ] Performance optimization
- [ ] Cross-browser testing
- [ ] Documentation review

**Done Criteria:**
- All acceptance criteria pass
- Accessibility audit passed
- Performance targets met
- QA checklist complete

---

## J) BACKEND GAPS SUMMARY

The following backend endpoints need to be implemented to support this UI plan:

| Priority | Endpoint | Effort | Notes |
|----------|----------|--------|-------|
| P0 | GET /person-completeness/summary/{twin_id} | 1 day | Aggregates all tables |
| P0 | GET /person-sources | 1 day | Query person_source_registry |
| P0 | PATCH /person-sources/{id} | 1/2 day | Update verification status |
| P0 | GET /person-claims | 1 day | Query person_claims |
| P0 | GET /person-claims/{id}/evidence | 1 day | Join with evidence_spans |
| P0 | PATCH /person-claims/{id} | 1/2 day | Update approval status |
| P0 | GET /person-topics | 1 day | Query person_topic_profiles |
| P0 | GET /person-completeness-runs/{id}/status | 1/2 day | Pipeline status polling |
| P1 | GET /person-timeline | 1 day | Query person_timeline_events |
| P1 | GET /person-contradictions | 1 day | Query person_contradictions |
| P1 | POST /person-contradictions/{id}/resolve | 1/2 day | Resolution logic |
| P1 | GET/PUT /person-runtime-policies/{twin_id} | 1 day | CRUD for policies |
| P1 | GET /public-profiles/{twin_id} | 1 day | Public-safe data |

**Total Backend Effort:** ~10-12 days

---

**END OF SPECIFICATION**

*This document is ready for contractor handoff. All sections include file/line evidence from the existing codebase, specific API contracts, and measurable acceptance criteria.*
