# Placeholder Inventory Report

Date: 2026-02-04

This report lists detected placeholders, stubs, mocks and hardcoded/sample data across the repo (grouped). Each entry: path, placeholder, why, user impact, recommended real behavior.

---

## Onboarding

- frontend/app/onboarding/page.tsx
  - Placeholder: onboarding completion saved only to `localStorage` (`onboardingCompleted`).
  - Impact: onboarding state is ephemeral; other devices/backend won't see completed state.
  - Fix: persist completion server-side (e.g., `POST /users/{id}/onboarding-complete` or `PATCH /twins/{id}`) and update session.

- frontend/components/onboarding/steps/ClaimIdentityStep.tsx
  - Placeholder: "TODO: Check uniqueness against backend" — uniqueness only checked client-side.
  - Impact: possible handle collisions and broken shareable URLs.
  - Fix: add `GET /twins/handle-availability?handle=` server check; enforce tenant-scoped uniqueness.

- frontend/components/onboarding/steps/FirstChatStep.tsx
  - Placeholder: interview data kept only in component state; no persistence or session creation.
  - Impact: twin is not actually trained; interviews are lost.
  - Fix: POST interview turns to backend (`/cognitive/interview/{twin_id}`), run scribe-extraction server-side, persist nodes and recall.

- frontend/components/onboarding/steps/PreviewTwinStep.tsx
  - Placeholder: shows canned/simulated responses when `twinId` missing.
  - Impact: misleading UX suggesting twin already trained.
  - Fix: clearly mark simulation, or disable preview until backend indicates twin readiness.

- frontend/app/onboarding/page.tsx (ingest calls)
  - Placeholder/Drift: FE calls `/ingest/document` and `/ingest/url` shapes may not match backend contract.
  - Impact: ingestion may fail silently during onboarding.
  - Fix: align FE ↔ BE API shapes and surface errors in UI.

---

## Core App & Tests

- backend/tests/*
  - Placeholder: several tests are skeletons/skipped (`pass`) or use heavy mocking.
  - Impact: poor coverage and false confidence.
  - Fix: replace placeholders with real unit/integration tests using fixtures or test DB.

- backend/modules/_core/* (host/scribe)
  - Placeholder: extraction/repair strategies left as TODO or partially stubbed.
  - Impact: incomplete interview-to-knowledge pipeline.
  - Fix: implement scribe extraction, confidence scoring, and durable persistence via RPC.

---

## Shared Utilities & Scripts

- scripts/* (simulation scripts)
  - Placeholder: use MagicMock to stub Supabase/OpenAI/Pinecone for demos.
  - Impact: good for dev but can mask integration issues.
  - Fix: mark as dev-only and add integrated smoke tests against test infra.

- docs and runbooks with TODOs
  - Placeholder: operational steps incomplete in docs.
  - Impact: onboarding/ops gaps for new engineers.
  - Fix: prioritize completing critical runbooks or clearly label TODOs.

---

## Backend

- backend/routers/cognitive.py — GET /cognitive/graph/{twin_id}
  - Placeholder: returns empty nodes/edges and static stats; comment: "TODO: Implement actual graph store query".
  - Impact: graph UI and readiness checks show empty state; blocks publish readiness.
  - Fix: query graph store (RPCs/materialized tables) and return accurate nodes/edges and cluster stats.

- backend/routers/interview.py — get_user_context()
  - Placeholder: `memory_count=0  # TODO: Return actual count from Zep`.
  - Impact: metrics and UI misreport memory availability.
  - Fix: integrate Zep/memory store and return accurate counts.

- backend/modules/_core/tenant_guard.py — emit_audit_event()
  - Placeholder: logs only; TODO to persist audit events to DB.
  - Impact: missing audit trail (compliance/security risk).
  - Fix: async insert into `audit_logs` with retries and observability.

- backend/modules/actions_engine.py
  - Placeholder: connector stubs (Gmail/Calendar/notifications) and TODOs.
  - Impact: Actions engine non-functional for action-based onboarding demos.
  - Fix: implement connector adapter layer, secret storage, and execution tests.

---

## Frontend (non-onboarding)

- Hardcoded dev tokens and sample twin IDs
  - Locations: various frontend test/components and `lint` artifacts (e.g., `development_token`, sample `twinId`).
  - Impact: misleading local behavior, test fragility, risk of leaking tokens.
  - Fix: remove hardcoded tokens; use auth context or test fixtures; rotate/remove leaked tokens from artifacts.

- UI toggles with "TODO: Persist to backend"
  - Placeholder: toggles update local state only.
  - Impact: admin/settings changes not persisted.
  - Fix: implement `PATCH` endpoints and wire optimistic UI with error handling.

---

## Immediate priorities (recommended)

1. Persist onboarding completion server-side (frontend + small backend endpoint).
2. Persist interview/training turns via `/cognitive/interview/{twin_id}` and run scribe extraction.
3. Add server-side handle-availability check and enforce uniqueness.
4. Replace graph endpoint placeholder with a real query to the graph store or RPC.
5. Remove/replace all hardcoded dev tokens and sample IDs in frontend/tests.

---

If you want, I will now:
- (A) Commit this report into the repo (done), then produce ONBOARDING_CONTRACT.md (Phase B) mapping UI steps to SOT endpoints.
- (B) Or immediately open PR-ready tasks to implement the 5 immediate priorities.

Which should I do next? (recommended: create ONBOARDING_CONTRACT.md next.)
