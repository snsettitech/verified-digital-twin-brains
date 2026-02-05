# Backend Data Model Plan (Plan Only)

## Current Storage And Access Pattern
- Postgres/Supabase accessed via service role in `backend/modules/observability.py` (Supabase client).
- No ORM; raw Supabase table calls are used across routers and modules (e.g., `backend/routers/chat.py`, `backend/modules/ingestion.py`).

## Migration Sources (Two Directories)
- Primary migrations: `backend/database/migrations/*` (phase migrations 3.5-11).
- Secondary migrations: `backend/migrations/*` (jobs + metrics + RLS).
- Consolidation required to avoid drift and missing tables (runtime uses tables defined only in `backend/migrations/*`, e.g., `metrics`, `jobs`, `usage_quotas`).

## Table Inventory (Current)

### Core Tenancy
- `tenants`, `twins`, `users` from `backend/database/schema/supabase_schema.sql`.
- Tenant scoping enforced in `backend/modules/auth_guard.py`.

### Knowledge + Ingestion
- `sources`, `chunks` from `backend/database/schema/supabase_schema.sql`.
- Phase 6 additions: `training_jobs`, `ingestion_logs`, `content_health_checks` from `backend/database/migrations/migration_phase6_mind_ops.sql`.

### Conversations
- `conversations`, `messages` from `backend/database/schema/supabase_schema.sql`.
- Session linkage in `backend/database/migrations/migration_phase7_omnichannel.sql` (`conversations.session_id`).

### Verified Knowledge
- `verified_qna`, `answer_patches`, `citations` from `backend/database/schema/supabase_schema.sql` and `backend/database/migrations/migration_phase4_verified_qna.sql`.
- Embeddings stored in `verified_qna.question_embedding` as JSON in `backend/modules/verified_qna.py`.

### Access Groups / Roles
- `access_groups`, `group_memberships`, `content_permissions`, `group_limits`, `group_overrides` from `backend/database/migrations/migration_phase5_access_groups.sql`.

### Sessions + Rate Limiting + Invitations
- `twin_api_keys`, `sessions`, `rate_limit_tracking`, `user_invitations` from `backend/database/migrations/migration_phase7_omnichannel.sql`.
- Tenant API keys from `backend/database/migrations/migration_scope_enforcement.sql` (`tenant_api_keys`).

### Governance + Audit
- `audit_logs`, `governance_policies`, `twin_verification` from `backend/database/migrations/migration_phase9_governance.sql`.
- Tenant scoping updates in `backend/database/migrations/migration_scope_enforcement.sql` and `migration_v2_scope_hardening.sql`.

### Metrics + Quotas
- `metrics`, `usage_quotas`, `service_health_logs` from `backend/migrations/phase10_metrics.sql`.
- `user_events`, `session_analytics`, `page_views`, `daily_metrics`, `user_profiles` from `backend/migrations/create_metrics_tables.sql`.

### Graph + Memory
- `nodes`, `edges` from `backend/database/migrations/migration_phase3_5_gate3_graph.sql`.
- `memory_events` from `backend/database/migrations/migration_memory_events.sql`.
- `owner_beliefs`, `clarification_threads` from `backend/database/migrations/migration_owner_memory.sql`.

### Jobs
- `jobs`, `job_logs` from `backend/migrations/create_jobs_tables.sql`.
- `training_jobs` from `backend/database/migrations/migration_phase6_mind_ops.sql`.

### Interviews + Voice
- `interview_sessions` from `backend/database/migrations/interview_sessions.sql` and `migration_interview_sessions.sql`.
- Interview quality table in `backend/database/migrations/migration_interview_session_quality.sql`.

## Vector Database Usage
- Pinecone index in `backend/modules/clients.py`.
- Namespace convention: `namespace=twin_id` when upserting vectors in `backend/modules/ingestion.py`.
- `chunks.vector_id` stores Pinecone vector IDs (`backend/database/schema/supabase_schema.sql`).
- Verified QnA embeddings are stored in Postgres JSON (`backend/modules/verified_qna.py`), not Pinecone.

## Proposed Data Model Changes

### 1) Consolidate Migrations Into One Source Of Truth
- Target: `backend/database/migrations/*` as canonical.
- Move or reapply `backend/migrations/create_jobs_tables.sql` and `backend/migrations/phase10_metrics.sql` into the primary migration chain.
- Update `backend/database/schema/supabase_schema.sql` comment block to include the new canonical ordering.

### 2) Unify API Keys (Tenant-Scoped)
- Canonical table: `tenant_api_keys` from `backend/database/migrations/migration_scope_enforcement.sql`.
- Deprecate `twin_api_keys` from `backend/database/migrations/migration_phase7_omnichannel.sql` after data migration.
- Migration plan:
  - Add a migration to copy `twin_api_keys` into `tenant_api_keys` (map twin -> tenant via `twins.tenant_id`).
  - Update widget auth in `backend/routers/chat.py` to use tenant keys with `allowed_twin_ids`.
  - Drop `twin_api_keys` after a release window.

### 3) Unify Jobs Model
- Canonical tables: `jobs` and `job_logs` from `backend/migrations/create_jobs_tables.sql`.
- Extend `jobs.job_type` to include `graph_extraction`, `ingestion`, `health_check`, `reindex` (current constraint in `create_jobs_tables.sql` is missing `graph_extraction`).
- Migrate `training_jobs` data into `jobs` and remove `training_jobs` table after refactor.
- Update `backend/routers/ingestion.py`, `backend/modules/training_jobs.py`, and `backend/worker.py` to use unified jobs.

### 4) Fix Twin Verification Table Mismatch
- Canonical table: `twin_verification` from `backend/database/migrations/migration_phase9_governance.sql`.
- Update `backend/routers/verify.py` and `backend/routers/twins.py` to use `twin_verification` (singular).
- Optional: add a view `twin_verifications` for backward compatibility during migration.

### 5) Remove Out-Of-Scope Tables
- Drop tables only after routes and code are removed:
  - `events`, `tool_connectors`, `action_triggers`, `action_drafts`, `action_executions` (actions engine).
  - `escalations`, `escalation_replies` (escalation flow).
  - `nodes`, `edges`, `memory_events` (graph if fully removed).
  - `interview_sessions` and interview quality tables.
  - `session_analytics`, `page_views`, `daily_metrics`, `user_profiles` (unused; contains Stripe fields).

### 6) Specialization Columns Cleanup
- Decide on one of:
  - Remove `specialization` and `specialization_id` entirely (single expert product).
  - Keep one field in `twins.settings` (JSONB) and drop both columns.
- Update `backend/routers/twins.py` and `backend/routers/specializations.py` accordingly.

### 7) Metrics And Analytics Alignment
- Keep `metrics`, `service_health_logs`, `user_events` for basic analytics.
- Keep `usage_quotas` only if used for rate limiting; remove if solely for billing/entitlements.
- Ensure `backend/modules/metrics_collector.py` remains the canonical writer.

## RLS And Tenancy Checks
- RLS enablement script in `backend/migrations/enable_rls_all_tables.sql`.
- Phase hardening in `backend/database/migrations/migration_v2_scope_hardening.sql`.
- Verify that all new/retained tables include tenant-safe policies or are accessed only via service role in `backend/modules/observability.py`.

## Rollback Strategy (For Each Migration)
- Every structural migration should include a rollback SQL stub that:
  - Restores old columns/tables where possible.
  - Preserves data with shadow tables if destructive changes are required.
  - Keeps the system in a readable state for API compatibility.
