# ISSUE-006: [P0] Enforce Owner/Public Mode in Identity Gate and Chat Policy

## Metadata

- Priority: `P0`
- Type: `Behavior correctness / access policy`
- Source: `FORENSIC_AUDIT_REPORT.md` + owner-adaptive assistant upgrade objective
- Suggested labels: `backend`, `chat`, `identity`, `priority:P0`
- Status: `Completed`

## Problem Statement

The system already passes context-derived mode to identity gating, but the `mode` parameter is not used in decision logic. This means owner and public interactions are effectively evaluated by one behavior path, creating risk of policy drift and inconsistent adaptive behavior.

## Why This Matters

- Owner-aware behavior is a core requirement for adaptive twin credibility.
- Public users must never be able to perform knowledge mutation actions.
- Behavior differences should be explicit and testable, not implicit by route shape.

## Evidence

- `backend/modules/identity_gate.py:140` (`mode` exists in signature)
- `backend/modules/identity_gate.py:140` (only `mode` occurrence in file)
- `backend/modules/interaction_context.py:19`
- `backend/modules/interaction_context.py:20`
- `backend/modules/interaction_context.py:21`
- `backend/modules/interaction_context.py:22`
- `backend/modules/interaction_context.py:23`
- `backend/routers/chat.py:398`
- `backend/routers/chat.py:926`
- `backend/routers/chat.py:1182`

## Scope

In scope:

- Make `run_identity_gate()` behavior mode-aware (`owner` vs `public`).
- Define deterministic decision policy by mode:
  - Owner: `ANSWER` or `CLARIFY` with structured proposal.
  - Public: grounded `ANSWER` or uncertainty response, without direct knowledge writes.
- Ensure mode decision is propagated through metadata for observability.

Out of scope:

- New model training infrastructure.
- New identity providers.

## Implementation Checklist

- [x] Add explicit branch logic in `run_identity_gate()` for `mode`.
- [x] Update caller expectations in all chat entry points (owner, widget, public share).
- [x] Ensure public flow cannot create owner memory records directly.
- [x] Emit mode and decision reason in trace metadata for debugging.
- [x] Add unit tests for mode-specific gate behavior.

## Acceptance Criteria

- [x] Owner and public paths produce different, deterministic gate outcomes for person-specific missing knowledge.
- [x] Public paths cannot mutate owner knowledge records directly.
- [x] Owner paths can produce structured clarification/correction proposals.

## Verification Plan

- [x] Unit test `run_identity_gate()` with same query across `mode=owner` and `mode=public`.
- [x] API test owner chat route returns clarification payload when owner-specific evidence is missing.
- [x] API test public routes return uncertainty path and do not write owner knowledge.
- [x] Validate metadata includes gate mode and decision reason.

## Risks and Mitigations

- Risk: Behavior regression for existing public chat flows.
  Mitigation: Add route-level integration tests before rollout.
- Risk: Overblocking legitimate public answers.
  Mitigation: Keep factual grounded answers enabled when evidence exists.
