# Roadmap: Auth + Multi-Tenancy (Epic A)

> Foundation for all other epics. Must be bulletproof.

## Overview

Implement Supabase Auth integration with FastAPI backend, enforcing multi-tenant isolation via RLS policies and API middleware.

## Tasks

### A1: Supabase Project Setup
**Status**: Not Started
**Estimated**: 2 hours

- [ ] Create Supabase project (if not exists)
- [ ] Configure auth providers (email/password)
- [ ] Create tenants table
- [ ] Create users table (synced from auth.users)
- [ ] Set up RLS policies for tenants/users

**Acceptance Criteria**:
- Supabase project accessible
- Auth flow works in Supabase dashboard
- RLS policies active and tested

**Test Plan**:
```sql
-- As anon user, should see nothing
SELECT * FROM tenants; -- Returns 0 rows
SELECT * FROM users; -- Returns 0 rows

-- After sign in, should see own data only
SELECT * FROM tenants WHERE id = auth.uid(); -- Returns own tenant
```

---

### A2: Database Migrations
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: A1

- [ ] Create migration: 001_tenants.sql
- [ ] Create migration: 002_users.sql
- [ ] Create migration: 003_add_rls_policies.sql
- [ ] Create user sync trigger from auth.users
- [ ] Test migrations locally

**Acceptance Criteria**:
- All migrations run without error
- User sync trigger works on signup
- RLS policies enforced

**Test Plan**:
```bash
# Run migrations
supabase db push

# Test user sync
supabase functions invoke sync-user --body '{"event":"INSERT"}'
```

---

### A3: FastAPI Backend Setup
**Status**: Not Started
**Estimated**: 3 hours

- [ ] Initialize FastAPI project structure
- [ ] Add dependencies (supabase, pydantic, etc.)
- [ ] Create config module with env vars
- [ ] Create Supabase client utilities
- [ ] Set up CORS for frontend

**Acceptance Criteria**:
- Backend starts without error
- Health endpoint returns 200
- Environment variables loaded

**Test Plan**:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Test health
curl http://localhost:8000/health
```

---

### A4: JWT Auth Middleware
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: A3

- [ ] Create JWT verification dependency
- [ ] Extract user_id and tenant_id from token
- [ ] Create CurrentUser model
- [ ] Add protected route decorator
- [ ] Handle auth errors gracefully

**Acceptance Criteria**:
- All protected routes require valid JWT
- Invalid/expired tokens return 401
- User context available in routes

**Security Requirements**:
- ⚠️ NEVER use service role key for user requests
- ✅ Use anon key + user JWT for RLS
- ✅ Validate JWT signature

**Test Plan**:
```python
# test_auth.py
def test_protected_route_without_token():
    response = client.get("/api/twins")
    assert response.status_code == 401

def test_protected_route_with_valid_token():
    token = create_test_token(user_id="123")
    response = client.get("/api/twins", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_protected_route_with_expired_token():
    token = create_expired_token()
    response = client.get("/api/twins", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
```

---

### A5: Tenant Isolation Middleware
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: A4

- [ ] Create TenantContext dependency
- [ ] Inject tenant_id into all DB queries
- [ ] Create Supabase client per-request with user JWT
- [ ] Add tenant_id to logging context

**Acceptance Criteria**:
- All queries scoped to tenant
- Cross-tenant access impossible
- Tenant context in all log entries

**Security Requirements**:
- ⚠️ tenant_id must come from JWT, never from request body
- ✅ RLS policies as second line of defense

**Test Plan**:
```python
# test_tenant_isolation.py
def test_user_cannot_access_other_tenant_data():
    # Create resources as tenant A
    response_a = client.post("/api/twins",
        headers=auth_header(tenant="A"),
        json={"name": "Twin A"})
    twin_id = response_a.json()["id"]

    # Try to access as tenant B - must fail
    response_b = client.get(f"/api/twins/{twin_id}",
        headers=auth_header(tenant="B"))
    assert response_b.status_code == 404
```

---

### A6: Next.js Frontend Setup
**Status**: Not Started
**Estimated**: 3 hours

- [ ] Initialize Next.js 14 project with App Router
- [ ] Add Supabase client library
- [ ] Create auth context/provider
- [ ] Set up environment variables
- [ ] Create basic layout

**Acceptance Criteria**:
- Frontend builds without error
- Supabase client configured
- Environment variables loaded

**Test Plan**:
```bash
cd frontend
npm install
npm run dev

# Open http://localhost:3000
# Should see landing page
```

---

### A7: Auth UI Components
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: A6

- [ ] Create sign up page
- [ ] Create sign in page
- [ ] Create auth callback handler
- [ ] Add protected route wrapper
- [ ] Create user profile dropdown

**Acceptance Criteria**:
- User can sign up with email
- User can sign in
- Protected pages redirect to login
- User can sign out

**Test Plan**:
```typescript
// e2e/auth.spec.ts
test('user can sign up', async ({ page }) => {
    await page.goto('/signup');
    await page.fill('[name=email]', 'test@example.com');
    await page.fill('[name=password]', 'SecurePass123!');
    await page.click('button[type=submit]');
    await expect(page).toHaveURL('/dashboard');
});

test('protected pages require auth', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL('/login');
});
```

---

### A8: User Sync Function
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: A2

- [ ] Create Supabase Edge Function or DB trigger
- [ ] Sync new auth.users to public.users
- [ ] Create tenant for new users
- [ ] Handle edge cases (duplicate, failed sync)

**Acceptance Criteria**:
- New signups create user + tenant records
- Users table stays in sync with auth.users
- Failed syncs are logged/retriable

**Test Plan**:
```sql
-- After signup, verify sync
SELECT * FROM auth.users WHERE email = 'test@example.com';
SELECT * FROM public.users WHERE email = 'test@example.com';
SELECT * FROM public.tenants WHERE id = (SELECT tenant_id FROM public.users WHERE email = 'test@example.com');
```

---

### A9: API Auth Endpoints
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: A4

- [ ] GET /api/auth/me - Get current user
- [ ] POST /api/auth/refresh - Refresh token (if needed)
- [ ] Document auth flow in API contracts

**Acceptance Criteria**:
- /me returns current user details
- Token refresh works
- API docs include auth info

**Test Plan**:
```python
def test_get_current_user():
    token = create_test_token(user_id="123", email="test@example.com")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
```

---

## Security Checklist

- [ ] JWT validation uses Supabase's public key
- [ ] RLS policies on all tables with tenant_id
- [ ] Service role key never exposed to client
- [ ] Service role key only used in background jobs
- [ ] CORS configured for production domains only
- [ ] Password requirements enforced
- [ ] Rate limiting on auth endpoints

## Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| A1 | Not Started | | |
| A2 | Not Started | | |
| A3 | Not Started | | |
| A4 | Not Started | | |
| A5 | Not Started | | |
| A6 | Not Started | | |
| A7 | Not Started | | |
| A8 | Not Started | | |
| A9 | Not Started | | |
