# ADK Migration Guide

## Overview

This branch (`feat/adk-migration`) migrates the agent orchestration layer from
LangChain/LangGraph to a lightweight async pipeline, preparing for full Google
ADK integration.

**Migration Strategy:** Parallel runtime with feature flag (`AGENT_RUNTIME`).
Both LangGraph and ADK paths coexist until parity is proven.

## Architecture

```
AGENT_RUNTIME=langgraph (default)
  chat.py → agents/runner.py → modules/agent.py (LangGraph StateGraph)

AGENT_RUNTIME=adk
  chat.py → agents/runner.py → agents/pipeline.py (plain async pipeline)
```

## New Files

| File | Purpose |
|------|---------|
| `agents/message_types.py` | Plain-dict message abstraction (replaces HumanMessage/AIMessage) |
| `agents/state.py` | Pipeline state factory (replaces TwinState TypedDict) |
| `agents/pipeline.py` | Async pipeline orchestrator (replaces StateGraph) |
| `agents/runner.py` | Feature-flag router between ADK and LangGraph |
| `adk_tools/pinecone_search.py` | Knowledge base search (replaces @tool decorator) |
| `sessions/supabase_session.py` | State persistence (replaces PostgresSaver) |
| `tests/test_adk_parity.py` | Parity test suite |
| `migrations/add_conversation_state_table.sql` | DB migration for state persistence |

## Infrastructure Files

| File | Purpose |
|------|---------|
| `.env.staging.template` | All env vars needed for staging |
| `render-staging.yaml` | Render blueprint for staging services |
| `.github/workflows/adk-staging-ci.yml` | CI pipeline for the migration branch |

## Setup Instructions

### 1. Supabase Staging

Option A — Supabase Branching (recommended):
```bash
# In Supabase dashboard: Settings → Branching → Enable
# Create branch linked to feat/adk-migration
```

Option B — Separate project:
```bash
# Create new project in Supabase dashboard
# Run all migrations from backend/migrations/ in order
# Run the new migration:
#   backend/migrations/add_conversation_state_table.sql
```

### 2. Render Staging

1. Go to https://dashboard.render.com
2. New → Blueprint → Connect your repo
3. Select `render-staging.yaml` as the blueprint
4. Set branch to `feat/adk-migration`
5. Add environment variables (secrets) in Render dashboard:
   - SUPABASE_URL (staging)
   - SUPABASE_KEY (staging anon key)
   - SUPABASE_SERVICE_KEY (staging service key)
   - JWT_SECRET (staging)
   - OPENAI_API_KEY
   - PINECONE_API_KEY
   - PINECONE_INDEX_NAME
   - ANTHROPIC_API_KEY
   - CEREBRAS_API_KEY
   - GOOGLE_API_KEY
   - COHERE_API_KEY

### 3. Vercel Preview

Automatic — Vercel creates preview deployments for every push.
Set in Vercel project settings:
- `NEXT_PUBLIC_API_URL` = your staging Render URL

### 4. GitHub Secrets (for CI)

Add these secrets in GitHub → Settings → Secrets → Actions:
- `STAGING_SUPABASE_URL`
- `STAGING_SUPABASE_KEY`
- `STAGING_SUPABASE_SERVICE_KEY`
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`

### 5. Test Locally

```bash
# Set the runtime flag
export AGENT_RUNTIME=adk

# Run unit tests
cd backend && python -m pytest tests/test_adk_parity.py -v

# Start the server
cd backend && uvicorn main:app --port 8000
```

## Migration Phases

### Phase 1: Foundation (current)
- [x] Branch created
- [x] Message abstraction layer
- [x] Pipeline state definition
- [x] Async pipeline orchestrator
- [x] Feature-flag runner
- [x] Pinecone search tool (framework-free)
- [x] Supabase session service
- [x] Parity test suite
- [x] CI/CD workflow
- [x] Staging infrastructure configs
- [ ] Run conversation_state migration on staging Supabase
- [ ] Deploy to staging Render
- [ ] First end-to-end query through ADK pipeline

### Phase 2: Full Pipeline Parity
- [ ] All 6 node functions working with plain-dict messages
- [ ] Streaming contract matches frontend expectations
- [ ] 20+ regression queries produce equivalent quality
- [ ] Latency within 10% of LangGraph path

### Phase 3: Tests & Cleanup
- [ ] Migrate 21 test files to use message_types
- [ ] CI green on all tests
- [ ] Remove LangChain imports from ADK code path

### Phase 4: Cutover
- [ ] Feature flag flip: AGENT_RUNTIME=adk in production
- [ ] Monitor for 1 week
- [ ] Remove LangChain dependencies from requirements.txt
- [ ] Delete modules/agent.py LangGraph code
- [ ] Celebrate

## Rollback

If ADK pipeline causes issues in staging:
```bash
# Flip back to LangGraph instantly
AGENT_RUNTIME=langgraph
```
No code changes needed — the feature flag controls everything.
