# Person Completeness Layer v1 - Implementation Documentation

## Executive Summary

This document describes the implementation of the Person Completeness Layer v1 - a advisor-like structured person modeling system built on top of the existing Deep Research pipeline. The system provides evidence-grounded, structured, and verifiable person modeling with features for trust, auditability, and runtime confidence gating.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PERSON COMPLETENESS PIPELINE v1                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  STAGE 1: SOURCE_REGISTRY_BUILT                                         │
│  ├─ Collects sources from research runs, ingestion, web verification    │
│  ├─ URL normalization and content hash deduplication                    │
│  └─ Authority tier assignment (1-7)                                     │
│                                                                          │
│  STAGE 2: CLAIMS_EXTRACTED                                              │
│  ├─ Rule-based + LLM-assisted extraction                               │
│  ├─ Evidence span attachment (quote, timestamp, offset)                │
│  ├─ First vs third party source detection                              │
│  └─ Claim deduplication via fingerprinting                             │
│                                                                          │
│  STAGE 3: TIMELINE_BUILT                                                │
│  ├─ Temporal claim aggregation                                         │
│  ├─ Date normalization and conflict detection                          │
│  └─ Event deduplication                                                  │
│                                                                          │
│  STAGE 4: TOPIC_GRAPH_BUILT                                             │
│  ├─ Topic aggregation from claims                                      │
│  ├─ Answerability scoring (coverage, verification, recency)            │
│  └─ Hierarchical topic relationships                                   │
│                                                                          │
│  STAGE 5: STYLE_PROFILE_BUILT                                           │
│  ├─ First-party content analysis                                       │
│  ├─ Tone descriptors and sentence profiling                            │
│  └─ Versioned profiles per twin                                        │
│                                                                          │
│  STAGE 6: CONTRADICTIONS_DETECTED                                       │
│  ├─ Timeline conflict detection                                        │
│  ├─ Role conflict detection                                            │
│  └─ Factual conflict detection                                         │
│                                                                          │
│  STAGE 7: ANSWERABILITY_SCORED                                          │
│  ├─ Global answerability score                                         │
│  ├─ Per-topic answerability scores                                     │
│  └─ Score explanation generation                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

                              ↓

┌─────────────────────────────────────────────────────────────────────────┐
│                     RUNTIME CONFIDENCE GATE                             │
├─────────────────────────────────────────────────────────────────────────┤
│  • Answerability threshold checking                                     │
│  • Contradiction awareness                                              │
│  • Fallback message generation                                          │
│  • "I don't know" when confidence insufficient                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Schema Summary

### New Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `person_source_registry` | Extended source tracking | URL normalization, content hash, authority tier (1-7) |
| `person_claims` | Structured claims | SPO triples, temporal bounds, verification status, fingerprint |
| `person_claim_evidence_spans` | Granular evidence | Quote/timestamp/offset, source party detection |
| `person_timeline_events` | Derived timeline | Date precision, event deduplication, conflict flagging |
| `person_topic_profiles` | Topic expertise | Answerability scoring, coverage/verification/recency metrics |
| `person_style_profile` | Writing style | Versioned, tone descriptors, sentence profiling |
| `person_contradictions` | Conflict tracking | Severity levels, adjudication workflow |
| `person_answerability_scores` | Runtime scores | Global + per-topic, component breakdown |
| `person_runtime_policies` | Behavior config | Thresholds, fallback behavior, PII rules |
| `person_completeness_runs` | Pipeline tracking | Stage progress, metrics, idempotency |

### Relationship to Existing Tables

