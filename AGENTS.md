# AI Operating Manual: Verified Digital Twin Brain

> **Critical**: This document defines how AI agents must operate in this repository to prevent regressions.

## Architecture Map & Folder Ownership

```
verified-digital-twin-brain/
├── frontend/                 # Next.js 16, TypeScript, Tailwind
│   ├── app/                  # App Router pages (DO NOT change routing structure)
│   ├── components/           # React components (ADD NEW, AVOID breaking existing)
│   ├── lib/                  # Context, Supabase, Feature Flags (CRITICAL: auth patterns)
│   └── middleware.ts         # DO NOT TOUCH - handles auth redirects
│
├── backend/                  # FastAPI, Python 3.12, LangGraph
│   ├── routers/              # API endpoints (ADD NEW, FOLLOW patterns)
│   ├── modules/              # Business logic
│   │   ├── _core/            # DO NOT TOUCH - core abstractions
│   │   ├── auth_guard.py     # DO NOT TOUCH - authentication patterns
│   │   ├── observability.py  # DO NOT TOUCH - Supabase client singleton
│   │   └── clients.py        # DO NOT TOUCH - OpenAI/Pinecone client management
│   ├── database/             # Supabase integration (reference only)
│   ├── migrations/           # SQL migrations (ADD NEW, test in Supabase first)
│   └── main.py               # DO NOT change CORS/auth middleware order
│
├── .github/workflows/        # CI configuration
├── scripts/                  # Preflight scripts (single source of truth)
└── docs/                     # Documentation
```

### Folder Ownership Rules

- **`backend/modules/_core/`**: Core abstractions - NEVER modify, only extend via interfaces
- **`backend/modules/auth_guard.py`**: Authentication patterns - DO NOT change auth flow
- **`backend/modules/observability.py`**: Supabase client - MUST use singleton, never create duplicate clients
- **`backend/modules/clients.py`**: OpenAI/Pinecone clients - MUST use centralized initialization
- **`backend/main.py`**: Middleware order is critical - DO NOT reorder CORS/auth middleware
- **`frontend/lib/`**: Auth patterns - DO NOT change Supabase client initialization
- **`frontend/middleware.ts`**: Auth redirects - DO NOT modify without understanding full flow

## Do-Not-Touch Zones

### 1. Core Modules (backend/modules/_core/)
**Rule**: Never modify core modules. Extend via interfaces only.
- These are base abstractions used by specializations
- Changes here break all specializations
- If you need new functionality, add it via composition, not inheritance

### 2. Authentication Patterns
**Files**:
- `backend/modules/auth_guard.py`
- `backend/routers/auth.py`
- `frontend/lib/supabase/client.ts`
- `frontend/middleware.ts`

**Rule**: Follow existing patterns exactly. Do not:
- Change JWT validation logic
- Modify auth guard dependencies
- Alter Supabase client initialization
- Change middleware order in `main.py`

### 3. Database Schema & Migrations
**Rule**: 
- Always use migrations in `backend/database/migrations/` for schema changes
- `backend/database/schema/` and `supabase_schema.sql` are reference only
- Test migrations in Supabase SQL Editor before committing
- Include RLS policies in every migration
- Use `CREATE TABLE IF NOT EXISTS` pattern

### 4. Client Management
**Rule**: 
- Supabase: Use `from modules.observability import supabase` (singleton)
- OpenAI/Pinecone: Use `modules/clients.py` centralized initialization
- Never create duplicate client instances at module level
- Never initialize clients in router files

### 5. RAG-Lite Path
**Rule**: Do not break the existing RAG-lite retrieval path. This includes:
- `backend/modules/retrieval.py` - Core retrieval logic
- `backend/modules/answering.py` - Answer generation
- Verified QnA matching must continue to work

## Conventions

### API Error Handling

**Pattern**: Use HTTPException with descriptive detail
```python
# ✅ CORRECT
raise HTTPException(status_code=404, detail="Twin not found or access denied")

# ❌ WRONG
raise HTTPException(status_code=404, detail="Not found")  # Too vague
```

