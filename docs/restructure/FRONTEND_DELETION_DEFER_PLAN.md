# Frontend Deletion and Deferral Plan

**Last Updated:** 2026-02-04  
**Product:** Clone-for-Experts (Web-Only)  
**Status:** PLAN ONLY

---

## Overview

This document provides a detailed plan for safely removing or deferring frontend files that are out of scope for the Clone-for-Experts MVP. All items listed here are explicitly excluded based on the product scope definition.

### Out of Scope Features (Per Requirements)
- ❌ Stripe or paid gating UI
- ❌ Telegram or chat platform integration
- ❌ Escalation or safety dashboards
- ❌ Access group management
- ❌ Action automations (connectors, triggers)
- ❌ Team/user management (enterprise tier)

---

## Deletion Strategy

### Approach: Soft Removal

Rather than immediately deleting files, we recommend a phased approach:

1. **Phase 1: Hide from Navigation** - Remove from `SIDEBAR_CONFIG`
2. **Phase 2: Add Deprecation Warning** - Console log on component mount
3. **Phase 3: Move to `/deprecated/`** - Archive for reference
4. **Phase 4: Delete** - After 30 days with no issues

This approach:
- Prevents broken links during transition
- Allows rollback if scope changes
- Maintains git history
- Reduces risk of accidental data loss

---

## Files to Remove

### Route Pages (Immediate Hide)

| File Path | Feature | Action | Risk Level |
|-----------|---------|--------|------------|
| `app/dashboard/actions/page.tsx` | Automations | Hide → Delete | Low |
| `app/dashboard/actions/connectors/page.tsx` | Integration setup | Hide → Delete | Low |
| `app/dashboard/actions/triggers/page.tsx` | Trigger config | Hide → Delete | Low |
| `app/dashboard/actions/history/page.tsx` | Execution logs | Hide → Delete | Low |
| `app/dashboard/actions/inbox/page.tsx` | Draft actions | Hide → Delete | Low |
| `app/dashboard/escalations/page.tsx` | Safety review | Hide → Delete | Low |
| `app/dashboard/governance/page.tsx` | Governance UI (out of scope) | Hide → Delete | Low |
| `app/dashboard/access-groups/page.tsx` | Access control | Hide → Delete | Low |
| `app/dashboard/access-groups/[group_id]/page.tsx` | Group details | Hide → Delete | Low |
| `app/dashboard/users/page.tsx` | Team management | Hide → Delete | Low |
| `app/dashboard/right-brain/page.tsx` | Creative mode | Hide → Delete | Low |
| `app/auth/accept-invitation/page.tsx` | Team invites | Hide → Defer | Medium |

### Components (Archive)

| File Path | Feature | Action | Dependencies |
|-----------|---------|--------|--------------|
| `components/ui/PremiumModal.tsx` | Stripe upsell | Archive | Used in settings |
| `components/console/tabs/ActionsTab.tsx` | Actions console | Archive | ConsoleLayout |
| `components/console/tabs/EscalationsTab.tsx` | Escalations console | Archive | ConsoleLayout |

### Backend Integration Points (Document Only)

These frontend files call backend routes that should be verified before deletion:

| Frontend File | Backend Route | Action |
|---------------|---------------|--------|
| `app/dashboard/actions/page.tsx` | `GET /actions/{twin_id}` | Document drift |
| `app/dashboard/escalations/page.tsx` | `GET /escalations/{twin_id}` | Document drift |
| `app/dashboard/access-groups/page.tsx` | `GET /twins/{twin_id}/access-groups` | Document drift |

---

## Detailed File Analysis

### 1. Actions System (Complete Removal)

**Files:**
```
app/dashboard/actions/
├── page.tsx                    (18,379 bytes)
├── connectors/
│   └── page.tsx               
├── triggers/
│   └── page.tsx               
├── history/
│   └── page.tsx               
└── inbox/
    └── page.tsx               
```

**Component:**
```
components/console/tabs/ActionsTab.tsx  (10,050 bytes)
```

**Backend Routes Used:**
- `GET /actions/{twin_id}` - List actions
- `POST /actions/{twin_id}` - Create action
- `GET /actions/stats` - Action stats
- `GET /connectors` - Connector list
- `POST /actions/{id}/execute` - Execute action

**Removal Steps:**
1. Remove from `SIDEBAR_CONFIG` (if listed)
2. Remove tab from `ConsoleLayout` (if included)
3. Move files to `_deprecated/actions/`
4. Delete after 30 days

**Risk Assessment:** LOW
- No other pages depend on these
- No shared components used exclusively by actions

---

### 2. Escalations System (Complete Removal)

**Files:**
```
app/dashboard/escalations/
└── page.tsx                    (12,744 bytes)
```

**Component:**
```
components/console/tabs/EscalationsTab.tsx  (9,798 bytes)
```

**Backend Routes Used:**
- `GET /escalations/{twin_id}` - List escalations
- `POST /escalations/{id}/resolve` - Resolve escalation
- `PATCH /escalations/{id}` - Update escalation

**Removal Steps:**
1. Remove from navigation if present
2. Remove from console tabs
3. Archive files

**Risk Assessment:** LOW
- Self-contained feature
- No cross-dependencies

---

### 3. Governance System (Complete Removal)

**Files:**
```
app/dashboard/governance/
└── page.tsx                    (size TBD)
```

