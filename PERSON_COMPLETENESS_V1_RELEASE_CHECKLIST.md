# Person Completeness V1 - Release Checklist

## Pre-Flight Verification

### 1. Backend Guardrails ✅

#### A. One Profile Per User Enforcement

**POST /profile (Idempotent)**
```python
# Check: Returns existing profile if one exists
existing = get_or_create_profile_for_user(user)
if existing:
    return existing  # No duplicate creation
```
✅ Implemented in `backend/routers/profile.py:196-199`

**POST /deep-research/runs (Attaches to existing)**
```python
# Check: Attaches to existing twin if one exists
existing_twin = self.db.table("twins")...
if existing_twin.data:
    twin_id = existing_twin.data[0]["id"]  # Reuse existing
```
✅ Implemented in `backend/modules/name_deep_research_service.py:424-443`

#### B. Legacy Onboarding Redirect

**Frontend: /onboarding → /onboarding/v2**
```typescript
// In onboarding/page.tsx
useEffect(() => {
  router.replace('/onboarding/v2');
}, [router]);
```
✅ Implemented in `frontend/app/onboarding/page.tsx:115-118`

---

## 2. E2E Flow Validation

### Flow A: With-Links Onboarding

```
[Start] → /onboarding/v2
    ↓
GET /profile → 404 (no profile exists)
    ↓
Screen 1: Identity
    - Full name: "Jane Doe"
    - Headline: "Founder"
    - Build mode: "with_links"
    ↓
POST /profile
    ↓
200 OK → { id: "twin_abc123", name: "Jane Doe", ... }
    ↓
Screen 2: Optional Hints (skipped or filled)
    ↓
PATCH /profile
    ↓
Screen 3: Add Sources
    - URLs: ["https://example.com/article"]
    - Files: uploaded
    ↓
POST /twins/{id}/ingest-url (for each URL)
POST /twins/{id}/upload (for each file)
POST /profile/person-completeness/run
    ↓
Building Screen
    ↓
GET /profile/build-status (poll every 3s)
    ↓
Status: "completed"
    ↓
Redirect to /dashboard/profile
```

**Verification Checklist:**
- [ ] Exactly one profile created (check DB: one twin record per tenant)
- [ ] Build status stages map correctly:
  - "pending" → "building" → "ready"
  - progress_percent increases
- [ ] Back navigation does not recreate profile (idempotent)
- [ ] Refresh mid-build resumes correctly (poll continues)

**Test Commands:**
```bash
# Create profile
curl -X POST $API_BASE/profile \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"full_name":"Jane Doe","headline":"Founder","build_mode":"with_links"}'

# Should return same profile on retry
curl -X POST $API_BASE/profile \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"full_name":"Jane Doe","headline":"Founder","build_mode":"with_links"}'
# Response: Same id, not new id

# Poll build status
curl $API_BASE/profile/build-status \
  -H "Authorization: Bearer $TOKEN"
```

---

### Flow B: Name-Only Onboarding

```
[Start] → /onboarding/v2
    ↓
GET /profile → 404 (no profile exists)
    ↓
Screen 1: Identity
    - Full name: "Jane Doe"
    - Build mode: "name_only"
    ↓
POST /deep-research/runs
    ↓
200 OK → { run_id: "run_abc", twin_id: "twin_xyz", ... }
    ↓
Building Screen
    ↓
GET /deep-research/runs/{run_id} (poll until completed)
    ↓
Status: "completed"
    ↓
POST /profile/person-completeness/run (optional enrichment)
    ↓
GET /profile/build-status (poll until ready)
    ↓
Status: "ready"
    ↓
Redirect to /dashboard/profile
```

**Verification Checklist:**
- [ ] No POST /profile call before deep research
- [ ] Exactly one profile created (deep research creates twin internally)
- [ ] GET /profile after completion returns the created profile
- [ ] If user already has profile, research attaches to existing (no duplicate)

**Test Commands:**
```bash
# Start deep research (should NOT call POST /profile first)
curl -X POST $API_BASE/deep-research/runs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Jane Doe","hints":{}}'
# Response: { run_id, twin_id, status, created_at }

# Poll research status
curl $API_BASE/deep-research/runs/{run_id} \
  -H "Authorization: Bearer $TOKEN"

# After completion, profile should exist
curl $API_BASE/profile \
  -H "Authorization: Bearer $TOKEN"
# Should return 200 with profile, not 404

# Retry deep research with same user
curl -X POST $API_BASE/deep-research/runs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Jane Doe Updated","hints":{}}'
# Should attach to existing twin_id, not create new one
```

---

### Flow C: Returning User

```
User with existing profile visits /dashboard
    ↓
ProfileContext mounts
    ↓
GET /profile
    ↓
200 OK → { id: "twin_abc", name: "Jane Doe", status: "ready", ... }
    ↓
No redirect to onboarding
    ↓
Sidebar shows Profile hub
    ↓
No TwinSelector visible
```

**Verification Checklist:**
- [ ] GET /profile returns 200 immediately (no onboarding redirect)
- [ ] Sidebar shows Profile link, no selector
- [ ] /onboarding redirects to /onboarding/v2
- [ ] /onboarding/v2 would see profile exists and could redirect to dashboard

**Test Commands:**
```bash
# Existing user
curl $API_BASE/profile \
  -H "Authorization: Bearer $TOKEN"
# Should return 200, not 404
```

---

### Flow D: Public Share

