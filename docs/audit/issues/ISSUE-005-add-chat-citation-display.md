# ISSUE-005: [P1] Add Citation Display to Chat UI

## Metadata

- Priority: `P1`
- Type: `Trust UX / chat output fidelity`
- Source: `FORENSIC_AUDIT_REPORT.md` issue #5
- Suggested labels: `enhancement`, `frontend`, `chat`, `priority:P1`
- Status: `Completed`

## Problem Statement

Backend chat responses include citations and confidence metadata, but citation presentation is not guaranteed consistently across all chat surfaces. Users need visible, clickable source grounding in every primary chat experience.

## Why This Matters

- Citations are a core product promise and trust mechanism.
- Missing or inconsistent citation UI makes answers look unverified.
- Confidence without source links is insufficient for auditability.

## Evidence

- `backend/routers/chat.py:662`
- `frontend/components/Chat/ChatInterface.tsx:344`
- `frontend/components/Chat/MessageList.tsx:446`
- `frontend/components/Chat/ChatWidget.tsx:296`
- `frontend/components/ui/CitationsDrawer.tsx:17`
- `frontend/app/share/[twin_id]/[token]/page.tsx:513`

## Scope

In scope:

- Ensure citation chips/links are shown for assistant messages across all supported chat views.
- Use a consistent display pattern and click behavior.
- Show confidence state with clear high/low visual distinction.

Out of scope:

- Rewriting retrieval ranking logic.
- Citation semantic scoring.

## Implementation Checklist

- [x] Define one citation display contract for all chat UIs.
- [x] Render clickable citation bubbles with source identity.
- [x] Open source details via existing drawer or source link action.
- [x] Ensure confidence badge appears alongside citations.
- [x] Add fallback copy when citations are unavailable.
- [x] Add component tests for metadata-to-UI mapping.
- [x] Add one E2E test for SSE stream that verifies citation rendering.

## Acceptance Criteria (from audit report)

- [x] Citations shown as clickable bubbles.
- [x] Link to source document.
- [x] Visual distinction between high/low confidence.

## Verification Plan

- [x] Ask a question with known sourced answer and confirm citations render.
- [x] Click citation bubble and confirm source drawer/link behavior.
- [x] Confirm high/low confidence states use distinct styles.
- [x] Validate behavior in both dashboard chat and shared/public chat views.

## Risks and Mitigations

- Risk: Citation metadata shape differs between routes.
  Mitigation: Normalize message schema in one utility before render.
- Risk: UI clutter from many citations.
  Mitigation: Clamp inline bubbles and provide "show all" drawer action.