**Status Codes**:
- `401`: Missing/invalid authentication (JWT error)
- `403`: Access denied (user doesn't own resource)
- `404`: Resource not found OR access denied (don't leak existence)
- `500`: Server error (unexpected exception)

### Logging

**Pattern**: Use print statements for debugging, structured logging for production
```python
# ✅ CORRECT - Debug logging
print(f"[MODULE_NAME] Action: {action}, User: {user_id}")

# ❌ WRONG - No context
print("Error occurred")
```

**Critical**: Never log PII (personally identifiable information) or secrets.

### Auth Checks

**Pattern**: Always use dependency injection
```python
# ✅ CORRECT
@router.get("/twins/{twin_id}")
async def get_twin(
    twin_id: str,
    user: dict = Depends(get_current_user)
):
    # Verify ownership
    verify_owner(user, twin_id)
    # ... rest of logic

# ❌ WRONG - Manual auth check
@router.get("/twins/{twin_id}")
async def get_twin(twin_id: str):
    token = request.headers.get("Authorization")  # Manual parsing
    # This breaks the pattern
```

**Required imports**:
```python
from modules.auth_guard import get_current_user, verify_owner
```

### Database Migrations

**Pattern**: Always follow this structure
```sql
-- Migration: descriptive_name.sql
-- Purpose: Brief description

-- Create table
CREATE TABLE IF NOT EXISTS my_table (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    -- ... columns
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add RLS
ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view own records"
    ON my_table FOR SELECT
    USING (twin_id IN (SELECT id FROM twins WHERE tenant_id = auth.uid()));

-- Indexes
CREATE INDEX IF NOT EXISTS idx_my_table_twin_id ON my_table(twin_id);
```

**Rules**:
1. Test in Supabase SQL Editor first
2. Include RLS policies for every table
3. Use `IF NOT EXISTS` for idempotency
4. Document in `docs/ops/RUNBOOKS.md` if complex

## Verification Commands

### Single Source of Truth

**ALWAYS run before pushing**:
```powershell
# Windows
./scripts/preflight.ps1

# Linux/Mac
./scripts/preflight.sh
```

This runs:
- Frontend: `npm ci` → `npm run lint` → `npm run build`
- Backend: `pip install` → `flake8` (syntax) → `pytest`

**CI automatically runs** (`.github/workflows/lint.yml`):
- Same checks on every PR
- Must pass before merge

### Quick Verification

**Frontend**:
```bash
cd frontend
npm run lint
npm run build
```

**Backend**:
```bash
cd backend
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -v --tb=short -m "not network"
```

## Common AI Failure Patterns

### 1. Missing Database Columns

**Symptom**: `postgrest.exceptions.APIError: Could not find column 'X'`

**Root Cause**: Code references column that doesn't exist in database

**Fix**:
1. Check `backend/database/schema/` for column definition
2. Create migration if missing
3. Apply in Supabase SQL Editor
4. Reload PostgREST schema cache (Supabase Dashboard → Settings → API → Reload Schema)

**Prevention**: Always check schema before referencing columns

### 2. Schema Mismatches (tenant_id vs owner_id)

**Symptom**: Query returns empty when data exists

**Root Cause**: Wrong column name in query

**Fix**: Use `tenant_id` for ownership in twins table (NOT `owner_id`)

**Reference**: `docs/KNOWN_FAILURES.md` for full list

### 3. Missing React Hooks in Imports

**Symptom**: `Cannot find name 'useCallback'` or similar

**Root Cause**: Hook used but not imported

**Fix**: Add ALL React hooks to import upfront
```typescript
// ✅ CORRECT
import { useState, useEffect, useCallback, useMemo } from 'react';

// ❌ WRONG
import { useState } from 'react';  // Missing hooks that are used later
```

### 4. Files Not Tracked by Git

**Symptom**: Works locally, missing in CI/Vercel

**Root Cause**: Files not added to git

**Fix**: 
```bash
git ls-files <path>  # Verify file is tracked
git add -f <path>    # Force add if needed
```

**Prevention**: Always check `git status` before committing

### 5. Case Sensitivity Issues (Windows vs Linux)

**Symptom**: Works on Windows, fails in CI

**Root Cause**: Case-sensitive filesystem in Linux

**Fix**: Use `git mv` to fix casing
```bash
git mv Folder __tmp__
git mv __tmp__ folder
```

**Prevention**: Use consistent casing from the start

### 6. CORS Errors

**Symptom**: `blocked by CORS policy`

**Root Cause**: Origin not in `allowed_origins` in `backend/main.py`

**Fix**: Add origin to `allowed_origins` list
```python
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,...").split(",")
```

### 7. JWT Authentication Failures

**Symptom**: `401 Unauthorized` or `Invalid JWT signature`

**Root Cause**: JWT secret mismatch or missing audience

**Fix**: 
1. Get correct secret from Supabase Dashboard → Settings → API → JWT Secret
2. Verify `JWT_SECRET` in backend `.env` matches
3. Check `auth_guard.py` uses correct audience ("authenticated")

**Reference**: `docs/ops/AUTH_TROUBLESHOOTING.md` for detailed debugging

### 8. Breaking Existing Routers/Endpoints

**Symptom**: API contract changes break frontend

**Root Cause**: Changed request/response structure without updating frontend

**Fix**: 
- Maintain backward compatibility OR
- Update frontend in same PR
- Document breaking changes in PR description

**Prevention**: Check `docs/api_contracts.md` before changing endpoints

### 9. .gitignore Too Broad

**Symptom**: `Module not found: @/lib/...`

**Root Cause**: Pattern like `lib/` excludes `frontend/lib/`

**Fix**: Use specific paths like `backend/lib/` not `lib/`

### 10. Missing Multi-Tenant Filters

**Symptom**: Users see other users' data

**Root Cause**: Query doesn't filter by `tenant_id` or `twin_id`

**Fix**: ALWAYS filter by `tenant_id` or `twin_id` in queries
```python
# ✅ CORRECT
result = supabase.table("twins").select("*").eq("tenant_id", user["tenant_id"]).execute()

# ❌ WRONG - No filter
result = supabase.table("twins").select("*").execute()
```

## Reference Documents

- **Project Context**: `CLAUDE.md`
- **Coding Standards**: `.agent/CODING_STANDARDS.md`
- **Operational Brief**: `docs/ops/AGENT_BRIEF.md`
- **Known Failures**: `docs/KNOWN_FAILURES.md`
- **Quality Gate**: `docs/ops/QUALITY_GATE.md`
- **Auth Troubleshooting**: `docs/ops/AUTH_TROUBLESHOOTING.md`
- **API Contracts**: `docs/api_contracts.md`
- **Recursive Prompting System**: `docs/ai/recursive_system.md` - How the system improves itself

## Pre-Flight Checklist

Before every commit:
- [ ] Ran `./scripts/preflight.ps1` (exit code 0)
- [ ] Checked `git status` for untracked files
- [ ] Verified new files with `git ls-files <path>`
- [ ] All React hooks added to imports
- [ ] No broad patterns in `.gitignore`
- [ ] Migration tested in Supabase SQL Editor (if applicable)
- [ ] Auth checks use `Depends(get_current_user)`
- [ ] Queries filter by `tenant_id` or `twin_id`
- [ ] No secrets or PII in logs

## Emergency Rollback

If a change breaks production:

1. **Vercel (Frontend)**: Dashboard → Deployments → Promote previous deployment
2. **Render (Backend)**: Dashboard → Events → Rollback
3. **Git**: `git revert HEAD --no-edit && git push origin main`

See `docs/ops/QUALITY_GATE.md` for detailed rollback procedures.

