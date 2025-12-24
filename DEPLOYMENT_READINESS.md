# Deployment Readiness Report

**Date:** 2025-12-23  
**Stack:** Next.js → Vercel | FastAPI → Render/Railway | Supabase | Pinecone

---

## 1. Frontend Readiness Checklist

### 1.1 Required Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ Yes | Supabase project URL | `https://xyz.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ Yes | Supabase anon/public key | `eyJhbGci...` |
| `NEXT_PUBLIC_BACKEND_URL` | ✅ Yes | Backend API URL | `https://api.yourapp.com` |
| `NEXT_PUBLIC_API_URL` | ⚠️ Alias | Same as BACKEND_URL (consolidate) | `https://api.yourapp.com` |
| `NEXT_PUBLIC_DEV_TOKEN` | ❌ Remove | Dev-only, DO NOT use in production | N/A |
| `NEXT_PUBLIC_FRONTEND_URL` | Optional | For invitation URLs | `https://yourapp.com` |

### 1.2 Auth Redirect URLs (Supabase Dashboard)

Configure in Supabase → Authentication → URL Configuration:

```
# Site URL
https://yourapp.com

# Redirect URLs (add all)
https://yourapp.com/auth/callback
http://localhost:3000/auth/callback  (for local dev)
```

### 1.3 Protected Route Behavior

| Route | Protection | Behavior |
|-------|------------|----------|
| `/dashboard/*` | ✅ Protected | Redirects to `/auth/login` if no session |
| `/onboarding/*` | ✅ Protected | Redirects to `/auth/login` if no session |
| `/auth/*` | Redirects authenticated | Sends logged-in users to `/dashboard` |
| `/share/*` | Public | No auth required |
| `/` | Public | Landing page |

### 1.4 Build Configuration

```bash
# Build command
npm run build

# Output directory (for Vercel)
.next

# Node version
18.x or 20.x
```

### 1.5 Known Runtime Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `NEXT_PUBLIC_DEV_TOKEN` in production | HIGH | Must NOT be set in production env |
| SSR auth hydration | LOW | Supabase auth-helpers handles this |
| API URL mismatch | MEDIUM | Ensure `NEXT_PUBLIC_BACKEND_URL` points to production backend |

---

## 2. Backend Readiness Checklist

### 2.1 Required Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SUPABASE_URL` | ✅ Yes | Supabase project URL | `https://xyz.supabase.co` |
| `SUPABASE_KEY` | ✅ Yes | Supabase anon key | `eyJhbGci...` |
| `SUPABASE_SERVICE_KEY` | ✅ Yes | Supabase service role key | `eyJhbGci...` |
| `JWT_SECRET` | ✅ Yes | Supabase JWT secret | Copy from Supabase Dashboard |
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API key | `sk-...` |
| `PINECONE_API_KEY` | ✅ Yes | Pinecone API key | `pc-...` |
| `PINECONE_INDEX_NAME` | ✅ Yes | Pinecone index name | `digital-twin` |
| `ALLOWED_ORIGINS` | ✅ Yes | CORS allowlist | `https://yourapp.com` |
| `DEV_MODE` | ✅ Set to `false` | Disables dev bypass | `false` |
| `HOST` | Optional | Server host | `0.0.0.0` |
| `PORT` | Optional | Server port | `8000` |

### 2.2 JWT Verification Logic

**Location:** `backend/modules/auth_guard.py`

```python
# Uses jose library to decode Supabase JWT
SECRET_KEY = os.getenv("JWT_SECRET", "secret")
ALGORITHM = "HS256"
payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

**Critical:** `JWT_SECRET` must match the JWT secret from:
`Supabase Dashboard → Settings → API → JWT Secret`

### 2.3 CORS Configuration

**Location:** `backend/main.py`

```python
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2.4 Health Check Endpoint

```
GET /health
Response: {"status": "healthy", "service": "verified-digital-twin-brain-api", "version": "1.0.0"}
```

### 2.5 Error Handling

| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid JWT |
| 403 | User doesn't have access to resource |
| 404 | Resource not found |
| 500 | Server error (logged to stdout) |

### 2.6 Service-Role Key Usage

**Location:** `backend/modules/observability.py`

Used for: Database operations that bypass RLS (backend is trusted)

```python
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
```

---

## 3. Supabase Readiness Checklist

### 3.1 Required Tables (P0)

| Table | Purpose | Required |
|-------|---------|----------|
| `users` | User profiles | ✅ Yes |
| `tenants` | Workspace/org | ✅ Yes |
| `twins` | Digital twin configs | ✅ Yes |
| `conversations` | Chat sessions | ✅ Yes |
| `messages` | Chat messages | ✅ Yes |
| `specializations` | Twin templates | ✅ Yes |
| `verified_qna` | Knowledge base | Optional |
| `sources` | Ingested content | Optional |

