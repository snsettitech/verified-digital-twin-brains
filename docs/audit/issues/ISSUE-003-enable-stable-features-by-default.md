# ISSUE-003: [P1] Enable Stable Features by Default

## Metadata

- Priority: `P1`
- Type: `Configuration / platform behavior`
- Source: `FORENSIC_AUDIT_REPORT.md` issue #3
- Suggested labels: `enhancement`, `backend`, `ops`, `priority:P1`
- Status: `Completed`

## Problem Statement

Historically, key routes remained disabled unless environment flags were explicitly enabled, which led to missing features in deployments and inconsistent behavior across environments.

## Why This Matters

- Production behavior drifts from expected product behavior.
- Debugging is harder due to hidden route availability.
- Feature adoption is blocked by configuration defaults, not code readiness.

## Resolution Summary

The launched route gates called out in this audit have since been cleaned up:

- Realtime ingestion compat routes are mounted unconditionally.
- Advisor retrieval routes are mounted unconditionally.
- Dead VC route startup plumbing was removed because there is no live VC-only router file.
- `ENABLE_ENHANCED_INGESTION` remains as an explicit opt-in flag for the still-optional enhanced ingestion surface.

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
- [x] Set default `true` for `ENABLE_REALTIME_INGESTION` and `ENABLE_ADVISOR_RETRIEVAL` if stable.
- [x] Remove stale opt-out flags once the launched path is always on.
- [x] Add startup log summary that prints enabled/disabled feature map.
- [x] Add smoke tests that assert route availability under default config.
- [x] Update `.env.example` and deployment runbook documentation.

## Acceptance Criteria (from audit report)

- [x] Remove `ENABLE_REALTIME_INGESTION` flag (enable by default).
- [x] Remove `ENABLE_ADVISOR_RETRIEVAL` flag (enable by default).
- [x] Document any remaining feature flags.

## Verification Plan

- [x] Boot backend with no feature env vars and confirm stable routes are mounted.
- [x] Confirm legacy disable env vars no longer affect the launched route surface.
- [x] Confirm docs match runtime behavior.

## Risks and Mitigations

- Risk: Enabling unstable paths in production.
  Mitigation: Gate defaults behind smoke tests and staged rollout.
- Risk: Existing deployments rely on current disabled defaults.
  Mitigation: Document behavior change and keep the cleanup focused on launched paths only.

