# Frontend Keep, Tweak, Refactor, Delete Plan

**Last Updated:** 2026-02-04  
**Product:** Clone-for-Experts (Web-Only)  
**Status:** PLAN ONLY

---

## Summary

This document categorizes every frontend file according to its fate in the Clone-for-Experts restructure:

- **KEEP** = Use as-is, no changes
- **TWEAK** = Minor modifications (rename, props, styling)
- **REFACTOR** = Significant restructure or split
- **DELETE** = Remove or defer (out of scope)

---

## Route Pages (`frontend/app/`)

### KEEP AS-IS

| File | Reason |
|------|--------|
| `app/layout.tsx` | Root layout, no changes |
| `app/page.tsx` | Landing page, minor copy updates |
| `app/auth/login/page.tsx` | Auth flow works |
| `app/auth/signup/page.tsx` | Auth flow works |
| `app/auth/callback/page.tsx` | OAuth callback |
| `app/auth/forgot-password/page.tsx` | Password reset |
| `app/auth/layout.tsx` | Auth layout |
| `app/share/[twin_id]/[token]/page.tsx` | Public chat, core feature |

### KEEP WITH TWEAKS

| File | Changes Needed |
|------|----------------|
| `app/dashboard/layout.tsx` | Update sidebar import, rename dashboard → studio |
| `app/dashboard/page.tsx` | Refocus as Studio home, remove conversation modal |
| `app/dashboard/knowledge/page.tsx` | Rename to content, update header copy |
| `app/dashboard/simulator/page.tsx` | Rename to quality, add verification UI |
| `app/dashboard/widget/page.tsx` | Split into embed + share pages |
| `app/dashboard/settings/page.tsx` | Split into identity (twin) + settings (account) |
| `app/dashboard/api-keys/page.tsx` | Keep for developer features |
| `app/dashboard/metrics/page.tsx` | Move to /operate/analytics |
| `app/onboarding/page.tsx` | Simplify steps, remove specialization if not needed |

### REFACTOR

| File | Refactor Description |
|------|----------------------|
| `app/dashboard/page.tsx` | Extract conversation inbox to `/operate/conversations` |
| `app/dashboard/settings/page.tsx` | Split: Twin settings → `/studio/identity`, Account → `/settings` |
| `app/dashboard/widget/page.tsx` | Split: Embed code → `/launch/embed`, Share → `/launch/share`, Brand → `/launch/brand` |

### DELETE / DEFER

| File | Reason |
|------|--------|
| `app/auth/accept-invitation/page.tsx` | Team invites not in MVP |
| `app/dashboard/access-groups/page.tsx` | Out of scope (enterprise) |
| `app/dashboard/access-groups/[group_id]/` | Out of scope |
| `app/dashboard/actions/page.tsx` | Out of scope (automations) |
| `app/dashboard/actions/connectors/` | Out of scope |
| `app/dashboard/actions/triggers/` | Out of scope |
| `app/dashboard/actions/history/` | Out of scope |
| `app/dashboard/actions/inbox/` | Out of scope |
| `app/dashboard/escalations/page.tsx` | Out of scope (safety) |
| `app/dashboard/governance/page.tsx` | Out of scope (governance UI) |
| `app/dashboard/right-brain/page.tsx` | Unused feature |
| `app/dashboard/users/page.tsx` | Team management not in MVP |
| `app/dashboard/brain/page.tsx` | Duplicate/unused |
| `app/dashboard/studio/page.tsx` | Consolidate with dashboard |
| `app/dashboard/twins/page.tsx` | Single-twin MVP, selector in header |
| `app/dashboard/twins/[id]/page.tsx` | Single-twin MVP |

---

## UI Components (`frontend/components/ui/`)

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `Badge.tsx` | Status indicators |
| `Card.tsx` | Content containers |
| `EmptyState.tsx` | Empty data placeholders |
| `ErrorBoundary.tsx` | Error catching |
| `Modal.tsx` | Dialog system |
| `PageTransition.tsx` | Animations |
| `Skeleton.tsx` | Loading states |
| `SkipNavigation.tsx` | Accessibility |
| `StatCard.tsx` | Metrics display |
| `SyncStatusBanner.tsx` | Connection status |
| `Toast.tsx` | Notifications |
| `Toggle.tsx` | Switch inputs |
| `TwinSelector.tsx` | Twin picker |
| `VerificationBadge.tsx` | Status badge |
| `index.tsx` | Exports |

### DELETE / DEFER

| File | Reason |
|------|--------|
| `PremiumModal.tsx` | Out of scope (Stripe gating) |
| `DeleteTwinModal.tsx` | KEEP - needed for settings |

---

## Console Components (`frontend/components/console/`)

### KEEP WITH TWEAKS

| File | Changes |
|------|---------|
| `ConsoleLayout.tsx` | Repurpose for Studio section |
| `TabNavigation.tsx` | Update tab structure |
| `index.ts` | Update exports |

### Console Tabs (`frontend/components/console/tabs/`)

