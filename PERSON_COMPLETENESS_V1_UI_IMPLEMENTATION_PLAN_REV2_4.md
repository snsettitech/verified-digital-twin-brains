# Person Completeness v1 - UI Implementation Plan
## REVISION 2.4: "Profile" Language, One Profile Per User, Fixed Onboarding Flow

**Prepared for:** Contractor/Development Team  
**Date:** 2026-02-25  
**Version:** 2.4 (Mandatory UX Restructuring)  
**Classification:** Contractor-Ready Handoff Document

---

## MANDATORY CHANGES IN THIS REVISION

| Change | Requirement |
|--------|-------------|
| **Zero "twin" in UI** | All user-facing strings use "Profile", "Digital Brain", or person's name |
| **One profile per user** | Auto-load single profile; no selector; no multi-profile UX |
| **Onboarding 3 screens** | Name (required), Optional hints (skippable), Add content (conditional) |
| **Fixed name-only flow** | Use `/deep-research/runs` returned `twin_id`; no duplicate creation |
| **No email field** | Use Supabase auth email; no manual entry |
| **No profile name field** | Full name = profile display name |

---

## 1. TERMINOLOGY MAPPING (INTERNAL vs USER-FACING)

### 1.1 Internal Code (Keep "twin_id" for Backend Compatibility)

```typescript
// INTERNAL: Use existing identifiers (don't refactor backend)
interface ProfileContextType {
  profileId: string;        // Maps to twin_id in API calls
  profile: Profile | null;  // Maps to twin object
  refreshProfile: () => Promise<void>;
}

// API calls still use twin_id internally
await getTwin(profileId, '/twins/{twinId}/person-sources');
```

### 1.2 User-Facing Copy (NEVER Use "Twin")

| ❌ NEVER Use | ✅ Always Use |
|-------------|--------------|
| "Twin" | "Profile" |
| "Digital Twin" | "Digital Brain" or "AI Profile" |
| "Twin Name" | "Your Name" or "Profile Name" |
| "Create Twin" | "Create Your Profile" |
| "My Twins" | "My Profile" |
| "Active Twin" | "Your Profile" |
| "Twin Selector" | N/A (removed) |

### 1.3 UI Copy Audit Checklist

**Before delivery, verify NO string contains:**
- [ ] "twin" (case insensitive)
- [ ] "Twin" 
- [ ] "TWIN"
- [ ] "twinId" in user-facing error messages
- [ ] "digital twin" (use "Digital Brain")

**QA Command:**
```bash
grep -ri "twin" frontend/app/onboarding/ frontend/app/dashboard/profile/ \
  --include="*.tsx" --include="*.ts" | grep -v "twin_id" | grep -v "// "
# Should return zero results
```

---

## 2. ONE PROFILE PER USER ARCHITECTURE

### 2.1 Profile Context (Replaces Multi-Twin State)

**File:** `frontend/lib/context/ProfileContext.tsx` (NEW - Replaces TwinContext for v1)

```typescript
'use client';

import { createContext, useContext, useState, useEffect } from 'react';

interface Profile {
  id: string;              // Internal: maps to twin_id
  name: string;            // User's full name
  headline?: string;
  status: 'draft' | 'building' | 'ready' | 'needs_attention';
  answerabilityScore: number;
  settings?: Record<string, unknown>;
}

interface ProfileContextType {
  // Single profile state (never an array)
  profile: Profile | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  refreshProfile: () => Promise<void>;
  createProfile: (data: CreateProfileData) => Promise<string>; // Returns profileId
}

const ProfileContext = createContext<ProfileContextType | undefined>(undefined);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // On mount: fetch user's single profile
  useEffect(() => {
    loadProfile();
  }, []);
  
  const loadProfile = async () => {
    setIsLoading(true);
    try {
      // Try to fetch existing profile
      const response = await authFetchStandalone('/profile'); // NEW endpoint
      if (response.ok) {
        const data = await response.json();
        setProfile(data);
      } else if (response.status === 404) {
        // No profile exists - will route to onboarding
        setProfile(null);
      }
    } finally {
      setIsLoading(false);
    }
  };
  
  const createProfile = async (data: CreateProfileData): Promise<string> => {
    // Creates profile and returns ID
    const response = await authFetchStandalone('/profile', {
      method: 'POST',
      body: JSON.stringify(data)
    });
    const result = await response.json();
    setProfile(result);
    return result.id;
  };
  
  return (
    <ProfileContext.Provider value={{ profile, isLoading, error: null, refreshProfile: loadProfile, createProfile }}>
      {children}
    </ProfileContext.Provider>
  );
}

export const useProfile = () => {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error('useProfile must be used within ProfileProvider');
  return ctx;
};
```

