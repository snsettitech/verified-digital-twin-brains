# Backend Deletion / Defer Plan (Plan Only)

## Evidence Rules
- Each candidate lists the exact backend files and the route registration or import paths proving current wiring.
- "Delete" means remove after dependent calls are removed. "Defer" means keep but disable (e.g., un-register router or keep env flag off) until dependencies are removed.
- Verification steps use ripgrep patterns and route inventory diffs to prove removal.

## Category 1: Old Digital Brains Features Not Needed For Web-Only Clone-For-Experts

### Actions Engine + Connectors (DEFER then DELETE)
- Files:
  - `backend/routers/actions.py` (routes `/twins/{twin_id}/events`, `/triggers`, `/action-drafts`, `/executions`, `/connectors`)
  - `backend/modules/actions_engine.py` (EventEmitter, TriggerMatcher, ActionDraftManager)
  - `backend/database/migrations/migration_phase8_actions_engine.sql` (tables `events`, `tool_connectors`, `action_triggers`, `action_drafts`, `action_executions`)
- Why (evidence): Out-of-scope. Actively wired in runtime via `app.include_router(actions.router)` in `backend/main.py` and invoked from public chat in `backend/routers/chat.py` (`EventEmitter.emit` + `ActionDraftManager.get_pending_drafts`).
- Replacement: None (public chat should not trigger automation). If any notification is needed, replace with analytics event in `backend/routers/metrics.py`.
- Verify unused before delete:
  - `rg -n "actions_engine|action-drafts|triggers|executions|connectors" backend frontend`
  - Ensure `app.include_router(actions.router)` removed from `backend/main.py` and routes removed from `docs/restructure/BACKEND_ROUTE_INVENTORY.md`.

### Escalations + Safety Layer (DEFER then DELETE)
- Files:
  - `backend/routers/escalations.py` (routes `/twins/{twin_id}/escalations`, `/escalations`)
  - `backend/modules/escalation.py`
  - `backend/modules/safety.py`
  - Base schema tables in `backend/database/schema/supabase_schema.sql` (`escalations`, `escalation_replies`)
  - Metrics references in `backend/routers/metrics.py` (escalation rate, activity feed)
- Why (evidence): Explicitly out-of-scope (no special safety/escalation). Routes are registered in `backend/main.py`. Metrics depends on escalations so must be refactored before delete.
- Replacement: Verified QnA creation should be manual (`/twins/{twin_id}/verified-qna`) instead of escalation-driven (`modules/verified_qna.py` currently expects escalation_id).
- Verify unused before delete:
  - `rg -n "escalations|escalation_replies|safety" backend frontend`
  - Remove escalation references from `backend/routers/metrics.py` and `frontend` UI (`frontend/components/console/tabs/EscalationsTab.tsx`, `frontend/app/dashboard/escalations/*`).

### Cognitive Interview + Reasoning + Audio (DEFER then DELETE)
- Files:
  - `backend/routers/cognitive.py`
  - `backend/routers/interview.py` (prefix `/api/interview`)
  - `backend/routers/reasoning.py`
  - `backend/routers/audio.py`
  - `backend/modules/reasoning_engine.py`, `backend/modules/audio_generator.py`, `backend/modules/zep_memory.py`, `backend/modules/memory_extractor.py`
  - Interview tables in `backend/database/migrations/interview_sessions.sql`, `migration_interview_sessions.sql`, `migration_interview_session_quality.sql`
- Why (evidence): Out-of-scope (web-only chat, no voice, no interview). Routers registered in `backend/main.py`. Chat uses reasoning engine in `backend/routers/chat.py` (is_reasoning_query path) so remove that path first.
- Replacement: None. Standard chat pipeline (`modules/agent.py`) remains.
- Verify unused before delete:
  - `rg -n "interview|reasoning|audio|zep" backend frontend`
  - Remove UI references (`frontend/app/dashboard/interview/page.tsx`, `frontend/components/interview/*`).

### Specializations + VC Routes (DEFER then DELETE)
- Files:
  - `backend/routers/specializations.py`
  - `backend/api/vc_routes.py` (conditional in `backend/main.py` via `ENABLE_VC_ROUTES`)
  - `backend/modules/specializations/*`
  - Columns in `backend/migrations/add_twin_specialization.sql` and `backend/database/migrations/migration_phase3_5_gate1_specialization.sql`
- Why (evidence): Product is single "expert" path. Specializations are optional and VC routes are gated by env flag in `backend/main.py` but still present.
- Replacement: Use a fixed specialization in `twins.settings` or remove specialization fields from API.
- Verify unused before delete:
  - `rg -n "specialization" backend frontend`
  - Ensure `ENABLE_VC_ROUTES` is not used and `app.include_router(specializations.router)` removed from `backend/main.py`.

