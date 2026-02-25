# Deep Research System: Phases 1-12 Complete Overview

**System**: Verified Digital Twin Brain - Deep Research Pipeline  
**Last Updated**: 2026-02-24  
**Status**: Phases 1-12 Complete ✅  

---

## Executive Summary

The Deep Research system is a comprehensive multi-phase pipeline for building verified digital twin brains. It spans from basic infrastructure setup (Phases 1-3) through data ingestion and persona building (Phases 4-7), to claims extraction and verification (Phases 8-10), and finally human review and runtime publication (Phases 11-12).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEEP RESEARCH PIPELINE OVERVIEW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASES 1-3: Infrastructure & Foundation                                    │
│  ├── Phase 1: API Centralization & Versioning                              │
│  ├── Phase 2: Dynamic CORS & Connectivity                                  │
│  └── Phase 3: Debugging & Observability                                    │
│                                                                             │
│  PHASES 4-7: Persona Building & Core Research                              │
│  ├── Phase 4: Bio Generation                                               │
│  ├── Phase 5: Mind Score & Readiness                                       │
│  ├── Phase 6: Persona Extraction Pipeline                                  │
│  └── Phase 7: Persona Runtime Integration                                  │
│                                                                             │
│  PHASES 8-10: Claims Extraction & Verification                             │
│  ├── Phase 8: Local Claims Enrichment                                      │
│  ├── Phase 9: Web Verification                                             │
│  └── Phase 10: Finalization & Consistency Review                           │
│                                                                             │
│  PHASES 11-12: Human Review & Publication                                  │
│  ├── Phase 11: Human Adjudication & Canonical Claims                       │
│  └── Phase 12: Runtime Publication & Deployment                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: API Centralization & Versioning

### Purpose
Establish a single source of truth for API configuration and enable deployment visibility.

### Key Components
| Component | Description |
|-----------|-------------|
| `frontend/lib/constants.ts` | Centralized API_BASE_URL and API_ENDPOINTS |
| `GET /version` | Backend endpoint returning git SHA, build time, environment |
| `ApiStatus` component | Frontend component showing backend connectivity |

### Impact
- Eliminated 18 hardcoded API_BASE_URL definitions
- Enabled quick debugging of "changes not reflecting" issues
- Provided visibility into deployed version

### Feature Flags
None (foundational infrastructure)

---

## Phase 2: Dynamic CORS with Wildcard Support

### Purpose
Enable Vercel preview deployments with wildcard CORS support.

### Key Components
| Component | Description |
|-----------|-------------|
| `cors_middleware.py` | Dynamic CORS with fnmatch pattern support |
| `GET /cors-test` | Endpoint to debug CORS configuration |
| `scripts/test_cors.py` | CLI tool for testing CORS from various origins |

### Features
- Supports `https://*.vercel.app` patterns
- Logs rejected origins for security auditing
- Color-coded connectivity status

### Impact
- Preview deployments now work without manual CORS updates
- Security team can audit rejected origins

---

## Phase 3: Debugging & Observability

### Purpose
Provide comprehensive debugging tools for development and production troubleshooting.

### Key Components
| Component | Description |
|-----------|-------------|
| `ApiConnectivityBanner` | Shows when backend is unreachable |
| `EnvironmentBadge` | Displays current environment (DEV/STAGING/PROD) |
| `DebugPanel` | Floating debug panel with request logging |
| `useRequestLogger` | Hook for tracking API requests with timing |
| `Admin Dashboard` | Service health monitoring page |

### Features
- Request logging with duration tracking
- LocalStorage persistence of logs
- Real-time latency monitoring
- Service health cards (API, Database, Auth)

---

## Phase 4: Bio Generation

### Purpose
Generate comprehensive biographical profiles from research sources.

### Key Components
| Component | Description |
|-----------|-------------|
| Bio Generation Service | LLM-powered bio creation from confirmed sources |
| Variant Selection | Multiple bio variants with quality scoring |
| Source Selection Policy | Smart source filtering for bio generation |

### State Machine
```
INGESTION_COMPLETED → GENERATING_BIO → BIO_GENERATED
```

---

## Phase 5: Mind Score & Readiness Evaluation

