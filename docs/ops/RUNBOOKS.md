# Runbooks

> Build/deploy troubleshooting, env var checklist, and request tracing.

## Vercel Troubleshooting

### Build Fails with "Module not found"

**Symptoms:**
```
Module not found: Can't resolve '@/lib/context/TwinContext'
```

**Diagnosis:**
1. Check if file exists locally: `ls frontend/lib/context/TwinContext.tsx`
2. Check if tracked by Git: `git ls-files frontend/lib/context/TwinContext.tsx`

**Root Causes:**
- `.gitignore` has broad pattern like `lib/` ignoring the folder
- File was never committed
- Case mismatch (Windows vs Linux)

**Fix:**
```powershell
# Fix .gitignore (change `lib/` to `backend/lib/`)
# Then force-add:
git add -f frontend/lib/
git commit -m "Fix: Add missing lib files"
git push
```

### TypeScript Error: "Cannot find name"

**Symptoms:**
```
Type error: Cannot find name 'useCallback'.
```

**Fix:**
Add missing hook to import:
```typescript
import React, { useState, useEffect, useCallback } from 'react';
```

### Build Uses Old Commit

**Symptoms:** Vercel shows success but old code

**Fix:**
1. Check Vercel Dashboard → Deployments → Commit SHA
2. Confirm it matches your latest: `git log -1 --oneline`
3. If mismatched, trigger redeploy in Vercel

---

## Render Troubleshooting

### "No open ports detected"

**Cause:** Start command not binding to correct port

**Fix:** Ensure start command uses `$PORT`:
```yaml
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### JWT_SECRET Warning

**Symptoms:**
```
WARNING: JWT_SECRET is not properly configured for production!
```

**Fix:**
1. Get JWT Secret from Supabase → Settings → API → JWT Secret
2. Add to Render → Environment Variables → `JWT_SECRET`

---

## Environment Variables Checklist

### Vercel (Frontend)
| Variable | Source |
|----------|--------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Settings → API |
| `NEXT_PUBLIC_BACKEND_URL` | Your Render URL |

### Render (Backend)
| Variable | Source |
|----------|--------|
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_KEY` | Supabase → Settings → API (anon key) |
| `SUPABASE_SERVICE_KEY` | Supabase → Settings → API (service role) |
| `JWT_SECRET` | Supabase → Settings → API → JWT Secret |
| `OPENAI_API_KEY` | OpenAI Dashboard |
| `PINECONE_API_KEY` | Pinecone Console |
| `PINECONE_INDEX_NAME` | Your index name |
| `ALLOWED_ORIGINS` | Your Vercel URL |

---

## Tracing a Request

### Frontend → Backend → LLM

1. **Browser DevTools** (Network tab)
   - Find the API request (e.g., `/chat`)
   - Check request/response headers and body

2. **Render Logs**
   - Go to Render Dashboard → Logs
   - Filter by timestamp
   - Look for FastAPI logs

3. **LLM Call Tracing**
   - Check LangSmith if configured
   - Or add `print()` statements temporarily

### Database Query Tracing

1. **Supabase Dashboard** → SQL Editor
2. Run query manually to verify
3. Check RLS policies if 403/empty results

---

## Pinecone Sanity Checks

```python
# Quick check in Python
from pinecone import Pinecone
pc = Pinecone(api_key="your-key")
index = pc.Index("your-index")
print(index.describe_index_stats())
```

## Supabase Sanity Checks

```sql
-- Check table exists
SELECT * FROM twins LIMIT 1;

-- Check RLS is working
SELECT * FROM pg_policies WHERE tablename = 'twins';

-- Check user exists
SELECT * FROM users WHERE id = 'user-uuid';
```
