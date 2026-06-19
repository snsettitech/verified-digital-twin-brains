# ISSUE-003: [P1] Enable Stable Features by Default

## Metadata

- Priority: `P1`
- Type: `Configuration / platform behavior`
- Source: `FORENSIC_AUDIT_REPORT.md` issue #3
- Suggested labels: `enhancement`, `backend`, `ops`, `priority:P1`
- Status: `Completed`

## Problem Statement

Key routes remain disabled unless environment flags are explicitly enabled, which leads to missing features in deployments and inconsistent behavior across environments.

## Why This Matters

- Production behavior drifts from expected product behavior.
- Debugging is harder due to hidden route availability.
- Feature adoption is blocked by configuration defaults, not code readiness.

## Evidence

- `backend/main.py:64`
- `backend/main.py:87`
- `backend/main.py:102`
- `backend/main.py:119`

Current state in `main.py`:

- Realtime ingestion routes are always mounted
- `ENABLE_ENHANCED_INGESTION` remains opt-in
- Advisor retrieval routes are always mounted
- `ENABLE_VC_ROUTES` remains opt-in

## Scope

In scope:

- Remove legacy env gates for stable routes that are now always on.
- Keep unstable/optional features behind explicit flags.
- Document current feature matrix and required env vars.

Out of scope:

- Large refactor of module ownership.
- Enabling features that do not pass smoke checks.

## Implementation Checklist

- [x] Define "stable feature" list with engineering sign-off.
- [x] Promote `ENABLE_REALTIME_INGESTION` and `ENABLE_ADVISOR_RETRIEVAL` through default-on rollout once stable.
- [x] Remove legacy opt-out flags once routes are confirmed stable.
- [x] Add startup log summary that prints enabled/disabled feature map.
- [x] Add smoke tests that assert route availability under default config.
- [x] Update `.env.example` and deployment runbook documentation.

## Acceptance Criteria (from audit report)

- [x] Remove `ENABLE_REALTIME_INGESTION` flag and keep the routes always on.
- [x] Remove `ENABLE_ADVISOR_RETRIEVAL` flag and keep the routes always on.
- [x] Document any remaining feature flags.

## Verification Plan

- [x] Boot backend with no feature env vars and confirm stable routes are mounted.
- [x] Confirm stable routes stay mounted even if legacy env vars are still present.
- [x] Confirm docs match runtime behavior.

## Risks and Mitigations

- Risk: Enabling unstable paths in production.
  Mitigation: Gate defaults behind smoke tests and staged rollout.
- Risk: Existing deployments may still carry stale env vars that no longer affect route mounting.
  Mitigation: Document the removal and verify stable routes remain available under legacy env configuration.