| File | Status | Reason |
|------|--------|--------|
| `ChatTab.tsx` | TWEAK | Rename to QualityTestTab |
| `KnowledgeTab.tsx` | TWEAK | Rename to ContentTab |
| `OverviewTab.tsx` | REFACTOR | Extract stats for analytics |
| `PublicChatTab.tsx` | KEEP | Embed preview |
| `PublishTab.tsx` | REFACTOR | Split into Share/Embed/Brand pages |
| `SettingsTab.tsx` | REFACTOR | Split into Identity/Settings |
| `TrainingTab.tsx` | TWEAK | Integrate with Quality testing |
| `ActionsTab.tsx` | DELETE | Out of scope |
| `EscalationsTab.tsx` | DELETE | Out of scope |

---

## Chat Components (`frontend/components/Chat/`)

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `ChatInterface.tsx` | Main chat UI |
| `ChatWidget.tsx` | Embeddable widget |
| `GraphContext.tsx` | Knowledge context panel |
| `MessageList.tsx` | Message renderer |
| `InterviewInterface.tsx` | Voice capture |

---

## Ingestion Components (`frontend/components/ingestion/`)

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `UnifiedIngestion.tsx` | Multi-source upload |

---

## Onboarding Components (`frontend/components/onboarding/`)

### KEEP WITH TWEAKS

| File | Changes |
|------|---------|
| `Wizard.tsx` | Simplify step count |
| `steps/WelcomeStep.tsx` | Update copy |
| `steps/CreateTwinStep.tsx` | Keep |
| `steps/ClaimIdentityStep.tsx` | Merge with identity |
| `steps/DefineExpertiseStep.tsx` | Simplify |
| `steps/AddContentStep.tsx` | Keep |
| `steps/SetPersonalityStep.tsx` | Keep |
| `steps/PreviewTwinStep.tsx` | Keep |
| `steps/LaunchStep.tsx` | Keep |
| `index.ts` | Update exports |

### DELETE / DEFER

| File | Reason |
|------|--------|
| `steps/ChooseSpecializationStep.tsx` | Simplify to single vertical |
| `steps/SeedFAQsStep.tsx` | Optional, defer |
| `steps/TrainingStep.tsx` | Merge with preview |
| `steps/FirstChatStep.tsx` | Merge with preview |

---

## Interview Components (`frontend/components/interview/`)

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `InterviewControls.tsx` | Voice recording |
| `TranscriptPanel.tsx` | Transcript display |
| `index.ts` | Exports |

---

## Other Components

### KEEP WITH TWEAKS

| File | Changes |
|------|---------|
| `components/Sidebar.tsx` | Major restructure for new IA |
| `components/TILFeed.tsx` | Evaluate for Operate section |
| `components/FeedbackWidget.tsx` | Keep for quality feedback |

### DELETE / DEFER

| File | Reason |
|------|--------|
| `components/Brain/` | Unused |
| `components/cognitive/` | Backend-focused, evaluate |
| `components/features/` | Evaluate purpose |

---

## Library Files (`frontend/lib/`)

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `lib/api.ts` | API base URL resolver |
| `lib/context/TwinContext.tsx` | Core state |
| `lib/context/ThemeContext.tsx` | Theme toggle |
| `lib/context/index.ts` | Exports |
| `lib/hooks/useAuthFetch.ts` | Auth wrapper |
| `lib/supabase/client.ts` | Supabase client |
| `lib/supabase/server.ts` | Server client |

### REFACTOR

| File | Changes |
|------|---------|
| `lib/navigation/config.ts` | Update to Studio/Launch/Operate structure |
| `lib/navigation/types.ts` | Add section type |

---

## Context Files (`frontend/contexts/`)

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `SpecializationContext.tsx` | Vertical config |
| `index.ts` | Exports |

---

## Public Files (`frontend/public/`)

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `widget.js` | Embeddable widget script |
| `favicon.ico` | Favicon |

---

## Configuration Files

### KEEP AS-IS

| File | Purpose |
|------|---------|
| `middleware.ts` | Auth middleware |
| `next.config.ts` | Next.js config |
| `tsconfig.json` | TypeScript config |
| `package.json` | Dependencies |
| `tailwind.config.js` | Tailwind (if exists) |
| `globals.css` | Global styles |

---

## Summary Counts

| Action | Pages | Components | Total |
|--------|-------|------------|-------|
| KEEP | 9 | 25 | 34 |
| TWEAK | 9 | 12 | 21 |
| REFACTOR | 3 | 4 | 7 |
| DELETE | 16 | 8 | 24 |

**Total files reviewed:** 86

---

## Priority Order

### Phase 1: Foundation
1. Update `lib/navigation/config.ts` with new structure
2. Refactor `Sidebar.tsx` for new IA
3. Keep all UI components as-is

### Phase 2: Studio Section
1. Rename `/dashboard/knowledge` → `/studio/content`
2. Create `/studio/identity` from settings split
3. Rename `/dashboard/simulator` → `/studio/quality`
4. Create `/studio/roles` (new)

### Phase 3: Launch Section
1. Split widget page into `/launch/share`, `/launch/embed`, `/launch/brand`
2. Create `PublishTab` refactors

### Phase 4: Operate Section
1. Create `/operate/conversations` from dashboard extraction
2. Create `/operate/audience` (new)
3. Move `/dashboard/metrics` → `/operate/analytics`

### Phase 5: Cleanup
1. Delete out-of-scope pages
2. Remove unused components
3. Update onboarding flow
