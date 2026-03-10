# Langfuse P2 Implementation Summary

## Overview
This document summarizes the P2 (Priority 2) advanced Langfuse observability features implemented.

---

## Phase 1: Regression Testing System ✅

### Goal
Automatically test new deployments against known examples to catch regressions before production.

### Implementation

**New Files:**
- `backend/modules/regression_testing.py` - Core regression test runner
- `backend/routers/regression_testing.py` - API endpoints

#### Features
1. **Test Runner** (`RegressionTestRunner`)
   - Runs dataset items against chat endpoint
   - Compares new scores to baseline scores
   - Calculates score differences and regression percentages
   - Generates pass/fail/warning status

2. **Baselines**
   - Save current scores as baseline with tags (e.g., "v1.2.3")
   - Compare future runs against specific baselines
   - Track score changes over time

3. **Report Generation**
   - Pass rate percentage
   - Average score diff
   - Worst regressions list
   - Execution time tracking

#### API Endpoints

```bash
# Run regression test
POST /admin/regression/test
{
  "dataset_name": "high_quality_responses",
  "twin_id": "abc-123",
  "sample_size": 50,        # Optional
  "baseline_tag": "v1.2.3", # Optional
  "background": false       # Run synchronously
}

# List available datasets
GET /admin/regression/datasets

# Get test result
GET /admin/regression/test/{test_id}

# Save baseline
POST /admin/regression/baseline
{
  "dataset_name": "high_quality_responses",
  "tag": "pre-refactor"
}

# List baselines for dataset
GET /admin/regression/baselines/{dataset_name}
```

#### Pass/Fail Criteria
- **Failed**: Score drop ≥ 10% from baseline
- **Warning**: Score drop ≥ 5% from baseline
- **Passed**: Score drop < 5% or improved

### Usage
```python
from modules.regression_testing import run_regression_test

report = await run_regression_test(
    dataset_name="high_quality_responses",
    twin_id="twin-123",
    sample_size=50
)

print(f"Pass rate: {report.summary['pass_rate']}%")
print(f"Failed items: {report.failed}")
```

---

## Phase 2: Langfuse Alerting Integration ✅

### Goal
Get notified when quality drops or errors spike.

### Implementation

**New Files:**
- `backend/modules/alerting.py` - Alert manager and rules engine
- `backend/routers/alerts.py` - API endpoints

#### Alert Rule Types

1. **Error Rate Alert**
   - Triggers when error rate > threshold (default: 10%)
   - Time window: 5 minutes
   - Severity: ERROR

2. **Quality Drop Alert**
   - Triggers when avg quality < threshold (default: 0.7)
   - Time window: 10 minutes
   - Severity: WARNING

3. **Latency Spike Alert**
   - Triggers when P95 latency > threshold (default: 5000ms)
   - Time window: 10 minutes
   - Severity: WARNING

4. **Score Drop Alert**
   - Triggers when specific score drops below threshold
   - Monitors: faithfulness, citation_alignment, etc.
   - Severity: ERROR

#### Features
1. **Cooldown Periods** - Prevent alert spam (default: 30 min)
2. **Webhook Notifications** - Send to Slack/email
3. **Alert History** - Track all triggered alerts
4. **Background Monitoring** - Continuous rule checking

#### API Endpoints

```bash
# List all alert rules
GET /admin/alerts/rules

# Create new alert rule
POST /admin/alerts/rules
{
  "name": "High Error Rate",
  "rule_type": "error_rate",
  "threshold": 0.15,
  "time_window_minutes": 5,
  "severity": "error",
  "enabled": true
}

# Update alert rule
PUT /admin/alerts/rules/{rule_id}
{
  "threshold": 0.2,
  "enabled": false
}

# Delete alert rule
DELETE /admin/alerts/rules/{rule_id}

# Run alert check manually
POST /admin/alerts/check

# Get alert history
GET /admin/alerts/history?hours=24&severity=error&limit=100

# Start background monitoring
POST /admin/alerts/start-monitoring?interval_minutes=5

# Get rule types
GET /admin/alerts/rule-types

# Get severities
GET /admin/alerts/severities
```

