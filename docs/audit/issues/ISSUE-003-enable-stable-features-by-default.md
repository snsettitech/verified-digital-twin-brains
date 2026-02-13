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

Current defaults in `main.py`:

- `ENABLE_REALTIME_INGESTION` defaults to `false`
- `ENABLE_ENHANCED_INGESTION` defaults to `false`
- `ENABLE_DELPHI_RETRIEVAL` defaults to `false`
- `ENABLE_VC_ROUTES` defaults to `false`

## Scope

In scope:

- Flip defaults to enabled for stable features.
- Keep unstable/optional features behind explicit flags.
- Document current feature matrix and required env vars.

Out of scope:

- Large refactor of module ownership.
- Enabling features that do not pass smoke checks.

## Implementation Checklist

- [x] Define "stable feature" list with engineering sign-off.
- [x] Set default `true` for `ENABLE_REALTIME_INGESTION` and `ENABLE_DELPHI_RETRIEVAL` if stable.
- [x] Keep explicit opt-out flags for emergency kill switch.
- [x] Add startup log summary that prints enabled/disabled feature map.
- [x] Add smoke tests that assert route availability under default config.
- [x] Update `.env.example` and deployment runbook documentation.

## Acceptance Criteria (from audit report)

- [x] Remove `ENABLE_REALTIME_INGESTION` flag (enable by default).
- [x] Remove `ENABLE_DELPHI_RETRIEVAL` flag (enable by default).
- [x] Document any remaining feature flags.

## Verification Plan

- [x] Boot backend with no feature env vars and confirm stable routes are mounted.
- [x] Confirm explicit disable env var still works for emergency rollback.
- [x] Confirm docs match runtime behavior.

## Risks and Mitigations

- Risk: Enabling unstable paths in production.
  Mitigation: Gate defaults behind smoke tests and staged rollout.
- Risk: Existing deployments rely on current disabled defaults.
  Mitigation: Document behavior change and provide rollback env flags.

