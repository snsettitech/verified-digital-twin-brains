# ISSUE-008: [P0] Capture Owner Corrections as Structured Knowledge Candidates

## Metadata

- Priority: `P0`
- Type: `Learning loop / owner authoring`
- Source: owner-adaptive assistant upgrade objective
- Suggested labels: `backend`, `frontend`, `chat`, `memory`, `priority:P0`
- Status: `Completed`

## Problem Statement

The codebase already supports clarification threads and owner memory records, but owner correction flow from normal chat messages is not fully wired as a first-class "teach the twin" path. This limits practical learning-through-conversation.

## Why This Matters

- Owner correction should be fast and native to conversation.
- Structured correction capture is required for persistent quality improvement.
- Without strong correction capture, system behavior appears static to owners.

## Evidence

- `backend/routers/chat.py:424`
- `backend/routers/chat.py:937`
- `backend/routers/chat.py:1192`
- `backend/modules/owner_memory_store.py:312`
- `backend/modules/owner_memory_store.py:333`
- `backend/routers/owner_memory.py:223`
- `backend/routers/owner_memory.py:242`
- `backend/routers/interview.py:490`
- `frontend/components/Chat/MessageList.tsx:287`

## Scope

In scope:

- Add/complete owner correction submission from chat responses.
- Persist corrections as structured candidates with provenance (query, answer, message/conversation IDs).
- Reuse existing clarification/proposal queue for owner approval.
- Ensure approved corrections produce durable knowledge records.

Out of scope:

- Full RLHF pipeline.
- Autonomous knowledge approval without owner review.

## Implementation Checklist

- [x] Define backend contract for chat-based owner correction submission.
- [x] Save correction candidates as `pending_owner`/`proposed` with provenance fields.
- [x] Implement owner approval endpoint usage in chat workflow (reuse `/clarifications/{id}/resolve` where possible).
- [x] Link approved corrections to retrieval-visible store (`owner_beliefs` and/or verified QnA path).
- [x] Add frontend actions for submit, review state, and approve/reject.

## Acceptance Criteria

- [x] Owner can submit a correction directly from chat UI.
- [x] Correction appears in pending review queue with full provenance.
- [x] Owner approval persists the correction as reusable knowledge for future answers.
- [x] Non-owner users cannot submit owner corrections.

## Verification Plan

- [x] API test for owner correction submission and pending queue visibility.
- [x] API test for approve path creating active knowledge record.
- [x] UI test for "teach/correct" action and state transition.
- [x] Regression check that unresolved proposals are not used as authoritative knowledge.

## Risks and Mitigations

- Risk: Correction spam or low-quality submissions.
  Mitigation: Owner-only write permissions + optional rate limits.
- Risk: Duplicate or contradictory corrections.
  Mitigation: Add similarity/conflict checks before approval.