```
research_runs (existing)
    ↓ (1:N)
person_completeness_runs (tracks pipeline runs)
    ↓ (1:N for sources)
person_source_registry
    ↓ (used by)
person_claims ←→ research_claims (optional link)
    ↓ (1:N)
person_claim_evidence_spans
    ↓ (used to derive)
person_timeline_events
    ↓ (aggregates to)
person_topic_profiles
    ↓ (contributes to)
person_answerability_scores
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PERSON_COMPLETENESS_ENABLED` | `true` | Master enable flag |
| `PC_ENABLED_TWIN_IDS` | `""` | Comma-separated list of twins to enable |
| `PC_DISABLED_TWIN_IDS` | `""` | Comma-separated list of twins to disable |
| `PC_ROLLOUT_PCT` | `100` | Percentage rollout (0-100) |
| `PC_FAIL_FAST` | `false` | Stop pipeline on first error |
| `PC_CONTINUE_ON_FAILURE` | `true` | Continue pipeline if stage fails |
| `PC_SOURCE_REGISTRY_ENABLED` | `true` | Enable stage 1 |
| `PC_CLAIM_EXTRACTION_ENABLED` | `true` | Enable stage 2 |
| `PC_CLAIM_MODEL` | `gpt-4o-mini` | Model for claim extraction |
| `PC_TIMELINE_ENABLED` | `true` | Enable stage 3 |
| `PC_TOPIC_GRAPH_ENABLED` | `true` | Enable stage 4 |
| `PC_STYLE_PROFILE_ENABLED` | `true` | Enable stage 5 |
| `PC_CONTRADICTION_ENABLED` | `true` | Enable stage 6 |
| `PC_ANSWERABILITY_ENABLED` | `true` | Enable stage 7 |

### Per-Twin Runtime Policies

Configured via `person_runtime_policies` table:

```sql
INSERT INTO person_runtime_policies (
    twin_id,
    audience,
    confidence_threshold_answer,
    confidence_threshold_style,
    fallback_behavior,
    require_citation
) VALUES (
    'twin-uuid',
    'public',
    0.5,  -- 50% confidence required
    0.6,  -- 60% style confidence required
    'i_dont_know',
    true
);
```

## API Changes

### New Functions

```python
# Pipeline execution
from modules.person_completeness_pipeline import run_person_completeness_pipeline

result = await run_person_completeness_pipeline(
    twin_id="twin-uuid",
    research_run_id="optional-research-run-uuid",
    force_rebuild=False
)

# Runtime confidence check
from modules.runtime_confidence_gate import check_answer_confidence

gate_result = await check_answer_confidence(
    twin_id="twin-uuid",
    query="user query",
    query_topic="optional-topic"
)

if gate_result.decision == "block":
    return gate_result.fallback_message
```

### State Machine Fix

```python
# Import the fix
from modules.research_orchestrator_state_fix import (
    is_deep_research_enabled,
    get_next_auto_status,
    patch_research_orchestrator
)

# Apply patch at startup
patch_research_orchestrator()

# Check if run should continue to deep research
if is_deep_research_enabled(run_data):
    next_status = get_next_auto_status(
        ResearchRunStatus.FINALIZING,
        run_data
    )  # Returns CLAIMS_ENRICHMENT
else:
    next_status = ResearchRunStatus.COMPLETED
```

## Test Plan

### Unit Tests

```bash
# Pipeline tests
pytest backend/tests/test_person_completeness_pipeline.py -v

# State machine fix tests
pytest backend/tests/test_state_machine_fix.py -v

# Runtime confidence gate tests
pytest backend/tests/test_runtime_confidence_gate.py -v
```

### Test Coverage

| Component | Test File | Coverage |
|-----------|-----------|----------|
| Configuration | `test_person_completeness_pipeline.py` | Enablement logic, stage selection |
| Pipeline Orchestrator | `test_person_completeness_pipeline.py` | Stage execution, error handling |
| Source Registry Builder | `test_person_completeness_pipeline.py` | URL normalization, dedup |
| Claim Extraction | `test_person_completeness_pipeline.py` | Rule-based + LLM extraction |
| State Machine Fix | `test_state_machine_fix.py` | Deep research paths, skip adjudication |
| Runtime Confidence | `test_runtime_confidence_gate.py` | Thresholds, fallback messages |

### Integration Tests

```bash
# End-to-end pipeline test with mocks
pytest backend/tests/test_person_completeness_pipeline.py::TestIntegration -v
```

## Backfill Instructions

### For All Twins

```bash
cd backend
python scripts/backfill_person_completeness.py --all-twins --batch-size 10
```

### For Specific Twin

```bash
python scripts/backfill_person_completeness.py --twin-id <twin-uuid>
```