### Enhanced Ingestion (Firecrawl, Social, Pipelines) (DELETE once confirmed unused)
- Files:
  - `backend/routers/enhanced_ingestion.py` (conditional in `backend/main.py` via `ENABLE_ENHANCED_INGESTION`)
  - `backend/modules/web_crawler.py`, `backend/modules/social_ingestion.py`, `backend/modules/auto_updater.py`
- Why (evidence): Out-of-scope; adds Firecrawl/Twitter/LinkedIn complexity. Routes only registered when `ENABLE_ENHANCED_INGESTION=true` in `backend/main.py`.
- Replacement: Keep standard ingestion in `backend/routers/ingestion.py` (file, url, youtube, podcast, x thread).
- Verify unused before delete:
  - `rg -n "ingest/website|pipelines|rss|linkedin|firecrawl" frontend backend`
  - Ensure `ENABLE_ENHANCED_INGESTION=false` in runtime config and remove router registration.

### External Tool Connectors / Web Search (DEFER then DELETE)
- Files:
  - `backend/modules/tools.py` (Composio tools + DuckDuckGo search)
  - `backend/modules/agent.py` (imports `get_cloud_tools`)
- Why (evidence): Out-of-scope (no platform/tool integrations). Tools are optional but wired in agent init in `backend/modules/agent.py`.
- Replacement: Keep retrieval tool only (`get_retrieval_tool`) in `backend/modules/tools.py` or move retrieval tool into `modules/retrieval.py`.
- Verify unused before delete:
  - `rg -n "get_cloud_tools|composio|DuckDuckGo" backend`
  - Remove tool setup from `backend/modules/agent.py` and ensure tests still pass.

## Category 2: Duplicate Or Overlapping Endpoints / Dead Code

### Dual API Key Systems (MERGE then DELETE ONE)
- Files:
  - Twin-scoped keys: `backend/modules/api_keys.py` + `/api-keys` in `backend/routers/auth.py` (uses `twin_api_keys` from `backend/database/migrations/migration_phase7_omnichannel.sql`)
  - Tenant-scoped keys: `backend/routers/api_keys.py` + `tenant_api_keys` from `backend/database/migrations/migration_scope_enforcement.sql`
- Why (evidence): Duplicate endpoints with same paths (`/api-keys`) registered in `backend/main.py`. Widget uses twin-scoped key validation in `backend/routers/chat.py`.
- Replacement: Keep tenant-scoped `tenant_api_keys` and update widget/public usage to accept tenant keys with `allowed_twin_ids`.
- Verify unused before delete:
  - `rg -n "twin_api_keys|tenant_api_keys" backend frontend`
  - Ensure only one `/api-keys` router is registered in `backend/main.py`.

### Dual Job Systems (MERGE then DELETE ONE)
- Files:
  - `backend/modules/training_jobs.py` + `/training-jobs` routes in `backend/routers/ingestion.py` (table `training_jobs` in `backend/database/migrations/migration_phase6_mind_ops.sql`)
  - `backend/modules/jobs.py` + `/jobs` routes in `backend/routers/jobs.py` (tables `jobs`, `job_logs` in `backend/migrations/create_jobs_tables.sql`)
- Why (evidence): Two async job models with different tables. Worker uses both (`backend/worker.py`) and graph extraction uses `jobs` (`backend/modules/_core/scribe_engine.py`).
- Replacement: Single `jobs` table with `job_type` expanded to include ingestion and graph extraction; remove `training_jobs` table/routes after migration.
- Verify unused before delete:
  - `rg -n "training_jobs" backend`
  - Confirm ingestion routes use `/jobs` and `backend/worker.py` only targets the unified model.

### Twin Verification Table Name Mismatch (FIX then DELETE OLD)
- Files:
  - `backend/routers/verify.py` inserts into `twin_verifications` (plural)
  - `backend/modules/governance.py` uses `twin_verification` (singular)
  - `backend/database/migrations/migration_phase9_governance.sql` creates `twin_verification`
- Why (evidence): Runtime mismatch prevents verification status from being shared across code paths.
- Replacement: Standardize on `twin_verification` table name and update verify route accordingly.
- Verify unused before delete:
  - `rg -n "twin_verifications" backend` should return none after fix.

### Specialization Columns Duplication (CLEANUP)
- Files:
  - `backend/migrations/add_twin_specialization.sql` adds `twins.specialization`
  - `backend/database/migrations/migration_phase3_5_gate1_specialization.sql` adds `twins.specialization_id`
  - `backend/routers/specializations.py` uses `twins.specialization`
- Why (evidence): Two columns representing same concept.
- Replacement: Remove specialization entirely or keep one canonical column.
- Verify unused before delete:
  - `rg -n "specialization_id|specialization" backend frontend`

