# Quick Start Checklist - After SQL Diagnostic

You've run the SQL queries. Use this checklist to proceed:

---

## ✅ STEP 1: Review SQL Results

**What did you find?**
- [x] ✅ **Database is ready!** All tables, RPC functions, and RLS are enabled
- [x] Tables count: 25+ (good!)
- [x] All critical tables exist
- [x] RPC functions exist
- [x] RLS enabled

**✅ Database setup complete! Skip to STEP 4 (Environment Variables)**

---

## 📋 STEP 2: Run Missing Migrations

**Location:** Supabase Dashboard → SQL Editor

**Run migrations in this order** (copy-paste from `backend/database/migrations/`):

1. [ ] `migration_phase4_verified_qna.sql`
2. [ ] `migration_phase5_access_groups.sql`
3. [ ] `migration_phase6_mind_ops.sql`
4. [ ] `migration_phase7_omnichannel.sql`
5. [ ] `migration_phase8_actions_engine.sql`
6. [ ] `migration_phase9_governance.sql`
7. [ ] `migration_phase3_5_gate1_specialization.sql`
8. [ ] `migration_phase3_5_gate2_tenant_guard.sql`
9. [ ] `migration_phase3_5_gate3_fix_rls.sql` ⚠️ **IMPORTANT - RPC functions**
10. [ ] `migration_phase3_5_gate3_graph.sql`
11. [ ] `migration_interview_sessions.sql`
12. [ ] `migration_gate5_versioning.sql`
13. [ ] `enable_rls_all_tables.sql` (from `backend/migrations/`)
14. [ ] `phase10_metrics.sql` (from `backend/migrations/`) - Optional

**After running migrations:**
- [ ] Go to Supabase Dashboard → Settings → Database → **"Reload Schema Cache"**

---

## ⚙️ STEP 3: Run Migrations (SKIP - Already Done!)

**✅ Database is already set up correctly - Skip this step!**

## ⚙️ STEP 4: Check Environment Variables (DO THIS NOW!)

### Backend (`backend/.env`)

Required variables:
- [ ] `SUPABASE_URL=https://xxx.supabase.co`
- [ ] `SUPABASE_KEY=eyJ...` (anon key)
- [ ] `SUPABASE_SERVICE_KEY=eyJ...` (service_role key)
- [ ] `JWT_SECRET=...` (from Supabase Dashboard → Settings → API)
- [ ] `OPENAI_API_KEY=sk-...`
- [ ] `PINECONE_API_KEY=...`
- [ ] `PINECONE_INDEX_NAME=digital-twin`
- [ ] `ALLOWED_ORIGINS=http://localhost:3000`
- [ ] `DEV_MODE=false`

**Get values from:**
- Supabase Dashboard → Settings → API
- OpenAI Dashboard → API Keys
- Pinecone Dashboard → API Keys

### Frontend (`frontend/.env.local`)

Required variables:
- [ ] `NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co`
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...` (same as SUPABASE_KEY)
- [ ] `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`

---

## 🔍 STEP 5: Verify Pinecone Index

- [ ] Go to Pinecone Dashboard: https://app.pinecone.io
- [ ] Check if index named `digital-twin` (or your `PINECONE_INDEX_NAME`) exists
- [ ] If missing: Create index (Dimension: **3072**, Metric: **cosine**)

---

## 🧪 STEP 6: Test Backend

```bash
cd backend
python main.py
```

- [ ] Backend starts without errors
- [ ] See "Application startup complete"
- [ ] In another terminal: `curl http://localhost:8000/health`
- [ ] Response: `{"status":"healthy",...}`

---

## 🌐 STEP 7: Test Frontend

```bash
cd frontend
npm run dev
```

- [ ] Frontend starts without errors
- [ ] Open http://localhost:3000
- [ ] Browser console: No red errors
- [ ] Page loads successfully

---

## 👤 STEP 8: Test User Flow

- [ ] Click "Login" / "Sign in with Google"
- [ ] Complete OAuth flow
- [ ] Redirected to dashboard/onboarding
- [ ] Backend logs show: "User created successfully"
- [ ] Create a twin (if onboarding)
- [ ] Send a chat message
- [ ] Receive response (even if "I don't know")

---

## 🎯 CURRENT STATUS

**✅ Database: COMPLETE**
**⏭️ Next: Check Environment Variables**

Run: `python scripts/check_env_vars.py`

---

## 📚 Need Help?

- **Database issues:** See `docs/NEXT_STEPS_AFTER_SQL_CHECK.md`
- **Known bugs:** See `docs/KNOWN_FAILURES.md`
- **Environment setup:** See `DEPLOYMENT_READINESS.md`

---

## ⚡ Quick Commands Reference

```bash
# Check backend health
curl http://localhost:8000/health

# Check enhanced health (if Phase 10 migration applied)
curl http://localhost:8000/metrics/health

# Test user sync (need JWT token from browser)
curl -X POST http://localhost:8000/auth/sync-user \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```
