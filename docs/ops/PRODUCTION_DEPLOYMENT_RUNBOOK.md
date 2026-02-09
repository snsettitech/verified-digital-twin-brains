# Production Deployment Runbook

Last updated: 2026-02-09

## 1) Current live topology (from MCP inventory)

### Backend / worker (Render)
- Workspace: `tea-d55pn0fgi27c73doeodg` (`digitalbrains`)
- API service: `srv-d55qmb95pdvs73cagk60`
  - URL: `https://verified-digital-twin-brains.onrender.com`
  - RootDir: `backend`
  - Runtime: Python
- Worker service: `srv-d5ht2763jp1c73evn1dg`
  - RootDir: `backend`
  - Runtime: Python
- Redis (Render Key Value): `red-d621ercoud1c7397mstg` (`digitalbrains_redis`)

### Frontend (Vercel)
- Team: `team_089B927pMqpQwivzqc1Hzr4f`
- Project: `prj_tye8zjjKLvhdjH2pyBXno8JaylYk` (`verified-digital-twin-brains`)
- Latest prod deployment: `dpl_8m2hVKqHYtjVFwY1ibz5X9JoxoLL`
- Active aliases include: `digitalbrains.vercel.app`

### Data plane
- Supabase project: `jvtffdbuwyhmcynauety` (`verified-digital-twin-brain`) - healthy
- Pinecone index: `digital-twin-brain` - ready
- Migration state includes:
  - `phase7_feedback_learning_loop`
  - `add_feedback_learning_job_type`

## 2) Deployment strategy (recommended + fallbacks)

### Primary (recommended): Git-backed rolling deploy
1. Commit scoped release to `main`.
2. Render auto-deploys API + worker from `main`.
3. Vercel auto-deploys frontend production from `main`.
4. Run production smoke + rollback gate.

Why: your infra is already live and configured for Git auto-deploy.

### Fallback A: Blue/green canary on Render
1. Create clone services on Render from a release branch.
2. Validate canary URL and worker behavior.
3. Promote by merging same commit to `main`.

### Fallback B: Vercel claimable preview (emergency frontend)
1. Use `scripts/deploy.sh frontend` or Vercel deploy workflow for preview.
2. Validate frontend against current backend.
3. Promote with normal Git production deploy.

## 3) Pre-deploy hardening (must pass before cutover)

### Code and test gates
1. Backend targeted persona gates:
   - `python -m pytest backend/tests/test_feedback_router.py backend/tests/test_persona_feedback_learning_jobs.py backend/tests/test_persona_feedback_learning.py backend/tests/test_persona_specs_router.py -q`
2. Full backend gate:
   - `python -m pytest -q`
3. Frontend gate:
   - `npm --prefix frontend run typecheck`
4. E2E gate (at least critical flows):
   - `cmd /c npx playwright test tests/e2e/persona_training_loop.spec.ts tests/e2e/persona_channel_separation.spec.ts`
5. Persona regression gate:
   - `python backend/eval/persona_regression_runner.py --dataset backend/eval/persona_regression_dataset.json --output docs/ai/improvements/proof_outputs/prod_gate_persona_regression.json --min-pass-rate 0.95 --min-adversarial-pass-rate 0.95 --min-channel-isolation-pass-rate 1.0`

### Config hardening (required)
1. Render `ALLOWED_ORIGINS` must not be `*` in production.
   - Set explicit frontend origins only (example below).
2. Ensure `REDIS_URL` is set for both API + worker.
3. Ensure feedback-learning env knobs are set:
   - `FEEDBACK_LEARNING_MIN_EVENTS`
   - `FEEDBACK_LEARNING_COOLDOWN_MINUTES`
   - `FEEDBACK_LEARNING_AUTO_PUBLISH`
   - `FEEDBACK_LEARNING_RUN_REGRESSION_GATE`
4. Vercel Node version must match app engine target.
   - Frontend declares Node `20.x`; align Vercel project runtime to `20.x`.

## 4) Production env baseline

