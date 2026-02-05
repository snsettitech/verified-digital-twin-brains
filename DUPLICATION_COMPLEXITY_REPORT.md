# Duplication and Complexity Report

Last updated: 2026-02-04

Focus: duplicate implementations that create inconsistent behavior or unnecessary branches on the critical path. Each cluster includes risks and the recommended canonical path.

**Cluster 1: API clients and fetch wrappers**

- What is duplicated
  - `useAuthFetch` hook (`frontend/lib/hooks/useAuthFetch.ts`) with scoped methods (`getTenant`, `getTwin`).
  - `authFetchStandalone` and `getAuthToken` (same file) used outside React.
  - Direct raw `fetch` usage in many components (e.g., `frontend/app/dashboard/page.tsx`, `frontend/components/console/tabs/ChatTab.tsx`, `frontend/components/onboarding/steps/PreviewTwinStep.tsx`).
- Risks and bugs
  - Missing auth headers on critical endpoints, inconsistent error handling, and bypass of scope enforcement.
  - Multiple auth strategies lead to stale tokens and transient 401s.
- Impact on critical path
  - Chat and ingestion calls can fail due to missing auth or wrong scope; onboarding preview breaks.
- Recommended canonical path
  - Single fetch client that always injects auth and enforces tenant/twin scoping; no raw `fetch` outside that client. Use `useAuthFetch` everywhere or build a shared API client and refactor all calls to it.

**Cluster 2: Tenant and twin resolution**

- What is duplicated
  - Backend resolves tenant (`resolve_tenant_id` in `backend/modules/auth_guard.py`), while frontend sometimes sends `tenant_id` (`frontend/app/dashboard/right-brain/page.tsx`) and stores `activeTwinId` in localStorage (`frontend/lib/context/TwinContext.tsx`).
  - Scope enforcement exists in `useAuthFetch`, but many components bypass it.
- Risks and bugs
  - Drift between client-selected twin and backend-verified twin; potential cross-tenant leakage if client data is trusted.
- Impact on critical path
  - Twin creation and ingestion can be attributed incorrectly, or requests fail with 403.
- Recommended canonical path
  - Backend is single source of truth for tenant; frontend never sends `tenant_id`. Use `activeTwin.id` only for twin-scoped routes and always through scoped API client.

**Cluster 3: API key systems (overlapping routes)**

- What is duplicated
  - Twin-scoped API keys in `backend/routers/auth.py` on `/api-keys`.
  - Tenant-scoped API keys in `backend/routers/api_keys.py` on `/api-keys` with different schema.
  - Frontend uses tenant-scoped API keys in `frontend/app/dashboard/api-keys/page.tsx`.
- Risks and bugs
  - Route collision and ambiguous behavior depending on router order; two schemas for the same path.
- Impact on critical path
  - Public widget / API key generation can break or return unexpected schema.
- Recommended canonical path
  - Choose tenant-scoped API keys (`backend/routers/api_keys.py`) as canonical; deprecate/remove twin-scoped duplicate routes or move them to a different path.

**Cluster 4: Ingestion pipelines**

- What is duplicated
  - `backend/routers/ingestion.py` and `backend/routers/enhanced_ingestion.py` both expose `/ingest/youtube/{twin_id}` with different logic.
  - Enhanced ingestion adds `/ingest/website`, `/ingest/rss`, `/ingest/twitter`, `/ingest/linkedin` with no FE usage.
- Risks and bugs
  - Duplicate route paths can shadow each other; inconsistent processing, duplicate source records, and confusing status transitions.
- Impact on critical path
  - Ingestion reliability suffers; debugging inconsistent artifacts becomes harder.
- Recommended canonical path
  - Keep a single ingestion router for the core path. If enhanced ingestion is not required for MVP, gate or disable it, and ensure only one `/ingest/youtube` exists.

**Cluster 5: Retrieval endpoints and stream formats**

- What is duplicated
  - Owner chat: `/chat/{twin_id}` (stream).
  - Widget chat: `/chat-widget/{twin_id}` (stream).
  - Share chat: `/public/chat/{twin_id}/{token}` (non-stream).
  - Each returns different response shapes.
- Risks and bugs
  - FE expects mismatched stream event shapes (`content` vs `answer_token`) and JSON vs stream.
  - Multiple code paths for owner/public identity gate and owner memory handling.
- Impact on critical path
  - Public retrieval is unreliable; widget rendering fails.
- Recommended canonical path
  - Define one stream event contract and use it across `/chat` and `/chat-widget`, and either stream or non-stream for `/public/chat` but with a consistent shape and clear client handling.
**Cluster 6: Specialization endpoints**

- What is duplicated
  - `GET /specializations` in `backend/routers/twins.py`.
  - `GET /config/specializations` and `GET /config/specialization` in `backend/routers/specializations.py`.
- Risks and bugs
  - Two sources for specialization config increase risk of drift and inconsistent UI options.
- Impact on critical path
  - Twin creation flow depends on specialization; inconsistent lists cause onboarding errors.
- Recommended canonical path
  - Keep one specialization endpoint and redirect all FE usage to it.

**Cluster 7: Graph extraction paths**

- What is duplicated
  - Explicit graph extraction via `POST /ingest/extract-nodes/{source_id}` (`backend/routers/ingestion.py`).
  - Implicit extraction enqueued in chat flow (`backend/routers/chat.py`, scribe enqueue).
- Risks and bugs
  - Two paths may create overlapping graph nodes or inconsistent statuses.
- Impact on critical path
  - Graph artifacts can diverge from source ingestion, confusing readiness checks.
- Recommended canonical path
  - Choose one graph extraction trigger: explicit ingestion-time extraction or a single background job. Ensure a single status source.

**Cluster 8: Scope enforcement vs raw fetch**

- What is duplicated
  - Scope enforcement in `useAuthFetch` but bypassed by raw `fetch` in several pages.
- Risks and bugs
  - Drift between FE and BE scope expectations; silent data leaks or 403s.
- Impact on critical path
  - Critical calls (chat, metrics, verification) fail without auth in prod.
- Recommended canonical path
  - Ban raw `fetch` to backend routes in the UI; enforce usage of scoped methods only.

**Cluster 9: Source health and training job status**

- What is duplicated
  - Source health implied via `/sources/{source_id}/health` logs, and via training job pages expecting `/training-jobs` list.
- Risks and bugs
  - Two sources of truth for ingestion status; UI shows inconsistent states.
- Impact on critical path
  - Ingestion reliability and readiness checks are unclear.
- Recommended canonical path
  - Define a single ingestion status API surface that includes source health, job state, and artifact counts.

**Cluster 10: API key transport**

- What is duplicated
  - API key passed via `X-Twin-API-Key` header in auth guard and via body `api_key` in `/chat-widget`.
- Risks and bugs
  - Multiple API key transport paths create inconsistent security policies and rate limits.
- Impact on critical path
  - Public widget authentication can break depending on client implementation.
- Recommended canonical path
  - Standardize on a single API key transport method and enforce it consistently.

**Evidence References**

- Fetch wrappers: `frontend/lib/hooks/useAuthFetch.ts`, `frontend/lib/context/TwinContext.tsx`.
- Raw fetch call sites: `frontend/app/dashboard/page.tsx`, `frontend/components/console/tabs/ChatTab.tsx`, `frontend/components/onboarding/steps/PreviewTwinStep.tsx`.
- Ingestion routers: `backend/routers/ingestion.py`, `backend/routers/enhanced_ingestion.py`.
- Retrieval routers: `backend/routers/chat.py`.
- Specializations: `backend/routers/twins.py`, `backend/routers/specializations.py`.
