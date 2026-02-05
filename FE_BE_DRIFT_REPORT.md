# FE/BE Drift Report

Last updated: 2026-02-04

Scope: Contract drift between frontend network calls and backend routes. Evidence references point to concrete call sites and router implementations. Critical path issues are listed first.

**Critical Path Drifts**

1. Missing backend routes used in onboarding
   - FE calls `POST /ingest/document` and `POST /ingest/url` without a `{twin_id}` path param from `frontend/app/onboarding/page.tsx`.
   - Backend only defines `/ingest/file/{twin_id}` and `/ingest/url/{twin_id}` in `backend/routers/ingestion.py`.
   - Impact: onboarding ingestion fails for the critical path until routes are aligned.
   - Status: Resolved in Phase 2 via compatibility shims in `backend/routers/ingestion.py`.

2. Verified QnA creation missing
   - FE calls `POST /twins/{twinId}/verified-qna` in `frontend/app/onboarding/page.tsx`.
   - Backend only exposes `GET /twins/{twin_id}/verified-qna` and `PATCH/DELETE /verified-qna/{id}` in `backend/routers/knowledge.py`.
   - Impact: onboarding verified QnA seeding fails.

3. Chat request shape mismatch on onboarding preview
   - FE sends `{ message: string }` and expects JSON in `frontend/components/onboarding/steps/PreviewTwinStep.tsx`.
   - Backend expects `ChatRequest { query: string, ... }` and returns NDJSON stream in `backend/routers/chat.py`.
   - Impact: preview chat likely breaks or returns unreadable stream.
   - Status: Partial in Phase 2. Backend now accepts `{ message }` and emits canonical stream events with `token`, but FE still expects JSON (requires FE change or server-side fallback).

4. Chat widget stream shape mismatch
   - FE widget expects `type: "content"` with `session_id` in stream (`frontend/public/widget.js`).
   - Backend emits `answer_token`/`answer_metadata` stream and only includes `session_id` in clarify events (`backend/routers/chat.py`).
   - Impact: public widget may not render responses reliably.
   - Status: Resolved in Phase 2 by emitting `metadata` and `content` events with `token` (and legacy `content` field) in `backend/routers/chat.py`.

5. Source health response mismatch
   - FE expects `health.checks` array in `frontend/app/dashboard/knowledge/[source_id]/page.tsx`.
   - Backend returns `{ health_status, staging_status, logs }` in `backend/routers/sources.py`.
   - Impact: source detail page shows empty health data.
   - Status: Resolved in Phase 2 by adding `checks: []` derived from logs in `backend/routers/sources.py`.

6. Graph extraction response mismatch
   - FE expects `nodes` array in `frontend/components/ingestion/UnifiedIngestion.tsx`.
   - Backend returns counts only (`nodes_created`, `edges_created`, `chunks_processed`) in `backend/routers/ingestion.py`.
   - Impact: FE may assume nodes data exists when only counts are returned.

7. Verification status response mismatch
   - FE expects `counts` with `{vectors, chunks, live_sources}` in `frontend/components/console/tabs/PublishTab.tsx`.
   - Backend returns `{ vectors_count, graph_nodes, is_ready, issues, last_verified_* }` in `backend/routers/twins.py`.
   - Impact: publish readiness UI shows incorrect or empty data.

8. Source reject and bulk-approve request mismatch
   - FE sends JSON body `{ reason }` for `/sources/{source_id}/reject` and `{ source_ids: [...] }` for `/sources/bulk-approve` in `frontend/app/dashboard/knowledge/[source_id]/page.tsx` and `frontend/app/dashboard/knowledge/staging/page.tsx`.
   - Backend expects query param `reason` and a raw JSON array `List[str]` in `backend/routers/sources.py`.
   - Impact: backend receives empty reason and bulk approve fails validation.
   - Status: Resolved in Phase 2 by accepting both shapes in `backend/routers/sources.py`.

9. Training jobs list and retry missing
   - FE calls `GET /training-jobs?twin_id=...` and `POST /training-jobs/{jobId}/retry` in `frontend/app/dashboard/training-jobs/page.tsx`.
   - Backend only defines `GET /training-jobs/{job_id}` and `POST /training-jobs/process-queue` in `backend/routers/ingestion.py`.
   - Impact: training jobs UI cannot load or retry jobs.
   - Status: Resolved in Phase 2 by adding `GET /training-jobs` and `POST /training-jobs/{job_id}/retry` in `backend/routers/ingestion.py`.

10. Access groups list/create path mismatch
   - FE uses tenant-scoped `/access-groups` in `frontend/app/dashboard/access-groups/page.tsx`.
   - Backend exposes twin-scoped `/twins/{twin_id}/access-groups` in `backend/routers/twins.py`.
   - Impact: access groups UI cannot load or create groups.

