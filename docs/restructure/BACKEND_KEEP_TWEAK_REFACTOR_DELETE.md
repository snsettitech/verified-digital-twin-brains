# Backend Keep / Tweak / Refactor / Delete Mapping

## Buckets
- Keep as is: Works for the new product without change.
- Keep with small tweaks: Minor wiring or cleanup to fit the new scope.
- Refactor: Needs structural change to simplify or unify.
- Delete or defer: Out-of-scope for web-only clone-for-experts.

## Mapping Table (Subsystems + Routes)
| Subsystem | Bucket | Evidence (Files / Routes) | Notes |
| --- | --- | --- | --- |
| Auth + tenant identity | Keep with small tweaks | `backend/modules/auth_guard.py`, routes in `backend/routers/auth.py` | Keep tenant resolution and JWT auth. Add missing invitation accept endpoints (see `frontend/app/auth/accept-invitation/[token]/page.tsx`). |
| Core chat + retrieval | Keep as is | `backend/routers/chat.py`, `backend/modules/agent.py`, `backend/modules/retrieval.py` | Required for core web chat. Maintain SSE streaming and retrieval order (verified QnA -> vector). |
| Ingestion + auto-indexed workflow | Keep with small tweaks | `backend/routers/ingestion.py`, `backend/modules/ingestion.py`, `backend/modules/training_jobs.py` | Preserve ingestion + indexing as auto-indexed; remove any manual approval gating and keep ingestion always indexing. |
| Sources ops (no manual approval) | Keep with small tweaks | `backend/routers/sources.py` | Needed for studio build flow; keep list, delete, logs, and re-extract without approval steps. |
| Knowledge profile & verified QnA | Keep with small tweaks | `backend/routers/knowledge.py`, `backend/modules/verified_qna.py` | Add missing create endpoint for `/twins/{twin_id}/verified-qna` used in `frontend/app/onboarding/page.tsx`. |
| Share links + public chat | Keep with small tweaks | `backend/modules/share_links.py`, routes in `backend/routers/auth.py` and `backend/routers/chat.py` | Needed for launch flow. Ensure share-link validation stays. |
| Embed widget API keys | Refactor | `backend/modules/api_keys.py` + routes in `backend/routers/auth.py` vs `backend/routers/api_keys.py` | Two API key systems overlap; pick one model and unify. Widget expects `api_key` in `frontend/public/widget.js`. |
| Access groups / roles | Keep with small tweaks | `backend/modules/access_groups.py`, access-group routes in `backend/routers/twins.py` | Needed for simple role/boundary support. Remove unused knobs if desired (limits/overrides). |
| Training jobs + background worker | Refactor | `backend/modules/training_jobs.py`, `backend/modules/job_queue.py`, `backend/worker.py`, `/training-jobs` routes | Consolidate with `jobs` system for stable async status. |
| Generic jobs + job logs | Refactor | `backend/modules/jobs.py`, `backend/routers/jobs.py`, `backend/modules/_core/scribe_engine.py` | Uses `jobs` table (see `backend/migrations/create_jobs_tables.sql`) while ingestion uses `training_jobs`. Unify. |
| Metrics & analytics | Refactor | `backend/routers/metrics.py`, `backend/modules/metrics_collector.py` | Tables exist in `backend/migrations/*` but not in `backend/database/migrations/*`; unify migrations. |
| Audit logs | Keep with small tweaks | `backend/modules/governance.py`, `backend/routers/governance.py` | Keep tenant-scoped audit logs but drop governance policy features if out-of-scope. Fix schema if `audit_logs.twin_id` is NOT NULL (see `backend/database/migrations/migration_phase9_governance.sql`). |
| Observability health | Keep with small tweaks | `backend/routers/observability.py`, `backend/main.py` middleware | Keep health endpoints and correlation IDs. |
| Rate limiting + sessions | Keep with small tweaks | `backend/modules/rate_limiting.py`, `backend/modules/sessions.py`, `backend/database/migrations/migration_phase7_omnichannel.sql` | Needed for widget/public chat. |
| Verification / quality tests | Keep with small tweaks | `backend/routers/verify.py` | Required for studio quality checks. Ensure table name matches migration (`twin_verification` vs `twin_verifications`). |
| Graph / cognitive model | Refactor or defer | `backend/routers/graph.py`, `backend/modules/graph_context.py`, `backend/modules/_core/scribe_engine.py` | Currently used for graph stats and chat metadata. Decide whether to keep minimal graph stats or remove full cognitive flows. |
| Cognitive interview flow | Delete or defer | `backend/routers/cognitive.py`, `backend/modules/_core/*`, `backend/database/migrations/migration_gate5_versioning.sql` | Not required for web-only clone-for-experts. Frontend uses it (`frontend/components/Chat/InterviewInterface.tsx`). Remove if UI removed. |
| Interview (Realtime voice) | Delete or defer | `backend/routers/interview.py`, `backend/modules/zep_memory.py`, `backend/modules/memory_extractor.py` | Out-of-scope (voice). Requires external services (Neo4j/Graphiti). |
| Actions engine + connectors | Delete or defer | `backend/routers/actions.py`, `backend/modules/actions_engine.py`, `backend/database/migrations/migration_phase8_actions_engine.sql` | Out-of-scope per requirement. Frontend currently calls these routes. |
| Escalations + safety | Delete or defer | `backend/routers/escalations.py`, `backend/modules/escalation.py`, `backend/modules/safety.py` | Explicitly out-of-scope (no special safety/escalation). |
| Enhanced ingestion (crawl, RSS, social, pipelines) | Delete or defer | `backend/routers/enhanced_ingestion.py`, `backend/modules/web_crawler.py`, `backend/modules/social_ingestion.py`, `backend/modules/auto_updater.py` | Adds Firecrawl/Twitter/LinkedIn complexity. Only enabled with `ENABLE_ENHANCED_INGESTION` in `backend/main.py`. |
| Audio TTS | Delete or defer | `backend/routers/audio.py`, `backend/modules/audio_generator.py` | Out-of-scope (web chat only). |
| Reasoning engine | Delete or defer | `backend/routers/reasoning.py`, `backend/modules/reasoning_engine.py` | Out-of-scope. |
| Specializations + VC | Delete or defer | `backend/routers/specializations.py`, `backend/api/vc_routes.py`, `backend/modules/specializations/*` | New product is general clone-for-experts; no VC specialization. |
| External tool connectors / web search | Delete or defer | `backend/modules/tools.py` | Composio + web search are platform-level features, out-of-scope. |