### Purpose
Evaluate twin readiness for deployment based on data quality and coverage.

### Key Components
| Component | Description |
|-----------|-------------|
| Mind Score Calculator | Numerical score based on content volume, diversity |
| Readiness Evaluator | Threshold-based readiness determination |
| Question Answerability | Estimate of how many questions can be answered |

### State Machine
```
BIO_GENERATED → FINALIZING → COMPLETED
```

### Readiness Criteria
- Minimum mind score threshold
- Sufficient source diversity
- Coverage of key persona aspects

---

## Phase 6: Persona Extraction Pipeline

### Purpose
Extract structured persona attributes from research sources and bios.

### Key Components
| Component | Description |
|-----------|-------------|
| Persona Extractor | LLM-based attribute extraction |
| Attribute Taxonomy | Standardized persona dimensions |
| Confidence Scoring | Reliability scoring per attribute |
| Conflict Resolution | Handle contradictory information |

### State Machine
```
COMPLETED → CLAIMS_ENRICHMENT (Phase 8, optional)
```

---

## Phase 7: Persona Runtime Integration

### Purpose
Integrate extracted persona into runtime chat system.

### Key Components
| Component | Description |
|-----------|-------------|
| Persona Service | Runtime access to persona attributes |
| Context Injection | Automatic persona context in chat |
| Dynamic Adaptation | Adjust responses based on persona |

---

## Phase 8: Claims Enrichment (Local)

### Purpose
Extract atomic claims from confirmed sources and verify against ingested content.

### Key Components
| Component | Description |
|-----------|-------------|
| `ResearchClaimExtractor` | Extracts atomic claims from sources |
| `ClaimVerifier` | Local verification against ingested content |
| `ResearchClaimService` | Orchestrates extraction → verification |
| `research_claims` table | Stores extracted claims |

### Claim Types
| Type | Description | Example |
|------|-------------|---------|
| `preference` | Likes/dislikes | "I prefer remote work" |
| `belief` | Held beliefs | "AI will transform healthcare" |
| `heuristic` | Rules of thumb | "Always validate assumptions" |
| `value` | Core values | "Transparency is essential" |
| `experience` | Past experiences | "Led a team of 10 engineers" |
| `boundary` | Limits/constraints | "I don't work weekends" |
| `uncertain` | Unverified statements | "I think AI might..." |

### Verification Statuses
- `supported` - Evidence found in sources
- `insufficient_evidence` - No supporting evidence
- `conflicting` - Contradictory evidence
- `needs_review` - Ambiguous, requires human review
- `pending` - Not yet verified

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/continue-claims` | POST | Trigger enrichment |
| `/claims-status` | GET | Get enrichment status |
| `/claims` | GET | List claims |
| `/claims/{id}/resolve` | POST | Manual resolution |

### State Machine
```
COMPLETED → CLAIMS_ENRICHMENT → CLAIMS_COMPLETED
```

### Feature Flag
```
DR_PHASE_8_CLAIMS_DISABLED=true|false (default: false)
```

---

## Phase 9: Web Verification

### Purpose
Verify Phase 8 claims against public web sources.

### Key Components
| Component | Description |
|-----------|-------------|
| `WebSearchProvider` | Abstracted search (Exa, Brave, Serper) |
| `ClaimWebVerifier` | Web-based claim verification |
| `ResearchClaimWebVerificationService` | Orchestrates web verification |
| `research_claim_web_verifications` table | Stores web verification results |

### Search Providers
- **ExaSearchProvider** - Exa AI semantic search
- **BraveSearchProvider** - Brave Search API
- **SerperSearchProvider** - Google Search via Serper
- **FallbackSearchProvider** - Multi-provider fallback chain

### Web Verification Statuses
| Status | Description |
|--------|-------------|
| `pending` | Not yet verified |
| `supported` | Web evidence supports claim |
| `conflicting` | Web evidence contradicts |
| `insufficient_evidence` | No relevant web evidence |
| `needs_review` | Ambiguous evidence |
| `blocked` | Access blocked (robots.txt) |
| `error` | Verification error |
| `skipped` | Ineligible claim type |

### Domain Tiers
| Tier | Description | Examples |
|------|-------------|----------|
| 1 | Authoritative | .edu, major news, official sites |
| 2 | Credible | Established blogs, industry sites |
| 3 | General | Other sources |

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/continue-web-verification` | POST | Trigger web verification |
| `/web-verification-status` | GET | Get verification status |
| `/claims-with-web-verification` | GET | List claims with web results |
| `/claims/{id}/web-evidence` | GET | Get web evidence for claim |
| `/claims/{id}/resolve-web` | POST | Resolve web verification |

