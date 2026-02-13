# ISSUE-012: [P1] Complete Teaching UX Wiring in Chat Surfaces

## Metadata

- Priority: `P1`
- Type: `Frontend UX / adaptive workflow`
- Source: owner-adaptive assistant upgrade objective
- Suggested labels: `frontend`, `chat`, `ux`, `priority:P1`
- Status: `Completed`

## Problem Statement

The chat UI already parses clarification and owner-memory metadata, but key teaching interactions remain partially stubbed (TODO paths), which blocks a complete owner correction workflow.

## Why This Matters

- Teaching should feel native to chat to drive correction throughput.
- Missing wiring creates dead-end UX and prevents behavior improvement.
- Owner vs public capabilities must be obvious in the UI.

## Evidence

- `frontend/components/Chat/ChatInterface.tsx:292`
- `frontend/components/Chat/ChatInterface.tsx:311`
- `frontend/components/Chat/ChatInterface.tsx:588`
- `frontend/components/Chat/MessageList.tsx:142`
- `frontend/components/Chat/MessageList.tsx:275`
- `frontend/components/Chat/MessageList.tsx:287`
- `backend/routers/owner_memory.py:242`

## Scope

In scope:

- Wire teaching cards and reaction actions to backend correction endpoints.
- Add owner-only controls for approve/reject and correction submission.
- Show queued/pending/applied states for clarification and memory actions.
- Preserve public view with non-mutating guidance only.

Out of scope:

- Full dashboard redesign.
- New design system foundation work.

## Implementation Checklist

- [x] Implement frontend API calls for correction submission and clarification resolve.
- [x] Replace TODO handlers in `MessageList` with real actions.
- [x] Show status badges for pending/applied/error states.
- [x] Hide owner-only mutation controls from public/share surfaces.
- [x] Add frontend tests for core teaching interactions.

## Acceptance Criteria

- [x] Owner can trigger and complete a correction flow directly in chat UI.
- [x] Public users cannot access owner mutation controls.
- [x] Clarification resolution status updates are visible and accurate.

## Verification Plan

- [x] UI test: owner submits correction, sees pending then applied state.
- [x] UI test: public share chat never renders owner mutation controls.
- [x] Manual test: clarification resolve request succeeds and metadata updates.

## Risks and Mitigations

- Risk: UI state drift between optimistic updates and backend truth.
  Mitigation: Re-fetch clarification/memory status after each mutation.
- Risk: Owner confusion between "pending" and "applied".
  Mitigation: Add explicit state labels and helper text.

