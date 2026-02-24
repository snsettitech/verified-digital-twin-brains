# Training Metrics V2 Migration Plan

## Executive Summary

This document outlines the migration path from V1 heuristic-based metrics to V2 eval-backed metrics while maintaining API contract compatibility.

**Current Version:** v1_heuristic  
**Target Version:** v2_eval_backed  
**Migration Strategy:** Gradual rollout with backward compatibility

---

## Current State (V1)

### V1 Heuristic Formulas

| Metric | V1 Method | Accuracy |
|--------|-----------|----------|
| Words Processed | Regex word count | High (actual count) |
| Questions Answerable | `(words/90) * quality * diversity * 0.85` | Medium (estimate) |
| Mind Score | Weighted component scores | Medium (proxy signals) |

### V1 Component Weights
```
Mind Score = 0.25*volume + 0.20*diversity + 0.20*quality + 
             0.10*freshness + 0.15*structure + 0.10*verification
```

---

## Target State (V2)

### V2 Eval-Backed Methods

| Metric | V2 Method | Accuracy |
|--------|-----------|----------|
| Words Processed | Same regex count | High (unchanged) |
| Questions Answerable | Synthetic QA evaluation | High (actual coverage) |
| Mind Score | Grounded answer rate + coverage | High (measured) |

### V2 New Components

1. **Synthetic QA Generation**
   - Generate questions from source content
   - Test twin's ability to answer
   - Measure coverage and accuracy

2. **Retrieval Quality Score**
   - Measure relevance of retrieved chunks
   - Track citation accuracy
   - Monitor hallucination rate

3. **Topic Coverage Analysis**
   - Extract topic graph from sources
   - Measure depth per topic
   - Identify knowledge gaps

---

## Migration Strategy

### Phase 1: Infrastructure (Weeks 1-2)

**Goal:** Add V2 calculation capability without changing API

1. **Create V2 Calculator Module**
   ```python
   # backend/modules/training_metrics_v2.py
   class TrainingMetricsV2Calculator:
       def compute_questions_answerable(self, twin_id: str) -> int:
           # Synthetic QA evaluation
           pass
       
       def compute_mind_score(self, twin_id: str) -> int:
           # Grounded answer rate + coverage
           pass
   ```

2. **Add Method Version Switching**
   ```python
   # backend/modules/training_metrics.py
   def compute_training_metrics(twin_id: str, method: str = "auto") -> TrainingMetrics:
       if method == "v1_heuristic":
           return _compute_v1(twin_id)
       elif method == "v2_eval":
           return _compute_v2(twin_id)
       elif method == "auto":
           # Check feature flag / tenant config
           return _compute_v2(twin_id) if _should_use_v2() else _compute_v1(twin_id)
   ```

3. **Database Schema (No Migration Needed)**
   - Use existing `twin.settings.training_metrics` JSON field
   - Add `method_version` field to track which version computed the metrics

### Phase 2: Dual Calculation (Weeks 3-4)

**Goal:** Run V1 and V2 side-by-side for comparison

1. **Compute Both Versions**
   - V2 runs in background
   - Store both results in settings
   ```json
   {
     "training_metrics": {
       "method_version": "v1_heuristic",
       "v2_preview": {
         "questions_answerable_est": 2150,
         "mind_score": 74,
         "method_version": "v2_eval"
       }
     }
   }
   ```

2. **Internal A/B Comparison Dashboard**
   - Compare V1 vs V2 metrics
   - Identify significant deltas
   - Tune V2 parameters

3. **Performance Monitoring**
   - V2 calculation latency (target: <5s for 100 sources)
   - Synthetic QA generation cost
   - Cache hit rates

### Phase 3: Gradual Rollout (Weeks 5-6)

**Goal:** Enable V2 for select twins/tenants

1. **Feature Flag Tiers**
   ```python
   TRAINING_METRICS_VERSION=auto  # Default: v1 for now
   TRAINING_METRICS_VERSION=v1    # Force V1
   TRAINING_METRICS_VERSION=v2    # Force V2
   ```

2. **Tenant-Level Opt-In**
   ```python
   # In tenant settings
   {
     "features": {
       "training_metrics_version": "v2"
     }
   }
   ```

3. **Gradual Migration**
   - Week 5: 10% of new twins use V2
   - Week 6: 50% of new twins use V2
   - Monitor for issues

### Phase 4: Full Migration (Weeks 7-8)

**Goal:** V2 becomes default

1. **Default Switch**
   - Change default from `v1_heuristic` to `v2_eval`
   - Existing twins keep V1 until recalculated

2. **Backfill Strategy**
   - Nightly job to recalculate V2 for active twins
   - Priority: High-traffic twins first
   - Estimated time: 1-2 weeks for full backfill

