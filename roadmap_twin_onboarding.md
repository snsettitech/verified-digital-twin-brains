# Roadmap: Twin Creation + Onboarding (Epic B)

> Enable users to create and configure their digital twins.

## Overview

Implement twin CRUD operations, onboarding flow with interview mode and document upload, and twin dashboard.

## Dependencies

- ✅ Epic A (Auth + Multi-Tenancy) must be complete

## Tasks

### B1: Twins Database Schema
**Status**: Not Started
**Estimated**: 2 hours

- [ ] Create migration: 004_twins.sql
- [ ] Add RLS policies for twins table
- [ ] Add indexes for common queries
- [ ] Test RLS isolation

**Schema**:
```sql
CREATE TABLE twins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    owner_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    specialization TEXT,
    personality JSONB DEFAULT '{}',
    onboarding_status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS Policy
ALTER TABLE twins ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own tenant twins"
ON twins FOR SELECT
USING (tenant_id = auth.jwt() ->> 'tenant_id');

CREATE POLICY "Users can create twins in own tenant"
ON twins FOR INSERT
WITH CHECK (tenant_id = auth.jwt() ->> 'tenant_id' AND owner_id = auth.uid());
```

**Acceptance Criteria**:
- Migration runs successfully
- RLS prevents cross-tenant access
- Indexes in place for performance

**Test Plan**:
```sql
-- Test RLS
SET LOCAL role = 'authenticated';
SET LOCAL "request.jwt.claims" = '{"tenant_id": "tenant-a"}';

-- Should only see tenant-a twins
SELECT * FROM twins;
```

---

### B2: Twins API Endpoints
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: B1

- [ ] POST /api/twins - Create twin
- [ ] GET /api/twins - List twins
- [ ] GET /api/twins/{id} - Get twin
- [ ] PATCH /api/twins/{id} - Update twin
- [ ] DELETE /api/twins/{id} - Delete twin

**Request/Response Models**:
```python
class TwinCreate(BaseModel):
    name: str
    description: Optional[str]
    specialization: Optional[str]  # "VC Brain", "Sales Coach", etc.

class TwinResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    specialization: Optional[str]
    onboarding_status: str
    created_at: datetime
```

**Acceptance Criteria**:
- All CRUD operations work
- tenant_id automatically set from JWT
- Validation errors return 422

**Test Plan**:
```python
# test_twins_api.py
def test_create_twin():
    response = client.post("/api/twins",
        headers=auth_header(user="user-a"),
        json={"name": "My VC Brain", "specialization": "VC Brain"})
    assert response.status_code == 201
    assert response.json()["name"] == "My VC Brain"

def test_list_twins_filtered_by_tenant():
    # Create twins for two tenants
    client.post("/api/twins", headers=auth_header(tenant="A"), json={"name": "Twin A"})
    client.post("/api/twins", headers=auth_header(tenant="B"), json={"name": "Twin B"})

    # List as tenant A - should only see Twin A
    response = client.get("/api/twins", headers=auth_header(tenant="A"))
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Twin A"
```

---

### B3: Twin Dashboard UI
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: B2, A7

- [ ] Create /dashboard page layout
- [ ] Create TwinCard component
- [ ] Create TwinList component
- [ ] Add "Create Twin" button/modal
- [ ] Add empty state for new users

**Acceptance Criteria**:
- Dashboard shows list of twins
- User can create new twin
- Empty state guides new users
- Responsive design

**Test Plan**:
```typescript
// e2e/dashboard.spec.ts
test('new user sees empty state', async ({ page }) => {
    await signIn(page, 'newuser@test.com');
    await expect(page.locator('[data-testid="empty-state"]')).toBeVisible();
    await expect(page.locator('text=Create your first twin')).toBeVisible();
});

test('user can create twin', async ({ page }) => {
    await signIn(page, 'user@test.com');
    await page.click('[data-testid="create-twin-btn"]');
    await page.fill('[name=name]', 'Test Twin');
    await page.click('button[type=submit]');
    await expect(page.locator('text=Test Twin')).toBeVisible();
});
```

---

### B4: Onboarding Flow Structure
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: B3

- [ ] Create /twins/[id]/onboarding page
- [ ] Create OnboardingWizard component
- [ ] Define onboarding steps:
  1. Configure (name, description, personality)
  2. Knowledge (interview OR upload)
  3. Complete
- [ ] Add progress indicator
- [ ] Update onboarding_status on completion