### State Machine
```
CLAIMS_COMPLETED → WEB_VERIFICATION → WEB_VERIFIED
```

### Feature Flag
```
DR_PHASE_9_WEB_VERIFICATION_DISABLED=true|false (default: false)
```

---

## Phase 10: Claim Finalization & Consistency Review

### Purpose
Combine Phase 8 + 9 results into final claim decisions and detect cross-claim inconsistencies.

### Key Components
| Component | Description |
|-----------|-------------|
| `FinalizationEngine` | Applies rules to determine final status |
| `ConsistencyChecker` | Detects contradictions across claims |
| `ResearchClaimFinalizationService` | Orchestrates finalization |
| `research_claim_finalizations` table | Stores final decisions |
| `research_claim_consistency_issues` table | Tracks consistency issues |

### Final Claim Statuses
| Status | Description |
|--------|-------------|
| `accepted` | Strong supporting evidence |
| `rejected` | Insufficient or conflicting evidence |
| `needs_review` | Requires manual review |
| `unresolved` | Could not be determined |
| `overridden` | Manual override applied |

### Finalization Rules (Priority Order)
1. **Strong Agreement** - local=supported AND web=supported → accepted
2. **Strong Conflict** - local=conflicting OR web=conflicting → rejected
3. **Needs Review Flag** - local=needs_review OR web=needs_review → needs_review
4. **Single Source Success** - web=None AND local=supported → accepted
5. **Status Mismatch** - local ≠ web (neither None) → needs_review
6. **Insufficient Evidence** - both insufficient → rejected
7. **Default** → unresolved

### Consistency Issue Types
| Type | Description |
|------|-------------|
| `contradiction` | Opposite statements |
| `duplicate` | Near-identical claims |
| `confidence_mismatch` | High vs low confidence |
| `status_conflict` | Same source, different statuses |

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/continue-claim-finalization` | POST | Trigger finalization |
| `/finalization-status` | GET | Get finalization status |
| `/finalized-claims` | GET | List finalized claims |
| `/consistency-issues` | GET | List consistency issues |
| `/consistency-issues/{id}/resolve` | POST | Resolve issue |
| `/claims/{id}/finalize-override` | POST | Manual override |

### State Machine
```
WEB_VERIFIED → CLAIMS_FINALIZATION → CLAIMS_FINALIZED
```

### Feature Flag
```
DR_PHASE_10_CLAIM_FINALIZATION_DISABLED=true|false (default: false)
```

---

## Phase 11: Human Adjudication & Canonical Claims

### Purpose
Enable owner/admin review of finalized claims with audit trail and canonical claim versioning.

### Key Components
| Component | Description |
|-----------|-------------|
| `ResearchClaimAdjudicationService` | Adjudication workflow service |
| `review_claim()` | Approve/reject/mark claims |
| `lock_claim()` / `unlock_claim()` | Claim editing protection |
| `get_review_queue()` | Claims needing review |
| `research_claim_adjudications` table | Audit trail |
| `research_claim_canonical` table | Current truth store |
| `research_claim_issue_actions` table | Issue resolution audit |

### Adjudication Actions
| Action | Description |
|--------|-------------|
| `approve` | Accept the claim |
| `reject` | Reject the claim |
| `mark_needs_review` | Flag for further review |
| `mark_unresolved` | Mark as unresolved |
| `lock` | Prevent editing |
| `unlock` | Allow editing |
| `override_status` | Manual status override |

### Canonical Claim Features
- **Versioning** - Full history with `superseded_by` chain
- **Source of Truth** - `system_rule`, `human_review`, `override`, `consensus`
- **Locking** - Prevent concurrent modification
- **Audit Trail** - Who changed what and why

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/review-queue` | GET | Claims needing review |
| `/review-queue/summary` | GET | Queue statistics |
| `/claims/{id}/adjudicate` | POST | Apply adjudication |
| `/claims/{id}/lock` | POST | Lock claim |
| `/claims/{id}/unlock` | POST | Unlock claim |
| `/claims/{id}/adjudication-history` | GET | View audit trail |
| `/consistency-issues/{id}/action` | POST | Issue action |