### 3.2 RLS Status (Critical)

| Table | RLS Status | Notes |
|-------|------------|-------|
| All tables | ✅ ON | Migration `enable_rls_all_tables.sql` applied |
| Backend access | ✅ Bypassed | Using service_role key |

### 3.3 Auth Providers

| Provider | Status | Notes |
|----------|--------|-------|
| Google OAuth | ✅ Required | Configure in Supabase Dashboard |
| Email/Password | Optional | Works out of box |
| Magic Link | Optional | Works out of box |

### 3.4 OAuth Configuration

**Supabase Dashboard → Authentication → Providers → Google:**

1. Enable Google provider
2. Add Google OAuth Client ID
3. Add Google OAuth Client Secret
4. Set authorized redirect URI in Google Console:
   - `https://xyz.supabase.co/auth/v1/callback`

---

## 4. External Dependencies

### 4.1 Pinecone

| Check | Status | Action if Missing |
|-------|--------|-------------------|
| Index exists | ⚠️ Verify | Create index named in `PINECONE_INDEX_NAME` |
| Dimension | Must be 1536 | For OpenAI embeddings |
| Environment | Verify region | Match in Pinecone console |

### 4.2 OpenAI

| Usage Location | Purpose |
|----------------|---------|
| `modules/agent.py` | Chat completions |
| `modules/clients.py` | Embeddings (text-embedding-ada-002) |

### 4.3 Background Jobs

| Component | Status | Notes |
|-----------|--------|-------|
| Scribe engine | Fire-and-forget | Non-blocking, failures logged |
| No cron jobs | ✅ OK | None required for P0 |
| No queues | ✅ OK | In-memory only (defaults to sync) |

---

## 5. DEPLOYMENT BLOCKERS

### Blocker 1: NEXT_PUBLIC_DEV_TOKEN Usage

**Why it blocks:** Several frontend components use `NEXT_PUBLIC_DEV_TOKEN` as fallback auth instead of real Supabase JWT.

**Files involved:**
- `components/Brain/BrainGraph.tsx`
- `components/Chat/InterviewInterface.tsx`
- `components/Chat/ChatInterface.tsx`
- `app/dashboard/api-keys/page.tsx`
- `app/dashboard/users/page.tsx`

**Minimal fix:** These components must use Supabase session token. The TwinContext provider already provides auth - these need to use `getToken()` from context.

**Severity:** HIGH - Auth bypass in production

### Blocker 2: Inconsistent API URL Variables

**Why it blocks:** Frontend uses both `NEXT_PUBLIC_BACKEND_URL` and `NEXT_PUBLIC_API_URL` - confusing and error-prone.

**Files involved:** Multiple components (see grep results)

**Minimal fix:** Standardize on `NEXT_PUBLIC_BACKEND_URL` everywhere.

**Severity:** MEDIUM - Deployment confusion

---

## 6. PRODUCTION CONFIGURATION

### 6.1 Frontend .env (Vercel)

```bash
# Required
NEXT_PUBLIC_SUPABASE_URL=https://xyz.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_BACKEND_URL=https://api.yourapp.com

# Optional
NEXT_PUBLIC_FRONTEND_URL=https://yourapp.com

# DO NOT SET:
# NEXT_PUBLIC_DEV_TOKEN (never set in production)
```

### 6.2 Backend .env (Render/Railway)

```bash
# Required - Core
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
JWT_SECRET=<copy from Supabase Dashboard → Settings → API → JWT Secret>
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pc-...
PINECONE_INDEX_NAME=digital-twin

# Required - Production
DEV_MODE=false
ALLOWED_ORIGINS=https://yourapp.com,https://www.yourapp.com

# Optional
PORT=8000
HOST=0.0.0.0
```

### 6.3 Supabase OAuth Redirect URLs

```
# Production
https://yourapp.com/auth/callback

# Local development 
http://localhost:3000/auth/callback
```

---

## 7. P0 Deployment Scope (Explicit)

### ✅ Allowed Features

1. Google OAuth login
2. User sync into `users` + `tenants` tables
3. One twin creation/loading
4. One working chat interaction

### ❌ Explicitly Deferred

- Analytics dashboards
- Persistent memory systems
- Slack/SMS/WhatsApp/Voice
- Stripe payments
- Advanced onboarding flows
- UX polish beyond blocking issues

---

## 8. Definition of Done

| Requirement | Status |
|-------------|--------|
| DEPLOYMENT_READINESS.md exists | ✅ This document |
| DEPLOYMENT_RUNBOOK.md exists | 🔄 Next step |
| All P0 blockers resolved or listed | ✅ Listed above |
| App deployable without manual guesswork | ⚠️ After blockers fixed |