### 2.2 Auto-Load Logic

**File:** `frontend/app/dashboard/layout.tsx` or `frontend/middleware.ts`

```typescript
// Auto-route based on profile existence
export function DashboardGuard({ children }: { children: React.ReactNode }) {
  const { profile, isLoading } = useProfile();
  const router = useRouter();
  
  useEffect(() => {
    if (isLoading) return;
    
    if (!profile) {
      // No profile exists - route to onboarding
      router.push('/onboarding');
    } else if (profile.status === 'building') {
      // Profile building - route to building screen
      router.push('/onboarding/building');
    }
    // else: profile ready - stay on dashboard
  }, [profile, isLoading]);
  
  if (isLoading) return <LoadingSpinner />;
  if (!profile) return null; // Will redirect
  
  return children;
}
```

### 2.3 Backend Endpoint for Single Profile (NEW)

**File:** `backend/routers/profile.py` (NEW - wraps twins with single-profile semantics)

```python
@router.get("/profile")
async def get_user_profile(user=Depends(get_current_user)):
    """
    Get the user's single profile.
    Returns 404 if no profile exists (triggers onboarding).
    """
    tenant_id = user.get("tenant_id")
    
    # Get most recent active "twin" for this user
    result = supabase.table("twins") \
        .select("*") \
        .eq("tenant_id", tenant_id) \
        .is_("settings->>deleted_at", "null") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    
    if not result.data:
        raise HTTPException(404, "Profile not found")
    
    twin = result.data[0]
    
    # Map to "profile" response (no "twin" in keys)
    return {
        "id": twin["id"],
        "name": twin["name"],  # User's full name
        "headline": twin.get("settings", {}).get("headline"),
        "status": map_twin_status_to_profile(twin["status"]),
        "answerabilityScore": get_answerability_score(twin["id"]),
        "createdAt": twin["created_at"]
    }

@router.post("/profile")
async def create_user_profile(
    request: CreateProfileRequest,
    user=Depends(get_current_user)
):
    """
    Create user's profile (single twin per user).
    Idempotent: returns existing if already created.
    """
    tenant_id = user.get("tenant_id")
    
    # Check for existing
    existing = await get_user_profile(user)
    if existing:
        return existing  # Idempotent
    
    # Create new twin (internal), return as profile
    twin_data = {
        "name": request.full_name,  # User's full name
        "tenant_id": tenant_id,
        "status": "draft",
        "settings": {
            "headline": request.headline,
            "build_mode": request.build_mode
        }
    }
    
    result = supabase.table("twins").insert(twin_data).execute()
    return map_twin_to_profile(result.data[0])
```

---

## 3. ONBOARDING (3 SCREENS MAX)

### 3.1 Screen 1: Your Identity

**Route:** `/onboarding`

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  ← Back to home                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│              Create Your Profile                        │
│                                                         │
│  Your Full Name *                                       │
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
│  ───── How would you like to build? ─────              │
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

**Fields:**
| Field | Type | Required | Source |
|-------|------|----------|--------|
| full_name | text | ✅ | User input (no pre-fill, user can edit) |
| headline | text | ❌ | User input |
| build_mode | radio | ✅ | "with_links" or "name_only" |

**No Email Field:** Use `user.email` from Supabase auth.

**No Profile Name Field:** `full_name` becomes the display name.

**API Calls:**
```typescript
// WITH LINKS MODE
if (build_mode === 'with_links') {
  // 1. Create profile first
  const profile = await createProfile({
    full_name: fullName,
    headline: headline,
    build_mode: 'with_links'
  });
  
  // 2. Go to hints screen
  router.push('/onboarding?step=2');
}

// NAME-ONLY MODE  
if (build_mode === 'name_only') {
  // 1. Start deep research FIRST (creates profile internally)
  const { research_run_id, twin_id: profileId } = await post('/deep-research/runs', {
    full_name: fullName,
    headline: headline,
    mode: 'name_only'
  });
  
  // 2. SKIP profile creation - use returned profileId
  // 3. Go directly to building
  router.push(`/onboarding/building?research_run_id=${research_run_id}&profile_id=${profileId}`);
}
```

### 3.2 Screen 2: Optional Hints (With Links Only)

**Route:** `/onboarding?step=2`

**Show if:** `build_mode === 'with_links'`

**Skip if:** `build_mode === 'name_only'`

**Fields:**
| Field | Type | Required |
|-------|------|----------|
| role | select | ❌ |
| location | text | ❌ |
| expertise_tags | multi-select | ❌ |

**CTA:** "Continue →" or "Skip"