3. **V1 Deprecation**
   - Mark V1 as deprecated in docs
   - Keep V1 code for 1 quarter
   - Remove after confirmation of V2 stability

---

## API Contract Stability

### What Stays the Same

The API response format remains **unchanged**:

```json
{
  "training_metrics": {
    "words_processed": 167123,
    "words_processed_display": "167.1K",
    "questions_answerable_est": 2140,
    "questions_answerable_display": "2.1K",
    "mind_score": 72,
    "mind_score_label": "Strong",
    "method_version": "v2_eval",  // Only this changes
    "last_computed_at": "...",
    "notes": "..."
  }
}
```

### Frontend Compatibility

- No frontend changes required
- `method_version` field is informational
- Component scores (debug endpoint) may have new fields

---

## Rollback Plan

### Immediate Rollback (< 1 hour)

```bash
# Set feature flag to force V1
export TRAINING_METRICS_VERSION=v1
```

### Selective Rollback

```python
# In admin endpoint
POST /admin/twins/{twin_id}/metrics/version
{
  "version": "v1_heuristic"
}
```

### Data Preservation

- V1 metrics cached in `training_metrics.v1_fallback`
- Can restore if V2 calculation fails

---

## Testing Strategy

### Unit Tests

```python
# test_training_metrics_v2.py
def test_v2_questions_answerable():
    # Mock synthetic QA pipeline
    pass

def test_v2_mind_score():
    # Mock retrieval quality
    pass
```

### Integration Tests

1. **A/B Test Comparison**
   - Compare V1 vs V2 for 100 sample twins
   - Assert delta < 20% for questions_answerable
   - Assert delta < 15 points for mind_score

2. **Performance Tests**
   - V2 calculation < 5s for twin with 100 sources
   - Memory usage < 500MB

3. **Contract Tests**
   - API response schema unchanged
   - Frontend component renders correctly

### Canary Deployment

1. Deploy to staging
2. Run synthetic traffic for 24 hours
3. Deploy to 5% of production traffic
4. Monitor for 48 hours
5. Gradual rollout to 100%

---

## Monitoring & Alerting

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| V2 calculation latency | < 5s | > 10s |
| V2 error rate | < 1% | > 5% |
| V1 vs V2 delta (questions) | < 30% | > 50% |
| V1 vs V2 delta (mind) | < 20 points | > 30 points |

### Alerts

```python
# Pseudo-alert configuration
ALERT v2_calculation_latency > 10s:
  severity: warning
  action: Check synthetic QA pipeline

ALERT v2_error_rate > 5%:
  severity: critical
  action: Rollback to V1

ALERT v1_v2_delta_questions > 50%:
  severity: warning
  action: Review V2 algorithm
```

---

## Timeline

| Week | Milestone |
|------|-----------|
| 1-2 | Infrastructure, V2 calculator |
| 3-4 | Dual calculation, internal dashboard |
| 5-6 | Gradual rollout (10% → 50%) |
| 7-8 | Full migration, V2 default |
| 9-12 | Monitoring, V1 deprecation period |
| 13+ | V1 removal (if stable) |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| V2 calculation too slow | Medium | High | Background async calculation |
| V2 scores wildly different | Low | High | A/B testing, gradual rollout |
| Synthetic QA cost too high | Medium | Medium | Caching, sampling |
| API contract breakage | Low | Critical | Comprehensive contract tests |

---

## Success Criteria

1. **Zero API contract breakages**
2. **V2 calculation < 5s for 95th percentile**
3. **V1 vs V2 delta within acceptable bounds**
4. **No customer-facing regressions**
5. **Clean rollback within 1 hour if needed**

---

## Appendix: Implementation Notes

### Synthetic QA Pipeline

```python
# Pseudocode for V2 questions_answerable

def compute_questions_answerable_v2(twin_id: str) -> int:
    sources = get_sources(twin_id)
    
    # Generate questions from sources
    questions = []
    for source in sources:
        qs = llm_generate_questions(source.content_text, n=5)
        questions.extend(qs)
    
    # Test twin's ability to answer
    answered = 0
    for q in questions:
        response = query_twin(twin_id, q)
        if is_answer_accurate(q, response, source):
            answered += 1
    
    # Scale up based on coverage
    coverage_ratio = answered / len(questions)
    estimated_total = int(len(questions) * coverage_ratio * source_diversity_factor)
    
    return estimated_total
```

### Cached Calculation

```python
# To avoid recomputing on every request
@cache_for(hours=24)
def compute_training_metrics_v2(twin_id: str) -> TrainingMetrics:
    # Expensive calculation here
    pass
```

---

## Related Documents

- `TRAINING_METRICS_V1.md` - Current V1 documentation
- `API_CONTRACT.md` - API stability guarantees
- `FEATURE_FLAGS.md` - Feature flag configuration
