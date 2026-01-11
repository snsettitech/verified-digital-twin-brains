# Deployment Next Steps

**Commit:** `b4a5d13` - P0-P1 Reliability & Security Hardening: Complete P0 tasks (Day 5)  
**Status:** ✅ Code pushed to `main` branch  
**Date:** 2025-01-XX

## ✅ Completed

1. **Code Committed**: All P0 reliability and security hardening changes committed
2. **Pushed to GitHub**: Changes pushed to `origin/main`
3. **CI/CD Triggered**: GitHub Actions workflow (`.github/workflows/lint.yml`) will run automatically

## 🔄 Automatic Processes

### CI/CD Pipeline
The GitHub Actions workflow (`.github/workflows/lint.yml`) will automatically:
- ✅ Test backend (lint, syntax check, pytest)
- ✅ Test frontend (lint, typecheck, build)
- ✅ Verify all changes pass CI checks

**Check CI Status:**
- Visit: `https://github.com/snsettitech/verified-digital-twin-brain/actions`
- Look for workflow run triggered by commit `b4a5d13`

### Deployment (if configured)
- **Vercel (Frontend)**: Auto-deploys on push to `main` (if connected)
- **Render/Railway (Backend)**: Auto-deploys on push to `main` (if configured)

## ⚠️ Required Manual Steps

### 1. Database Migrations (CRITICAL - DO FIRST)

**Run in Supabase SQL Editor (in order):**

```sql
-- 1. Security hardening (if not already applied)
-- File: backend/database/migrations/migration_security_definer_hardening.sql
\i backend/database/migrations/migration_security_definer_hardening.sql

-- 2. Add graph_extraction job type (NEW - REQUIRED)
-- File: backend/database/migrations/migration_add_graph_extraction_job_type.sql
\i backend/database/migrations/migration_add_graph_extraction_job_type.sql

-- 3. Verify migration applied
SELECT constraint_name, check_clause 
FROM information_schema.check_constraints 
WHERE table_name = 'jobs' AND constraint_name = 'valid_job_type';
-- Should show: job_type IN ('ingestion', 'reindex', 'health_check', 'other', 'graph_extraction')
```

**⚠️ IMPORTANT:** Without these migrations:
- Graph extraction jobs will fail (job_type constraint violation)
- SECURITY DEFINER functions may not be hardened (security risk)

### 2. Verify CI/CD Success

Wait for GitHub Actions to complete (usually 3-5 minutes):
- ✅ Backend lint/tests pass
- ✅ Frontend lint/typecheck/build pass

If CI fails:
- Check GitHub Actions logs
- Fix issues and push again

### 3. Deployment Platforms

#### Vercel (Frontend)
- Check Vercel Dashboard → Deployments
- Should auto-deploy if connected to GitHub repo
- Verify build succeeds
- Check environment variables are set

#### Render/Railway (Backend)
- Check platform dashboard → Deployments
- Should auto-deploy if connected to GitHub repo
- Verify build succeeds
- Check environment variables are set
- **Important**: Ensure worker process is configured (for graph extraction jobs)

### 4. Post-Deployment Verification

#### Backend Health Check
```bash
curl https://your-backend-url.com/health
# Expected: {"status": "healthy", ...}
```

#### Graph Job Status Endpoint
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://your-backend-url.com/twins/{twin_id}/graph-job-status
# Should return job status (may be empty initially)
```

#### Security Verification
1. **Supabase Dashboard → Database → Advisors**
   - Should show **zero** "function_search_path_mutable" findings
   - If findings exist, run `migration_security_definer_hardening.sql`

2. **Auth Tests**
   - Try accessing another tenant's twin → Should return 404
   - Try accessing another tenant's source → Should return 404

## 📋 Deployment Checklist

- [ ] Database migrations applied (Supabase SQL Editor)
- [ ] CI/CD pipeline passes (GitHub Actions)
- [ ] Frontend deploys successfully (Vercel)
- [ ] Backend deploys successfully (Render/Railway)
- [ ] Environment variables configured (all platforms)
- [ ] Health check passes (`/health` endpoint)
- [ ] Graph job status endpoint works
- [ ] Security verification (Database Advisors - zero findings)
- [ ] Auth tests pass (wrong tenant → 404)

## 🚨 If Deployment Fails

### Backend Build Fails
1. Check Render/Railway logs
2. Verify Python version matches `.python-version` (3.12)
3. Check `requirements.txt` is valid
4. Verify environment variables are set

### Frontend Build Fails
1. Check Vercel logs
2. Verify Node version matches `.nvmrc` (20)
3. Check `package-lock.json` is in sync
4. Verify environment variables are set

### Database Migration Fails
1. Check Supabase SQL Editor error message
2. Verify migrations are run in order
3. Check if migrations were already applied (idempotent, safe to re-run)

## 📊 What Changed

### Files Modified (66 files)
- **Backend**: Auth guard, routers, job system, graph extraction
- **Frontend**: Package files (minor updates)
- **CI/CD**: GitHub Actions workflow
- **Migrations**: New migration for graph_extraction job type
- **Documentation**: Deployment guides and status docs

### Key Features Added
1. **Ownership Verification**: `verify_source_ownership()`, `verify_conversation_ownership()`
2. **Graph Job Queue**: Observable, reliable graph extraction with retries
3. **Job Status Endpoint**: `/twins/{twin_id}/graph-job-status`
4. **CI/CD Improvements**: Version file usage for consistency

## 🎯 Success Criteria

After deployment:
- ✅ All 5 golden flows work end-to-end
- ✅ Zero SECURITY DEFINER vulnerabilities
- ✅ Graph jobs visible in status endpoint
- ✅ Auth tests pass (wrong tenant → 404)
- ✅ 10 consecutive successful deployments

---

**Next Steps After Deployment:**
1. Monitor deployment logs
2. Run post-deployment verification
3. Test golden flows in staging
4. Proceed to P1 tasks (LangGraph Durability, GraphRAG-Lite, Retrieval Quality Gates)

