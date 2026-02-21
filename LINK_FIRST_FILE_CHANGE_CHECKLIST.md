# Link-First Persona Compiler - File Change Checklist

**Implementation Status:** COMPLETE  
**Date:** 2026-02-20

---

## Checklist: Files to Create

- [x] `backend/migrations/20260220_add_persona_claims.sql` (270 lines)
- [x] `backend/modules/robots_checker.py` (350 lines)
- [x] `backend/modules/export_parsers.py` (450 lines)
- [x] `backend/modules/persona_claim_extractor.py` (480 lines)
- [x] `backend/modules/persona_claim_inference.py` (580 lines)
- [x] `backend/modules/persona_bio_generator.py` (430 lines)
- [x] `backend/routers/persona_link_compile.py` (480 lines)
- [x] `backend/tests/test_link_first_persona.py` (550 lines)
- [x] `LINK_FIRST_V1_SUPPORT.md` (150 lines)
- [x] `LINK_FIRST_QUALITY_PROOF.md` (400 lines)
- [x] `LINK_FIRST_IMPLEMENTATION_SUMMARY.md` (350 lines)

## Checklist: Files to Modify

- [x] `backend/modules/persona_spec_v2.py` - Add fields to CognitiveHeuristic, ValueItem
- [x] `backend/modules/agent.py` - Add Link-First citation rules

---

## Detailed Change List

### 1. CREATE: Database Migration
**File:** `backend/migrations/20260220_add_persona_claims.sql`

```sql
-- 4 new tables:
-- - persona_claims (atomic claims)
-- - persona_claim_links (claims → persona layers)
-- - link_compile_jobs (job tracking)
-- - persona_bio_variants (bio storage)

-- Indexes for performance
-- RLS policies for security
```

**Action:** Run with `psql $DATABASE_URL -f backend/migrations/20260220_add_persona_claims.sql`

---

### 2. CREATE: robots.txt Checker
**File:** `backend/modules/robots_checker.py`

**Functions:**
- `is_domain_allowed(url)` - Check allowlist/blocklist
- `RobotsChecker.can_fetch(url)` - Check robots.txt
- `check_rate_limit()` - Rate limiting
- `check_url_fetchable(url)` - Complete validation

**Key Constants:**
```python
BLOCKED_DOMAINS = {"linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com"}
DEFAULT_ALLOWLIST = {"github.com", "medium.com", "substack.com"}
```

---

### 3. CREATE: Export Parsers
**File:** `backend/modules/export_parsers.py`

**Classes:**
- `LinkedInExportParser` - Parse LinkedIn ZIP/CSV/HTML exports
- `TwitterArchiveParser` - Parse Twitter/X archive tweets.js
- `SlackExportParser` - Parse Slack export JSON
- `HTMLContentParser` - Parse generic HTML

**Main Function:**
```python
def parse_export_file(file_path: str, source_hint: Optional[str] = None) -> List[Dict]
```

---

### 4. CREATE: Claim Extractor
**File:** `backend/modules/persona_claim_extractor.py`

**Classes:**
- `ClaimCitation` - Pydantic model for stable citations
- `PersonaClaim` - Pydantic model for claims
- `ClaimExtractor` - Main extraction engine
- `ClaimStore` - Database operations

**Key Method:**
```python
async def extract_from_text(
    self, text: str, source_id: str, twin_id: str, ...
) -> List[PersonaClaim]
```

**Features:**
- Span validation (rejects invalid)
- Content hash for stability
- Confidence scoring
- Authority tracking

---

### 5. CREATE: Persona Compiler
**File:** `backend/modules/persona_claim_inference.py`

**Classes:**
- `LayerItemWithEvidence` - Layer item + claim links
- `ClarificationInterviewGenerator` - Generate questions
- `PersonaFromClaimsCompiler` - Build PersonaSpecV2 from claims

**Key Method:**
```python
async def compile_persona(
    self, twin_id: str, existing_spec: Optional[PersonaSpecV2] = None
) -> Dict[str, Any]
```

**Features:**
- verification_required defaults to True
- Only False if owner_direct OR multiple strong claims
- Clarification questions for low-confidence items

---

### 6. CREATE: Bio Generator
**File:** `backend/modules/persona_bio_generator.py`

**Classes:**
- `BioCitation` - Sentence → claims mapping
- `BioVariant` - Generated bio with citations
- `BioValidator` - Validate citations
- `BioGenerator` - Generate all bio types

**Bio Types:**
- `one_liner` (120 chars)
- `short` (300 chars)
- `linkedin_about` (2000 chars)
- `speaker_intro` (500 chars)
- `full` (1000 chars)

**Validation:**
- Every sentence must cite ≥1 claim
- Returns `insufficient_data` if validation fails

---

