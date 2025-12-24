# Deployment Runbook

**Version:** 3.0  
**Date:** 2025-12-24  
**Status:** ✅ Production Ready

---

## Quick Start

### Prerequisites
- Supabase project with migrations applied
- Vercel account (frontend)
- Render/Railway account (backend)
- API keys: OpenAI, Pinecone

### Deploy Steps

1. **Apply Migrations** (Supabase SQL Editor)
   ```sql
   -- Run all migrations in order:
   -- backend/migrations/*.sql
   ```

2. **Backend** (Render/Railway)
   ```bash
   Build: pip install -r requirements.txt
   Start: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

3. **Frontend** (Vercel)
   ```bash
   Build: npm run build
   Output: .next
   ```

---

## Environment Variables

### Backend (Required)
```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...  # anon key
SUPABASE_SERVICE_KEY=eyJ...  # service role
JWT_SECRET=<from Supabase Dashboard → Settings → API>
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=digital-twin
ALLOWED_ORIGINS=https://yourapp.com
DEV_MODE=false
```

### Frontend (Required)
```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_BACKEND_URL=https://your-backend.onrender.com
```

---

## Health Checks

```bash
# Basic
curl https://api.yourapp.com/health

# Enhanced (Phase 10)
curl https://api.yourapp.com/metrics/health
```

---

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Basic health check |
| `/auth/sync-user` | User sync after OAuth |
| `/auth/my-twins` | List user's twins |
| `/cognitive/interview/{twin_id}` | Interview endpoint |
| `/chat/{twin_id}` | Chat with twin |
| `/metrics/health` | Service status |
| `/metrics/system` | System metrics |

---

## Post-Deploy Verification

1. ✅ Health check returns 200
2. ✅ Google OAuth login works
3. ✅ User created in database
4. ✅ Twin creation works
5. ✅ Right Brain interview loads
6. ✅ Chat sends/receives messages
7. ✅ Cross-tenant isolation verified

---

## Rollback

```bash
git revert HEAD
# Redeploy
```

---

## Phase 10 Migration

```sql
-- Required before first deploy
-- backend/migrations/phase10_metrics.sql
```

Creates: `metrics`, `usage_quotas`, `service_health_logs`

---

## Safe to Deploy: YES ✅