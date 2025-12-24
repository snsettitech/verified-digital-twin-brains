# Deployment Runbook (Security Hardened)

**Version:** 2.0 (Corrected)  
**Date:** 2025-12-23  
**Status:** Ready for 10 External Users

---

## 1. Overall Direction Confirmation

### ✅ Directionally Correct For:

| Requirement | Status | Notes |
|------------|--------|-------|
| P0 Beta Deployment | ✅ Yes | All foundational components implemented |
| 10 Real Users | ✅ Yes | Auth, isolation, rate limiting in place |
| Delphi-style Credibility | ✅ Yes | KB-first grounding, confidence fallbacks |

---

## 2. Security Fixes Applied

### 2.1 Production Auth Bypass: REMOVED ✅

**Previous State:** `DEV_MODE=true` allowed fake development tokens to bypass auth.

**Current State:** 
- DEV_MODE bypass logic **completely removed** from `auth_guard.py`
- All requests now require valid Supabase JWT or API key
- No emergency shortcuts exist (rollback-based recovery only)

**File:** `backend/modules/auth_guard.py`

### 2.2 JWT Verification: STRENGTHENED ✅

| Check | Status | Implementation |
|-------|--------|----------------|
| Signature verified | ✅ | `jwt.decode()` with `SUPABASE_JWT_SECRET` |
| Expiry enforced | ✅ | `options={"verify_exp": True}` |
| Supabase JWT secret used | ✅ | From `JWT_SECRET` env var |
| Tenant from DB (not JWT) | ✅ | Lookup via `users.tenants(id)` |
| Weak secret warning | ✅ | Startup stderr warning |

### 2.3 Tenant Isolation: ENFORCED ✅

| Control | Status | Location |
|---------|--------|----------|
| `tenant_id` on domain tables | ✅ | twins, via owner_id lookup |
| RLS enabled | ✅ | All 30+ tables via migration |
| `verify_twin_access()` | ✅ | Checks `twins.owner_id == user_id` |
| Backend uses service_role | ✅ | Bypasses RLS for trusted operations |

---

## 3. Security & Isolation Checklist

### Pre-Deploy Verification

```bash
# 1. Verify RLS is enabled (run in Supabase SQL Editor)
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public';
-- All tables should show rowsecurity = true

# 2. Verify no open policies (run in Supabase SQL Editor)
SELECT schemaname, tablename, policyname, permissive, cmd
FROM pg_policies
WHERE schemaname = 'public';
-- Should show service_role_bypass policies only
```

### Mandatory Smoke Test: Cross-Tenant Isolation

After deploy, test with 2 real users:

```
1. User A creates a twin → Record twin_id_a
2. User B logs in
3. User B calls: GET /twins/{twin_id_a}/graph
4. EXPECTED: 403 Forbidden ("You do not have access to this twin")
5. User B calls: POST /chat/{twin_id_a}
6. EXPECTED: 403 Forbidden
```

**If User B can access User A's twin: STOP DEPLOYMENT IMMEDIATELY**

---

## 4. Rate Limiting & Abuse Protection

### Implemented Controls

| Control | Status | Configuration |
|---------|--------|---------------|
| Per-session rate limit | ✅ | 30 requests/hour for widgets |
| Request size limit | ⚠️ | FastAPI default (1MB) |
| Token limit per response | ⚠️ | OpenAI model default |
| Logging with context | ✅ | stdout with user context |

### Recommended Cost Guardrails

Add to backend `.env`:

```bash
# OpenAI spending controls (implement in agent.py if needed)
MAX_TOKENS_PER_REQUEST=2000
DAILY_OPENAI_SPEND_CEILING_USD=50
```

---

## 5. Operational Safety

### 5.1 Rollback Strategy (Primary Failure Response)

**If auth breaks:**

1. **DO NOT** enable DEV_MODE (bypass no longer exists)
2. Check JWT_SECRET matches Supabase
3. Verify Supabase redirect URLs
4. Roll back to previous commit if needed: `git revert HEAD`
5. Redeploy previous working version

### 5.2 Failure Handling

| Failure | Response |
|---------|----------|
| Supabase unavailable | 500 error, user sees "Service temporarily unavailable" |
| Pinecone unavailable | Chat degrades gracefully, returns "I don't have context" |
| OpenAI unavailable | 500 error, logged, user sees error message |
| Invalid JWT | 401 with "Token has expired" or "Invalid token" |
| Wrong tenant access | 403 with "You do not have access to this twin" |

---

## 6. Deployment Steps

### Step 1: Backend (Render/Railway)

```bash
# Required Environment Variables
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_KEY=eyJhbGci...           # anon key
SUPABASE_SERVICE_KEY=eyJhbGci...   # service role key
JWT_SECRET=<EXACT copy from Supabase Dashboard → Settings → API → JWT Secret>
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=digital-twin

# Production settings (CRITICAL)
DEV_MODE=false
ALLOWED_ORIGINS=https://yourapp.com,https://www.yourapp.com
HOST=0.0.0.0
PORT=8000
```

