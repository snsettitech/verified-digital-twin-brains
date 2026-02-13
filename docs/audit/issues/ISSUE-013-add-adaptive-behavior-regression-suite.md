# ISSUE-013: [P1] Add Adaptive Behavior Regression Suite

## Metadata

- Priority: `P1`
- Type: `Quality / release safety`
- Source: owner-adaptive assistant upgrade objective
- Suggested labels: `backend`, `frontend`, `tests`, `priority:P1`
- Status: `Completed`

## Problem Statement

The owner-aware adaptive behavior requires strict policy guarantees, but current test coverage does not comprehensively guard owner/public behavior splits, uncertainty policy, and correction persistence precedence.

## Why This Matters

- This capability is policy-heavy and prone to subtle regressions.
- Without regression coverage, future changes can silently reintroduce hallucination and permission drift.
- Safe rollout requires executable contract checks, not only manual QA.

## Evidence

- `backend/tests/test_chat_interaction_context.py:254`
- `backend/modules/identity_gate.py:140`
- `backend/modules/retrieval.py:566`
- `backend/routers/chat.py:596`
- `backend/routers/feedback.py:48`

## Scope

In scope:

- Add backend integration tests for:
  - owner vs public gate outcomes
  - uncertainty fallback phrase
  - public no-knowledge-mutation rule
  - approved correction precedence in retrieval
- Add frontend tests for clarify/teaching action rendering and role gating.
- Add one end-to-end scenario from correction submission to future answer improvement.

Out of scope:

- Full load/performance benchmarking.
- UI visual regression suite expansion.

## Implementation Checklist

- [x] Add fixture coverage for owner, widget, and public share contexts.
- [x] Add policy tests for uncertainty and no-hallucination behavior when evidence is missing.
- [x] Add tests for correction approval and retrieval precedence.
- [x] Add tests for feedback route auth and authorization constraints.
- [x] Integrate suite in CI as blocking checks for adaptive behavior files.

## Acceptance Criteria

- [x] Test suite fails against known pre-fix bugs and passes after fixes.
- [x] CI enforces adaptive behavior contracts on PRs touching chat/retrieval/identity paths.
- [x] Regression suite covers owner/public behavior and correction persistence end-to-end.

## Verification Plan

- [x] Run focused backend tests for chat, retrieval, owner-memory, feedback routes.
- [x] Run frontend tests for `ChatInterface` and `MessageList` teaching flows.
- [x] Execute one scripted end-to-end scenario in CI or staging.

## Risks and Mitigations

- Risk: Flaky SSE and async timing tests.
  Mitigation: Use deterministic fixtures and bounded polling helpers.
- Risk: Slow CI from heavy integration setup.
  Mitigation: Keep regression suite targeted and parallelized.

