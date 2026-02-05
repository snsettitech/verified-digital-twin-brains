# Frontend Route and Component Inventory

**Last Updated:** 2026-02-04

This document provides a comprehensive inventory of the current frontend structure for the Verified Digital Twin Brain application. It serves as the baseline for the web-only Clone-for-Experts product redesign.

---

## Current Route Map

### Navigation Structure (`frontend/lib/navigation/config.ts`)

The sidebar is organized into 4 sections:

```
Build
├── Dashboard      → /dashboard
├── Knowledge      → /dashboard/knowledge

Train
├── Simulator      → /dashboard/simulator

Share
├── Widget         → /dashboard/widget
├── API Keys       → /dashboard/api-keys

Settings
├── Settings       → /dashboard/settings
```

### Complete Route Inventory

| Route | Page File | Purpose | Status |
|-------|-----------|---------|--------|
| `/` | `app/page.tsx` | Landing page | Active |
| `/auth/login` | `app/auth/login/page.tsx` | Login | Active |
| `/auth/signup` | `app/auth/signup/page.tsx` | Registration | Active |
| `/auth/callback` | `app/auth/callback/page.tsx` | OAuth callback | Active |
| `/auth/forgot-password` | `app/auth/forgot-password/page.tsx` | Password reset | Active |
| `/auth/accept-invitation` | `app/auth/accept-invitation/page.tsx` | Team invites | Unused |
| `/onboarding` | `app/onboarding/page.tsx` | Wizard flow | Active |
| `/dashboard` | `app/dashboard/page.tsx` | Main dashboard | Active |
| `/dashboard/knowledge` | `app/dashboard/knowledge/page.tsx` | Content sources | Active |
| `/dashboard/knowledge/[source_id]` | (subfolders) | Source details | Active |
| `/dashboard/simulator` | `app/dashboard/simulator/page.tsx` | Test chat | Active |
| `/dashboard/widget` | `app/dashboard/widget/page.tsx` | Embed code | Active |
| `/dashboard/settings` | `app/dashboard/settings/page.tsx` | Twin/account settings | Active |
| `/dashboard/api-keys` | `app/dashboard/api-keys/page.tsx` | API key management | Active |
| `/dashboard/access-groups` | `app/dashboard/access-groups/page.tsx` | Access control | Unused |
| `/dashboard/access-groups/[group_id]` | (subfolders) | Group details | Unused |
| `/dashboard/actions` | `app/dashboard/actions/page.tsx` | Automations | Out of Scope |
| `/dashboard/actions/connectors` | (subfolders) | Integration setup | Out of Scope |
| `/dashboard/actions/triggers` | (subfolders) | Trigger config | Out of Scope |
| `/dashboard/actions/history` | (subfolders) | Execution logs | Out of Scope |
| `/dashboard/actions/inbox` | (subfolders) | Draft actions | Out of Scope |
| `/dashboard/escalations` | `app/dashboard/escalations/page.tsx` | Safety review | Out of Scope |
| `/dashboard/governance` | `app/dashboard/governance/page.tsx` | Governance (out of scope) | Out of Scope |
| `/dashboard/insights` | `app/dashboard/insights/page.tsx` | Analytics | Keep |
| `/dashboard/interview` | `app/dashboard/interview/page.tsx` | Voice capture | Keep |
| `/dashboard/jobs` | `app/dashboard/jobs/page.tsx` | Background jobs | Keep |
| `/dashboard/jobs/[id]` | (subfolders) | Job details | Keep |
| `/dashboard/metrics` | `app/dashboard/metrics/page.tsx` | System metrics | Keep |
| `/dashboard/right-brain` | `app/dashboard/right-brain/page.tsx` | Creative mode | Unused |
| `/dashboard/share` | `app/dashboard/share/page.tsx` | Share link mgmt | Keep |
| `/dashboard/studio` | `app/dashboard/studio/page.tsx` | Main console | Keep |
| `/dashboard/training-jobs` | `app/dashboard/training-jobs/page.tsx` | Training queue | Keep |
| `/dashboard/twins` | `app/dashboard/twins/page.tsx` | Twin list | Keep |
| `/dashboard/twins/[id]` | (subfolders) | Twin console | Keep |
| `/dashboard/users` | `app/dashboard/users/page.tsx` | Team members | Unused |
| `/dashboard/verified-qna` | `app/dashboard/verified-qna/page.tsx` | Verified answers | Keep |
| `/share/[twin_id]/[token]` | `app/share/[twin_id]/[token]/page.tsx` | Public chat | Active |