#### Environment Variables
```bash
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/xxx  # Optional
```

### Usage
```python
from modules.alerting import get_alert_manager

# Check all rules
alerts = await get_alert_manager().check_all_rules()

# Add custom rule
from modules.alerting import AlertRule, AlertRuleType, AlertSeverity

rule = AlertRule(
    id="custom_rule",
    name="My Custom Alert",
    rule_type=AlertRuleType.SCORE_DROP,
    threshold=0.6,
    time_window_minutes=15,
    severity=AlertSeverity.WARNING,
    filters={"score_name": "faithfulness"}
)

get_alert_manager().add_rule(rule)
```

---

## Phase 3: Dynamic Few-Shot Prompting ✅

### Goal
Automatically inject high-quality examples into prompts based on query type.

### Implementation

**New File:**
- `backend/modules/few_shot_prompting.py` - Example selector and formatter

#### Features
1. **Query Type Detection**
   - Uses dialogue_mode from router
   - Falls back to query text analysis
   - Types: stance, factual, smalltalk, teaching, repair, general

2. **Example Selection**
   - Fetches from `high_quality_responses` dataset
   - Filters by query type and min score (default: 0.8)
   - Sorts by score (highest first)
   - Configurable max examples (default: 3)

3. **Formatting Styles**
   - `qa` - Q&A format: "Q1: ... A1: ..."
   - `conversation` - Conversation format: "User: ... Assistant: ..."
   - `structured` - XML-style: "<example>...</example>"

4. **Usage Tracking**
   - Tracks which examples were used in each trace
   - Helps identify most useful examples

#### Query Type Detection
```python
# From dialogue mode
dialogue_mode = "STANCE_GLOBAL"  # → query_type = "stance"

# From query text
"What do I think about..."  # → query_type = "stance"
"Hello, how are you?"       # → query_type = "smalltalk"
```

#### Integration
```python
from modules.few_shot_prompting import inject_few_shot

# In router_node, planner_node, or realizer_node
prompt_with_examples = inject_few_shot(
    base_prompt="You are a helpful assistant...",
    query=user_query,
    dialogue_mode=dialogue_mode
)
```

#### Fallback Examples
When Langfuse is unavailable, uses hardcoded high-quality examples:
- Stance queries
- Factual queries
- Smalltalk queries

### Usage
```python
from modules.few_shot_prompting import get_examples, format_examples

# Get examples
examples = get_examples(query_type="stance", n=3)

# Format for prompt
examples_text = format_examples(examples, style="qa")

# Or inject automatically
from modules.few_shot_prompting import inject_few_shot
enhanced_prompt = inject_few_shot(base_prompt, query, dialogue_mode)
```

---

## Phase 4: Metrics & Analytics API ✅

### Goal
Provide API endpoints for custom dashboards.

### Implementation

**New Files:**
- `backend/modules/metrics_collector.py` - Metrics aggregation from Langfuse
- `backend/routers/langfuse_metrics.py` - API endpoints

#### Metrics Available

1. **Quality Metrics**
   - Overall quality score over time
   - Min/max/avg per time bucket
   - Hourly or daily aggregation

2. **Latency Metrics**
   - Average latency
   - P50, P95, P99 percentiles
   - Min/max latency

3. **Error Metrics**
   - Total traces
   - Error count and rate
   - Breakdown by error type

4. **Persona Metrics**
   - Structure/policy compliance score
   - Voice fidelity score
   - Overall persona score
   - Rewrite count

5. **Dataset Stats**
   - Item count per dataset
   - Average score per dataset

#### API Endpoints

```bash
# Full dashboard metrics
GET /metrics/dashboard?hours=24

# Quality scores over time
GET /metrics/quality?hours=24&interval=hour

# Latency statistics
GET /metrics/latency?hours=24

# Error statistics
GET /metrics/errors?hours=24

# Persona compliance metrics
GET /metrics/persona?hours=24

# Dataset statistics
GET /metrics/dataset

# Search traces
GET /metrics/traces/search?from_hours=24&status=error&limit=50
```

