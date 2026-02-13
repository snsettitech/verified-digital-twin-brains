# ISSUE-010: [P0] Harden Feedback Endpoint and Learning Job Triggers

## Metadata

- Priority: `P0`
- Type: `Security / data integrity`
- Source: forensic code audit finding
- Suggested labels: `backend`, `security`, `feedback`, `priority:P0`
- Status: `Completed`

## Problem Statement

The feedback submission route currently accepts requests without authentication checks and can trigger local feedback-training events and learning jobs using provided identifiers.

## Why This Matters

- Unauthenticated mutation-adjacent events can poison learning signals.
- Attackers can submit synthetic feedback against arbitrary twins.
- Violates owner-control boundary for adaptive behavior loops.

## Evidence

- `backend/routers/feedback.py:48`
- `backend/routers/feedback.py:104`
- `backend/routers/feedback.py:128`
- `backend/routers/feedback.py:130`

## Scope

In scope:

- Add authentication/authorization requirements to feedback route.
- Validate that provided `conversation_id`/`twin_id` belong to authorized context.
- Gate learning-job enqueue behavior by trust level and context.
- Add rate limiting and audit logging for abuse monitoring.

Out of scope:

- External anti-fraud platform integration.
- UI redesign of feedback controls.

## Implementation Checklist

- [x] Add route dependency (`Depends(...)`) for authenticated contexts.
- [x] Add public feedback path validation for share/widget tokens if retained.
- [x] Enforce ownership/tenant checks before recording training events.
- [x] Block enqueueing of feedback learning jobs for unauthorized or unresolved twin scope.
- [x] Add tests for unauthorized, cross-tenant, and valid flows.

## Acceptance Criteria

- [x] Unauthenticated owner feedback calls are rejected.
- [x] Cross-tenant/cross-twin identifier spoofing is blocked.
- [x] Learning jobs are enqueued only for authorized, valid contexts.
- [x] Security tests cover unauthorized and malicious payload paths.

## Verification Plan

- [x] API test without token returns 401/403.
- [x] API test with valid token but mismatched `conversation_id` fails.
- [x] API test with valid owner context records feedback and enqueues job.
- [x] Log review confirms audit entries for blocked attempts.

## Risks and Mitigations

- Risk: Breaking existing anonymous feedback UX.
  Mitigation: Support explicit public token-based feedback contract if required.
- Risk: Reduced feedback volume.
  Mitigation: Keep friction low for authenticated users and valid public sessions.

