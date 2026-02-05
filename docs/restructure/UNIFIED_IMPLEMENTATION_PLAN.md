# Unified Implementation Plan (Plan Only)

**Last Updated:** 2026-02-04  
**Scope:** Backend + Frontend + Docs, aligned to Clone-for-Experts (web-only)  
**Guardrails:** Remove UI entry points before backend deletions, keep ingestion + retrieval functional, `main` stays releasable after every PR.

## Alignment Review Of Existing Plan

**Aligned**
- Backend PR sequencing in `docs/restructure/BACKEND_PR_EXECUTION_PLAN.md` matches the backend API contract in `docs/restructure/BACKEND_API_CONTRACT_V1.md`.
- Data model consolidation steps align with `docs/restructure/BACKEND_DATA_MODEL_PLAN.md`.
- Deletion targets and rationale align with `docs/restructure/BACKEND_DELETION_DEFER_PLAN.md`.

**Gaps To Address**
- No unified plan tying backend PRs to frontend route updates and endpoint drift fixes.
- Frontend docs reference incorrect endpoints (examples: public chat, share validation, conversations, metrics stats) compared to `docs/restructure/BACKEND_ROUTE_INVENTORY.md`.
- No sequencing rule for removing frontend UI before removing backend routers.
- No explicit PR for standardizing frontend API calls to the canonical endpoints in `docs/restructure/BACKEND_API_CONTRACT_V1.md`.

## Deletion-First Unified Plan (Backend + Frontend + Docs)

### PR 0: Contract Lock + Doc Alignment
**Goal:** Freeze canonical endpoints and fix doc drift before code changes.
- Update `docs/restructure/FRONTEND_ROUTE_AND_COMPONENT_INVENTORY.md` to match `docs/restructure/BACKEND_ROUTE_INVENTORY.md`.
- Update `docs/restructure/FRONTEND_STATE_MODEL.md` and `docs/restructure/FRONTEND_UX_REDESIGN_SPEC.md` to use canonical endpoints:
  - Public chat: `POST /public/chat/{twin_id}/{token}`
  - Share validation: `GET /public/validate-share/{twin_id}/{token}`
  - Conversations: `GET /conversations/{twin_id}`
  - Knowledge profile: `GET /twins/{twin_id}/knowledge-profile`
  - Metrics: `GET /metrics/dashboard/{twin_id}` and `GET /metrics/usage/{twin_id}?days=`
- Ensure `docs/restructure/README.md` references backend docs or note that it is frontend-only.
**Verification:** Manual doc review for endpoint consistency across `docs/restructure/*`.

### PR 1: Backend Missing MVP Endpoints
**Goal:** Close known FE/BE gaps without breaking existing flows.
- Add invitation acceptance endpoints in `backend/routers/auth.py` using `backend/modules/user_management.py`.
- Add `POST /twins/{twin_id}/verified-qna` in `backend/routers/knowledge.py` using `backend/modules/verified_qna.py`.
- Fix `twin_verifications` vs `twin_verification` in `backend/routers/verify.py` and `backend/routers/twins.py`.
**Verification:** Update `backend/tests/test_auth_comprehensive.py` and `backend/tests/test_p0_integration.py`.

### PR 2: Frontend Endpoint Alignment (No Backend Deletions)
**Goal:** Update frontend API calls to canonical endpoints.
- Update FE API usage to match `docs/restructure/BACKEND_API_CONTRACT_V1.md` for public chat, share validation, conversations, and knowledge profile.
- Ensure public chat uses `POST /public/chat/{twin_id}/{token}`.
- Ensure share page validates via `GET /public/validate-share/{twin_id}/{token}`.
- Remove any UI that assumes manual source approval; ingestion is auto-indexed and uses delete/re-extract only.
**Verification:** Update or add FE tests or QA checklist items in `docs/restructure/FRONTEND_QA_CHECKLIST.md`.

