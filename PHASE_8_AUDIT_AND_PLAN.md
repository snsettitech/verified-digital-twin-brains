# Phase 8 Compatibility Audit and Implementation Plan

## 1) Phase 8 Compatibility Audit

### Existing Infrastructure Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| `persona_claim_extractor.py` | ✅ Reusable | Existing claim extraction with `ClaimExtractor`, `ClaimCitation`, `PersonaClaim` models |
| `persona_claim_inference.py` | ✅ Reusable | Persona compilation from claims |
| `research_orchestrator.py` | ✅ Compatible | Terminal state `COMPLETED` - Phase 8 attaches post-completion |
| `deep_research_config.py` | ✅ Extensible | Feature flag infrastructure exists |
| `crawl.py` router | ✅ Compatible | Pattern for continue-* endpoints established |
| Database migrations | ✅ Clean slate | No existing research_claims table |
| `persona_link_compile.py` | ✅ Reference | Claim endpoints exist for legacy flow |

### State Machine Analysis
```
Phase 1-7 Flow:
planning → queued → crawling → awaiting_confirmation → ready_for_ingestion 
  → ingesting → ingestion_completed → generating_bio → bio_generated 
  → finalizing → COMPLETED (terminal)

Phase 8 Attachment Point:
COMPLETED → (optional) → CLAIMS_ENRICHING → CLAIMS_COMPLETED
```

### Key Findings
1. **No existing research_claims table** - Clean implementation possible
2. **Existing persona_claims table** - Separate from research claims, no conflict
3. **Terminal state `COMPLETED`** is safe attachment point - Phase 8 is opt-in enrichment
4. **Feature flags already configured** - Add `DR_PHASE_8_CLAIMS_DISABLED` 
5. **Extraction engine exists** - `ClaimExtractor` class can be extended/reused

### Contracts to Preserve
- `next_actions` (plural) as canonical
- `next_action` alias for backward compatibility
- All existing research run statuses
- Research summary response format (additive only)

---

## 2) Phase 8 Implementation Plan

### Files to Create

| File | Purpose |
|------|---------|
| `backend/modules/research_claim_extractor.py` | Extract claims from confirmed sources (research-specific) |
| `backend/modules/research_claim_verifier.py` | Local verification: supported/insufficient/conflicting/needs_review |
| `backend/modules/research_claim_service.py` | Orchestration: extract → verify → persist |
| `backend/database/migrations/migration_phase_8_research_claims.sql` | Claims tables and indexes |
| `backend/routers/research_claims.py` | New router for claim endpoints |
| `frontend/lib/api/researchClaims.ts` | Frontend API client for claims |
| `frontend/components/onboarding/ClaimsReview.tsx` | Claims review UI component |
| `frontend/tests/research-claims.test.ts` | Contract and helper tests |
| `backend/tests/test_research_claims.py` | Backend tests |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/modules/deep_research_config.py` | Add `DR_PHASE_8_CLAIMS_DISABLED` flag |
| `backend/modules/research_orchestrator.py` | Add `CLAIMS_ENRICHING`, `CLAIMS_COMPLETED` statuses (optional) |
| `backend/routers/crawl.py` | Add `POST /twins/{id}/research/{run_id}/continue-claims` |
| `backend/main.py` | Register research_claims router |
| `frontend/components/onboarding/StepResearch.tsx` | Add claims flow after completion |
| `frontend/components/onboarding/ResearchProgress.tsx` | Show claims phase |

### Database Schema (Migration)

```sql
-- research_claims table
- id (UUID, PK)
- research_run_id (UUID, FK)
- twin_id (UUID, FK)
- claim_text (TEXT)
- claim_type (ENUM: preference, belief, heuristic, value, experience, boundary, uncertain)
- verification_status (ENUM: supported, insufficient_evidence, conflicting, needs_review, pending)
- confidence (FLOAT)
- authority (STRING)
- source_id (UUID, FK to sources)
- source_url (TEXT)
- evidence_quotes (JSONB)
- created_at, updated_at (TIMESTAMPTZ)

-- research_claim_enrichment (summary table)
- research_run_id (UUID, PK, FK)
- status (ENUM: pending, enriching, completed, failed)
- total_claims (INT)
- supported_count (INT)
- insufficient_count (INT)
- conflicting_count (INT)
- needs_review_count (INT)
- started_at, completed_at (TIMESTAMPTZ)

-- Indexes
- idx_research_claims_run_id
- idx_research_claims_verification_status
- idx_research_claims_twin_id
```

### Feature Flags

```python
# In deep_research_config.py
phase_8_claims_disabled: bool = Field(
    default=False,
    description="Disable Phase 8 claims enrichment"
)

# Check
if os.getenv("DR_PHASE_8_CLAIMS_DISABLED", "false").lower() == "true":
    # Return 503 or skip
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/twins/{twin_id}/research/{run_id}/continue-claims` | POST | Start/continue claim enrichment |
| `/twins/{twin_id}/research/{run_id}/claims-status` | GET | Get enrichment status |
| `/twins/{twin_id}/research/{run_id}/claims` | GET | List claims with filters |
| `/twins/{twin_id}/research/{run_id}/claims/{claim_id}/resolve` | POST | Manual review resolution |

---

## 3) Implementation Sequence

1. **Database Migration** - Create tables first (safe, additive)
2. **Backend Modules** - Extractor → Verifier → Service
3. **Backend Router** - Endpoints with feature flag checks
4. **Frontend API Client** - Type-safe contracts
5. **Frontend UI** - Claims review component
6. **Integration** - Wire into StepResearch flow
7. **Tests** - Unit, integration, regression

---

## 4) Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Conflicts with existing persona_claims | Use `research_claims` table name (different namespace) |
| State machine complexity | Phase 8 runs POST-completed, separate from main flow |
| Performance on large source sets | Batch extraction, limit max claims per run |
| Feature flag not respected | Check at router entry and service level |
| Contract breaking changes | Additive fields only, preserve all existing |

---

## 5) Deferred to Phase 9

- Web verification against external sources
- Claim analytics dashboard
- Automatic claim updates on re-crawl
- Cross-run claim deduplication
- Advanced claim inference
