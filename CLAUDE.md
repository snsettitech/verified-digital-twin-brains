# CLAUDE.md - Verified Digital Twin Brain

> Project-level instructions for Claude Code. Integrates with [everything-claude-code](https://github.com/affaan-m/everything-claude-code) plugin.

## Project Overview

Enterprise-grade AI platform for creating trustworthy, auditable digital twins with multi-tenant isolation, governance layers, and agentic capabilities. Full-stack: Python/FastAPI backend + Next.js 16 TypeScript frontend.

## Tech Stack

- **Backend**: Python 3.11-3.12, FastAPI, LangChain, LangGraph, OpenAI GPT-4o, Pinecone (3072-dim), Supabase PostgreSQL, Redis, Neo4j/Graphiti
- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, Playwright
- **Deployment**: Vercel (frontend) + Render/Railway (backend + worker)

## Critical Rules

### 1. Multi-Tenant Isolation (MANDATORY)

Every database query and vector search MUST filter by `tenant_id` or `twin_id`. No exceptions.

```python
# ALWAYS use auth dependency injection
from modules.auth_guard import get_current_user, verify_owner

@router.get("/twins/{twin_id}")
async def get_twin(twin_id: str, user: dict = Depends(get_current_user)):
    await verify_owner(twin_id, user["id"])
```

### 2. Do-Not-Touch Zones

- `backend/modules/_core/` - Core abstractions; extend via interfaces only
- `backend/modules/auth_guard.py` - Follow existing auth patterns exactly
- `backend/modules/observability.py` - Supabase client singleton
- `backend/modules/clients.py` - Centralized client initialization
- `backend/main.py` - Middleware order is critical; DO NOT reorder
- `frontend/lib/supabase/client.ts` - Supabase client init
- `backend/database/migrations/` - Test in Supabase SQL Editor first

### 3. Client Management

Import singletons from modules, never create at module level:

```python
from modules.observability import supabase
from modules.clients import openai_client
```

### 4. Security

- No hardcoded secrets or API keys
- Environment variables for all sensitive data
- Parameterized queries only
- RLS policies must block cross-tenant access
- Error messages must not leak sensitive data

### 5. Code Style

**Python**: Async-first, type hints required, `Depends()` for injection, PEP 8
**TypeScript**: Functional components, hooks pattern, Tailwind utilities, centralized API clients

## Build & Test Commands

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
pytest -v --tb=short -m "not network"
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
npm run typecheck
npx playwright test
```

### Health Check

```bash
python scripts/verify_features.py
```

## Git Workflow

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- Never commit to main directly
- PRs require review, CI must be green
- Keep PRs small and single-purpose
- Include migration verification steps if SQL changes

## Available ECC Commands

- `/tdd` - Test-driven development workflow
- `/plan` - Create implementation plan before coding
- `/code-review` - Quality and security review
- `/build-fix` - Fix build errors
- `/e2e` - Generate and run E2E tests
- `/python-review` - Python-specific code review
- `/learn` - Extract reusable patterns from session

## Environment Variables

See `.env.example` for the full list. Required:

```
OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY,
PINECONE_API_KEY, PINECONE_INDEX_NAME, JWT_SECRET,
COHERE_API_KEY, REDIS_URL
```

## Project Structure

```
backend/
  routers/        # 40+ API route modules
  modules/        # 70+ business logic modules
  database/       # Migrations and schema
  main.py         # FastAPI entry point
  worker.py       # Background job processor

frontend/
  app/            # Next.js App Router pages
  components/     # React components
  lib/            # API clients, auth context
  contexts/       # React contexts

tests/            # Backend test files
docs/             # Architecture, API contracts, guides
```

## Reference Documentation

- `AGENTS.md` - Full agent development guide
- `docs/quick-start.md` - Setup guide
- `docs/architecture/system-overview.md` - System architecture
- `docs/architecture/api-contracts.md` - REST API spec
- `docs/ai/agent-manual.md` - AI agent operating manual