---

## Component Library

### Core UI Components (`frontend/components/ui/`)

| Component | File | Purpose | Reusable |
|-----------|------|---------|----------|
| Badge | `Badge.tsx` | Status indicators | ✅ |
| Card | `Card.tsx` | Content containers | ✅ |
| DeleteTwinModal | `DeleteTwinModal.tsx` | Destructive action confirmation | ✅ |
| EmptyState | `EmptyState.tsx` | Empty data placeholder | ✅ |
| ErrorBoundary | `ErrorBoundary.tsx` | Error catching wrapper | ✅ |
| Modal | `Modal.tsx` | Dialog system | ✅ |
| PageTransition | `PageTransition.tsx` | Animation wrapper | ✅ |
| PremiumModal | `PremiumModal.tsx` | Upsell prompts | Out of Scope |
| Skeleton | `Skeleton.tsx` | Loading states | ✅ |
| SkipNavigation | `SkipNavigation.tsx` | Accessibility skip links | ✅ |
| StatCard | `StatCard.tsx` | Metric display | ✅ |
| SyncStatusBanner | `SyncStatusBanner.tsx` | Connection status | ✅ |
| Toast | `Toast.tsx` | Notifications | ✅ |
| Toggle | `Toggle.tsx` | Switch input | ✅ |
| TwinSelector | `TwinSelector.tsx` | Twin picker dropdown | ✅ |
| VerificationBadge | `VerificationBadge.tsx` | Status badge | ✅ |

### Pre-configured Empty States (`frontend/components/ui/EmptyState.tsx`)

- `EmptyKnowledge` - No sources
- `EmptyConversations` - No chats
- `EmptyEscalations` - No pending reviews (Out of Scope)
- `EmptyActions` - No automations (Out of Scope)
- `EmptyTwins` - No twins created
- `EmptySearch` - No search results
- `ErrorState` - Error with retry

### Console Components (`frontend/components/console/`)

| Component | File | Purpose |
|-----------|------|---------|
| ConsoleLayout | `ConsoleLayout.tsx` | Tab container |
| TabNavigation | `TabNavigation.tsx` | Tab switcher |

### Console Tabs (`frontend/components/console/tabs/`)

| Tab | File | Maps To |
|-----|------|---------|
| ActionsTab | `ActionsTab.tsx` | Out of Scope |
| ChatTab | `ChatTab.tsx` | Studio → Testing |
| EscalationsTab | `EscalationsTab.tsx` | Out of Scope |
| KnowledgeTab | `KnowledgeTab.tsx` | Studio → Content |
| OverviewTab | `OverviewTab.tsx` | Dashboard |
| PublicChatTab | `PublicChatTab.tsx` | Visitor chat embed |
| PublishTab | `PublishTab.tsx` | Launch → Deploy |
| SettingsTab | `SettingsTab.tsx` | Studio → Identity |
| TrainingTab | `TrainingTab.tsx` | Studio → Training |

### Chat Components (`frontend/components/Chat/`)

| Component | File | Purpose |
|-----------|------|---------|
| ChatInterface | `ChatInterface.tsx` | Main chat UI |
| ChatWidget | `ChatWidget.tsx` | Embeddable widget |
| GraphContext | `GraphContext.tsx` | Knowledge context panel |
| InterviewInterface | `InterviewInterface.tsx` | Voice capture |
| MessageList | `MessageList.tsx` | Message renderer |

### Ingestion Components (`frontend/components/ingestion/`)

| Component | File | Purpose |
|-----------|------|---------|
| UnifiedIngestion | `UnifiedIngestion.tsx` | Multi-source upload |

### Onboarding Components (`frontend/components/onboarding/`)

