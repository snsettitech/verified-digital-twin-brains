# Backend PR Execution Plan (Deletion-First)

## Guardrails
- Each PR keeps `main` releasable.
- Remove UI entry points before backend router deletion.
- Ingestion + retrieval must remain functional after every PR.

## PR 0: Auto-Indexed Ingestion Baseline (No Approval)
- Goal: Make ingestion always index immediately and remove manual approval surfaces.
- Files:
  - `backend/modules/ingestion.py`, `backend/routers/ingestion.py`, `backend/routers/sources.py`.
  - Remove `/sources/{source_id}/approve`, `/sources/{source_id}/reject`, `/sources/bulk-approve`.
- Verification:
  - Ingest a file and ensure status transitions `processing -> live` with chunks indexed.

## PR 1: Delete Actions Engine (Backend Wiring)
- Goal: Remove action triggers and action draft workflows after UI removal.
- Files:
  - `backend/routers/actions.py`, `backend/modules/actions_engine.py`.
  - Remove router registration from `backend/main.py`.
- Verification:
  - `rg -n "actions_engine" backend` returns only archived refs.

## PR 2: Delete Escalations + Safety
- Goal: Eliminate escalation workflow and safety layer.
- Files:
  - `backend/routers/escalations.py`, `backend/modules/escalation.py`, `backend/modules/safety.py`.
  - Remove escalation references in metrics.
- Verification:
  - Metrics endpoints still respond; ingest + chat smoke test.

## PR 3: Delete Cognitive / Interview / Reasoning / Audio
- Goal: Remove voice and cognitive interview surface area.
- Files:
  - `backend/routers/cognitive.py`, `backend/routers/interview.py`, `backend/routers/reasoning.py`, `backend/routers/audio.py`.
  - Remove any chat branches tied to reasoning.
- Verification:
  - Core chat, share, and ingestion endpoints still operate.

## PR 4: Delete Enhanced Ingestion + External Tooling
- Goal: Keep only baseline ingestion.
- Files:
  - `backend/routers/enhanced_ingestion.py`, `backend/modules/web_crawler.py`, `backend/modules/social_ingestion.py`, `backend/modules/auto_updater.py`.
- Verification:
  - `/ingest/file`, `/ingest/url`, `/ingest/youtube` still function.

## PR 5: Delete Specializations + VC Routes
- Goal: Remove VC-specific and specialization-only surfaces.
- Files:
  - `backend/routers/specializations.py`, `backend/api/vc_routes.py`, `backend/modules/specializations/*`.
- Verification:
  - `GET /twins/{twin_id}` unaffected; chat retrieval still works.

## PR 6: Unify Jobs Model (Refactor After Deletions)
- Goal: Replace `training_jobs` with `jobs` + `job_logs`.
- Files:
  - `backend/modules/training_jobs.py`, `backend/modules/jobs.py`, `backend/routers/ingestion.py`, `backend/worker.py`.
- Verification:
  - Job lifecycle test + ingestion status endpoint test.

## PR 7: API Key Unification (Tenant-Scoped)
- Goal: Single API key model for widget + embed.
- Files:
  - `backend/routers/chat.py`, `backend/routers/api_keys.py`, migration for backfill.
- Verification:
  - Widget auth integration test and manual widget validation.

## PR 8: Analytics + Audience
- Goal: Minimal enterprise analytics.
- Files:
  - Add `GET /audience/{twin_id}` and ensure `metrics_collector` is canonical writer.
- Verification:
  - Integration tests + smoke test in Operate flow.

## PR 9: Migrations Cleanup
- Goal: Drop unused tables after deletions and consolidate migrations.
- Files:
  - `backend/database/migrations/*` cleanup and drop tables for removed features.
- Verification:
  - Run migrations in staging and re-run tenant/RLS tests.