#### Response Format
```json
{
  "time_range": {
    "from": "2024-01-15T10:00:00",
    "to": "2024-01-16T10:00:00",
    "hours": 24
  },
  "quality": [
    {
      "timestamp": "2024-01-15 10:00",
      "avg_score": 0.85,
      "min_score": 0.65,
      "max_score": 0.98,
      "count": 45
    }
  ],
  "latency": {
    "count": 156,
    "avg_ms": 1200,
    "p50_ms": 980,
    "p95_ms": 2500,
    "p99_ms": 4500
  },
  "errors": {
    "total_traces": 156,
    "error_count": 8,
    "error_rate": 5.13,
    "error_types": {
      "ConnectionError": 3,
      "TimeoutError": 5
    }
  },
  "persona": {
    "persona_overall": {"avg": 0.88, "count": 120},
    "persona_structure_policy": {"avg": 0.91, "count": 120},
    "persona_voice_fidelity": {"avg": 0.85, "count": 120},
    "rewrite_count": 12
  },
  "datasets": {
    "high_quality_responses": {"item_count": 450, "avg_score": 0.87},
    "needs_improvement": {"item_count": 32, "avg_score": 0.42}
  }
}
```

### Usage
```python
from modules.metrics_collector import get_metrics_collector

collector = get_metrics_collector()

# Get all dashboard metrics
metrics = await collector.get_full_dashboard_metrics(hours=24)

# Get specific metrics
quality = await collector.get_quality_metrics(from_time, to_time, interval="hour")
latency = await collector.get_latency_metrics(from_time, to_time)
errors = await collector.get_error_metrics(from_time, to_time)
```

---

## Phase 5: Dataset Export for Fine-Tuning ✅

### Goal
Export datasets in formats ready for model training.

### Implementation

**New Files:**
- `backend/modules/dataset_exporter.py` - Export logic
- `backend/routers/dataset_export.py` - API endpoints

#### Export Formats

1. **JSONL** (default)
   - Standard JSON Lines format
   - Includes full metadata
   - Files: `{name}.train.jsonl`, `{name}.val.jsonl`

2. **CSV**
   - Spreadsheet-friendly format
   - Columns: query, response, score, query_type
   - Files: `{name}.train.csv`, `{name}.val.csv`

3. **OpenAI**
   - OpenAI fine-tuning format
   - Messages array with system/user/assistant roles
   - Files: `{name}.train.jsonl`, `{name}.val.jsonl`

4. **HuggingFace**
   - HuggingFace datasets format
   - instruction/input/output/context format
   - Creates directory with train.jsonl and validation.jsonl

#### Features

1. **Filtering**
   - Min/max score filter
   - Query type filter
   - Date range filter

2. **Train/Val Split**
   - Configurable split ratio (default: 80/20)
   - Random shuffle with seed

3. **Statistics**
   - Item counts
   - Score distributions
   - Query type breakdown

#### API Endpoints

```bash
# Export dataset
POST /admin/datasets/{dataset_name}/export
{
  "output_path": "/data/exports/high_quality.jsonl",
  "format": "openai",
  "min_score": 0.8,
  "max_score": 1.0,
  "query_type": "stance",
  "from_date": "2024-01-01T00:00:00",
  "to_date": "2024-01-31T23:59:59",
  "train_split": 0.8,
  "background": false
}

# Get export formats
GET /admin/datasets/export/formats

# Get dataset stats
GET /admin/datasets/{dataset_name}/stats
```

#### Export Output
```bash
# JSONL output
data/exports/
  high_quality.train.jsonl
  high_quality.val.jsonl
  high_quality.stats.json

# HuggingFace output
data/exports/high_quality/
  train.jsonl
  validation.jsonl
  stats.json
```