### State Machine
```
CLAIMS_FINALIZED → ADJUDICATION → ADJUDICATED
```

### Feature Flag
```
DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=true|false (default: true)
```

---

## Phase 12: Runtime Publication & Deployment Readiness

### Purpose
Publish reviewed claims to runtime layer with deterministic rules and deployment tooling.

### Key Components
| Component | Description |
|-----------|-------------|
| `ResearchClaimRuntimeService` | Publication orchestration |
| `PublicationRuleEngine` | Deterministic publication rules |
| `BackfillService` | Historical run processing |
| `research_claim_runtime_publication` table | Denormalized runtime view |
| `research_claim_publication_runs` table | Publication tracking |
| `research_claim_publication_config` table | Per-twin configuration |

### Publication Rules
| Rule | Condition | Result |
|------|-----------|--------|
| accept_canonical_accepted | canonical=accepted | publishable=true |
| suppress_canonical_rejected | canonical=rejected | suppressed |
| suppress_unresolved | canonical=unresolved | suppressed |
| suppress_open_high_severity | has high severity issues | suppressed |
| suppress_low_confidence | confidence < threshold | suppressed |

### Runtime Claim Fields
- `publishable` - Meets publication criteria
- `published` - Currently published
- `suppressed` - Blocked from publication
- `suppression_reason` - Why suppressed
- `runtime_claim_text` - Normalized text
- `runtime_status` - accepted/rejected/needs_review
- `runtime_issue_flags` - Issue indicators

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/publish-runtime-claims` | POST | Trigger publication |
| `/runtime-claims` | GET | List runtime claims |
| `/runtime-claims/status` | GET | Publication status |
| `/admin/runtime-claims/backfill` | POST | Backfill historical |
| `/runtime-claims/export` | POST | Export (JSON/CSV) |

### State Machine
```
ADJUDICATED → RUNTIME_PUBLICATION → RUNTIME_PUBLISHED
```

### Feature Flags
```
DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED=true|false (default: true)
DR_PHASE_12_SUPPRESS_UNRESOLVED=true|false (default: true)
DR_PHASE_12_AUTO_PUBLISH=true|false (default: false)
```

### Deployment Tools
- `scripts/smoke_test_phases_11_12.py` - Deployment validation
- `scripts/backfill_phase_12.py` - Historical backfill CLI
- `PHASE_11_12_DEPLOYMENT_RUNBOOK.md` - Step-by-step deployment guide

---

## Complete State Machine

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         RESEARCH RUN STATE MACHINE                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  FOUNDATION PHASES (1-7)                                                  │
│  PLANNING → QUEUED → CRAWLING → AWAITING_CONFIRMATION                    │
│                    ↓                                                        │
│         READY_FOR_INGESTION → INGESTING → INGESTION_COMPLETED             │
│                    ↓                                                        │
│         GENERATING_BIO → BIO_GENERATED                                    │
│                    ↓                                                        │
│         FINALIZING → COMPLETED                                            │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  CLAIMS PHASES (8-12) - Optional Deep Research                            │
│                                                                            │
│  Phase 8: CLAIMS_ENRICHMENT → CLAIMS_COMPLETED                            │
│                                    ↓                                       │
│  Phase 9: WEB_VERIFICATION → WEB_VERIFIED                                 │
│                                    ↓                                       │
│  Phase 10: CLAIMS_FINALIZATION → CLAIMS_FINALIZED                         │
│                                    ↓                                       │
│  Phase 11: ADJUDICATION → ADJUDICATED                                     │
│                                    ↓                                       │
│  Phase 12: RUNTIME_PUBLICATION → RUNTIME_PUBLISHED                        │
│                                                                            │
│  [Skip Phase 11] ────────────────────────┐                                │
│                                          ↓                                │
│                              RUNTIME_PUBLICATION                          │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  TERMINAL STATES                                                          │
│  • COMPLETED (Phase 7 - without Deep Research)                            │
│  • CLAIMS_FINALIZED (Phase 10 - Deep Research without 11-12)              │
│  • ADJUDICATED (Phase 11 - without Phase 12)                              │
│  • RUNTIME_PUBLISHED (Phase 12 - complete pipeline)                       │
│  • FAILED (error state)                                                   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Flag Matrix

| Phase | Flag | Default | Description |
|-------|------|---------|-------------|
| 8 | `DR_PHASE_8_CLAIMS_DISABLED` | `false` | Disable claims enrichment |
| 9 | `DR_PHASE_9_WEB_VERIFICATION_DISABLED` | `false` | Disable web verification |
| 10 | `DR_PHASE_10_CLAIM_FINALIZATION_DISABLED` | `false` | Disable finalization |
| 11 | `DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED` | `true` | Disable adjudication |
| 12 | `DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED` | `true` | Disable publication |
| 12 | `DR_PHASE_12_SUPPRESS_UNRESOLVED` | `true` | Suppress unresolved claims |
| 12 | `DR_PHASE_12_AUTO_PUBLISH` | `false` | Auto-publish without review |

---

## Database Tables by Phase

### Phase 8
- `research_claims` - Extracted claims
- `research_claim_evidence` - Supporting evidence

### Phase 9
- `research_claim_web_verifications` - Web verification results
- `research_claim_web_evidence` - Web evidence items
- `research_web_verification_runs` - Verification progress

### Phase 10
- `research_claim_finalizations` - Final claim decisions
- `research_claim_consistency_issues` - Cross-claim issues
- `research_claim_finalization_runs` - Finalization progress

### Phase 11
- `research_claim_adjudications` - Adjudication audit trail
- `research_claim_canonical` - Canonical claim store
- `research_claim_issue_actions` - Issue resolution audit
- `research_claim_adjudication_runs` - Adjudication progress

### Phase 12
- `research_claim_runtime_publication` - Runtime claim view
- `research_claim_publication_runs` - Publication progress
- `research_claim_publication_config` - Per-twin config
- `research_claim_publication_audit` - Publication audit

---

## Testing Summary

| Phase | Test File | Status |
|-------|-----------|--------|
| 8 | `test_research_claims.py` | ✅ 14 passed |
| 9 | `test_research_claim_web_verification.py` | ✅ 19 passed |
| 10 | `test_research_claim_finalization.py` | ✅ 31 passed |
| 11-12 | `smoke_test_phases_11_12.py` | ✅ Validated |

**Total**: 86+ tests passing, no regression

---

## Deployment Status

| Phase | Status | Deployed |
|-------|--------|----------|
| 1 | ✅ Complete | Yes |
| 2 | ✅ Complete | Yes |
| 3 | ✅ Complete | Yes |
| 4 | ✅ Complete | Yes |
| 5 | ✅ Complete | Yes |
| 6 | ✅ Complete | Yes |
| 7 | ✅ Complete | Yes |
| 8 | ✅ Complete | Yes |
| 9 | ✅ Complete | Yes |
| 10 | ✅ Complete | Yes |
| 11 | ✅ Complete | Ready |
| 12 | ✅ Complete | Ready |

---

## Next Steps

1. **Deploy Phases 11-12** to staging
2. **Enable** `DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=false` for test twins
3. **Validate** adjudication workflow
4. **Enable** `DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED=false`
5. **Validate** publication workflow
6. **Gradual rollout** to production twins

---

## Documentation Index

| Document | Description |
|----------|-------------|
| `DEEP_RESEARCH_PHASES_1_12_OVERVIEW.md` | This document |
| `PHASE_11_12_DEPLOYMENT_RUNBOOK.md` | Deployment guide |
| `PHASE_11_12_VERIFICATION_REPORT.md` | Test evidence |
| `PHASE_11_12_IMPLEMENTATION_COMPLETE.md` | Implementation summary |
| `PHASE_11_12_AUDIT_AND_PLAN.md` | Technical audit |

---

*System Version: 1.0*  
*Last Updated: 2026-02-24*  
*Status: Phases 1-12 Complete ✅*