**Build Command:** `pip install -r requirements.txt`  
**Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Step 2: Frontend (Vercel)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xyz.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...
NEXT_PUBLIC_BACKEND_URL=https://your-backend.onrender.com
```

**DO NOT SET:** `NEXT_PUBLIC_DEV_TOKEN` (removed from codebase)

### Step 3: Supabase Configuration

**Authentication → URL Configuration:**
```
Site URL: https://yourapp.com
Redirect URLs:
- https://yourapp.com/auth/callback
```

**Authentication → Providers → Google:**
- Enable
- Add Client ID and Secret
- Google Console redirect: `https://xyz.supabase.co/auth/v1/callback`

---

## 7. Post-Deploy Smoke Tests

### Test 1: Health Check
```bash
curl https://your-backend.onrender.com/health
# Expected: {"status": "healthy"}
```

### Test 2: Auth Flow
1. Open `https://yourapp.com`
2. Click "Login with Google"
3. Complete OAuth
4. Check: Redirected to `/dashboard`
5. Check: User in `public.users` table
6. Check: Tenant in `public.tenants` table

### Test 3: Twin Access
1. Complete onboarding (create twin)
2. Navigate to Right Brain
3. Check: Twin loads (not 403)
4. Check: Graph visualization appears

### Test 4: Chat E2E
1. Send message in chat
2. Check: Response returns
3. Check: `conversations` and `messages` have rows

### Test 5: Cross-Tenant Isolation ⚠️ CRITICAL
1. Log in as User A, create twin, record twin_id
2. Log out, log in as User B
3. Try to access User A's twin via API
4. Expected: 403 Forbidden

---

## 8. One-Week Scope (Realistic)

### ✅ In Scope for Beta

| Feature | Status |
|---------|--------|
| Google OAuth login | ✅ |
| User + Tenant sync | ✅ |
| Twin creation/loading | ✅ |
| KB-grounded chat | ✅ |
| Confidence scores | ✅ |
| Session memory only | ✅ |

### ❌ Explicitly Deferred

| Feature | Reason |
|---------|--------|
| Full persistent memory | Complexity, not P0 |
| Multi-channel (Slack/SMS) | Integration work |
| Analytics dashboards | Polish, not P0 |
| Payment/billing | Not needed for beta |
| Advanced onboarding | Polish, not P0 |

---

## 9. Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| JWT_SECRET misconfiguration | HIGH | Startup warning + clear 500 error |
| First user has no twin | LOW | Redirect to onboarding |
| OpenAI rate limits | MEDIUM | Graceful degradation |
| Pinecone cold start | LOW | Retry logic in agent |

---

## 10. Final Decision

### Safe to Onboard 10 Users: **YES** ✅

**Justification:**

1. **Auth bypass removed** - No DEV_MODE shortcuts exist
2. **JWT verification complete** - Signature, expiry, Supabase secret
3. **Tenant isolation enforced** - RLS + verify_twin_access
4. **Rate limiting exists** - Per-session limits for widgets
5. **Clear error handling** - 401/403/500 with descriptive messages
6. **Rollback strategy defined** - Git revert, no emergency bypasses

**Conditions:**

- [ ] `JWT_SECRET` set to exact Supabase value
- [ ] `DEV_MODE=false` in production
- [ ] Cross-tenant isolation smoke test passes
- [ ] Health check returns 200

---

## Appendix: File Changes Summary

| File | Change |
|------|--------|
| `backend/modules/auth_guard.py` | Removed DEV_MODE bypass, strengthened JWT |
| `backend/main.py` | /health endpoint, startup validation |
| `frontend/components/Chat/InterviewInterface.tsx` | Supabase auth |
| `frontend/components/Brain/BrainGraph.tsx` | Supabase auth |
| `frontend/components/Chat/ChatInterface.tsx` | Supabase auth |
| `DEPLOYMENT_READINESS.md` | Created |
| `DEPLOYMENT_RUNBOOK.md` | This file (corrected) |

---

## Phase 10 Additions (Enterprise Scale)

### New Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /metrics/health` | Enhanced health check (Supabase, Pinecone, OpenAI) |
| `GET /metrics/system` | System-wide metrics summary |
| `GET /metrics/usage/{twin_id}` | Per-twin usage metrics |
| `GET /metrics/quota/{tenant_id}` | Tenant quota status |

### Migration Required

Apply the Phase 10 migration in Supabase SQL Editor:

```sql
-- Run contents of: backend/migrations/phase10_metrics.sql
-- Creates: metrics, usage_quotas, service_health_logs tables
```

### Dashboard Access

After deployment, the metrics dashboard is available at:
- `/dashboard/metrics` - System metrics, health status, quota usage

### Post-Deploy Verification

```bash
# Test enhanced health check
curl https://your-backend.onrender.com/metrics/health
# Expected: { "status": "healthy", "services": { ... } }
```

