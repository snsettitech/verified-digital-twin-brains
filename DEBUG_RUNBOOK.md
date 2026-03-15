# Debug Runbook

## Prerequisites

- Python 3.11
- Node.js 20 and npm 10
- Supabase project URL and service-role key
- Pinecone API key and index name
- OpenAI API key
- Optional for worker/deep research: Redis, Exa, Firecrawl, Anthropic/Cerebras/HF, Neo4j

## Install

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

## Env Checklist

### Required to boot the API

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` or `SUPABASE_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`

### Strongly recommended locally

- `JWT_SECRET`
- `ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`
- `FRONTEND_URL=http://localhost:3000`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_FRONTEND_URL=http://localhost:3000`

### Required to boot the worker reliably

- API vars above
- one LLM provider key: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` or `CEREBRAS_API_KEY`
- `REDIS_URL` if you want Redis queueing instead of DB polling

## Run Backend

```bash
cd backend
.venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Expected:

- startup banner
- feature-flag summary
- `FastAPI initialization complete. Bound to PORT: 8000`
- health endpoints at `http://localhost:8000/health` and `http://localhost:8000/docs`

## Run Frontend

```bash
cd frontend
npm run dev
```

Expected:

- app on `http://localhost:3000`
- auth/session gate handled by `frontend/proxy.ts`

## Run Worker

```bash
cd backend
.venv\Scripts\activate
python worker.py
```

Expected:

- env validation passes
- queue mode logged
- idle heartbeat instead of immediate crash

## Smoke Test Flow

1. Start backend.
2. Start frontend.
3. Open `http://localhost:3000/auth/login`.
4. Sign in with a valid Supabase user.
5. Complete onboarding or open an existing profile/twin.
6. Open `/dashboard/chat` or `/dashboard/profile`.
7. Send one chat request or start one research run.
8. Confirm backend logs a successful request and the frontend renders a non-error state.

## Common Failure Points

- Missing backend env: `backend/main.py` exits early if `SUPABASE_URL`, a Supabase key, `OPENAI_API_KEY`, `PINECONE_API_KEY`, or `PINECONE_INDEX_NAME` is missing.
- Missing frontend public vars: `frontend/proxy.ts` and auth callback depend on Supabase public vars.
- Stale docs/scripts: old references to `frontend/middleware.ts` or `backend/.env.example` are obsolete; use `frontend/proxy.ts` and repo-root `.env.example`.
- Worker startup failures: `worker.py` needs queue/provider env beyond the minimal API bootstrap.
- Hardcoded fallback URLs: `frontend/next.config.ts` still contains production URL fallbacks; override them in local env files to avoid confusing cross-environment traffic.

## Shortest Start Command

If you want a helper script instead of manual terminals:

```bash
./scripts/dev.ps1
```

or

```bash
./scripts/dev.sh
```

Those scripts now use repo-root `.env` and `frontend/.env.local`.