### PR 3: Auto-Indexed Ingestion Baseline (No Approval)
**Goal:** Make ingestion always index immediately and remove manual approval surfaces.
- Backend: Remove `/sources/*/approve|reject|bulk-approve` and any staging gating.
- Backend: Ensure `/ingest/file` and `/ingest/url` always index and return `status=live`.
- Frontend: Remove any staging/approval UI and status assumptions.
**Verification:** Upload a file -> status `processing -> live` -> chunks indexed.

### PR 4: Frontend Scope Reduction (UI First)
**Goal:** Remove UI entry points for out-of-scope features before backend removal.
- Hide/remove UI for actions, escalations, interviews, audio, reasoning, governance, and right-brain flows.
- Keep URLs stable where needed via redirects or stubs.
**Verification:** Manual UI walkthrough plus targeted FE tests.

### PR 5: Backend Removals (Feature By Feature)
**Goal:** Delete backend wiring in a strict order after UI removal.
1. Actions engine
2. Escalations + safety
3. Cognitive/interview/reasoning/audio
4. Enhanced ingestion + external tooling
5. Specializations + VC routes
**Verification:** `rg -n` checks in `backend/`, run core ingestion + chat tests between removals.

### PR 6: Unified Jobs Model + Frontend Alignment
**Goal:** Replace `training_jobs` with unified `jobs` and keep ingestion stable.
- Backend: Extend `jobs.job_type` in `backend/migrations/create_jobs_tables.sql`.
- Backend: Update `backend/modules/training_jobs.py`, `backend/routers/ingestion.py`, and `backend/worker.py` to use `backend/modules/jobs.py`.
- Frontend: Update any job status UI to use `/jobs`.
**Verification:** Update `backend/tests/test_p0_integration.py` and add a job lifecycle unit test.

### PR 7: API Key Unification (Tenant-Scoped)
**Goal:** Single API key model for widget + embed.
- Backend: Update `backend/routers/chat.py` widget auth to use tenant keys from `backend/routers/api_keys.py`.
- Backend: Add migration under `backend/database/migrations/` to backfill `twin_api_keys` into `tenant_api_keys`.
- Backend: Deprecate `backend/modules/api_keys.py` and `/api-keys` in `backend/routers/auth.py` for one release.
- Frontend: Update widget provisioning to use tenant keys consistently.
**Verification:** Add tests in `backend/tests/test_api_integration.py`, validate `frontend/public/widget.js`.

### PR 8: Migrations Consolidation + Data Model Cleanup
**Goal:** Single migration chain and remove unused tables.
- Consolidate `backend/migrations/*` into `backend/database/migrations/*`.
- Add migration to drop unused tables after code removal.
- Resolve specialization columns to a single canonical representation or remove entirely.
**Verification:** Run migrations in staging, update RLS tests in `backend/tests/test_tenant_guard.py`.

### PR 9: Analytics + Audience
**Goal:** Provide minimal enterprise analytics and audience list.
- Add `GET /audience/{twin_id}` in `backend/routers/metrics.py` or new router.
- Ensure `backend/modules/metrics_collector.py` is the canonical writer.
- Update FE Operate pages to use the new endpoint.
**Verification:** Add integration tests, update FE QA checklist.

### PR 10: Post-MVP Hardening
**Goal:** Final cleanup, verification, and docs updates.
- Remove deprecated backend routes if unused.
- Finalize doc updates in `docs/restructure/*`.
- Run E2E smoke tests for ingest -> chat -> conversations -> analytics.
**Verification:** Use `docs/restructure/BACKEND_VERIFICATION_PLAN.md` and `docs/restructure/FRONTEND_QA_CHECKLIST.md`.

## Cross-Cutting Rules
- Always remove frontend entry points before backend router deletion.
- Keep public chat, share links, and widget flows working in every PR.
- Maintain ingestion, indexing, and retrieval correctness after each PR.
- No manual source approval workflow. Ingestion is auto-indexed by default.