**Backend Routes Used:**
- None in MVP. Ingestion is auto-indexed with no manual review step.

**Removal Steps:**
1. Remove from navigation
2. Archive file
3. No replacement needed (auto-indexed ingestion)

**Risk Assessment:** LOW
- No manual review step remains

---

### 4. Access Groups System (Defer)

**Files:**
```
app/dashboard/access-groups/
├── page.tsx                    (8,777 bytes)
└── [group_id]/
    └── page.tsx               
```

**Backend Routes Used:**
- `GET /twins/{twin_id}/access-groups` - List groups
- `POST /twins/{twin_id}/access-groups` - Create group
- `DELETE /access-groups/{id}` - Delete group

**Removal Steps:**
1. Hide from navigation
2. Keep files for future enterprise tier
3. Mark as `@deprecated` in comments

**Risk Assessment:** LOW
- Enterprise feature, not blocking MVP
- Preserve for future use

---

### 5. Team Management (Defer)

**Files:**
```
app/dashboard/users/
└── page.tsx                    (size TBD)
```

**Also affects:**
```
app/auth/accept-invitation/
└── page.tsx                    (size TBD)
```

**Backend Routes Used:**
- `GET /auth/team-members` - List team
- `POST /auth/invite` - Send invite
- `POST /auth/accept-invitation` - Accept invite

**Removal Steps:**
1. Hide from navigation
2. Keep auth/accept-invitation working but hidden
3. Defer team features to post-MVP

**Risk Assessment:** MEDIUM
- Keep invitation acceptance for edge cases
- Don't break existing invite links

---

### 6. Premium/Stripe Modal (Archive)

**Files:**
```
components/ui/PremiumModal.tsx  (6,767 bytes)
```

**Used In:**
- Various feature-gated components
- Settings page upgrade prompts

**Removal Steps:**
1. Search for all import statements
2. Replace with no-op or remove conditional
3. Archive component

**Risk Assessment:** MEDIUM
- May be referenced in multiple places
- Need full codebase search before removal

**Search Command:**
```bash
grep -r "PremiumModal" frontend/
grep -r "premium" frontend/app/ frontend/components/
```

---

### 7. Right-Brain Mode (Delete)

**Files:**
```
app/dashboard/right-brain/
└── page.tsx                    (size TBD)
```

**Purpose:** Creative/experimental chat mode (unused)

**Removal Steps:**
1. Verify not linked anywhere
2. Delete immediately (unused feature)

**Risk Assessment:** LOW
- Completely unused
- No dependencies

---

## Pre-Deletion Checklist

For each file marked for deletion:

- [ ] Search for all imports of the file/component
- [ ] Search for all route links to the page
- [ ] Verify backend route can be safely ignored
- [ ] Check for shared components only used by this file
- [ ] Document any data that might be orphaned
- [ ] Create migration path if data exists

---

## Navigation Config Changes

### Current (`frontend/lib/navigation/config.ts`):
```typescript
export const SIDEBAR_CONFIG: SidebarConfig = [
    {
        title: 'Build',
        items: [
            { name: 'Dashboard', href: '/dashboard', icon: 'home' },
            { name: 'Knowledge', href: '/dashboard/knowledge', icon: 'book' },
        ]
    },
    {
        title: 'Train',
        items: [
            { name: 'Simulator', href: '/dashboard/simulator', icon: 'chat' },
        ]
    },
    {
        title: 'Share',
        items: [
            { name: 'Widget', href: '/dashboard/widget', icon: 'code' },
            { name: 'API Keys', href: '/dashboard/api-keys', icon: 'key' },
        ]
    },
    {
        title: 'Settings',
        items: [
            { name: 'Settings', href: '/dashboard/settings', icon: 'settings' },
        ]
    }
];
```

**Items NOT currently in nav (safe to delete):**
- Actions (not in config)
- Escalations (not in config)
- Governance (not in config)
- Access Groups (not in config)
- Users (not in config)
- Right-Brain (not in config)

**Conclusion:** Many out-of-scope pages are already hidden from navigation. Safe to archive/delete without user-facing impact.

---

## Rollback Plan

If any deletion causes issues:

1. **Git Recovery:** `git checkout HEAD~1 -- path/to/file`
2. **Archived Files:** Restore from `_deprecated/` folder
3. **Navigation:** Re-add to `SIDEBAR_CONFIG`
4. **Routes:** Next.js auto-registers routes from `app/`

---

## Timeline

| Week | Action |
|------|--------|
| Week 1 | Remove from navigation, add deprecation warnings |
| Week 2 | Move to `_deprecated/` folder |
| Week 3 | Verify no issues in production |
| Week 4 | Delete from repository |

---

## Files Summary

| Category | Count | Total Size (approx) |
|----------|-------|---------------------|
| Route Pages to Delete | 12 | ~100 KB |
| Components to Archive | 3 | ~27 KB |
| **Total** | **15** | **~127 KB** |

---

## Notes

1. **Keep backend routes:** Backend `/actions/`, `/escalations/`, etc. routes can remain dormant. They don't affect performance if not called.

2. **Database tables:** Tables like `actions`, `escalations`, `access_groups` can remain. No migration needed for frontend-only removal.

3. **Environment variables:** No env vars need removal for these features.

4. **Test files:** Check for any test files related to deleted features:
   ```bash
   find frontend/tests -name "*action*" -o -name "*escalation*"
   ```
