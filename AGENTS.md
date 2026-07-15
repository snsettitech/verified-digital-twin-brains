# AGENTS.md - Verified Digital Twin Brain

> **Purpose**: This document provides essential context for AI coding agents working on the Verified Digital Twin Brain project. Read this first before making any changes.

---

## Project Overview

The **Verified Digital Twin Brain** is an enterprise-grade AI platform for creating trustworthy, auditable digital twins with multi-tenant isolation, governance layers, and agentic capabilities. It creates AI systems that can represent real people or organizations, use their authorized knowledge and preferences, and answer or act across tools with permissions, provenance, and auditability.

## Bug Fix Status — ALL 5 PHASES COMPLETE ✅

**78/78 tests passing** across 5 systematic fix phases.

### Phase 0 — Security (COMPLETE ✅) — 16/16 tests

| Bug | File | Fix |
| --- | ---- | --- |
| #1 CRITICAL: Cross-tenant account deletion | `routers/auth.py` | delete_account only deletes twins where `owner_user_id == user_id` |
| #2 CRITICAL: Cross-twin data leakage | `modules/retrieval.py` | Added `_enforce_twin_scope()` post-retrieval guard |
| #5 CRITICAL: Tenant auto-creation on reads | `modules/auth_guard.py` | All read deps use `create_if_missing=False` |
| #6 HIGH: Orphaned user row on delete | `routers/auth.py` | Hard-deletes `public.users` row; anonymization is fallback only |
| #20 MEDIUM: Unvalidated email in sync-user | `routers/auth.py` | Email regex validation before any DB writes |

### Phase 1 — Twin Management (COMPLETE ✅) — 9/9 tests

| Bug | File | Fix |
| --- | ---- | --- |
| #7 HIGH: Twin delete missing tenant scope | `routers/twins.py` | `.eq("tenant_id", twin_tenant_id)` added to final DELETE |
| #15 MEDIUM: Race condition in twin creation | `modules/twin_service.py` | Immediately claim `owner_user_id` on unclaimed duplicate |

### Phase 2 — Data Ingestion (COMPLETE ✅) — 28/28 tests

| Bug | File | Fix |
| --- | ---- | --- |
| #3 CRITICAL: Partial ingestion without rollback | `modules/ingestion.py` | Pinecone upsert first, then delete old chunks, then insert new |
| #4 CRITICAL: Metadata mutation in vector loop | `modules/ingestion.py` | `md = dict(vector.get("metadata") or {})` prevents in-place mutation |
| #8 HIGH: No bounds on chunk_entries_override | `modules/ingestion.py` | Hard cap at 5000 entries |
| #9 HIGH: Null embedding validation | `modules/ingestion.py` | `ValueError` if `get_embedding()` returns None or empty list |
| #13 HIGH: metadata_override overwrites security fields | `modules/ingestion.py` | Re-assert `twin_id`, `source_id`, `chunk_id` after override |
| #22 MEDIUM: Prompt questions lose text in embedding | `modules/ingestion.py` | Returns `"{descriptor}: {chunk}"` for full semantic searchability |
| #24 MEDIUM: Stale chunk references before vector upsert | `modules/ingestion.py` | Same fix as #3 — ordering rewrite |

### Phase 3 — Vector Retrieval (COMPLETE ✅) — 6/6 tests

| Bug | File | Fix |
| --- | ---- | --- |
| #14 HIGH: Partial namespace failure not retried | `modules/retrieval.py` | Retry primary namespace whenever it specifically failed (not just when all fail) |

### Phase 4 — Chat Pipeline (COMPLETE ✅) — 19/19 tests

| Bug | File | Fix |
| --- | ---- | --- |
| #10 HIGH: Message ordering not guaranteed | `modules/observability.py` | Secondary `.order("id", desc=False)` for deterministic order |
| #11 HIGH: Async tasks not cancelled on disconnect | `routers/chat.py` | `pending_task.cancel()` in stream generator finally block |
| #12 HIGH: Stream missing done event on error | `routers/chat.py` | Always emit `{"type":"done"}` after error event |
| #16 MEDIUM: Prompt injection in coreference | `modules/conversation_context.py` | Escape `{`/`}` in query before `.format()` |
| #17 MEDIUM: Unescaped history in prompts | `modules/conversation_context.py` | Escape `{`/`}` in history content before returning |
| #18 MEDIUM: Missing query max-length validation | `routers/chat.py` | Reject queries > 4096 chars with HTTP 422 |
| #19 MEDIUM: Citation/context mismatch | `routers/chat.py` | Filter citations to only source_ids present in final context |
| #25 LOW: Missing connection cleanup | `routers/chat.py` | Same fix as #11 — task cancel in finally |

