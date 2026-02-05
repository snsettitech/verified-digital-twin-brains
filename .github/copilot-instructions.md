# GitHub Copilot Instructions for Verified Digital Twin Brain

**Last Updated:** February 2026  
**Project Status:** Phase 9/10 - Production-ready

This document guides AI agents to be immediately productive in this codebase.

## 🏗️ Architecture at a Glance

```
Frontend (Next.js 16)  →  Backend (FastAPI)  →  {Supabase + Pinecone + OpenAI}
  Dashboard             Auth, Twins, Chat         Multi-tenant, Vectors, LLMs
  20 sections           17 routers, 33 modules    Verified QnA, Graph, Memory
```

**Key principle**: Multi-tenant isolation via `tenant_id` filtering on **every** database and vector query.

---

## ⚠️ Critical Knowledge: Do-Not-Touch Zones

These modules are foundation—modify only to extend, never to replace:

1. **`backend/modules/_core/`**: Interview orchestration, memory extraction, versioning
   - Modify only via composition; changes here cascade to all specializations
   
2. **`backend/modules/auth_guard.py`**: JWT validation, tenant resolution
   - Pattern: Always use `Depends(get_current_user)` + `verify_owner()`
   
3. **`backend/modules/observability.py`**: Supabase singleton
   - Import: `from modules.observability import supabase` (never create new clients)
   
4. **`backend/modules/clients.py`**: OpenAI/Pinecone/Cohere clients
   - Functions: `get_openai_client()`, `get_pinecone_index()`, `get_async_openai_client()`
   
5. **`backend/main.py`**: CORS and middleware order
   - Middleware order matters; never reorder or remove
   
6. **`frontend/middleware.ts`** and **`frontend/lib/`**: Auth patterns
   - Do not modify Supabase client initialization

---

## 📋 Workflow Essentials

### Running Tests & Validation
```bash
# Always run before pushing (Windows)
./scripts/preflight.ps1

# Linux/Mac
./scripts/preflight.sh
```

Runs: linting → type checks → tests. Must pass before merge.

### Local Development
```bash
# Backend (terminal 1)
cd backend && python -m uvicorn main:app --reload

# Frontend (terminal 2)
cd frontend && npm run dev

# Worker (terminal 3, if testing background jobs)
cd backend && python worker.py
```

### Database Changes
1. **Write migration** in `backend/database/migrations/` (SQL)
2. **Test in Supabase SQL Editor** before committing
3. **Include RLS policies** for every table
4. **Use `IF NOT EXISTS`** for idempotency
5. **Reference**: `backend/database/schema/supabase_schema.sql` is reference only

---

## 🔑 Project-Specific Patterns

### 1. Authentication & Ownership Checks
```python
from modules.auth_guard import get_current_user, verify_owner

@router.post("/twins/{twin_id}/chat")
async def chat(
    twin_id: str,
    request: ChatRequest,
    user: dict = Depends(get_current_user)  # Always inject user
):
    verify_owner(user, twin_id)  # Always verify ownership
    # Only then proceed with logic
```

**Why**: `tenant_id` is derived from JWT claims, not from request body. Never trust client input.

### 2. Supabase Queries (Always Filter by Tenant)
```python
from modules.observability import supabase

# ✅ CORRECT: Filter by tenant_id
response = supabase.table("twins").select("*").eq("tenant_id", tenant_id).execute()

# ❌ WRONG: No tenant filter = data leak
response = supabase.table("twins").select("*").execute()
```

### 3. Vector Search (Pinecone)
```python
from modules.clients import get_pinecone_index
from modules.embeddings import get_embedding

embedding = get_embedding(query_text)
index = get_pinecone_index()
results = index.query(
    vector=embedding,
    top_k=5,
    filter={"twin_id": {"$eq": twin_id}}  # Always filter by twin_id or access group
)
```

### 4. API Error Handling
- `401`: Missing/invalid JWT
- `403`: Access denied (verify_owner failed)
- `404`: Not found OR access denied (don't leak existence)
- `500`: Unexpected server error

```python
raise HTTPException(
    status_code=403, 
    detail="Twin not found or access denied"  # Don't reveal which
)
```

---

## 🗂️ Key File References

| What | Where |
|------|-------|
| All API routes | `backend/routers/*.py` |
| Core logic | `backend/modules/*.py` |
| Database schema | `backend/database/schema/supabase_schema.sql` |
| Frontend pages | `frontend/app/` (App Router) |
| Components | `frontend/components/` |
| Auth context | `frontend/lib/supabase/client.ts` |
| Supabase client | `modules/observability.py` |
| OpenAI/Pinecone | `modules/clients.py` |
| Specializations | `backend/modules/specializations/` |

---

## 💡 Common Tasks

### Adding a New API Endpoint
1. Create router in `backend/routers/new_feature.py`
2. Include router in `backend/main.py`
3. Always use `Depends(get_current_user)` for auth
4. Always verify ownership with `verify_owner()`
5. Always filter Supabase/Pinecone queries by tenant_id

### Modifying Database Schema
1. Create migration in `backend/database/migrations/`
2. Test in Supabase SQL Editor
3. Include RLS policies
4. Never modify `supabase_schema.sql` directly (reference only)

### Adding Frontend Feature
1. Add component in `frontend/components/`
2. Use Next.js App Router conventions
3. Auth patterns already in `frontend/lib/`
4. Never modify `frontend/middleware.ts`

### Debugging a Bug
1. Check `.cursorrules` for debugging protocol
2. If database issue: `backend/database/schema/supabase_schema.sql` + migrations
3. If connectivity: `modules/clients.py` and `.env` vars
4. If auth: `modules/auth_guard.py` and JWT secret (must match Supabase exactly)

---

## 🚀 Deployment Checklist

- [ ] All tests pass (`./scripts/preflight.ps1`)
- [ ] No hardcoded API keys or URLs
- [ ] Environment variables documented in `.env.example`
- [ ] RLS policies added for new tables
- [ ] Tenant_id filtering on all data queries
- [ ] HTTP status codes follow convention (401/403/404/500)

---

## 📖 Extended Reading

- **System Architecture**: [docs/architecture/system-overview.md](../docs/architecture/system-overview.md) (890+ lines, comprehensive)
- **API Contracts**: [docs/architecture/api-contracts.md](../docs/architecture/api-contracts.md)
- **AI Operating Manual**: [docs/ai/agent-manual.md](../docs/ai/agent-manual.md) (detailed folder rules)
- **Cursor Rules**: [.cursorrules](.cursorrules) (quick reference, similar to this)

---

## 🎯 Golden Rules

1. **Context First**: Always check system-overview.md before significant changes
2. **Filter Everything**: Every query MUST filter by `tenant_id` or `twin_id`
3. **Auth Always**: Use `Depends(get_current_user)` + `verify_owner()` patterns
4. **Singleton Clients**: Never create duplicate Supabase/OpenAI/Pinecone instances
5. **Test Before Push**: Run `./scripts/preflight.ps1` to catch regressions
6. **No Placeholders**: Never commit placeholder URLs, keys, or secrets
7. **Verify Ownership**: Cross-check that user owns the twin/resource before modifying

---

## ❓ Questions Before Modifying Core Logic

- Does this change affect tenant isolation?
- Does this break the existing RAG retrieval path?
- Have I tested in `preflight.ps1`?
- Are all database queries filtered by `tenant_id`?
- Did I add RLS policies for new tables?
- Is this change compatible with existing specializations?