### Unused Metrics Tables (DELETE after verification)
- Files:
  - `backend/migrations/create_metrics_tables.sql` creates `session_analytics`, `page_views`, `daily_metrics`, `user_profiles` (includes Stripe fields)
- Why (evidence): Runtime code does not query these tables (`rg -n "session_analytics|page_views|daily_metrics|user_profiles" backend` only hits migrations). Stripe fields are out-of-scope.
- Replacement: Use `metrics` and `user_events` in `backend/modules/metrics_collector.py` and `backend/routers/metrics.py`.
- Verify unused before delete:
  - `rg -n "session_analytics|page_views|daily_metrics|user_profiles" backend` returns only migration files.

## Category 3: Legacy Experiments / Unused Flags / Abandoned Integrations

### Debug Retrieval Router (DEFER then DELETE)
- Files: `backend/routers/debug_retrieval.py` (prefix `/debug`) registered in `backend/main.py`.
- Why (evidence): Debug-only. No frontend references found.
- Replacement: Keep a private internal script in `backend/scripts/` instead of a public route.
- Verify unused before delete: `rg -n "debug/retrieval" frontend` should return none.

### YouTube Preflight Router (DEFER then DELETE if unused)
- Files: `backend/routers/youtube_preflight.py` (prefix `/youtube`) registered in `backend/main.py`.
- Why (evidence): No frontend reference found; ingestion uses direct `/ingest/youtube` in `backend/routers/ingestion.py`.
- Replacement: None.
- Verify unused before delete: `rg -n "youtube/preflight" frontend` returns none.

### Feedback Router (DEFER then DELETE if unused)
- Files: `backend/routers/feedback.py` (routes `/feedback/{trace_id}` and `/feedback/reasons`) registered in `backend/main.py`.
- Why (evidence): Frontend submits feedback to `/api/feedback/...` via Next API (`frontend/components/FeedbackWidget.tsx`), not backend route.
- Replacement: Either keep Next API or move to backend and update frontend explicitly.
- Verify unused before delete: `rg -n "feedback" frontend` and confirm no calls to backend `/feedback`.

### Langfuse / External Tracing (DEFER)
- Files: `backend/modules/langfuse_client.py`, `langfuse` usage in `backend/routers/chat.py` and `backend/modules/_core/scribe_engine.py`.
- Why (evidence): Optional integration; keep if used for ops, otherwise remove to simplify dependencies.
- Replacement: Retain basic correlation ID logging in `backend/main.py`.
- Verify unused before delete: `rg -n "langfuse" backend` and ensure env vars are not required.

## Category 4: Over-Engineered Workflows To Simplify

### Graph Extraction + Cognitive Graph (DEFER then DELETE)
- Files:
  - `backend/modules/_core/scribe_engine.py` (graph extraction jobs)
  - `backend/modules/graph_context.py`, `backend/routers/graph.py`
  - `backend/database/migrations/migration_phase3_5_gate3_graph.sql` (nodes/edges)
  - `backend/database/migrations/migration_memory_events.sql` and `migration_owner_memory.sql` (memory events used by scribe)
- Why (evidence): Graph is not in scope for the simplified product. Chat currently references graph stats and enqueues graph jobs in `backend/routers/chat.py`.
- Replacement: Remove graph stats and job enqueue from chat; keep owner memory + clarifications (from `migration_owner_memory.sql`) only.
- Verify unused before delete:
  - `rg -n "graph_context|scribe_engine|nodes|edges" backend frontend`
  - Ensure `backend/routers/graph.py` is not registered in `backend/main.py`.

### TIL / Memory Events Feed (DEFER then DELETE if not needed)
- Files: `backend/routers/til.py`, `backend/modules/memory_events.py`, `backend/database/migrations/migration_memory_events.sql`.
- Why (evidence): UI exists (`frontend/components/TILFeed.tsx`) but TIL is not part of the new product scope.
- Replacement: Use analytics endpoints in `backend/routers/metrics.py` for ops visibility.
- Verify unused before delete: `rg -n "til|memory-events" frontend backend`.

### Owner Memory Clarification Auto-Workflow (SIMPLIFY, NOT DELETE)
- Files: `backend/modules/identity_gate.py`, `backend/modules/owner_memory_store.py`, `backend/routers/owner_memory.py`, tables in `backend/database/migrations/migration_owner_memory.sql`.
- Why (evidence): In-scope for identity and boundaries, but current flow is complex. Keep but simplify UI and reduce modes (owner vs public) if needed.
- Replacement: None; just a minimal, auditable boundary system.
- Verify unchanged functionality: Unit tests around `run_identity_gate` and `owner_memory` endpoints.