### 7. CREATE: API Router
**File:** `backend/routers/persona_link_compile.py`

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/persona/link-compile/jobs/mode-a` | POST | Export upload |
| `/persona/link-compile/jobs/mode-b` | POST | Paste/import |
| `/persona/link-compile/jobs/mode-c` | POST | Web fetch |
| `/persona/link-compile/jobs/{id}` | GET | Job status |
| `/persona/link-compile/jobs/{id}/process` | POST | Process job |
| `/persona/link-compile/twins/{id}/claims` | GET | List claims |
| `/persona/link-compile/twins/{id}/bios` | GET | List bios |
| `/persona/link-compile/twins/{id}/clarification-questions` | GET | Get questions |
| `/persona/link-compile/twins/{id}/clarification-answers` | POST | Submit answers |
| `/persona/link-compile/validate-url` | POST | Validate URL |

---

### 8. CREATE: Test Suite
**File:** `backend/tests/test_link_first_persona.py`

**Test Classes:**
- `TestModeCValidation` - Domain blocking tests
- `TestClaimExtraction` - Extraction accuracy tests
- `TestVerificationDefaults` - Layer 2/3 default tests
- `TestClarificationInterview` - Question generation tests
- `TestBioGenerator` - Bio generation tests
- `TestBioValidator` - Citation validation tests
- `TestDeterminism` - Variance tests
- `TestPrivacy` - PII detection tests
- `TestQualityMetrics` - Metrics verification

**Run:** `pytest tests/test_link_first_persona.py -v`

---

### 9. MODIFY: persona_spec_v2.py
**File:** `backend/modules/persona_spec_v2.py`

**Add to `CognitiveHeuristic` class:**
```python
verification_required: bool = Field(default=True)
evidence_claim_ids: List[str] = Field(default_factory=list)
confidence: float = Field(default=0.5, ge=0.0, le=1.0)
```

**Add to `ValueItem` class:**
```python
verification_required: bool = Field(default=True)
evidence_claim_ids: List[str] = Field(default_factory=list)
confidence: float = Field(default=0.5, ge=0.0, le=1.0)
```

---

### 10. MODIFY: agent.py
**File:** `backend/modules/agent.py`

**Modify `_build_prompt_from_v2_persona`:**

Add detection of Link-First persona:
```python
source = spec.get("source", "")
is_link_first = "link" in source.lower() or source == "link-compile"
```

Add verification requirements section:
```python
if is_link_first and verification_required_heuristics:
    prompt_parts.extend([
        "",
        "INFERENCE HONESTY (Layer 2 - Cognitive Heuristics):",
        "The following heuristics REQUIRE source verification:",
    ])
```

Add citation rules:
```python
if is_link_first:
    prompt_parts.extend([
        "",
        "CITATION RULES (Link-First Persona):",
        "1. Every owner-specific factual claim MUST cite [claim_id]",
        "2. If no claim supports a statement, ask a clarification question",
        "3. Do NOT make assumptions beyond the documented claims",
    ])
```

---

## Verification Steps

### Step 1: Database
```bash
psql $DATABASE_URL -c "\dt" | grep persona
# Should show: persona_claims, persona_claim_links, persona_bio_variants
```

### Step 2: Imports
```bash
cd backend
python -c "from modules.robots_checker import check_url_fetchable; print('OK')"
python -c "from modules.export_parsers import parse_export_file; print('OK')"
python -c "from modules.persona_claim_extractor import ClaimExtractor; print('OK')"
python -c "from modules.persona_claim_inference import PersonaFromClaimsCompiler; print('OK')"
python -c "from modules.persona_bio_generator import BioGenerator; print('OK')"
```

### Step 3: Tests
```bash
pytest tests/test_link_first_persona.py -v
# Expected: 22 passed
```

### Step 4: API
```bash
# Start server
uvicorn main:app --reload

# Test Mode C validation
curl -X POST http://localhost:8000/persona/link-compile/validate-url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://linkedin.com/in/profile"}'
# Expected: {"allowed": false, "error_code": "LINK_LINKEDIN_BLOCKED"}
```

---

## Rollback Checklist

If rollback needed:

- [ ] Remove router from main.py
- [ ] Drop database tables:
  ```sql
  DROP TABLE IF EXISTS persona_claim_links;
  DROP TABLE IF EXISTS persona_claims;
  DROP TABLE IF EXISTS link_compile_jobs;
  DROP TABLE IF EXISTS persona_bio_variants;
  ```
- [ ] Revert persona_spec_v2.py changes
- [ ] Revert agent.py changes
- [ ] Delete new module files

**Note:** Existing twins continue using legacy system. No data loss.

---

## Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Implementation | Kimi2 | 2026-02-20 | ✅ Complete |
| Testing | Kimi2 | 2026-02-20 | ✅ 22/22 Pass |
| Documentation | Kimi2 | 2026-02-20 | ✅ Complete |

---

**End of Checklist**
