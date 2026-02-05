# Backend Restructure Overview

## Scope And Constraints
- Deletion-first strategy: remove non-core features before adding new ones.
- Keep ingestion + retrieval functional after every change.
- Primary goal: simplify to a web-only clone-for-experts product while preserving a strong ingestion/retrieval moat.

## Strategy Update (Auto-Indexed Ingestion)
- Manual source approval is removed; ingestion auto-indexes on upload.
- Sources APIs return normalized statuses (no staging workflow).

## Current Backend Architecture (Snapshot)
- Framework: FastAPI app in `backend/main.py` with uvicorn entrypoints in `backend/Procfile` and `backend/railway.json`.
- Router registration (directly in `backend/main.py`): `auth`, `chat`, `ingestion`, `youtube_preflight`, `twins`, `actions`, `knowledge`, `sources`, `governance`, `escalations`, `specializations`, `observability`, `cognitive`, `graph`, `metrics`, `jobs`, `til`, `feedback`, `audio`, `reasoning`, `interview`, `api_keys`, `debug_retrieval`, `verify`, `owner_memory`.
- Conditional routers: `enhanced_ingestion` gated by `ENABLE_ENHANCED_INGESTION`, and `api/vc_routes.py` gated by `ENABLE_VC_ROUTES` in `backend/main.py`.
- Health endpoints defined in `backend/main.py`: `GET /health` and `GET /`.
- Background worker: `backend/worker.py` consumes queue from `backend/modules/job_queue.py`, processes `backend/modules/training_jobs.py` and graph extraction from `backend/modules/_core/scribe_engine.py`.

## Step 0 Inventory (Summary)
### Framework And Entrypoints
- FastAPI app and middleware in `backend/main.py` (CORS + correlation ID logging).
- Runtime entrypoints: `backend/Procfile`, `backend/railway.json`.

### Routers And Routes
- Full route inventory documented in `docs/restructure/BACKEND_ROUTE_INVENTORY.md` with definitions from `backend/routers/*.py` and registrations in `backend/main.py`.

### Background Workers And Queues
- Worker loop: `backend/worker.py`.
- Queue backend: `backend/modules/job_queue.py` (Redis or in-memory).
- Training jobs: `backend/modules/training_jobs.py` (table `training_jobs` from `backend/database/migrations/migration_phase6_mind_ops.sql`).
- Graph extraction jobs: `backend/modules/_core/scribe_engine.py` uses `backend/modules/jobs.py` and `backend/migrations/create_jobs_tables.sql`.

### Storage (Postgres/Supabase)
- Supabase client in `backend/modules/observability.py`.
- Base schema reference: `backend/database/schema/supabase_schema.sql`.
- Migrations: `backend/database/migrations/*` and `backend/migrations/*` (split source of truth).
- RLS enablement: `backend/migrations/enable_rls_all_tables.sql` and tenant hardening in `backend/database/migrations/migration_v2_scope_hardening.sql`.

### Vector Database Usage
- Pinecone client in `backend/modules/clients.py`.
- Ingestion upserts to Pinecone with `namespace=twin_id` in `backend/modules/ingestion.py`.
- Retrieval queries Pinecone in `backend/modules/retrieval.py`.
- Vector IDs stored in `chunks.vector_id` from `backend/database/schema/supabase_schema.sql`.

### External Integrations
- OpenAI: `backend/modules/clients.py`, `backend/modules/agent.py`, `backend/modules/ingestion.py`.
- Pinecone: `backend/modules/clients.py`, `backend/modules/ingestion.py`, `backend/modules/retrieval.py`.
- Cohere (rerank): `backend/modules/clients.py`, `backend/modules/retrieval.py`.
- ElevenLabs (TTS): `backend/modules/clients.py`, `backend/modules/audio_generator.py`.
- Firecrawl (web crawl): `backend/modules/web_crawler.py`.
- Media ingestion deps (yt-dlp, pydub, ffmpeg): `backend/modules/media_ingestion.py`.
- Composio + web search tools: `backend/modules/tools.py`.
- Langfuse tracing: `backend/modules/langfuse_client.py` and usage in `backend/routers/chat.py`, `backend/modules/_core/scribe_engine.py`.

### Observability
- Request logging and correlation IDs in `backend/main.py`.
- Metrics + health in `backend/modules/metrics_collector.py` and `backend/routers/metrics.py`.
- Health router in `backend/routers/observability.py`.

## Product Pivot Alignment (High Level)
Target modules for the simplified product:
1. Studio build flow: ingestion, indexing, roles, identity/boundaries, knowledge quality tests.
2. Launch flow: share links + embed widget (web only) + domain allowlist.
3. Operate flow: conversation review, audience list, basic analytics.
4. Enterprise basics: tenant isolation, correlation IDs, audit logs, retryable jobs, stable async status, observability, migrations, stepwise plan.