| Component | File |
|-----------|------|
| Wizard | `Wizard.tsx` |
| WelcomeStep | `steps/WelcomeStep.tsx` |
| ChooseSpecializationStep | `steps/ChooseSpecializationStep.tsx` |
| CreateTwinStep | `steps/CreateTwinStep.tsx` |
| ClaimIdentityStep | `steps/ClaimIdentityStep.tsx` |
| DefineExpertiseStep | `steps/DefineExpertiseStep.tsx` |
| AddContentStep | `steps/AddContentStep.tsx` |
| SeedFAQsStep | `steps/SeedFAQsStep.tsx` |
| SetPersonalityStep | `steps/SetPersonalityStep.tsx` |
| PreviewTwinStep | `steps/PreviewTwinStep.tsx` |
| TrainingStep | `steps/TrainingStep.tsx` |
| FirstChatStep | `steps/FirstChatStep.tsx` |
| LaunchStep | `steps/LaunchStep.tsx` |

### Interview Components (`frontend/components/interview/`)

| Component | File |
|-----------|------|
| InterviewControls | `InterviewControls.tsx` |
| TranscriptPanel | `TranscriptPanel.tsx` |

---

## Context Providers

| Context | File | Purpose |
|---------|------|---------|
| TwinContext | `lib/context/TwinContext.tsx` | Twin state, user auth |
| ThemeContext | `lib/context/ThemeContext.tsx` | Dark/light mode |
| SpecializationContext | `contexts/SpecializationContext.tsx` | Vertical config |

---

## Data Dependencies (API Calls)

### Dashboard Page (`app/dashboard/page.tsx`)
- `GET /health` - Backend health check
- `GET /metrics/stats?twin_id={id}` - Stats summary
- `GET /twins/{id}/conversations` - Recent conversations

### Knowledge Page (`app/dashboard/knowledge/page.tsx`)
- `GET /sources/{twin_id}` - Source list
- `GET /cognitive/profile/{twin_id}` - Knowledge profile
- `DELETE /sources/{source_id}` - Delete source
Note: Uploads auto-index on completion; no extra step required.

### Simulator Page (`app/dashboard/simulator/page.tsx`)
- Uses `ChatInterface` component
- `POST /chat/{twin_id}` - Send message (streaming)

### Widget Page (`app/dashboard/widget/page.tsx`)
- `GET /twins/{twin_id}/share-link` - Get embed code
- `POST /twins/{twin_id}/share-link` - Generate link

### Settings Page (`app/dashboard/settings/page.tsx`)
- `GET /twins/{twin_id}` - Twin config
- `PATCH /twins/{twin_id}` - Update settings
- `DELETE /twins/{twin_id}` - Delete twin
- `POST /auth/change-password` - Change password

### Share Page (`app/share/[twin_id]/[token]/page.tsx`)
- `GET /twins/{twin_id}/share-link/validate` - Validate token
- `POST /chat/{twin_id}/public` - Public chat

---

## Backend Route Alignment

Based on `backend/main.py`, the following routers are active:

| Router | Prefix | Status |
|--------|--------|--------|
| auth | /auth | Active |
| chat | /chat | Active |
| ingestion | /ingest | Active |
| twins | /twins | Active |
| actions | /actions | Out of Scope |
| knowledge | /knowledge | Active |
| sources | /sources | Active |
| governance | /governance | Out of Scope |
| escalations | /escalations | Out of Scope |
| specializations | /specializations | Active |
| cognitive | /cognitive | Active |
| graph | /graph | Active |
| metrics | /metrics | Active |
| jobs | /jobs | Active |
| interview | /interview | Active |
| api_keys | /api-keys | Active |
| verify | /verify | Active |
| owner_memory | /owner-memory | Active |

---

## Known FE/BE Drift Issues (from FE_BE_DRIFT_REPORT.md)

1. ✅ Ingestion routes aligned (shims added)
2. ⚠️ Chat widget stream format mismatch (partial fix)
3. ⚠️ Verified QnA creation endpoint missing
4. ⚠️ Auth missing on some owner routes
5. ✅ Share link response aligned
6. ⚠️ Access groups route scope mismatch

---

## Files Summary

| Category | Count |
|----------|-------|
| Route pages (app/) | 34 |
| UI Components | 17 |
| Console tabs | 9 |
| Chat components | 5 |
| Onboarding steps | 12 |
| Context providers | 3 |
| **Total Components** | ~60 |