**API:**
```typescript
PATCH /profile  // Updates current user's profile
{
  "hints": { role, location, expertise_tags }
}
```

### 3.3 Screen 3: Add Your Content (With Links Only)

**Route:** `/onboarding?step=3`

**Show if:** `build_mode === 'with_links'`

**Validation:** Must have ≥1 source (URL or file)

**API:**
```typescript
// Submit URLs
POST /persona/link-compile/jobs/mode-c
{ "urls": [...] }

// Upload files
POST /persona/link-compile/jobs/mode-a
FormData: { files[] }

// Trigger person completeness
POST /profile/run-completeness
{ "trigger": "onboarding_complete" }

// Response: { run_id }
router.push(`/onboarding/building?run_id=${run_id}`);
```

### 3.4 Building Screen

**Route:** `/onboarding/building?run_id={id}` OR `/onboarding/building?research_run_id={id}&profile_id={id}`

**Polling:**
```typescript
// For with-links: poll person completeness
const status = await get(`/profile/build-status?run_id=${runId}`);

// For name-only: poll deep research first, then person completeness
const researchStatus = await get(`/deep-research/runs/${researchRunId}`);
if (researchStatus.status === 'completed') {
  // Now poll person completeness
  const pcStatus = await get(`/profile/build-status?profile_id=${profileId}`);
}
```

---

## 4. INFORMATION ARCHITECTURE

### 4.1 Navigation (No Selector)

**File:** `frontend/lib/navigation/config.ts`

```typescript
export const SIDEBAR_CONFIG: SidebarConfig = [
  {
    title: 'Your Profile',  // Changed from "Build"
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
      { name: 'Chat with Your Brain', href: '/dashboard/chat', icon: 'chat' },
      { name: 'Share Profile', href: '/dashboard/share', icon: 'share' },
    ]
  },
  {
    title: 'Settings',
    items: [
      { name: 'Profile Settings', href: '/dashboard/settings', icon: 'settings' },
      { name: 'Audience & Safety', href: '/dashboard/settings/policies', icon: 'shield' },
    ]
  }
];
```

**No TwinSelector in Sidebar.**

### 4.2 Page Titles

| Route | Title |
|-------|-------|
| `/dashboard/profile` | "Your Profile Overview" |
| `/dashboard/profile/sources` | "Your Sources" |
| `/dashboard/profile/claims` | "Your Claims" |
| `/dashboard/chat` | "Chat with Your Digital Brain" |
| `/dashboard/share` | "Share Your Profile" |

---

## 5. API CONTRACT (PROFILE-CENTRIC)

### 5.1 New Profile Endpoints (Backend)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profile` | Get user's single profile (404 if none) |
| POST | `/profile` | Create profile (idempotent) |
| PATCH | `/profile` | Update profile settings |
| GET | `/profile/build-status` | Poll build progress |
| POST | `/profile/run-completeness` | Trigger person completeness |

### 5.2 Existing Endpoints (Unchanged)

| Method | Endpoint | Notes |
|--------|----------|-------|
| POST | `/deep-research/runs` | Returns `{ research_run_id, twin_id }` |
| GET | `/deep-research/runs/{id}` | Poll research status |

### 5.3 Legacy Twin Endpoints (Internal Use)

```typescript
// Keep using these internally, but wrap in ProfileContext
// User never sees "twin" in UI

GET /twins/{twin_id}/person-sources
PATCH /twins/{twin_id}/person-sources/{id}
GET /twins/{twin_id}/person-claims
// etc.
```

---

## 6. ACCEPTANCE CRITERIA & QA

### 6.1 Zero "Twin" in UI

| Test | Method | Expected |
|------|--------|----------|
| No "twin" in UI strings | `grep -ri "twin" frontend/app --include="*.tsx" \| grep -v twin_id` | Zero results |
| No "twin" in error messages | Check all toast/error messages | None contain "twin" |
| No "twin" in page titles | View all page `<title>` tags | None contain "twin" |
| No "twin" in navigation | Check sidebar labels | None contain "twin" |

### 6.2 One Profile Per User

| Test | Method | Expected |
|------|--------|----------|
| No profile selector | Open dashboard | No selector visible |
| Auto-load profile | Login with existing profile | Dashboard loads with profile |
| Auto-route to onboarding | Login with no profile | Redirected to /onboarding |
| Single profile enforced | Try to create second profile | Returns existing profile (idempotent) |

### 6.3 Onboarding Flow

