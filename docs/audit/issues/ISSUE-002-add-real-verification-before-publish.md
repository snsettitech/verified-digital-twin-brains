# ISSUE-002: [P0] Add Real Verification Gate Before Publish

## Metadata

- Priority: `P0`
- Type: `Quality gate / trust`
- Source: `FORENSIC_AUDIT_REPORT.md` issue #2
- Suggested labels: `bug`, `backend`, `frontend`, `quality`, `priority:P0`
- Status: `Completed`

## Problem Statement

Current publish readiness is based on vector count plus the latest PASS record, but it does not guarantee the twin can answer grounded questions with valid citations at publish time.

## Why This Matters

- Users can publish twins that hallucinate or fail to cite.
- Verification appears present but is not outcome-driven enough.
- This directly impacts core trust and product reputation.

## Evidence

- `backend/routers/twins.py:342`
- `backend/routers/twins.py:424`
- `backend/routers/verify.py:28`
- `backend/routers/chat.py:662`
- `frontend/components/console/tabs/PublishTab.tsx:43`

## Scope

In scope:

- Add a concrete pre-publish verification run using test prompts.
- Validate answer quality signals (response, citation presence, confidence).
- Block publish when verification fails and show detailed reasons in UI.

Out of scope:

- Full semantic answer correctness grading against gold labels.
- New ML model training.

## Implementation Checklist

- [x] Add endpoint to run verification suite on demand for a twin.
- [x] Define minimum verification suite: 3 deterministic test prompts.
- [x] Validate each result includes non-empty answer and citation output.
- [x] Store structured verification run details with timestamp and score.
- [x] Require latest run PASS before enabling publish toggle.
- [x] Surface per-test results in Publish UI (pass/fail + reason).
- [x] Add backend tests for pass/fail gating behavior.

## Acceptance Criteria (from audit report)

- [x] Run 3 test questions before allowing publish.
- [x] Verify citations are returned.
- [x] Show verification results to user.

## Verification Plan

- [x] Create twin with known source content and run verification endpoint.
- [x] Confirm PASS only when all 3 tests satisfy gates.
- [x] Confirm publish action is blocked on FAIL.
- [x] Confirm Publish UI shows specific failing checks.

## Risks and Mitigations

- Risk: False failures due to retrieval variance.
  Mitigation: Deterministic prompts + conservative thresholds + retry window.
- Risk: Longer time-to-publish.
  Mitigation: Keep suite small and run asynchronously with progress state.