### Render API + worker required env
Core:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` (or `SUPABASE_KEY`)
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- `JWT_SECRET`
- `ALLOWED_ORIGINS` (explicit list, comma-separated)
- `DEV_MODE=false`
- `REDIS_URL`

Feature/perf:
- `GRAPH_RAG_ENABLED=true`
- `CONTENT_EXTRACT_MAX_CHUNKS=6`
- `ENABLE_ENHANCED_INGESTION` (true/false as intended)
- `ENABLE_VC_ROUTES=false` (unless actively used)

Feedback learning:
- `FEEDBACK_LEARNING_MIN_EVENTS=5` (or your chosen threshold)
- `FEEDBACK_LEARNING_COOLDOWN_MINUTES=30`
- `FEEDBACK_LEARNING_AUTO_PUBLISH=false`
- `FEEDBACK_LEARNING_RUN_REGRESSION_GATE=true`

YouTube pipeline (if used):
- `GOOGLE_API_KEY`
- `YOUTUBE_COOKIES_FILE`
- `YOUTUBE_PROXY`
- `YOUTUBE_MAX_RETRIES=5`
- `YOUTUBE_ASR_MODEL=whisper-large-v3`
- `YOUTUBE_ASR_PROVIDER=openai`
- `YOUTUBE_LANGUAGE_DETECTION=true`
- `YOUTUBE_PII_SCRUB=true`
- `YOUTUBE_VERBOSE_LOGGING=false`

### Vercel required env
- `NEXT_PUBLIC_BACKEND_URL=https://verified-digital-twin-brains.onrender.com`
- `NEXT_PUBLIC_SUPABASE_URL=https://jvtffdbuwyhmcynauety.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>`
- `NEXT_PUBLIC_FRONTEND_URL=https://digitalbrains.vercel.app`
- `NEXT_PUBLIC_E2E_BYPASS_AUTH` unset (or `0`) in production

## 5) Step-by-step release execution

### Step A - Freeze and package release
1. Create release branch from clean `main`.
2. Split into deploy-safe commits:
   - backend+schema
   - frontend
   - docs/proof
3. Tag candidate: `release-YYYYMMDD-HHMM`.

### Step B - Apply schema migrations first
1. Apply all pending migrations to Supabase (already includes latest feedback-learning migrations).
2. Verify migration list contains expected versions.
3. Run RLS sanity checks for tenant/twin scoped tables.

### Step C - Update production env
1. Update Render API env vars.
2. Update Render worker env vars.
3. Update Vercel project env vars.
4. Redeploy services (or push commit to trigger auto-deploy).

### Step D - Deploy backend and worker (Render)
1. Merge release commit to `main`.
2. Verify newest deploys:
   - API service `srv-d55qmb95pdvs73cagk60` status `live`
   - Worker service `srv-d5ht2763jp1c73evn1dg` status `live`
3. Run API smoke checks:
   - `GET /health` must return healthy
   - auth + chat + feedback endpoints basic checks

### Step E - Deploy frontend (Vercel)
1. Confirm production deployment for project `prj_tye8zjjKLvhdjH2pyBXno8JaylYk` is `READY`.
2. Confirm aliases include `digitalbrains.vercel.app`.
3. Verify frontend can call backend without CORS failure.

### Step F - Run post-deploy validation
1. Owner flow:
   - login -> dashboard -> training tab -> simulator
2. Public share flow:
   - share URL chat works
   - no training writes from public context
3. Feedback-learning smoke:
   - submit feedback
   - verify event is stored
   - verify job enqueue/processing path
4. Regression:
   - run persona regression runner against production-like config

## 6) Scheduling and background automation

### Feedback-learning scheduler (recommended)
Use one of:
1. Render Cron Job (preferred):
   - command:
     - `python backend/scripts/run_feedback_learning_scheduler.py --once --min-events 5 --limit-twins 100`
   - schedule:
     - every 15 minutes: `*/15 * * * *`
2. Continuous worker sidecar:
   - `python backend/scripts/run_feedback_learning_scheduler.py --interval-seconds 900 --min-events 5 --limit-twins 100`

Keep `auto_publish` disabled until your quality gate is stable in production.

## 7) Rollback playbook (fast)

### Backend rollback
1. In Render, promote previous `live` deploy for API + worker.
2. If needed, set emergency env:
   - `FEEDBACK_LEARNING_RUN_REGRESSION_GATE=false`
   - disable scheduler cron temporarily.

### Frontend rollback
1. In Vercel, rollback to previous production deployment.
2. Keep backend stable while frontend rollback propagates.

### Data rollback
1. Avoid destructive down-migrations during hot incident.
2. Prefer feature-flag rollback first.
3. If schema rollback is required, use explicit corrective migration.

## 8) Production go/no-go criteria

Release is `GO` only if all pass:
1. Render API + worker deploy status `live`.
2. Vercel production deploy `READY` and aliased.
3. `/health` healthy from public network.
4. Persona regression gate passes thresholds.
5. Feedback event -> learning job path works.
6. No P0/P1 errors in logs for 30 minutes post-deploy.

If any criterion fails -> `NO-GO` and rollback immediately.

## 9) MCP execution sequence (operator checklist)

1. Render workspace/services:
   - `get_selected_workspace`
   - `list_services`
2. Supabase migration verification:
   - `list_migrations`
3. Render deploy verification:
   - `list_deploys` for API + worker
   - `list_logs` (type `app`, level `error`)
   - `get_metrics` (`cpu_usage`, `memory_usage`, `http_request_count`)
4. Vercel deploy verification:
   - `get_project`
   - `list_deployments`
   - `get_deployment` (latest production)
5. Post-deploy smoke:
   - frontend + backend endpoint checks
   - feedback-learning end-to-end test.