### Key Rules Established

- `get_current_user`, `verify_owner`, `require_tenant`, `verify_twin_ownership`, `verify_source_ownership` — NEVER call `resolve_tenant_id(create_if_missing=True)`. Only `/auth/sync-user` creates tenants.
- All twin-scoped retrievals run through `_enforce_twin_scope()` which filters cross-twin matches before dedup/merge.
- Account deletion filters to user-owned twins only. Never deletes other users' twins in the same tenant.
- User deletion = hard-delete `public.users` row. Anonymization is fallback if hard-delete fails.
- Ingestion order: embed → Pinecone upsert → delete old DB chunks → insert new DB chunks. Never delete before embedding succeeds.
- metadata_override can never overwrite `twin_id`, `source_id`, or `chunk_id` — always re-asserted after override.
- All chat queries validated at entry: non-empty, max 4096 chars.
- Stream errors always emit terminal `{"type":"done"}` so clients can close cleanly.
- Ongoing bug fix tracking in `CRITICAL_BUG_FIX_PLAN.md` and `backend/tests/test_phase_*.py`.

---

## Persona Generation Learnings

- Persona creation must materialize a clean canonical stored profile in `twins.settings.public_profile` during generation time. Do not treat late UI reconstruction as the primary source of persona truth.
- Persona creation must also write a prompt-facing companion pack in `twins.settings.persona_identity_pack` so the chat runtime starts from stable identity facts instead of rebuilding identity from noisy retrieval.
- Persona chat grounding must prefer this order: canonical profile, verified facts and approved profile fields, featured resources or top sources, vector retrieval, graph or memory context, final generation.
- Public persona photo resolution is part of persona materialization when a strong public image exists. Prefer owner-provided or OAuth images first, then strong public profile images from official or high-confidence public sources.
- Marketplace cards, public share pages, authenticated previews, and chat prompts should all read from the same canonical persona artifact first and only derive missing fields second.

### Key Stats
- **Backend**: 40+ API routers, 70+ business logic modules
- **Frontend**: Next.js 16 with App Router, 20+ dashboard sections
- **Database**: Supabase PostgreSQL with 26+ tables and RLS policies
- **AI Stack**: GPT-4o, Pinecone vectors (3072-dim), LangGraph agents
- **Deployment**: Vercel (frontend) + Render/Railway (backend + worker)
- **Current Phase**: 9/10 major phases complete, production-ready

---

## Technology Stack

### Backend (Python 3.11-3.12)
| Component | Technology |
|-----------|------------|
| Framework | FastAPI + Uvicorn |
| AI/ML | OpenAI GPT-4o, LangChain, LangGraph, Cohere |
| Vector DB | Pinecone (3072-dim embeddings) |
| Database | Supabase PostgreSQL with RLS |
| Auth | JWT + Supabase Auth |
| Memory | Graphiti (Zep) + Neo4j |
| Monitoring | Langfuse tracing |
| Queue | Redis + Background Worker |

### Frontend (TypeScript/Node.js)
| Component | Technology |
|-----------|------------|
| Framework | Next.js 16 (App Router) |
| UI | React 19, Tailwind CSS 4 |
| Auth | Supabase Auth Helpers |
| Testing | Playwright |
| Linting | ESLint 9 |
| Build | Standalone output for deployment |

---

## Project Structure

