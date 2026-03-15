# Repo Map

Generated: 2026-03-10

## Top Level

| Path | Purpose | Runtime critical | Notes |
| --- | --- | --- | --- |
| `backend/` | FastAPI API, worker, database migrations, tests, eval harnesses | Yes | Main backend runtime surface. |
| `frontend/` | Next.js 16 app, dashboard routes, public share UI, Playwright tests | Yes | `app/` and `proxy.ts` are the key entry surfaces. |
| `docs/` | Canonical architecture, ops, AI docs, plus archive | No | `docs/archive/` now holds historical reports and proof packs. |
| `.github/` | GitHub Actions workflows and PR process templates | No | CI/CD and hygiene guardrails. |
| `scripts/` | Repo-level helper scripts | No | Mixed quality: some current helpers, some legacy/manual utilities. |
| `tools/manual_verify/` | Manual verification scripts and proof helpers | No | Preferred home for non-runtime test/probe utilities. |
| `tests/` | Thin root-level test wrappers | No | Most real tests live under `backend/tests/` and `frontend/tests/`. |
| `.agent/` | Agent workflow docs and MCP examples | No | `.agent/mcp.json` is now local-only; `.agent/mcp.example.json` is the tracked template. |
| `context/` | Context-pack templates for AI workflows | No | Referenced by `scripts/context_pack.py` and context playbooks. |
| `render.yaml` | Render deployment blueprint for API + worker | Yes | Canonical deployment entrypoint. |
| `pytest.ini` | Python test configuration | No | Shared pytest defaults. |

## Backend Map

| Area | Role | Notes |
| --- | --- | --- |
| `backend/main.py` | FastAPI app bootstrap | Validates required env, builds CORS, registers routers, exposes health endpoints. |
| `backend/worker.py` | Background worker bootstrap | Validates env, processes Redis/DB-backed jobs, graph outbox, feedback learning. |
| `backend/routers/` | API route modules | Main runtime API surface. Registration lives in `backend/main.py`. |
| `backend/modules/` | Business logic and adapters | Core app behavior. Some files are active runtime, some are evaluation or legacy utilities. |
| `backend/database/` | Migrations and schema references | Runtime-adjacent; migration safety matters. |
| `backend/tests/` | Backend unit/integration tests | Primary Python test suite. |
| `backend/eval/` | Persona/evaluation runners | CI uses persona regression tooling here. |
| `backend/scripts/` | One-off backend utilities | Large manual-maintenance cluster; good review target, not blindly deleted. |

## Frontend Map

| Area | Role | Notes |
| --- | --- | --- |
| `frontend/app/` | App Router routes | Main frontend runtime surface. |
| `frontend/proxy.ts` | Request/session gate | Current auth redirect layer; replaces the stale `frontend/middleware.ts` guidance. |
| `frontend/components/` | Shared UI components | Cleanup removed a small set of unreferenced components. |
| `frontend/lib/` | API helpers, auth, context, feature flags, shared types | Core frontend support code. |
| `frontend/contexts/` | Additional React contexts | Thin area; one unused barrel file removed. |
| `frontend/tests/e2e/` | Playwright E2E specs | Current E2E suite. |
| `frontend/scripts/` | Frontend probe/enforcement scripts | `enforce-single-twin.js` is wired; several probe scripts remain manual-only. |

## Docs Map

| Area | Role | Notes |
| --- | --- | --- |
| `docs/quick-start.md` | High-level setup index | Now points to the canonical runbook and entrypoint map. |
| `docs/architecture/` | Architecture references | System overview, API contracts, security model. |
| `docs/ops/` | Operational runbooks | Deployment, queue, auth, troubleshooting. |
| `docs/ai/` | Agent-facing manuals | AI workflow/operator guidance. |
| `docs/archive/` | Historical plans, proof packs, implementation summaries | Non-canonical by default. |

## Key Runtime Entrypoints

- Backend API: `backend/main.py`
- Background worker: `backend/worker.py`
- Frontend app shell: `frontend/app/layout.tsx`
- Frontend auth/session gate: `frontend/proxy.ts`
- Dashboard provider composition: `frontend/app/dashboard/layout.tsx`
- Deployment config: `render.yaml`

## Likely Dead or Unclear Areas

- `backend/scripts/`: many one-off maintenance scripts have no workflow/package/deploy wiring.
- `backend/modules/`: several evaluation/legacy modules have zero reverse references in repo code and need human review before deletion.
- `frontend/scripts/`: manual probe scripts remain mixed into app-side tooling.
- `context/`: useful, but only for AI workflow docs and context-pack generation.
- `.agent/`: valuable for internal workflows, but local MCP credentials must stay untracked.
