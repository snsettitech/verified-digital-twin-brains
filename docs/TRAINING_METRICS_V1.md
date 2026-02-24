# Training Metrics V1 Documentation

## Overview

Delphi-style profile training metrics for the Digital Brains platform. These metrics provide users with understandable, market-friendly indicators of their twin's training completeness and knowledge coverage.

**Version:** v1_heuristic  
**Status:** Production Ready  
**Feature Flag:** `PROFILE_TRAINING_METRICS_ENABLED` (default: true)

---

## Metrics Overview

### 1. Words Processed

**Definition:** Total number of words extracted and processed from successfully ingested sources.

**Rules:**
- Counts words from `content_text` field in sources table (post-extraction, pre-chunking)
- Only includes sources with `status` in ("live", "processed", "staged", "active")
- Does NOT count failed sources
- Does NOT count binary files with no extracted text
- Uses regex-based word tokenization: `\b[a-zA-Z0-9\'-]+\b`

**Example Outputs:**
- 12,450 → "12.5K"
- 87,900 → "87.9K"
- 167,123 → "167.1K"

**Implementation:**
```python
from modules.training_metrics import count_words
word_count = count_words(content_text)
```

---

### 2. Questions Answerable (Estimated)

**Definition:** Estimated number of distinct user questions the twin can answer based on content volume, diversity, and extraction quality.

**⚠️ IMPORTANT:** This is an ESTIMATE, not a literal count of manually validated questions.

**V1 Heuristic Formula:**

```
base_estimate = words_processed / WORDS_PER_QUESTION_BASELINE
                where WORDS_PER_QUESTION_BASELINE = 90

quality_adjusted = base_estimate * quality_factor
                   where quality_factor = extraction_success_rate

diversity_adjusted = quality_adjusted * (1 + (diversity_factor - 1) * 0.3)
                     where diversity_factor increases with source type count

final_estimate = diversity_adjusted * COMPRESSION_FACTOR
                 where COMPRESSION_FACTOR = 0.85
```

**Example Outputs:**
- Small profile: 130 → "130"
- Medium profile: 980 → "980"
- Large profile: 2,140 → "2.1K"

---

### 3. Mind Score (0-100)

**Definition:** A user-facing training completeness / profile readiness score.

**Scoring Components (Weighted):**

| Component | Weight | Description |
|-----------|--------|-------------|
| Volume Score | 25% | Words processed (logarithmic scale) |
| Diversity Score | 20% | Source type variety |
| Quality Score | 20% | Extraction success rate |
| Freshness Score | 10% | Recency of sources |
| Structure Score | 15% | Content organization signals |
| Verification Score | 10% | Owner-approved QnA count |

**Formula:**
```
mind_score = round(
    0.25 * volume_score +
    0.20 * diversity_score +
    0.20 * quality_score +
    0.10 * freshness_score +
    0.15 * structure_score +
    0.10 * verification_score
)
```

**Score Labels:**

| Score Range | Label | Description |
|-------------|-------|-------------|
| 0-15 | Early | New/empty profile |
| 15-35 | Growing | Some data ingested |
| 35-55 | Developing | Building coverage |
| 55-75 | Strong | Multi-source profile |
| 75-90 | Highly Trained | Well-trained profile |
| 90-100 | Expert | Exceptional coverage |

**Color Coding:**
- 75-100: Emerald (green)
- 55-75: Blue
- 35-55: Amber (yellow)
- 15-35: Orange
- 0-15: Slate (gray)

---

## Technical Implementation

### Backend Module

**File:** `backend/modules/training_metrics.py`

**Key Functions:**

```python
# Compute metrics for a twin
from modules.training_metrics import compute_training_metrics
metrics = compute_training_metrics(twin_id="uuid")

# Get metrics formatted for API
from modules.training_metrics import get_training_metrics_for_api
api_response = get_training_metrics_for_api(twin_id="uuid")

# Update cached metrics in twin settings
from modules.training_metrics import update_twin_training_metrics
success = update_twin_training_metrics(twin_id="uuid")

# Check feature flag
from modules.training_metrics import is_training_metrics_enabled
enabled = is_training_metrics_enabled()  # Checks PROFILE_TRAINING_METRICS_ENABLED env var
```

### API Response Format

```json
{
  "training_metrics": {
    "words_processed": 167123,
    "words_processed_display": "167.1K",
    "questions_answerable_est": 2140,
    "questions_answerable_display": "2.1K",
    "mind_score": 72,
    "mind_score_label": "Strong",
    "method_version": "v1_heuristic",
    "last_computed_at": "2024-01-15T10:30:00Z",
    "notes": "Estimated metrics based on ingested content volume, diversity, and extraction quality."
  }
}
```

### Frontend Component

**File:** `frontend/components/ui/TrainingMetrics.tsx`

**Usage:**

```tsx
import { TrainingMetrics } from '@/components/ui';

// Full metrics display
<TrainingMetrics 
  metrics={trainingMetrics}
  size="md"
  showLabels={true}
/>

// Compact display for headers
<TrainingMetricsCompact metrics={trainingMetrics} />
```

