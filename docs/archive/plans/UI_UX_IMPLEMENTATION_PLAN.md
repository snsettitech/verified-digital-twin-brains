# Digital Twin UI/UX Implementation Plan

## Version
- Version: 2.0
- Last Updated: 2026-02-20
- Scope: Frontend + minimal backend alignment for owner and office-hours twins

## Executive Summary
This plan defines a production-safe UI/UX implementation for two twin modes:
1. Personal Twin (owner = user)
2. Office-Hours Twin (owner != user)

The plan is grounded in the existing Next.js App Router frontend and FastAPI backend. It preserves the current streaming lifecycle and enforces strict grounding, explicit memory writes, and field-level public safety.

## Ground Rules
- Preserve existing `/chat/{twin_id}` NDJSON streaming lifecycle. Do not rewrite parser internals.
- Wrap existing `ChatInterface.tsx`; extend via callbacks/events only.
- Every interactive control must be:
  - fully functional against a real endpoint, or
  - deterministically disabled (feature-gate + tooltip/state), or
  - deterministic 501 with explicit UI state.
- Identity answers: anchors + approved identity docs + approved beliefs only.
- Knowledge answers: document-grounded with citations.
- Memory writes: explicit-only (typed intent or explicit UI action), never automatic assistant writes.
- Actions: confirmation-gated; no silent destructive execution.
- Office-hours/public mode: published allowlist only; no private owner memory/settings/connectors/logs.
- Trust copy must stay truthful: no “end-to-end encrypted” or “open source” claims unless verified.

## Current Stack Evidence
- Frontend: Next.js App Router + React + Tailwind.
- Chat parser: `frontend/components/Chat/ChatInterface.tsx` (line-by-line NDJSON parsing with tail handling).
- Backend streaming: `backend/routers/chat.py` (`/chat/{twin_id}`, `/public/chat/{twin_id}/{token}`).

## Product Models
### 1) Personal Twin
- Purpose: productivity and decision support for owner.
- Access: owner private data allowed by owner permissions.
- Memory: explicit owner writes and owner correction workflows.

### 2) Office-Hours Twin
- Purpose: external/public guidance and policy-safe assistance.
- Access: published subsets only.
- Data exposure: strict field-level visibility matrix applies.

## Onboarding Anchors (Mandatory)
Add to onboarding:
- Goals: top 3 goals for next 90 days.
- Boundaries: do/don’t rules and privacy constraints.
- Uncertainty preference: ask vs infer.

Validation:
- Twin name required.
- At least one 90-day goal required before step advance.

Persistence:
- Store in twin settings under intent profile.

## Document Labeling Policy
Upload-time labels are required in UX:
- Identity
- Knowledge
- Policies

Identity label has extra confirmation:
- User must confirm source is safe for identity answers.

Backend behavior:
- Accept `source_label` and `identity_confirmed` fields.
- Reject identity label without confirmation.
- Persist label metadata best-effort across schema variants.

## Office-Hours Publishing Model
Owner-facing Publish Controls must manage:
- published identity topics
- published policy topics
- published source IDs

Public chat safety contract:
- Public responses may only cite published source IDs.
- Out-of-scope contexts are discarded and audited in trace metadata.
- Owner memory/private fields are never surfaced to public UI payloads.

## Field-Level Role/Data Visibility Matrix
### Owner dashboard pages
- Chat: full owner context, citations, planner metadata.
- Memory Center: full CRUD for owner memory.
- Privacy: retention + export + logs.
- Publish Controls: full read/write for publish allowlist.

### Public share pages
- Chat response text: allowed.
- Citations: allowed only from published source allowlist.
- Owner memory refs/topics: hidden.
- Owner private logs/settings/connectors: hidden.
- Consent notice: visible and explicit.

### Context Panel
- Owner mode: planner class/action/answerability, retrieval stats, citations, owner memory usage.
- Public mode: not exposed as owner diagnostics panel.