| Test | Method | Expected |
|------|--------|----------|
| 3 screens max | Complete onboarding | Exactly 3 screens (or 2 if skip hints) |
| Full name required | Try continue without name | Validation error |
| No email field | Inspect screen 1 | No email input field |
| No profile name field | Inspect screen 1 | No "profile name" or "twin name" field |
| Name becomes display | Complete onboarding | Profile shows full name |
| With-links flow | Select "I have links" | Goes to hints → sources → building |
| Name-only flow | Select "Just my name" | Skips hints/sources, goes to building |
| Name-only creates one profile | Check database after name-only | Exactly one twin row created |
| With-links creates one profile | Check database after with-links | Exactly one twin row created |

### 6.4 No Duplicate Profile Creation

| Test | Steps | Expected |
|------|-------|----------|
| Name-only single creation | 1. Start name-only onboarding<br>2. Check DB before completion<br>3. Complete onboarding | Only one twin created (by deep-research) |
| With-links single creation | 1. Start with-links onboarding<br>2. Check DB<br>3. Complete onboarding | Only one twin created (at start) |
| Refresh during onboarding | Refresh on screen 2 | Resumes at screen 2, no duplicate |
| Back button | Go to screen 2, back to 1, forward | No duplicate created |
| Idempotent POST /profile | Call POST /profile twice | Returns same profile both times |

### 6.5 Name-Only Flow Correctness

| Test | Steps | Expected |
|------|-------|----------|
| Correct API order | Network tab during name-only | 1. POST /deep-research/runs<br>2. GET /deep-research/runs/{id} (polling)<br>3. NO POST /profile<br>4. NO POST /twins |
| Returned profileId used | Check router.push | Uses `twin_id` from deep-research response |
| Building shows progress | View building screen | Shows name discovery, source crawling, etc. |
| Completion redirects | Wait for completion | Redirects to /dashboard/profile |

### 6.6 Navigation Labels

| Test | Check | Expected |
|------|-------|----------|
| Sidebar section title | "Your Profile" (not "Build" or "Twins") | ✅ |
| Chat link | "Chat with Your Brain" or "Chat with Your Profile" | ✅ |
| Share link | "Share Profile" or "Share Your Profile" | ✅ |
| Settings link | "Profile Settings" | ✅ |

---

## 7. IMPLEMENTATION MILESTONES

### Week 0: Profile Context & Terminology
- [ ] Create `ProfileContext` (single profile, no array)
- [ ] Implement `GET /profile`, `POST /profile` endpoints
- [ ] Replace all "twin" UI strings with "Profile"/"Brain"
- [ ] Remove TwinSelector from sidebar
- [ ] Add auto-load and auto-routing logic

### Week 1: Onboarding v2
- [ ] Screen 1: Name (required), headline (optional), build mode
- [ ] Remove email field
- [ ] Remove profile name field
- [ ] Implement name-only flow (no duplicate creation)
- [ ] Screen 2: Optional hints (conditional)
- [ ] Screen 3: Add content (conditional)
- [ ] Building screen with correct polling

### Week 2: Profile Screens
- [ ] Profile Overview
- [ ] Sources
- [ ] Claims

### Week 3: Remaining Screens
- [ ] Timeline
- [ ] Topics
- [ ] Review Queue

### Week 4: Settings & Public
- [ ] Audience Policies
- [ ] Public share (tokenized)

### Week 5: QA & Terminology Audit
- [ ] Run "zero twin" grep check
- [ ] Test duplicate creation prevention
- [ ] Test one-profile enforcement
- [ ] Security audit

---

## 8. BACKEND GAPS

### 8.1 New Profile Endpoints

| Priority | Endpoint | Description |
|----------|----------|-------------|
| P0 | `GET /profile` | Get user's single profile (404 if none) |
| P0 | `POST /profile` | Create profile (idempotent) |
| P0 | `PATCH /profile` | Update profile |
| P0 | `GET /profile/build-status` | Unified build status |
| P0 | `POST /profile/run-completeness` | Trigger PC pipeline |

### 8.2 Modified Deep Research

| Change | Description |
|--------|-------------|
| Ensure `twin_id` returned | `/deep-research/runs` must return `twin_id` for name-only flow |

### 8.3 Standard Person Endpoints

| Priority | Endpoint |
|----------|----------|
| P0 | `GET /twins/{id}/person-sources` |
| P0 | `GET /twins/{id}/person-claims` |
| P0 | `GET /twins/{id}/person-completeness/summary` |
| P1 | `GET /twins/{id}/person-timeline` |
| P1 | `GET /twins/{id}/person-topics` |
| P1 | `GET /twins/{id}/person-runtime-policies` |

---

**END OF REVISION 2.4**

*Zero "twin" in UI. One profile per user. Fixed onboarding flow. Contractor-ready.*
