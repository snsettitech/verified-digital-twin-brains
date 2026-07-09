# Env Audit

Generated from code/config scans on 2026-03-10.

## Vars Required To Start The API Locally

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` or `SUPABASE_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`

These are enforced directly by `backend/main.py`.

## Vars Required To Start The Frontend Locally

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_BACKEND_URL`
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_FRONTEND_URL`

These are required by `frontend/proxy.ts`, auth callback handling, and API helpers.

## Frequently Used Optional Runtime Vars

- Queue/worker: `REDIS_URL`, `DATABASE_URL`, `WORKER_QUEUE`
- Deep research: `SEARCH_PROVIDER`, `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `OPENAI_DEEP_RESEARCH_MODEL`, `NAME_ONLY_DEEP_RESEARCH_ENABLED`
- Graph memory: `GRAPH_MEMORY_ENABLED`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- Observability: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `LANGFUSE_RELEASE`
- Alternate providers: `ANTHROPIC_API_KEY`, `CEREBRAS_API_KEY`, `HF_API_TOKEN`, `HUGGINGFACEHUB_API_TOKEN`

## Example Vars Removed Or Left Out Intentionally

The env examples are now bootstrap-oriented, not exhaustive.

- Removed because code no longer uses them directly:
  - `SUPABASE_ACCESS_TOKEN`
  - `DEPLOYED_FRONTEND_URL`
  - `DEPLOYED_BACKEND_URL`
  - `NEO4J_DATABASE`
- Left out intentionally despite code references:
  - many fine-grained tuning flags for retrieval, chunking, graph memory, and person-completeness
  - CI-only vars such as `CI`, `PW_REPORTER`, `PW_TRACE_MODE`
  - one-off test/probe vars used only by manual scripts

## Risky Hardcoded Values

- `frontend/next.config.ts` still contains hardcoded production defaults for:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - `NEXT_PUBLIC_BACKEND_URL`
  - `NEXT_PUBLIC_API_URL`
  - `NEXT_PUBLIC_FRONTEND_URL`
- source fallbacks to `http://localhost:8000` still exist in several frontend/backend files
- `.agent/mcp.json` previously contained local credentials and was tracked; it is now untracked and replaced with `.agent/mcp.example.json`

## Changes Made To Env Templates

### `.env.example`

- re-centered on the actual backend bootstrap path
- added common worker/runtime vars (`DATABASE_URL`, `REDIS_URL`, provider keys)
- added deep-research and graph-memory essentials
- removed stale/untracked deployment-only placeholders
- clarified that frontend public vars live in `frontend/.env.example`

### `frontend/.env.example`

- kept only the vars required to boot the frontend cleanly
- added `NEXT_PUBLIC_SHOW_ENV_BADGE`
- added `NEXT_PUBLIC_E2E_BYPASS_AUTH`

## Recommendation

Keep `.env.example` minimal and treat `ENV_AUDIT.md` as the authoritative full-surface inventory. Do not try to mirror every feature-flag/tuning knob in the example template.
