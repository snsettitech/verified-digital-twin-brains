# Quick Start

Use this repo in three passes:

1. Read [DEBUG_RUNBOOK.md](../DEBUG_RUNBOOK.md) for local setup and smoke testing.
2. Read [RUNTIME_ENTRYPOINTS.md](../RUNTIME_ENTRYPOINTS.md) for the actual startup and route surfaces.
3. Use the deeper references only as needed:
   - [docs/architecture/system-overview.md](architecture/system-overview.md)
   - [docs/architecture/api_contracts.md](architecture/api_contracts.md)
   - [docs/ai/agent-manual.md](ai/agent-manual.md)
   - [docs/ops/README.md](ops/README.md)

## Short Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
copy .env.example .env
```

### Frontend

```bash
cd frontend
npm ci
copy .env.example .env.local
```

### Run

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm run dev
```

For the full env checklist, worker startup, common failures, and smoke-test flow, use [DEBUG_RUNBOOK.md](../DEBUG_RUNBOOK.md).