```
verified-digital-twin-brains/
├── frontend/                    # Next.js 16 Application
│   ├── app/                     # App Router pages
│   │   ├── auth/               # Authentication flows
│   │   ├── dashboard/          # Main dashboard sections
│   │   ├── onboarding/         # 8-step onboarding wizard
│   │   ├── share/              # Public twin sharing
│   │   └── admin/              # Admin governance UI
│   ├── components/             # React components
│   ├── lib/                    # API clients, auth context
│   ├── contexts/               # React contexts
│   └── middleware.ts           # Auth redirect middleware
│
├── backend/                     # FastAPI Application
│   ├── routers/                # 40+ API route modules
│   │   ├── auth.py             # JWT, user sync, sessions
│   │   ├── chat.py             # Chat endpoints
│   │   ├── twins.py            # Twin CRUD operations
│   │   ├── cognitive.py        # Interview, graph, builder
│   │   ├── ingestion.py        # Document/URL ingestion
│   │   ├── knowledge.py        # QnA, sources, chunks
│   │   ├── actions.py          # Triggers, drafts, execute
│   │   ├── governance.py       # Audit, policies
│   │   └── ...
│   ├── modules/                # Business logic (70+ modules)
│   │   ├── _core/              # Core abstractions (DO NOT MODIFY)
│   │   ├── auth_guard.py       # Authentication patterns
│   │   ├── observability.py    # Supabase client singleton
│   │   ├── clients.py          # OpenAI/Pinecone clients
│   │   ├── retrieval.py        # Hybrid RAG retrieval
│   │   ├── agent.py            # LangGraph agent
│   │   ├── answering.py        # Response generation
│   │   ├── memory.py           # Conversation context
│   │   └── specializations/    # 17 domain templates
│   ├── database/               # Migrations and schema
│   │   ├── migrations/         # SQL migration files
│   │   └── schema/             # Reference schema
│   ├── main.py                 # FastAPI app entry point
│   └── worker.py               # Background job processor
│
├── docs/                        # Documentation
│   ├── quick-start.md          # Essential setup guide
│   ├── architecture/           # System architecture
│   ├── ai/                     # AI agent manual
│   └── ops/                    # Operations runbooks
│
├── tests/                       # Test files
├── scripts/                     # Utility scripts
└── .github/workflows/           # CI/CD configuration
```

---

## Build and Development Commands

### Backend

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Development (local)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 120

# Worker (separate service)
python worker.py

# Testing
pytest -v --tb=short -m "not network"
pytest backend/tests/ -v

# Linting
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

### Frontend

```bash
# Setup
cd frontend
npm install

# Development
npm run dev          # Starts on http://localhost:3000

# Build
npm run build        # Production build
npm run build:vercel # Vercel-optimized build

# Quality checks
npm run lint         # ESLint
npm run typecheck    # TypeScript check

# Testing
npx playwright test  # E2E tests
```

---

## Code Style Guidelines

### Python (Backend)

1. **Async First**: Use `async def` for API endpoints and I/O-bound operations
2. **Dependency Injection**: Always use `Depends()` for auth and service injection
3. **Type Hints**: Use type annotations for function parameters and returns
4. **Error Handling**: Use HTTPException with descriptive detail
   ```python
   # ✅ CORRECT
   raise HTTPException(status_code=404, detail="Twin not found or access denied")
   
   # ❌ WRONG
   raise HTTPException(status_code=404, detail="Not found")  # Too vague
   ```
5. **Client Management**: Import singletons from modules, never create at module level
   ```python
   # ✅ CORRECT
   from modules.observability import supabase
   from modules.clients import openai_client
   ```
6. **Multi-tenancy**: Every query MUST filter by `tenant_id` or `twin_id`

### TypeScript (Frontend)

1. **Functional Components**: Use function declarations with explicit return types
2. **Hooks Pattern**: Use hooks for state and effects
3. **Tailwind**: Use utility classes, avoid custom CSS when possible
4. **API Calls**: Use centralized API clients in `lib/`
5. **Auth**: Use Supabase auth helpers, don't implement JWT logic manually

---

## Testing Instructions

### Backend Tests

```bash
cd backend

# Run all tests
pytest -v

# Run with network mocks only
pytest -v -m "not network"

# Run specific test files
pytest tests/test_chat.py -v
pytest tests/test_ingestion.py -v

# Run persona regression tests (CI)
pytest backend/tests/test_persona_regression_runner.py
python backend/eval/persona_regression_runner.py --dataset backend/eval/persona_regression_dataset.json --min-pass-rate 0.95
```

### Frontend Tests

```bash
cd frontend

# E2E tests
npx playwright test

# Lint and typecheck
npm run lint
npm run typecheck
```

### Feature Verification Script

```bash
# Backend health check
python scripts/verify_features.py
```

---

## Critical Do-Not-Touch Zones

The following files/modules have critical patterns that must not be modified:

### Backend
- **`backend/modules/_core/`** - Core abstractions; extend via interfaces only, never modify directly
- **`backend/modules/auth_guard.py`** - Authentication patterns; follow existing patterns exactly
- **`backend/modules/observability.py`** - Supabase client singleton; MUST use this import
- **`backend/modules/clients.py`** - OpenAI/Pinecone client management; centralized initialization only
- **`backend/main.py`** - Middleware order is critical; DO NOT reorder CORS/auth middleware

### Frontend
- **`frontend/lib/supabase/client.ts`** - Supabase client initialization
- **`frontend/proxy.ts`** - Auth redirects and proxy chain

### Database
- **`backend/database/migrations/`** - SQL migrations; test in Supabase SQL Editor first
- Always include RLS policies in migrations
- Use `CREATE TABLE IF NOT EXISTS` pattern

