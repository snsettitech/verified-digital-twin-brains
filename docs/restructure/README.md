# Frontend Restructure Planning

**Last Updated:** 2026-02-04  
**Product:** Clone-for-Experts (Web-Only)  
**Status:** 📋 PLAN ONLY - No code changes

---

## Overview

This folder contains the complete planning documentation for restructuring the Verified Digital Twin Brain frontend into a web-only Clone-for-Experts product. These documents were created as part of a planning-only phase and do not include any code modifications.

---

## Documents

| Document | Purpose |
|----------|---------|
| [FRONTEND_ROUTE_AND_COMPONENT_INVENTORY.md](./FRONTEND_ROUTE_AND_COMPONENT_INVENTORY.md) | Complete inventory of current routes, pages, and components |
| [FRONTEND_UX_REDESIGN_SPEC.md](./FRONTEND_UX_REDESIGN_SPEC.md) | New information architecture, user journeys, and screen specifications |
| [FRONTEND_KEEP_TWEAK_REFACTOR_DELETE.md](./FRONTEND_KEEP_TWEAK_REFACTOR_DELETE.md) | Classification of all files by action needed |
| [FRONTEND_DELETION_DEFER_PLAN.md](./FRONTEND_DELETION_DEFER_PLAN.md) | Detailed plan for removing out-of-scope features |
| [FRONTEND_STATE_MODEL.md](./FRONTEND_STATE_MODEL.md) | UI state handling specifications for all pages |
| [FRONTEND_DOCS_UPDATE_PLAN.md](./FRONTEND_DOCS_UPDATE_PLAN.md) | Documentation update requirements |
| [FRONTEND_QA_CHECKLIST.md](./FRONTEND_QA_CHECKLIST.md) | Manual QA, Playwright tests, and proof path walkthrough |

---

## Product Scope Summary

### Three Primary Areas

```
STUDIO (Build)           LAUNCH (Deploy)         OPERATE (Run)
├── Content              ├── Share Link          ├── Conversations
├── Identity             ├── Website Embed       ├── Audience
├── Roles                └── Branding            └── Analytics
└── Quality
```

### Explicitly Out of Scope

- ❌ Stripe or paid gating UI
- ❌ Telegram or chat platform integration
- ❌ Escalation or safety dashboards
- ❌ Access group management
- ❌ Action automations (connectors, triggers)

---

## Fastest Path to Working UI

Based on the inventory and analysis, the fastest path to a working web-only UI:

### Phase 1: Navigation Update (Day 1)
1. Update `lib/navigation/config.ts` with new structure
2. Rename sidebar sections to Studio/Launch/Operate
3. Keep all existing components working

### Phase 2: Route Aliases (Day 1-2)
1. Create route aliases: `/studio` → `/dashboard`
2. Create `/studio/content` → `/dashboard/knowledge`
3. Create `/studio/quality` → `/dashboard/simulator`
4. Each "new" route can initially redirect to existing pages

### Phase 3: Split Pages (Day 3-5)
1. Split `/dashboard/widget` into `/launch/share` and `/launch/embed`
2. Split `/dashboard/settings` into `/studio/identity` and `/settings`
3. Create `/operate/conversations` from dashboard modal

### Phase 4: Cleanup (Day 6-7)
1. Remove out-of-scope pages from navigation
2. Archive unused components
3. Update documentation

**Estimated MVP Time:** 5-7 days with existing team

---

## Top UX Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing user workflows | High | Use route redirects, maintain old URLs |
| Incomplete state handling | Medium | Apply FRONTEND_STATE_MODEL consistently |
| Chat streaming failures | High | Keep existing ChatInterface, add retry |
| Backend route drift | Medium | Reference FE_BE_DRIFT_REPORT.md |
| Mobile responsiveness gaps | Medium | Test on actual devices early |

---

## Minimum MVP Pages

The absolute minimum set of pages for a working MVP:

### Must Have (7 pages)

| Page | Current File | Required Data |
|------|--------------|---------------|
| Login | `app/auth/login/page.tsx` | Auth |
| Content | `app/dashboard/knowledge/page.tsx` | Sources API |
| Quality | `app/dashboard/simulator/page.tsx` | Chat API |
| Share | `app/dashboard/widget/page.tsx` (partial) | Share link API |
| Embed | `app/dashboard/widget/page.tsx` (partial) | Widget config |
| Public Chat | `app/share/[twin_id]/[token]/page.tsx` | Public chat API |
| Settings | `app/dashboard/settings/page.tsx` (partial) | Twin settings |

### Nice to Have (defer to v1.1)

| Page | Reason to Defer |
|------|-----------------|
| Roles | New feature, not critical path |
| Audience | Analytics extension |
| Branding | Cosmetic enhancement |
| Onboarding | Can use existing flow |

---

## Backend Dependencies

### Required Endpoints (Verified Working)

| Endpoint | Used By | Status |
|----------|---------|--------|
| `GET /sources/{twin_id}` | Content page | ✅ |
| `POST /chat/{twin_id}` | Quality page | ✅ |
| `GET /twins/{twin_id}/share-link` | Share page | ✅ |
| `POST /chat/{twin_id}/public` | Public chat | ✅ |
| `PATCH /twins/{twin_id}` | Identity page | ✅ |

### Potentially Missing (Need Verification)

| Endpoint | Needed For | Risk |
|----------|------------|------|
| `GET /twins/{twin_id}/conversations` | Conversations page | Medium |
| `GET /metrics/audience` | Audience page | Low (new feature) |
| Role CRUD endpoints | Roles page | Low (new feature) |

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Prioritize phases** based on team capacity
3. **Set MVP launch date** based on phase estimates
4. **Begin Phase 1** (Navigation Update)

---

## Related Documents

- [FE_BE_DRIFT_REPORT.md](../../FE_BE_DRIFT_REPORT.md) - Known frontend/backend misalignments
- [docs/architecture/](../architecture/) - System architecture docs
- [docs/ops/](../ops/) - Operational runbooks