**Acceptance Criteria**:
- Multi-step wizard navigation works
- Progress saved between steps
- Can skip steps and return later

**Test Plan**:
```typescript
test('onboarding wizard navigation', async ({ page }) => {
    await createTwin(page);
    await expect(page.locator('[data-testid="step-indicator"]')).toContainText('1 of 3');
    await page.click('[data-testid="next-btn"]');
    await expect(page.locator('[data-testid="step-indicator"]')).toContainText('2 of 3');
});
```

---

### B5: Interview Mode UI
**Status**: Not Started
**Estimated**: 5 hours
**Dependencies**: B4

- [ ] Create InterviewChat component
- [ ] Create InterviewHost service (backend)
- [ ] Implement interview conversation flow
- [ ] Extract knowledge from interview
- [ ] Store extracted knowledge as memory candidates

**Interview Flow**:
1. Host asks structured questions
2. User responds naturally
3. Host extracts entities/facts
4. Host confirms understanding
5. Knowledge stored for approval

**Acceptance Criteria**:
- Interview feels conversational
- Host asks relevant follow-ups
- Extracted knowledge is accurate
- Progress saved if user leaves

**Test Plan**:
```python
# test_interview.py
def test_interview_extracts_knowledge():
    response = client.post("/api/twins/{twin_id}/interview",
        headers=auth_header(),
        json={"message": "I invest in B2B SaaS startups"})

    # Should extract entities
    memory_candidates = get_memory_candidates(twin_id)
    assert any(mc["content"].contains("B2B SaaS") for mc in memory_candidates)
```

---

### B6: Document Upload UI
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: B4

- [ ] Create FileUpload component
- [ ] Support drag & drop
- [ ] Support multiple files
- [ ] Show upload progress
- [ ] Call ingestion API on upload

**Supported Formats**:
- PDF, DOCX, TXT, MD
- URLs (future: crawl web pages)

**Acceptance Criteria**:
- Files upload successfully
- Progress indicator works
- Error handling for failed uploads
- Queue processing feedback

**Test Plan**:
```typescript
test('user can upload document', async ({ page }) => {
    await goToOnboarding(page, twinId);
    await page.setInputFiles('[data-testid="file-input"]', 'test.pdf');
    await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
    await expect(page.locator('text=Processing complete')).toBeVisible({ timeout: 30000 });
});
```

---

### B7: Personality Configuration
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: B4

- [ ] Create PersonalityForm component
- [ ] Define personality traits/options
- [ ] Store personality in JSONB
- [ ] Use personality in chat prompts

**Personality Options**:
```typescript
interface TwinPersonality {
    tone: 'professional' | 'casual' | 'friendly';
    verbosity: 'concise' | 'detailed';
    formality: 'formal' | 'informal';
    expertise_level: 'beginner' | 'intermediate' | 'expert';
}
```

**Acceptance Criteria**:
- User can configure personality
- Settings persist
- Chat responses reflect personality

**Test Plan**:
```python
def test_personality_affects_responses():
    # Set personality to concise
    update_twin(twin_id, personality={"verbosity": "concise"})

    response1 = chat(twin_id, "Explain venture capital")

    # Set personality to detailed
    update_twin(twin_id, personality={"verbosity": "detailed"})

    response2 = chat(twin_id, "Explain venture capital")

    # Detailed response should be longer
    assert len(response2) > len(response1)
```

---

### B8: Specialization Templates
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: B2

- [ ] Define specialization templates
- [ ] Pre-configure interview questions per specialization
- [ ] Set default personality per specialization
- [ ] Create template selector UI

**Templates**:
- VC Brain: Investment thesis, portfolio, decision criteria
- Sales Coach: Products, objection handling, use cases
- Expert Witness: Expertise areas, past cases, methodologies
- Custom: Blank slate

**Acceptance Criteria**:
- User can select template
- Template pre-fills settings
- Custom option available

**Test Plan**:
```python
def test_specialization_sets_defaults():
    response = client.post("/api/twins",
        headers=auth_header(),
        json={"name": "My VC", "specialization": "vc_brain"})

    twin = response.json()
    assert twin["personality"]["expertise_level"] == "expert"
```

---

## Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| B1 | Not Started | | |
| B2 | Not Started | | |
| B3 | Not Started | | |
| B4 | Not Started | | |
| B5 | Not Started | | |
| B6 | Not Started | | |
| B7 | Not Started | | |
| B8 | Not Started | | |
