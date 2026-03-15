# Retrieval System Alerts & Runbook

**Date**: 2026-02-12  
**System**: Chat Retrieval Pipeline  

---

## Alert Severity Levels

| Severity | Description | Response Time |
|----------|-------------|---------------|
| P0 (Critical) | Retrieval completely down | Immediate (15 min) |
| P1 (High) | Degraded performance or high error rate | 1 hour |
| P2 (Medium) | Warnings, capacity concerns | 4 hours |
| P3 (Low) | Informational | Next business day |

---

## P0 Alerts (Critical)

### Alert: Retrieval Completely Down

**Trigger**: 
- Success rate = 0% for 5 minutes
- OR Health check endpoint returns unhealthy

**Symptoms**:
- Chat returns "I don't know" for all queries
- No contexts being retrieved
- Users reporting "brain not responding"

**Diagnostic Steps**:
1. Check health endpoint:
   ```bash
   curl /debug/retrieval/health
   ```

2. Run diagnostic script:
   ```bash
   python scripts/diagnose_retrieval.py <twin-id>
   ```

3. Check logs for errors:
   ```bash
   grep -i "retrieval\|error\|fail" logs/app.log
   ```

**Common Causes & Fixes**:

| Cause | Check | Fix |
|-------|-------|-----|
| Pinecone down | Health check fails | Wait for Pinecone recovery or failover |
| OpenAI API down | Embedding errors | Check OpenAI status page |
| Out of memory | System OOM errors | Restart app, scale up memory |
| Database connection lost | Supabase errors | Check DB connection pool |

**Escalation**: Escalate to on-call engineer immediately if not resolved in 15 minutes.

---

## P1 Alerts (High)

### Alert: High Error Rate

**Trigger**: 
- Error rate > 5% for 10 minutes
- OR Success rate < 95%

**Symptoms**:
- Intermittent retrieval failures
- Some queries work, others don't
- Increased latency

**Diagnostic Steps**:
1. Check metrics:
   ```bash
   curl /debug/retrieval/metrics
   ```

2. Look at error breakdown:
   ```json
   {
     "metrics": {
       "errors": {
         "pinecone_timeout": 15,
         "embedding_failed": 3
       }
     }
   }
   ```

**Common Causes & Fixes**:

| Cause | Fix |
|-------|-----|
| Pinecone rate limiting | Reduce query parallelism |
| Embedding API throttling | Enable circuit breaker |
| Namespace not found | Check CREATOR_NAMESPACE_DUAL_READ setting |
| Group permissions misconfigured | Verify access groups |

---

### Alert: High Latency

**Trigger**:
- Average retrieval time > 2000ms for 10 minutes
- OR p95 latency > 5000ms

**Diagnostic Steps**:
1. Check phase timing:
   ```bash
   curl /debug/retrieval/metrics | jq '.phase_timing'
   ```

2. Identify slow phase:
   ```json
   {
     "phase_timing": {
       "vector_search": {"avg_ms": 1500, "p95_ms": 3000},
       "embedding": {"avg_ms": 500, "p95_ms": 800}
     }
   }
   ```

**Common Causes & Fixes**:

| Slow Phase | Cause | Fix |
|------------|-------|-----|
| vector_search | Too many namespaces | Reduce namespace candidates |
| vector_search | Large index | Add Pinecone metadata filters |
| embedding | OpenAI slow | Use HuggingFace fallback |
| reranking | FlashRank slow | Disable reranking temporarily |

---

## P2 Alerts (Medium)

### Alert: No Vectors for Twin

**Trigger**:
- Twin has 0 vectors in all namespaces
- AND twin has sources uploaded

**Diagnostic Steps**:
1. Check namespace inspection:
   ```bash
   curl /debug/retrieval/namespaces/{twin_id}
   ```

2. Check source processing status in Supabase:
   ```sql
   SELECT id, filename, status, error_message 
   FROM sources 
   WHERE twin_id = 'xxx' AND status != 'completed';
   ```

**Common Causes**:
- Documents still processing
- Ingestion job failed
- Wrong namespace format

**Fix**:
- Retry failed ingestion jobs
- Check ingestion worker logs
- Verify CREATOR_NAMESPACE_DUAL_READ=true

---

### Alert: Namespace Cache Stale

**Trigger**:
- Creator ID resolution returning wrong values
- Vectors found in unexpected namespace

**Fix**:
```python
from modules.twin_namespace import clear_creator_namespace_cache
clear_creator_namespace_cache()
```

Or restart the app to clear all caches.

---

## P3 Alerts (Low)

### Alert: Low Retrieval Volume

**Trigger**:
- Retrieval count < expected for time of day

**Diagnostic**:
- Check if chat traffic is low
- Verify monitoring is working

---

## Monitoring Queries

### Prometheus Queries

```promql
# Retrieval success rate
rate(retrieval_successful[5m]) / rate(retrieval_total[5m])

# Average latency
retrieval_duration_ms{stat="avg"}

# Error rate by type
rate(retrieval_errors[5m]) by (error_type)

# Namespace hit rate
rate(retrieval_namespace_hits[5m]) by (namespace)
```

### Log Queries (Loki/ELK)

```
# Find retrieval errors
{app="digital-twin"} |= "retrieval" |= "error"

# Find slow retrievals
{app="digital-twin"} |= "retrieval_complete" | json | duration_ms > 2000

# Find specific twin issues
{app="digital-twin"} |= "twin_id" |= "xxx"
```

---

## Runbook: Common Issues

### Issue: "I don't know" responses

**Check**:
1. Are there vectors for the twin?
   ```bash
   curl /debug/retrieval/namespaces/{twin_id}
   ```

2. Is retrieval working?
   ```bash
   curl -X POST /debug/retrieval \
     -d '{"query": "test", "twin_id": "xxx"}'
   ```

3. Check confidence scores - might be below threshold

### Issue: Wrong contexts returned

**Check**:
1. Embedding quality:
   ```bash
   curl -X POST /debug/retrieval/test-embedding \
     -d '{"text": "your query"}'
   ```

2. Reranking scores in logs
3. Group permissions filtering too aggressively

### Issue: High Pinecone costs

**Check**:
1. Namespace query count
2. TopK values (reduce from 20 to 10)
3. Query expansion generating too many queries

**Fix**:
- Reduce `top_k` parameter
- Disable query expansion for simple queries
- Add caching layer

---

## Escalation Matrix

| Issue | First Response | Escalation |
|-------|---------------|------------|
| Complete outage | On-call engineer | Engineering manager (30 min) |
| Performance degradation | On-call engineer | Tech lead (1 hour) |
| Data inconsistency | Backend engineer | Data team (2 hours) |
| Infrastructure issues | DevOps | SRE team (immediate) |

---

## Contacts

- **On-call**: #incidents Slack channel
- **Engineering Manager**: manager@company.com
- **Tech Lead**: lead@company.com
- **Pinecone Support**: support@pinecone.io

---

## Related Documentation

- [Production Deployment Runbook](./PRODUCTION_DEPLOYMENT_RUNBOOK.md)
- [Feature Flags Guide](../../FEATURE_FLAGS_EXPLAINED.md)
- [Retrieval Diagnostic Report](../../RETRIEVAL_DIAGNOSTIC_REPORT.md)
