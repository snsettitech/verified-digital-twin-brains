# ISSUE-004: [P1] Remove or Implement Stubbed Dashboard Pages

## Metadata

- Priority: `P1`
- Type: `UX consistency / information architecture`
- Source: `FORENSIC_AUDIT_REPORT.md` issue #4
- Suggested labels: `enhancement`, `frontend`, `ux`, `priority:P1`
- Status: `Completed`

## Problem Statement

The audit flagged dashboard routes (`/dashboard/interview`, `/dashboard/simulator`, `/dashboard/right-brain`) as stubs. Current code now routes these pages to `TrainingModulePage`, but product intent and navigation still need an explicit decision and cleanup path.

## Why This Matters

- Ambiguous route purpose confuses users and increases maintenance overhead.
- Duplicate/legacy entry points can drift from the canonical training flow.
- Navigation clarity is required for onboarding and support docs.

## Evidence

- `frontend/app/dashboard/interview/page.tsx`
- `frontend/app/dashboard/simulator/page.tsx`
- `frontend/app/dashboard/right-brain/page.tsx`
- `frontend/lib/navigation/config.ts:31`

## Scope

In scope:

- Product decision for each legacy route: keep, redirect, or remove.
- Navigation and IA updates to reflect that decision.
- Clear UI messaging for any deferred features.

Out of scope:

- Full redesign of the training module itself.
- Introducing new route families unrelated to this decision.

## Implementation Checklist

- [x] Decide canonical route(s) for training/interview/simulator experiences.
- [x] If keeping legacy routes, add explicit redirects and canonical breadcrumbs.
- [x] If removing routes, remove sidebar links and add safe fallbacks.
- [x] Ensure no route renders "coming soon" placeholders without product approval.
- [x] Update docs and onboarding links to canonical destinations.
- [x] Add route-level tests for navigation correctness.

## Acceptance Criteria (from audit report)

- [x] Decision: implement Interview, Simulator, or remove.
- [x] Remove navigation links if pages removed.
- [x] Add proper 404 or "Coming Soon" if keeping.

## Verification Plan

- [x] Navigate all three routes and verify expected behavior and copy.
- [x] Validate sidebar links resolve to intended route(s).
- [x] Validate browser deep links for legacy URLs are handled correctly.

## Risks and Mitigations

- Risk: Breaking bookmarked links.
  Mitigation: Use redirects with deprecation notice instead of hard removal.
- Risk: Confusing naming persists even after route consolidation.
  Mitigation: Align copy with ISSUE-001 terminology changes.

