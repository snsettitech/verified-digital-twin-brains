# ISSUE-011: [P1] Fix Escalation to Verified QnA Contract Mismatch

## Metadata

- Priority: `P1`
- Type: `Backend correctness / bug fix`
- Source: forensic code audit finding
- Suggested labels: `bug`, `backend`, `escalation`, `priority:P1`
- Status: `Completed`

## Problem Statement

Escalation resolution calls `create_verified_qna(...)` using keyword arguments that do not match the current function signature, creating a runtime failure risk during owner resolution.

## Why This Matters

- Breaks core loop of converting owner resolution into reusable verified knowledge.
- Causes silent failure risk in a trust-critical path.
- Blocks improvement persistence from escalation workflow.

## Evidence

- `backend/routers/escalations.py:202`
- `backend/routers/escalations.py:278`
- `backend/modules/verified_qna.py:274`

## Scope

In scope:

- Align `create_verified_qna` call sites and function signature/adapter.
- Ensure escalation context (`escalation_id`, `twin_id`, citations) is handled correctly.
- Add tests that resolve an escalation and verify QnA insertion.

Out of scope:

- Redesigning the entire escalation subsystem.
- New escalation UI features.

## Implementation Checklist

- [x] Decide canonical function contract for creating verified QnA from escalation.
- [x] Update router call sites and helper implementation for consistency.
- [x] Add defensive validation and explicit error logging.
- [x] Add automated test for successful escalation-to-verified-QnA flow.

## Acceptance Criteria

- [x] Resolving escalation no longer throws argument mismatch/runtime errors.
- [x] Verified QnA row is created with expected twin linkage.
- [x] Existing legacy endpoint behavior remains backward compatible.

## Verification Plan

- [x] Unit/integration test for `resolve_escalation` path.
- [x] Confirm verified QnA retrieval path can immediately match created answer.
- [x] Manual API smoke test for both primary and legacy resolve endpoints.

## Risks and Mitigations

- Risk: Hidden callers rely on old helper signature.
  Mitigation: Provide temporary adapter function and deprecation note.
- Risk: Partial write when escalation resolve succeeds but QnA write fails.
  Mitigation: Wrap in transaction-like error handling and clear audit events.