## Chat Architecture (UI)
- `ChatInterface.tsx` remains the source of truth for stream parsing.
- Add `onStreamEvent` callback for parsed events:
  - metadata
  - content
  - clarify
  - done
  - error
- Dashboard chat page wraps `ChatInterface` and renders a read-only Context Panel.
- Context Panel updates are throttled to prevent layout thrash during token streaming.

## API Contract Normalization
Prefer twin-scoped endpoints:
- `GET /twins/{id}/actions`
- `POST /twins/{id}/actions/execute`
- `POST /twins/{id}/actions/{action_id}/approve`
- `POST /twins/{id}/actions/{action_id}/cancel`

Memory feedback normalization:
- `POST /memory/feedback` with `{ memory_id, action, correction? }`

Privacy:
- `GET /twins/{id}/logs`
- `GET /twins/{id}/export`

## Navigation + Feature Flags
Feature flags control rollout and safe fallback:
- `NEXT_PUBLIC_FF_DASHBOARD_CHAT`
- `NEXT_PUBLIC_FF_CONTEXT_PANEL`
- `NEXT_PUBLIC_FF_MEMORY_CENTER`
- `NEXT_PUBLIC_FF_PRIVACY_CONTROLS`
- `NEXT_PUBLIC_FF_PUBLISH_CONTROLS`
- `NEXT_PUBLIC_FF_SOURCE_LABELING`
- `NEXT_PUBLIC_FF_OFFICE_HOURS_MODE`

Disabled features must show deterministic gated UI state.

## Truthful Trust Copy
Replace unsupported claims with:
- “Private by default.”
- “You control storage, export, and deletion.”

## QA and Regression Strategy
### Stream contract tests
- Parse line-by-line NDJSON.
- Handle partial tail chunk (no trailing newline).
- Ensure no parser break on metadata/content/done sequence.

### Office-hours/public safety tests
- Validate citations are from published allowlist source IDs.
- Do not validate by filename substring only.

### Required E2E flows
- Onboarding with goals/boundaries/uncertainty saved.
- Dashboard chat stream remains functional with context panel enabled.
- Label-required upload with identity confirmation gate.
- Memory CRUD explicit-only behavior.
- Public share route enforces published visibility constraints.

## Implementation Milestones
### UI0 Foundations
- Runtime feature flags.
- New gated nav entries and routes.

### UI1 Onboarding Anchors
- Add goals, boundaries, privacy constraints, uncertainty preference.
- Save in twin settings.

### UI2 Chat Wrapper + Context Panel
- Wrap existing `ChatInterface` in `/dashboard/chat`.
- Consume parsed stream metadata events only.
- Throttle context updates.

### UI3 Memory Center
- Owner memory list/create/update/delete.
- Lock/unlock and correction actions.
- Explicit-only copy and behavior.

### UI4 Sources + Labeling
- Required upload label UI (Identity/Knowledge/Policies).
- Identity label confirmation gate.

### UI5 Office-Hours Safety + Publish Controls
- Publish controls page.
- Public chat safety filtering for source allowlist and owner-memory visibility.
- Consent banner and public-safe rendering.

## Backend Alignment Checklist
- Ingestion routes accept and validate labels.
- Owner memory lock endpoint exists.
- Twin logs endpoint exists.
- Actions normalized endpoints exist.
- Memory feedback endpoint exists.
- Public chat applies publish controls before response emission.

## Deployment Verification Checklist
After deploy:
- Health/version endpoints return expected build.
- Owner dashboard routes load with auth.
- Public share route denies invalid token and serves valid token.
- No SSE parse spikes / 401/403 spikes / missing route 404 spikes in logs.
- Smoke prompts:
  - owner: knowledge question with citations
  - owner: explicit memory save + lock
  - public: answer with published citations only

## Deliverables
- Updated plan doc (this file).
- Code changes by milestone with tests.
- Explicit pass/fail report for constraints and regression checks.