## Key Findings That Drive The Restructure
1. Duplicate or conflicting subsystems
- Two API key systems: twin-scoped keys in `backend/modules/api_keys.py` exposed by `backend/routers/auth.py`, and tenant-scoped keys in `backend/routers/api_keys.py` (tenant_api_keys table from `backend/database/migrations/migration_scope_enforcement.sql`).
- Two job systems: `training_jobs` (Phase 6 mind ops) in `backend/modules/training_jobs.py` plus generic `jobs` in `backend/modules/jobs.py` and `backend/routers/jobs.py`. Graph extraction uses `jobs` (see `backend/modules/_core/scribe_engine.py`), while ingestion uses `training_jobs` (see `backend/routers/ingestion.py`).
- Two specialization columns: `specialization` from `backend/migrations/add_twin_specialization.sql` and `specialization_id` from `backend/database/migrations/migration_phase3_5_gate1_specialization.sql`. Routers read `twins.specialization` in `backend/routers/specializations.py`.

2. Migrations split across two directories
- Migrations live in both `backend/database/migrations/*` and `backend/migrations/*`. Core tables (jobs, metrics, user_events, usage_quotas, service_health_logs) exist only in `backend/migrations/*` while runtime code uses them (e.g., `backend/routers/jobs.py`, `backend/modules/metrics_collector.py`, `backend/routers/metrics.py`).

3. Scope-expanding modules currently wired into runtime
- Actions engine (`backend/routers/actions.py`, `backend/modules/actions_engine.py`) is actively used in `/public/chat` flow (`backend/routers/chat.py`) and has UI surfaces in `frontend/app/dashboard/actions/*`.
- Escalations flow (`backend/routers/escalations.py`, `backend/modules/escalation.py`) is used by analytics (`backend/routers/metrics.py`) and UI (`frontend/app/dashboard/escalations/page.tsx`).
- Cognitive/Interview/Reasoning/Audio features are fully routed and used by the frontend (see `backend/routers/cognitive.py`, `backend/routers/interview.py`, `backend/routers/reasoning.py`, `backend/routers/audio.py` and references in `frontend/components/Chat/InterviewInterface.tsx`, `frontend/app/dashboard/right-brain/page.tsx`).

4. Missing or mismatched endpoints vs frontend
- Frontend calls missing endpoints for invitation acceptance: `/auth/invitation/{token}` and `/auth/accept-invitation` (see `frontend/app/auth/accept-invitation/[token]/page.tsx`). Only invite creation exists in `backend/routers/auth.py` and `backend/modules/user_management.py`.
- Frontend POSTs `/twins/{twinId}/verified-qna` (see `frontend/app/onboarding/page.tsx`) but backend only exposes GET/PATCH/DELETE for verified QnA in `backend/routers/knowledge.py`.
- Widget requires `api_key` in `frontend/public/widget.js`, but the embed UI (`frontend/app/dashboard/widget/page.tsx`) does not provision it.

## Restructure Direction (Summary)
- Consolidate to a single, minimal API surface for web chat + embed and a simple studio/ops set.
- Remove or defer non-core subsystems: actions engine, escalations, cognitive interview, audio, reasoning, VC specialization, enhanced ingestion pipelines, external tool connectors.
- Unify jobs and API key models, and unify migration sources.
- Keep ingestion + retrieval intact and testable at each step.

## Outputs Produced (Docs)
These files are created in `docs/restructure/`:
- `BACKEND_RESTRUCTURE_OVERVIEW.md`
- `BACKEND_ROUTE_INVENTORY.md`
- `BACKEND_KEEP_TWEAK_REFACTOR_DELETE.md`
- `BACKEND_DELETION_DEFER_PLAN.md`
- `BACKEND_API_CONTRACT_V1.md`
- `BACKEND_DATA_MODEL_PLAN.md`
- `BACKEND_PR_EXECUTION_PLAN.md`
- `BACKEND_VERIFICATION_PLAN.md`

## Step 0-5 Coverage
- Step 0: Full backend inventory with routes, workers, storage, vector DB, integrations, observability.
- Step 1: Map existing modules/routes to the new product buckets (keep/tweak/refactor/delete).
- Step 2: Deletion/defer plan with evidence and verification steps.
- Step 3: Refactor plan with module boundaries, API contract, data model changes, async jobs.
- Step 4: Missing pieces required for MVP and enterprise v1.
- Step 5: Verification plan for unit, integration, E2E, load, and security checks.
