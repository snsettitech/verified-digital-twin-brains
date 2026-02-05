# Backend Verification Plan (Plan Only)

## Test Principles
- Preserve ingestion + retrieval correctness on every refactor.
- Cover tenant isolation and public endpoints explicitly.
- Keep E2E smoke tests for the full loop: ingest -> chat -> review -> analytics.

## Unit Tests To Add Or Update
- Identity gate logic: `backend/modules/identity_gate.py` (add cases for stance vs non-stance) -> new tests in `backend/tests/test_core_modules.py`.
- Share link validation: `backend/modules/share_links.py` -> add tests for token mismatch and expiry in `backend/tests/test_core_modules.py`.
- API key validation (tenant scoped): `backend/routers/api_keys.py` and widget auth in `backend/routers/chat.py` -> add tests in `backend/tests/test_api_integration.py`.
- Unified jobs model: `backend/modules/jobs.py` -> add job lifecycle tests in `backend/tests/test_core_logic.py`.
- Verified QnA matching: `backend/modules/verified_qna.py` -> tests for exact/semantic match in `backend/tests/test_core_logic.py`.

## Integration Tests To Add Or Update
- Ingestion flow:
  - `POST /ingest/file/{twin_id}` -> `backend/routers/ingestion.py`.
  - Verify `sources`, `chunks`, Pinecone namespace `twin_id` (`backend/modules/ingestion.py`).
  - Update `backend/tests/test_p0_integration.py` and `backend/tests/test_content_extraction.py`.
- Chat flow:
  - `POST /chat/{twin_id}` SSE + `GET /conversations/{twin_id}` + `GET /conversations/{conversation_id}/messages` (`backend/routers/chat.py`).
  - Ensure `owner_memory` clarify path is covered (`backend/routers/owner_memory.py`).
- Share link flow:
  - `POST /twins/{twin_id}/share-link`, `GET /public/validate-share/{twin_id}/{token}`, `POST /public/chat/{twin_id}/{token}`.
  - Add integration test for public chat in `backend/tests/test_api_integration.py`.

## End-To-End Smoke Tests (Core Loop)
- Scripted flow (reuse `backend/verify_full_publish_flow.py` or add new):
  1. Create twin (`POST /twins`).
  2. Ingest a file (`POST /ingest/file/{twin_id}`).
  3. Process jobs until status complete (`/jobs` unified endpoint).
  4. Ask a question via `/chat/{twin_id}` and `/public/chat/{twin_id}/{token}`.
  5. Confirm conversation list + messages + metrics (`/metrics/dashboard/{twin_id}`).

## Load, Rate Limiting, Queue Resilience
- Load test public chat and widget:
  - `POST /chat-widget/{twin_id}` (SSE) and `POST /public/chat/{twin_id}/{token}`.
  - Verify `rate_limit_tracking` updates in `backend/modules/rate_limiting.py`.
- Queue resilience:
  - Stress test unified jobs queue in `backend/modules/job_queue.py` and `backend/worker.py`.
  - Ensure idempotency for graph/job processing where retained (`backend/modules/_core/scribe_engine.py`).

## Security And Tenancy Isolation
- Tenant isolation tests:
  - Use `backend/modules/auth_guard.py` to attempt cross-tenant access on twins, sources, and conversations.
  - Validate RLS policy coverage from `backend/migrations/enable_rls_all_tables.sql` and `backend/database/migrations/migration_v2_scope_hardening.sql`.
- Public endpoint protection:
  - Ensure `public/chat` requires valid share token (`backend/modules/share_links.py`).
  - Ensure widget requires API key + domain allowlist (`backend/routers/chat.py` + `backend/modules/api_keys.py` or unified tenant key logic).

## Observability Checks
- Correlation ID header propagation in `backend/main.py` (ensure `x-correlation-id` echoed).
- Health endpoints:
  - `GET /health` (in `backend/main.py`)
  - `GET /metrics/health` (in `backend/routers/metrics.py`)
  - `GET /observability/health` (in `backend/routers/observability.py`).
