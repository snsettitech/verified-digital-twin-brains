# Runtime Entrypoints

## Backend Startup Path

1. `render.yaml` starts the API with:
   `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 120`
2. `backend/main.py`:
   - validates required env on import
   - constructs the FastAPI app and lifespan hooks
   - applies dynamic CORS middleware
   - registers all active routers
   - exposes `/health`, `/health/deep`, `/startup`, `/docs`
3. Feature flags are read in `backend/main.py` for:
   - enhanced ingestion
   - VC routes
   - deep research
   - name-only deep research gating

### Registered Backend Route Groups

- Core: `auth`, `chat`, `twins`, `training_sessions`, `persona_specs`, `twin_runtime`
- Ingestion/retrieval: `ingestion`, `youtube_preflight`, `knowledge`, `sources`, `debug_retrieval`, `retrieval_delphi`
- Governance/workflow: `actions`, `governance`, `escalations`, `access_groups_compat`, `api_keys`, `jobs`
- Research/profile: `crawl`, `research_claims`, `deep_research`, `profile`, `profile_person_data`, `profile_public`
- Admin/observability: `dashboard`, `trace_compare`, `prompt_playground`, `ab_testing`, `cost_tracking`, `synthetic_monitoring`, `alerts`, `langfuse_metrics`, `dataset_export`, `regression_testing`

## Worker Startup Path

1. `render.yaml` starts the worker with:
   `cd backend && python worker.py`
2. `backend/worker.py`:
   - loads env from `.env`
   - validates worker-specific env
   - polls Redis or DB-backed queues
   - processes content extraction, graph extraction, graph outbox, and feedback learning jobs

## Frontend Startup Path

1. `frontend/package.json` provides the active scripts:
   - `npm run dev`
   - `npm run build`
   - `npm run start`
   - `npm run lint`
   - `npm run typecheck`
   - `npm run test:e2e:prod-canary`
   - `npm run enforce:ui:single`
   - `npm run enforce:ui:strict`
2. `frontend/proxy.ts` is the current auth/session gate.
3. `frontend/app/dashboard/layout.tsx` composes:
   - `ThemeProvider`
   - `TwinProvider`
   - `ProfileProvider`
   - `ToastProvider`
4. Frontend route families:
   - `/auth/*`
   - `/dashboard/*`
   - `/onboarding`
   - `/share/[twin_id]/[token?]`
   - `/admin`

## Automation-Wired Commands

### Deployment

- `render.yaml`
- `frontend/vercel.json`

### CI Workflows

- Backend: `pip install -r backend/requirements.txt`, `flake8`, `pytest -v --tb=short -m "not network"`
- Frontend: `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build`
- Persona regression: `python backend/eval/persona_regression_runner.py ...`
- Prod research canary: `playwright test frontend/tests/e2e/prod_research_canary.spec.ts`

### Repo Helpers

- `scripts/dev.ps1`
- `scripts/dev.sh`
- `scripts/preflight.ps1`
- `scripts/preflight.sh`
- `scripts/validate_before_commit.sh`

## Not Wired Into Automation

- `backend/scripts/*` one-offs
- `backend/verify_*.py` and quick-check scripts in `backend/`
- most `frontend/scripts/*.mjs` probe scripts
- `tools/manual_verify/*`

These are legitimate candidates for archive or further consolidation, but they were not deleted without stronger evidence.