---

## Recompute Triggers

Metrics are automatically recomputed:

1. **After successful ingestion job completion**
   - Location: `backend/modules/training_jobs.py`
   - Called after `status = "complete"` for ingestion/reindex jobs

2. **On-demand via API**
   - Metrics included in GET `/twins/{twin_id}` response
   - Cached for 1 hour to reduce compute load

3. **Manual recompute (admin/debug)**
   ```python
   from modules.training_metrics import update_twin_training_metrics
   update_twin_training_metrics(twin_id)
   ```

---

## Volume Score Tiers

| Words | Score | Description |
|-------|-------|-------------|
| 0 | 0 | Empty profile |
| 100 | 10 | Minimal content |
| 1,000 | 25 | Small profile |
| 10,000 | 50 | Medium profile |
| 50,000 | 70 | Large profile |
| 100,000 | 85 | Extensive profile |
| 500,000 | 95 | Massive profile |
| 1,000,000 | 100 | Maximum score |

---

## Source Type Detection

Source types are detected from citation URLs:

| URL Pattern | Type | Multiplier |
|-------------|------|------------|
| youtube.com, youtu.be | youtube | 1.2 |
| twitter.com, x.com | x | 1.1 |
| linkedin.com | linkedin | 1.2 |
| instagram.com | instagram | 1.1 |
| facebook.com | facebook | 1.0 |
| .rss, podcast | podcast | 1.3 |
| http/https (other) | web | 1.0 |
| No URL (file upload) | file | 1.0 |

---

## Known Limitations (V1)

1. **Duplicate Content**: V1 may overcount if the same content is ingested multiple times. No deduplication is performed.

2. **Question Estimate**: The "questions answerable" metric is a heuristic estimate, not a validated count. It assumes ~90 words per question baseline.

3. **Freshness Score**: Currently gives neutral/full score if timestamp data exists. V2 will implement time-decay scoring.

4. **Structure Score**: Based on word count thresholds. V2 will analyze actual document structure (headings, sections, etc.).

5. **Quality Score**: Based on extraction success rate. V2 will incorporate actual retrieval quality metrics.

---

## V2 Roadmap

### Planned Improvements

1. **Eval-Backed Metrics**
   - Synthetic question generation and answering
   - Grounded answer rate measurement
   - Actual retrieval quality scoring

2. **Deduplication**
   - Content hash-based deduplication
   - Near-duplicate detection

3. **Topic Coverage Analysis**
   - Extract topic graph from content
   - Measure coverage depth per topic
   - Identify knowledge gaps

4. **Freshness Scoring**
   - Time-decay based on content age
   - Priority boost for recent sources

5. **Structure Analysis**
   - Parse headings, sections, FAQs
   - Measure semantic organization

---

## Testing

**Test File:** `backend/tests/test_training_metrics.py`

**Run Tests:**
```bash
cd backend
pytest tests/test_training_metrics.py -v
```

**Test Coverage:**
- Word counting (empty, unicode, punctuation, large text)
- Number formatting (K, M, B)
- Volume score calculation
- Diversity score calculation
- Quality score calculation
- Mind score calculation
- Question estimation
- Determinism (same inputs = same outputs)
- Integration with Supabase

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROFILE_TRAINING_METRICS_ENABLED` | `true` | Enable/disable training metrics feature |

---

## Files Modified/Created

### Backend
- `backend/modules/training_metrics.py` (NEW)
- `backend/modules/schemas.py` (TrainingMetricsSchema added)
- `backend/modules/training_jobs.py` (Trigger added)
- `backend/routers/twins.py` (Endpoint updated)
- `backend/tests/test_training_metrics.py` (NEW)

### Frontend
- `frontend/components/ui/TrainingMetrics.tsx` (NEW)
- `frontend/components/ui/index.tsx` (Exports added)
- `frontend/app/dashboard/profile/page.tsx` (Integration)

### Documentation
- `docs/TRAINING_METRICS_V1.md` (THIS FILE)

---

## FAQ

**Q: Why is my word count different from my file's word count?**  
A: We count words from extracted text after cleaning (HTML removal, normalization). This may differ from your source document's word count.

**Q: How accurate is the "Questions Answerable" metric?**  
A: It's a heuristic estimate based on content volume. V2 will use actual synthetic question evaluation for higher accuracy.

**Q: Can I manually adjust my Mind Score?**  
A: No, the Mind Score is computed automatically based on your twin's content. Add more diverse, high-quality sources to improve it.

**Q: Why did my score drop after adding content?**  
A: This can happen if the new source had extraction failures, lowering your quality score. Check the source status in the Knowledge section.

**Q: How often are metrics updated?**  
A: Immediately after each successful ingestion. API responses are cached for 1 hour.

---

## Support

For issues or questions about training metrics:
1. Check the logs for computation errors
2. Verify `PROFILE_TRAINING_METRICS_ENABLED=true`
3. Run the test suite to verify installation
4. Contact engineering with the twin ID and expected vs actual metrics