---

## Security Considerations

### Multi-tenant Isolation
- **REQUIRED**: Every database query and vector search must filter by `tenant_id` or `twin_id`
- Use `Depends(get_current_user)` for authentication
- Use `verify_owner()` for ownership checks
- RLS policies must block cross-tenant data access

### Authentication Patterns
```python
from fastapi import Depends
from modules.auth_guard import get_current_user, verify_owner

@router.get("/twins/{twin_id}")
async def get_twin(twin_id: str, user: dict = Depends(get_current_user)):
    # verify_owner checks tenant isolation
    await verify_owner(twin_id, user["id"])
    ...
```

### Environment Variables
- Never hardcode secrets or API keys
- Use `.env` for local development
- Secrets are configured in Render/Vercel dashboards for production
- Never commit `.env` files

### Required Secrets (Backend)
```
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_KEY
PINECONE_API_KEY
PINECONE_INDEX_NAME
JWT_SECRET
COHERE_API_KEY
REDIS_URL
ELEVENLABS_API_KEY (for voice)
```

---

## Deployment Architecture

### Production Deployment

| Service | Platform | Command/Config |
|---------|----------|----------------|
| Frontend | Vercel | Auto-deploy on push to `main` |
| Backend API | Render | `uvicorn main:app` via `render.yaml` |
| Worker | Render | `python worker.py` via `render.yaml` |
| Database | Supabase | Managed PostgreSQL |
| Vector DB | Pinecone | Managed vector database |

### Feature Flags

Feature flags are controlled via environment variables:

```python
# In backend/main.py
ENHANCED_INGESTION_ENABLED = os.getenv("ENABLE_ENHANCED_INGESTION", "false").lower() == "true"
DELPHI_RETRIEVAL_ENABLED = os.getenv("ENABLE_DELPHI_RETRIEVAL", "true").lower() == "true"
VC_ROUTES_ENABLED = os.getenv("ENABLE_VC_ROUTES", "false").lower() == "true"
DEEP_RESEARCH_ENABLED = os.getenv("DEEP_RESEARCH_ENABLED", "false").lower() == "true"
```

Realtime ingestion compat routes are always registered; only the remaining
optional/rollout surfaces above stay env-gated.

---

## CI/CD Workflow

### GitHub Actions Workflows

1. **`lint.yml`** - Runs on PR/push to main
   - Backend: flake8 linting + pytest
   - Frontend: ESLint + TypeScript check + build

2. **`persona-regression.yml`** - Persona quality gate
   - Runs persona regression tests
   - Requires 95%+ pass rate

3. **`code-review.yml`** - Automated code review
4. **`checkpoint.yml`** - Repository checkpointing

### Branch Protection Rules

- Require pull request before merging
- Require 1 approval
- Dismiss stale approvals on new commits
- Require status checks to pass
- Require branch to be up to date
- Restrict force pushes

---

## Development Conventions

### API Error Status Codes
- `401` - Missing/invalid authentication (JWT error)
- `403` - Access denied (user doesn't own resource)
- `404` - Resource not found OR access denied (don't leak existence)
- `500` - Server error (unexpected exception)

### PR Requirements
1. Use PR template in `.github/PULL_REQUEST_TEMPLATE.md`
2. Keep PRs small and single-purpose
3. Include: scope, repro steps, evidence, risk notes
4. If migration included: include reversible SQL and verification steps
5. CI must be green before merge

### Agent Workflow (Two-Agent Pattern)
- **Codex**: Feature implementation, contained refactors
- **Antigravity**: Reproduction, tests, integration verification
- Branch naming: `codex/feat-...`, `antigravity/fix-...`
- Keep branches short-lived (under 3 days)

---

## Quick Reference

### Essential Files
- `docs/quick-start.md` - Setup and 1-hour path to production
- `docs/architecture/system-overview.md` - Master architecture
- `docs/architecture/api-contracts.md` - Full REST API specification
- `docs/ai/agent-manual.md` - Detailed AI agent instructions
- `docs/VISION.md` - Foundational product principles

### Critical Commands
```bash
# Daily health check
python scripts/verify_features.py

# Run tests
pytest -v -m "not network"
npm run lint && npm run typecheck

# Local development
uvicorn main:app --reload
npm run dev
```

### Support & Documentation
- Architecture: `docs/architecture/system-overview.md`
- API Contracts: `docs/architecture/api-contracts.md`
- AI Operating Manual: `docs/ai/agent-manual.md`

---

## License

Proprietary - All rights reserved.