#### Stats File
```json
{
  "export_timestamp": "2024-01-16T10:00:00",
  "total_items": 450,
  "train_items": 360,
  "val_items": 90,
  "train_split": 0.8,
  "avg_score": 0.87,
  "min_score": 0.80,
  "max_score": 0.98,
  "query_types": {
    "stance": 150,
    "factual": 200,
    "smalltalk": 100
  }
}
```

### Usage
```python
from modules.dataset_exporter import get_dataset_exporter, ExportFormat

exporter = get_dataset_exporter()

# Export for OpenAI fine-tuning
stats = await exporter.export_dataset(
    dataset_name="high_quality_responses",
    output_path="/data/exports/training.jsonl",
    format=ExportFormat.OPENAI,
    min_score=0.8,
    train_split=0.8
)

print(f"Exported {stats['total_items']} items")
print(f"Train: {stats['train_items']}, Val: {stats['val_items']}")
```

---

## Files Created/Modified

### New Files
| File | Purpose |
|------|---------|
| `backend/modules/regression_testing.py` | Regression test runner |
| `backend/modules/alerting.py` | Alert manager and rules |
| `backend/modules/few_shot_prompting.py` | Dynamic few-shot examples |
| `backend/modules/metrics_collector.py` | Metrics aggregation |
| `backend/modules/dataset_exporter.py` | Dataset export logic |
| `backend/routers/regression_testing.py` | Regression testing API |
| `backend/routers/alerts.py` | Alerts management API |
| `backend/routers/langfuse_metrics.py` | Metrics API |
| `backend/routers/dataset_export.py` | Dataset export API |

### Modified Files
| File | Change |
|------|--------|
| `backend/main.py` | Registered new routers |

---

## All API Endpoints Summary

### Regression Testing
- `POST /admin/regression/test` - Run regression test
- `GET /admin/regression/datasets` - List datasets
- `GET /admin/regression/test/{test_id}` - Get test result
- `POST /admin/regression/baseline` - Save baseline
- `GET /admin/regression/baselines/{dataset_name}` - List baselines

### Alerts
- `GET /admin/alerts/rules` - List rules
- `POST /admin/alerts/rules` - Create rule
- `PUT /admin/alerts/rules/{id}` - Update rule
- `DELETE /admin/alerts/rules/{id}` - Delete rule
- `POST /admin/alerts/check` - Run check
- `GET /admin/alerts/history` - Get history
- `POST /admin/alerts/start-monitoring` - Start monitoring
- `GET /admin/alerts/rule-types` - List rule types
- `GET /admin/alerts/severities` - List severities

### Metrics
- `GET /metrics/dashboard` - Full dashboard
- `GET /metrics/quality` - Quality metrics
- `GET /metrics/latency` - Latency metrics
- `GET /metrics/errors` - Error metrics
- `GET /metrics/persona` - Persona metrics
- `GET /metrics/dataset` - Dataset stats
- `GET /metrics/traces/search` - Search traces

### Dataset Export
- `POST /admin/datasets/{name}/export` - Export dataset
- `GET /admin/datasets/export/formats` - List formats
- `GET /admin/datasets/{name}/stats` - Get stats

---

## Complete Langfuse Integration Summary

### P0 (Critical) ✅
- Tracing for all chat endpoints
- Error tagging for failure visibility
- Agent graph node tracing

### P1 (Priority) ✅
- Frontend trace ID propagation
- Langfuse Prompt Management
- Automatic LLM Judge Scoring
- Dataset Collection
- Persona Audit Scoring

### P2 (Advanced) ✅
- Regression Testing System
- Langfuse Alerting Integration
- Dynamic Few-Shot Prompting
- Metrics & Analytics API
- Dataset Export for Fine-Tuning

---

## Next Steps (P3 Ideas)

1. **Custom Dashboard UI** - Build React components for metrics visualization
2. **Trace Comparison** - Compare two traces side-by-side
3. **Prompt Playground** - Test prompts directly in UI
4. **A/B Testing Framework** - Systematic prompt/model comparison
5. **Cost Optimization** - Track and optimize token usage
6. **Synthetic Monitoring** - Run test queries continuously
