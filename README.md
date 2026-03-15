# Verified Digital Twin Brains

Enterprise AI platform for building auditable digital twins with tenant isolation, governed knowledge ingestion, retrieval, and agentic workflows.

## Canonical Docs

- [DEBUG_RUNBOOK.md](DEBUG_RUNBOOK.md): fastest path to run the stack locally and smoke-test it.
- [REPO_MAP.md](REPO_MAP.md): top-level repo layout, runtime surfaces, and cleanup notes.
- [RUNTIME_ENTRYPOINTS.md](RUNTIME_ENTRYPOINTS.md): actual startup paths, route groups, automation entrypoints.
- [docs/quick-start.md](docs/quick-start.md): short setup overview and canonical doc index.
- [docs/architecture/system-overview.md](docs/architecture/system-overview.md): architecture reference.
- [docs/architecture/api_contracts.md](docs/architecture/api_contracts.md): API contract reference.
- [docs/ai/agent-manual.md](docs/ai/agent-manual.md): AI-agent operating guidance.

## Runtime

- Backend API: `backend/main.py`
- Worker: `backend/worker.py`
- Frontend app: `frontend/app/`
- Frontend auth gate: `frontend/proxy.ts`
- Deployment blueprint: `render.yaml`

## Cleanup Notes

- Historical reports and proof artifacts belong under `docs/archive/`.
- Manual verification utilities belong under `tools/manual_verify/`.
- Local secrets belong in `.env` and `frontend/.env.local`; do not commit them.