11. Governance page uses non-existent twin sources route
   - FE calls `GET /twins/{twin_id}/sources` in `frontend/app/dashboard/governance/page.tsx`.
   - Backend exposes `/sources/{twin_id}` in `backend/routers/sources.py`.
   - Impact: governance page source list fails.

12. Feedback route mismatch
   - FE posts to `/api/feedback/{traceId}` in `frontend/components/FeedbackWidget.tsx`.
   - Backend route is `/feedback/{trace_id}` in `backend/routers/feedback.py`.
   - Impact: feedback submissions 404 unless a Next.js API proxy exists.

13. Auth missing on critical/owner routes
   - FE uses raw `fetch` without bearer auth for: `/chat/{twin_id}`, `/debug/retrieval`, `/verify/twins/{twin_id}/run`, `/metrics/*` in `frontend/components/console/tabs/ChatTab.tsx`, `frontend/app/dashboard/page.tsx`, `frontend/app/dashboard/insights/page.tsx`.
   - Backend requires `get_current_user` or `verify_owner` for these routes.
    - Impact: unauthenticated requests fail or produce inconsistent behavior.

14. Share link token expectation drift
   - FE previously assumed `share_token` on twin record (e.g., `frontend/app/dashboard/twins/[id]/page.tsx`).
   - Backend stores share info in `settings.widget_settings` and exposes `/twins/{twin_id}/share-link`.
   - Impact: share link UI showed invalid links.
   - Status: Resolved in Phase 3/4 by fetching `/twins/{twin_id}/share-link` and using `share_url`/`share_token`.
**Other Drifts and Ambiguities**

- API key endpoints overlap and differ in schema
  - `backend/routers/auth.py` defines `/api-keys` (twin-scoped keys) while `backend/routers/api_keys.py` defines `/api-keys` (tenant-scoped keys with different schema).
  - FE uses tenant-scoped endpoints in `frontend/app/dashboard/api-keys/page.tsx`.
  - Impact: ambiguous source of truth for API keys.

- Specialization list endpoints duplicated
  - FE calls `GET /specializations` in `frontend/components/onboarding/steps/ChooseSpecializationStep.tsx`.
  - Backend also exposes `/config/specializations` and `/config/specialization` in `backend/routers/specializations.py`.
  - Impact: multiple entry points for same data and potential divergence.

- Chat widget uses `api_key` in body while auth guard accepts `X-Twin-API-Key` header elsewhere
  - Chat widget uses body field in `frontend/public/widget.js`.
  - Auth guard supports `X-Twin-API-Key` in `backend/modules/auth_guard.py`.
  - Impact: inconsistent API key transport between public and owner flows.

- TIL confirm/delete uses node name not node_id
  - FE uses node name in `frontend/components/TILFeed.tsx`.
  - Backend expects `{node_id}` in path in `backend/routers/til.py`.
  - Impact: confirm/delete may fail when name != id.

- Share link response expectations
  - FE uses share-link and sharing endpoints in `frontend/app/dashboard/settings/page.tsx`.
  - Backend responds with `ShareLinkResponse` in `backend/routers/auth.py`.
  - Drift risk: FE expects `share_url` always present; backend may omit when sharing disabled.

**Placeholder Responses**

- `GET /connectors` returns `[]` from `backend/routers/auth.py` while FE treats it as a tenant-scoped list in `frontend/app/dashboard/actions/page.tsx`.
- `GET /cognitive/graph/{twin_id}` is labeled placeholder in `backend/routers/cognitive.py` and is unused by FE (not critical path).

**Evidence References**

- Frontend call sites: `frontend/app/onboarding/page.tsx`, `frontend/components/onboarding/steps/PreviewTwinStep.tsx`, `frontend/public/widget.js`, `frontend/app/dashboard/knowledge/[source_id]/page.tsx`, `frontend/app/dashboard/knowledge/staging/page.tsx`, `frontend/components/ingestion/UnifiedIngestion.tsx`, `frontend/components/console/tabs/PublishTab.tsx`, `frontend/app/dashboard/training-jobs/page.tsx`, `frontend/app/dashboard/access-groups/page.tsx`, `frontend/app/dashboard/governance/page.tsx`, `frontend/components/FeedbackWidget.tsx`, `frontend/app/dashboard/page.tsx`.
- Backend routes: `backend/routers/ingestion.py`, `backend/routers/chat.py`, `backend/routers/sources.py`, `backend/routers/twins.py`, `backend/routers/knowledge.py`, `backend/routers/auth.py`, `backend/routers/api_keys.py`.