```
Visitor visits /share/{handle}
    ↓
Resolve handle → twin_id + token
    ↓
GET /share/{twin_id}/{token}/profile
    ↓
200 OK → Public-safe profile data
    ↓
Visitor asks question
    ↓
POST /public/chat/{twin_id}/{token}
    ↓
Response with citations, confidence
```

**Verification Checklist:**
- [ ] Public endpoint returns only public-safe data
- [ ] No private claims/sources leaked
- [ ] Rate limiting: 10 req/min per twin_id:IP
- [ ] Invalid token returns 403

**Test Commands:**
```bash
# Get public profile
curl $API_BASE/share/$TWIN_ID/$TOKEN/profile
# Should return: { name, headline, answerability_score, ... }
# Should NOT return: private_claims, unverified_sources, etc.

# Public chat
curl -X POST $API_BASE/public/chat/$TWIN_ID/$TOKEN \
  -d '{"message":"What is your expertise?"}'
# Should return: { response, citations, confidence }

# Rate limit test (run 11 times quickly)
for i in {1..11}; do
  curl -X POST $API_BASE/public/chat/$TWIN_ID/$TOKEN \
    -d '{"message":"test"}'
done
# 11th request should return 429 Too Many Requests
```

---

## 3. Contract Alignment Verification

### A. GET /profile/build-status

**Frontend Expects:**
```typescript
interface BuildStatus {
  profile_id: string;
  status: 'pending' | 'building' | 'ready' | 'needs_attention' | 'failed';
  stage: string;
  progress_percent: number;
  stats: Record<string, any>;
  quality_tier?: 'high_confidence' | 'with_gaps' | 'low_confidence' | 'failed';
}
```

**Backend Returns:**
✅ Defined in `backend/routers/profile.py:52-60`

### B. POST /deep-research/runs

**Frontend Expects:**
```typescript
interface DeepResearchRun {
  run_id: string;
  twin_id: string;  // Critical: must return this
  status: string;
  created_at: string;
}
```

**Backend Returns:**
✅ Returns `twin_id` in response (line 477 in name_deep_research_service.py)

### C. GET /share/{twin_id}/{token}/profile

**Frontend Expects:**
```typescript
interface PublicProfile {
  name: string;
  headline?: string;
  answerability_score: number;
  // NO: private_claims, sources, etc.
}
```

**Backend Returns:**
✅ Defined in `backend/routers/profile_public.py`

---

## 4. CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Release Checks

on: [push, pull_request]

jobs:
  enforce-ui:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Enforce Single Twin UI
        run: cd frontend && npm run enforce:ui:single

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: TypeScript Check
        run: cd frontend && npm run typecheck

  backend-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Backend Loads
        run: cd backend && python -c "import main"
```

---

## 5. Database Verification Queries

### Check for Duplicate Profiles
```sql
-- Should return 1 row per tenant (or 0 if no profile)
SELECT tenant_id, COUNT(*) as twin_count
FROM twins
WHERE settings->>'deleted_at' IS NULL
GROUP BY tenant_id
HAVING COUNT(*) > 1;
-- Expected: Empty result set
```

### Check Profile Creation Modes
```sql
-- Distribution of creation modes
SELECT 
  settings->>'creation_mode' as mode,
  COUNT(*) as count
FROM twins
GROUP BY settings->>'creation_mode';
-- Expected: name_first, manual, link_first
```

### Check Orphaned Research Runs
```sql
-- Research runs without twin_id (should be 0)
SELECT COUNT(*) 
FROM name_deep_research_runs
WHERE twin_id IS NULL;
-- Expected: 0
```

---

## 6. Definition of Done

### ✅ Required for Production

- [ ] `npm run enforce:ui:single` passes (0 violations)
- [ ] With-links onboarding E2E passes
- [ ] Name-only onboarding E2E passes
- [ ] Returning user flow passes
- [ ] Public share flow passes
- [ ] No duplicate profile creation in logs
- [ ] Build status polling has timeout (no infinite loops)
- [ ] Public endpoint never leaks private data (verified)

### 📋 Monitoring Post-Release

- [ ] Track profile creation rate (should match signup rate)
- [ ] Monitor for duplicate twin_id errors
- [ ] Track build status completion rate
- [ ] Monitor public share rate limits

---

## Quick Test Script

```bash
#!/bin/bash
# Quick smoke test for release

API_BASE="${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
TOKEN="$TEST_TOKEN"

echo "=== Release Smoke Test ==="

# 1. Backend loads
echo "1. Checking backend..."
cd backend && python -c "import main" && echo "✅ Backend loads"

# 2. UI enforcement
echo "2. Checking UI enforcement..."
cd frontend && npm run enforce:ui:single && echo "✅ UI clean"

# 3. TypeScript
echo "3. Checking TypeScript..."
cd frontend && npm run typecheck && echo "✅ TypeScript passes"

# 4. Profile endpoint (404 for new user)
echo "4. Checking profile endpoint..."
response=$(curl -s -w "%{http_code}" -H "Authorization: Bearer $TOKEN" $API_BASE/profile)
if [[ $response == *"404"* ]]; then
  echo "✅ Profile 404 for new user (expected)"
else
  echo "⚠️ Profile exists or error"
fi

echo "=== Smoke Test Complete ==="
```

---

## Sign-Off

| Role | Name | Date | Status |
|------|------|------|--------|
| Backend | | | |
| Frontend | | | |
| QA | | | |
| Product | | | |

**Release Version:** ___________  
**Release Date:** ___________  
**Rollback Plan:** Revert to previous deployment, DB has backward compatibility