### For Twins Needing Update

```bash
python scripts/backfill_person_completeness.py --needs-backfill
```

### Force Rebuild

```bash
python scripts/backfill_person_completeness.py --twin-id <twin-uuid> --force
```

## Limitations

### Current Implementation

1. **Claim Extraction**: Uses simplified rule-based patterns + LLM. Could be enhanced with NER and dependency parsing.

2. **Contradiction Detection**: Currently detects only explicit timeline/role conflicts. Semantic contradiction detection (via embeddings) not yet implemented.

3. **Style Profile**: Basic tone and sentence analysis. Advanced stylistic features (formality markers, discourse patterns) could be added.

4. **Topic Hierarchy**: Simple parent-child relationships. Full taxonomy/ontology integration not yet implemented.

5. **Real-time Updates**: Pipeline runs on-demand or via backfill. Real-time incremental updates not yet implemented.

### Known Issues

1. **Memory Usage**: Large twins with many sources may require batched processing.

2. **LLM Costs**: Claim extraction and topic building use LLM calls. Monitor costs for large-scale usage.

3. **Date Parsing**: Temporal extraction relies on regex patterns. Edge cases (fiscal years, seasons) may not parse correctly.

## Next Steps (Post-v1)

### Owner Verification

- Owner approval workflow for claims
- In-app claim review interface
- Bulk approve/reject functionality

### Social Auth Ingestion

- Twitter/X OAuth integration
- LinkedIn profile import
- GitHub repository analysis

### Private Uploads

- Secure document upload
- PII detection and redaction
- Medical/financial document handling

### Enhanced Verification

- Web search verification for claims
- Cross-reference with authoritative sources
- Automated fact-checking integration

### Analytics Dashboard

- Completeness score visualization
- Coverage gap identification
- Source authority distribution

## Migration Notes

### Backward Compatibility

- All new tables are additive
- Existing `research_claims` table preserved
- Optional links between new and existing tables
- Feature flags default to "enabled" but can be disabled

### Rollback Procedure

```sql
-- To rollback, simply disable the feature
UPDATE twins SET settings = settings || '{"person_completeness_enabled": false}'::jsonb;

-- To remove data (optional)
-- DELETE FROM person_completeness_runs WHERE created_at > '2026-02-25';
```

## Performance Considerations

### Indexing

All tables have appropriate indexes for:
- Twin ID lookups
- Status filtering
- Fingerprint deduplication
- Temporal queries

### Batching

Pipeline processes sources in batches to avoid memory issues:
- Default batch size: 100 sources
- Configurable via `PC_MAX_SOURCES` env var

### Caching

- Policy lookup cached per instance
- Global score cached per instance
- Refresh on new pipeline run

## Observability

### Metrics Collected

Per pipeline run (`person_completeness_runs`):
- `source_registry_count`
- `claims_extracted_count`
- `evidence_spans_count`
- `timeline_events_count`
- `topic_profiles_count`
- `contradictions_detected_count`

Per stage duration tracked in metadata.

### Logging

Structured logging at each stage:
```
INFO: Building source registry for twin {twin_id}
INFO: Source registry built: +{n} added, ~{m} updated, {d} deduped
INFO: Extracting claims for twin {twin_id}
INFO: Claim extraction completed: {n} claims, {e} evidence spans
```

## Support

### Troubleshooting

**Pipeline stuck in "running" status:**
```sql
-- Check for stuck runs
SELECT * FROM person_completeness_runs 
WHERE status = 'running' 
AND created_at < NOW() - INTERVAL '1 hour';

-- Reset if needed
UPDATE person_completeness_runs 
SET status = 'failed', error_message = 'Timeout' 
WHERE id = 'run-id';
```

**Low answerability scores:**
- Check `person_source_registry` for source count
- Check `person_claims` for claim count
- Verify `person_topic_profiles` has topics

**Missing evidence spans:**
- Verify sources have content_text populated
- Check extraction method is working (rule or LLM)

---

*Document Version: 1.0*
*Implementation Date: 2026-02-25*
*Compatible with: Deep Research Phases 8-12*
