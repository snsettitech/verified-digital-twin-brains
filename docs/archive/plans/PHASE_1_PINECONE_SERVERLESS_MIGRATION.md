# Phase 1: Pinecone Serverless Migration
## Detailed Implementation Plan

**Objective:** Migrate from Pinecone pod-based to Pinecone Serverless  
**Duration:** 2-3 weeks  
**Status:** Research Complete → Ready for Implementation  

---

## 📊 Current State Analysis

### Your Current Pinecone Setup
| Attribute | Current Value | Notes |
|-----------|---------------|-------|
| **Index Name** | `digital-twin-brain` | Pod-based |
| **Dimension** | 3072 | text-embedding-3-large |
| **Host** | `https://digital-twin-brain-nrnzovv.svc.aped-4627-b74a.pinecone.io` | AWS us-east-1 |
| **API Key** | `pcsk_...` | Available in .env |
| **Estimated Vectors** | Unknown | Need to verify |
| **Namespaces** | Twin-based (per-twin) | Current strategy |

### Why Migrate to Serverless?

| Metric | Pod-Based (Current) | Serverless (Target) | Improvement |
|--------|---------------------|---------------------|-------------|
| **Cost** | ~$200/month (estimated) | ~$50-150/month | **24-75% savings** |
| **Scaling** | Manual pod sizing | Auto-scale | Zero ops |
| **Cold Start** | None | <100ms | Acceptable |
| **Warm Query Latency** | ~30ms P99 | ~10-50ms P99 | **Better** |
| **Max Namespaces** | 1,000 per index | 25,000+ per index | **25x more** |
| **Multi-tenancy** | Complex | Native | Simplified |

### Delphi.ai Reference Architecture
From Pinecone case study:
- **100M+ vectors** across **12,000+ namespaces**
- **<100ms P95 latency** for retrieval
- **20 QPS globally** with zero scaling incidents
- **Namespace-per-creator** (not per-twin)

---

## ⚠️ Common Migration Issues (Research-Based)

### Issue 1: SSL/Certificate Errors (Windows)
**Symptoms:** `SSLCertVerificationError` when connecting  
**Root Cause:** Windows certificate store not properly configured  
**Solution:** Set `SSL_CERT_FILE` environment variable  
**Status:** ✅ Already fixed in your setup

### Issue 2: SDK Version Incompatibility
**Symptoms:** API errors, missing methods like `query_namespaces`  
**Root Cause:** Using SDK < 3.0.0  
**Solution:** Upgrade to `pinecone>=3.0.0`  
**Action Required:** ⏳ Verify and upgrade

### Issue 3: Migration Data Loss
**Symptoms:** Missing vectors after migration  
**Root Cause:** Writes during migration not captured  
**Solution:** Pause writes or log to replay  
**Mitigation:** Dual-write strategy during transition

### Issue 4: Namespace Strategy Mismatch
**Symptoms:** Query returns wrong results after migration  
**Root Cause:** Changed namespace naming convention  
**Solution:** Maintain namespace mapping during transition

### Issue 5: Metadata Filtering Changes
**Symptoms:** Filter queries slower or failing  
**Root Cause:** Serverless handles metadata differently  
**Solution:** Review and optimize metadata schema

### Issue 6: Cold Start Latency
**Symptoms:** First query slow (>500ms)  
**Root Cause:** Serverless cold start for inactive namespaces  
**Solution:** Keep-alive queries for hot namespaces

### Issue 7: Rate Limiting (429 Errors)
**Symptoms:** `TooManyRequests` errors  
**Root Cause:** Serverless has per-second operation limits  
**Solution:** Implement exponential backoff retry

---

## 🗓️ Detailed 3-Week Implementation Plan

### Week 1: Preparation & Testing

#### Day 1-2: Audit Current State
```python
# audit_current_state.py
from pinecone import Pinecone
import os

pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])

# List all indexes
indexes = pc.list_indexes()
print("Current Indexes:")
for idx in indexes:
    print(f"  - {idx['name']}: {idx.get('dimension', 'N/A')} dims")

# Analyze current index
index_name = "digital-twin-brain"
index = pc.Index(index_name)
stats = index.describe_index_stats()
print(f"\nIndex Stats for '{index_name}':")
print(f"  Total vectors: {stats.total_vector_count}")
print(f"  Dimension: {stats.dimension}")
print(f"  Namespaces: {len(stats.namespaces)}")
for ns, count in stats.namespaces.items():
    print(f"    - {ns}: {count} vectors")
```

**Deliverables:**
- [ ] Document current vector count per namespace
- [ ] Record current metadata schema
- [ ] Identify top 10 most queried namespaces
- [ ] Export sample vectors for testing

#### Day 3-4: Create Serverless Index
```python
# create_serverless_index.py
from pinecone import Pinecone, ServerlessSpec, Metric
import os

pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])

# Create serverless index
index_name = "digital-twin-serverless"

try:
    pc.create_index(
        name=index_name,
        dimension=3072,  # Match existing
        metric=Metric.COSINE,
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        ),
        tags={
            "environment": "production",
            "migration": "phase-1",
            "project": "digital-twin"
        }
    )
    print(f"✓ Created serverless index: {index_name}")
    
    # Get index host
    index_info = pc.describe_index(index_name)
    print(f"  Host: {index_info.host}")
    print(f"  Status: {index_info.status}")
    
except Exception as e:
    print(f"✗ Error: {e}")
```

**Deliverables:**
- [ ] Serverless index created
- [ ] Verify dimension (3072) and metric (cosine)
- [ ] Test connectivity
- [ ] Document new index host

#### Day 5: Migration Script Development
```python
# migrate_vectors.py
"""
Migrate vectors from pod-based to serverless index.
Handles batching, retries, and progress tracking.
"""
from pinecone import Pinecone
from pinecone.exceptions import PineconeException, ServiceException
import os
import time
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PineconeMigrator:
    def __init__(self, source_index_name: str, target_index_name: str):
        self.pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
        self.source = self.pc.Index(source_index_name)
        self.target = self.pc.Index(target_index_name)
        self.batch_size = 100  # Pinecone limit
        
    def migrate_namespace(self, namespace: str, max_retries: int = 3):
        """Migrate all vectors from one namespace."""
        logger.info(f"Migrating namespace: {namespace}")
        
        # Get all vector IDs
        ids = self._get_all_ids(namespace)
        logger.info(f"Found {len(ids)} vectors to migrate")
        
        # Fetch and migrate in batches
        for i in tqdm(range(0, len(ids), self.batch_size)):
            batch_ids = ids[i:i + self.batch_size]
            
            # Fetch from source
            fetch_response = self.source.fetch(ids=batch_ids, namespace=namespace)
            vectors = fetch_response.vectors
            
            if not vectors:
                continue
                
            # Prepare for upsert
            upsert_data = [
                {
                    "id": vid,
                    "values": vector.values,
                    "metadata": vector.metadata
                }
                for vid, vector in vectors.items()
            ]
            
            # Upsert with retry
            self._upsert_with_retry(upsert_data, namespace, max_retries)
            
    def _get_all_ids(self, namespace: str) -> list:
        """Get all vector IDs in a namespace."""
        ids = []
        pagination_token = None
        
        while True:
            response = self.source.list_paginated(
                namespace=namespace,
                limit=100,
                pagination_token=pagination_token
            )
            
            ids.extend([v.id for v in response.vectors])
            
            pagination_token = response.pagination.next
            if not pagination_token:
                break
                
        return ids
    
    def _upsert_with_retry(self, vectors: list, namespace: str, max_retries: int):
        """Upsert with exponential backoff."""
        for attempt in range(max_retries):
            try:
                self.target.upsert(vectors=vectors, namespace=namespace)
                return
            except ServiceException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Retry {attempt + 1} after {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise

# Usage
if __name__ == "__main__":
    migrator = PineconeMigrator(
        source_index_name="digital-twin-brain",
        target_index_name="digital-twin-serverless"
    )
    
    # Migrate specific namespace
    migrator.migrate_namespace("example-namespace")
```

**Deliverables:**
- [ ] Migration script created
- [ ] Error handling implemented
- [ ] Progress tracking added
- [ ] Tested on small namespace

---

### Week 2: Migration Execution

#### Day 1-3: Data Migration
```bash
# Run migration in batches
python migrate_vectors.py --namespace "twin_abc123" --batch-size 100
python migrate_vectors.py --namespace "twin_def456" --batch-size 100
# ... etc
```

**Migration Strategy:**
1. **Pause writes** to pod-based index (maintenance window)
2. **Migrate data** in namespace batches
3. **Verify counts** match between source and target
4. **Resume writes** to serverless index (dual-write during transition)

**Deliverables:**
- [ ] All namespaces migrated
- [ ] Vector counts verified
- [ ] Migration log saved

#### Day 4-5: Namespace Strategy Refactoring

**Current:** Namespace per twin (e.g., `twin_abc123`)  
**Target:** Namespace per creator (Delphi-style, e.g., `creator_user123_twin_abc123`)

```python
# modules/embeddings_v2.py
class PineconeServerlessManager:
    """
    Delphi-style namespace management for Pinecone Serverless.
    """
    
    def __init__(self):
        self.pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
        self.index = self.pc.Index("digital-twin-serverless")
        
    def get_namespace(self, creator_id: str, twin_id: str = None) -> str:
        """
        Generate namespace name following Delphi pattern:
        - Primary: creator_{creator_id}_twin_{twin_id}
        - Creator-wide: creator_{creator_id}
        """
        if twin_id:
            return f"creator_{creator_id}_twin_{twin_id}"
        return f"creator_{creator_id}"
    
    def upsert_vectors(
        self,
        vectors: list,
        creator_id: str,
        twin_id: str = None,
        metadata: dict = None
    ):
        """Upsert vectors with proper namespace."""
        namespace = self.get_namespace(creator_id, twin_id)
        
        # Add metadata for traceability
        for vector in vectors:
            if not vector.get("metadata"):
                vector["metadata"] = {}
            vector["metadata"]["creator_id"] = creator_id
            if twin_id:
                vector["metadata"]["twin_id"] = twin_id
        
        self.index.upsert(vectors=vectors, namespace=namespace)
        
    def query(
        self,
        vector: list,
        creator_id: str,
        twin_id: str = None,
        top_k: int = 10,
        filter: dict = None
    ):
        """Query within creator's namespace."""
        namespace = self.get_namespace(creator_id, twin_id)
        
        return self.index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_metadata=True
        )
    
    def delete_creator_data(self, creator_id: str):
        """
        Delete all data for a creator (GDPR compliance).
        This is much easier with creator-centric namespaces.
        """
        # Delete creator-wide namespace
        self.index.delete(delete_all=True, namespace=f"creator_{creator_id}")
        
        # Find and delete all twin namespaces
        # (List operation to find them)
```

**Deliverables:**
- [ ] New embedding module created
- [ ] Namespace strategy refactored
- [ ] Backward compatibility maintained

---

### Week 3: Testing, Cutover & Monitoring

#### Day 1-2: Integration Testing
```python
# test_serverless_integration.py
import pytest
from modules.embeddings_v2 import PineconeServerlessManager

class TestPineconeServerless:
    def setup_method(self):
        self.manager = PineconeServerlessManager()
        self.test_creator = "test_creator_123"
        self.test_twin = "test_twin_456"
    
    def test_namespace_generation(self):
        """Test namespace naming convention."""
        ns = self.manager.get_namespace(self.test_creator, self.test_twin)
        assert ns == "creator_test_creator_123_twin_test_twin_456"
        
        ns_creator_only = self.manager.get_namespace(self.test_creator)
        assert ns_creator_only == "creator_test_creator_123"
    
    def test_upsert_and_query(self):
        """Test basic upsert and query."""
        # Insert test vector
        test_vector = [0.1] * 3072
        self.manager.upsert_vectors(
            vectors=[{"id": "test-1", "values": test_vector, "metadata": {"text": "test"}}],
            creator_id=self.test_creator,
            twin_id=self.test_twin
        )
        
        # Query
        results = self.manager.query(
            vector=test_vector,
            creator_id=self.test_creator,
            twin_id=self.test_twin,
            top_k=1
        )
        
        assert len(results.matches) == 1
        assert results.matches[0].id == "test-1"
    
    def test_latency_requirements(self):
        """Verify <100ms P95 latency."""
        import time
        
        latencies = []
        test_vector = [0.1] * 3072
        
        for _ in range(100):
            start = time.time()
            self.manager.query(
                vector=test_vector,
                creator_id=self.test_creator,
                twin_id=self.test_twin,
                top_k=10
            )
            latencies.append((time.time() - start) * 1000)
        
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        print(f"P95 Latency: {p95:.2f}ms")
        assert p95 < 100, f"P95 latency {p95}ms exceeds 100ms target"
```

**Deliverables:**
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Latency benchmarks (<100ms P95)
- [ ] Load tests (20 QPS target)

#### Day 3: Gradual Cutover

**Feature Flag Strategy:**
```python
# modules/feature_flags.py
import os

def use_serverless() -> bool:
    """Check if serverless index should be used."""
    return os.environ.get("USE_PINECONE_SERVERLESS", "false").lower() == "true"

# In your code
if use_serverless():
    from modules.embeddings_v2 import PineconeServerlessManager as EmbeddingManager
else:
    from modules.embeddings import PineconeManager as EmbeddingManager
```

**Cutover Steps:**
1. **5% traffic** → Monitor errors and latency
2. **25% traffic** → Monitor for 24 hours
3. **50% traffic** → Monitor for 24 hours
4. **100% traffic** → Full cutover
5. **Decommission** old index after 7 days

**Deliverables:**
- [ ] Feature flags implemented
- [ ] Gradual rollout completed
- [ ] Monitoring dashboards active

#### Day 4-5: Monitoring & Documentation

**Monitoring Setup:**
```python
# modules/pinecone_monitoring.py
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class QueryMetrics:
    latency_ms: float
    namespace: str
    top_k: int
    result_count: int
    error: Optional[str] = None

class PineconeMonitor:
    """Monitor Pinecone Serverless performance."""
    
    def __init__(self):
        self.query_count = 0
        self.error_count = 0
        self.latencies = []
        
    def record_query(self, metrics: QueryMetrics):
        """Record query metrics."""
        self.query_count += 1
        self.latencies.append(metrics.latency_ms)
        
        if metrics.error:
            self.error_count += 1
            # Alert on high error rate
            if self.error_count / self.query_count > 0.01:
                self._alert(f"High error rate: {self.error_count}/{self.query_count}")
        
        # Alert on high latency
        if metrics.latency_ms > 100:
            self._alert(f"High latency: {metrics.latency_ms}ms")
    
    def get_stats(self):
        """Get current statistics."""
        if not self.latencies:
            return {}
        
        sorted_latencies = sorted(self.latencies)
        return {
            "total_queries": self.query_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / self.query_count,
            "p50_latency": sorted_latencies[int(len(sorted_latencies) * 0.5)],
            "p95_latency": sorted_latencies[int(len(sorted_latencies) * 0.95)],
            "p99_latency": sorted_latencies[int(len(sorted_latencies) * 0.99)],
        }
    
    def _alert(self, message: str):
        """Send alert (integrate with your alerting system)."""
        print(f"[ALERT] {message}")
        # TODO: Integrate with PagerDuty, Slack, etc.
```

**Deliverables:**
- [ ] Monitoring dashboard created
- [ ] Alerting configured
- [ ] Runbook documented
- [ ] Rollback procedure documented

---

## 📋 What You Need to Provide

### 1. API Keys & Access
```
✅ Already have:
  - PINECONE_API_KEY (from .env)
  
⏳ Need to verify:
  - Pinecone project permissions
  - Ability to create/delete indexes
```

### 2. Current State Information
```
⏳ Need from you:
  - Current vector count (can get via audit script)
  - Current namespace list
  - Peak QPS (queries per second)
  - Current monthly Pinecone cost
  - Any specific compliance requirements (GDPR, etc.)
```

### 3. Testing Data
```
⏳ Need from you:
  - Test creator account (for safe testing)
  - Sample twin data for validation
  - Expected query patterns (for benchmarking)
```

### 4. Infrastructure Decisions
```
⏳ Need your decision:
  - Maintenance window duration (recommended: 2-4 hours)
  - Rollback tolerance (how long to keep old index)
  - Monitoring integration (Slack, PagerDuty, etc.)
  - Feature flag system (if not already using)
```

### 5. Risk Tolerance
```
⏳ Need your input:
  - Acceptable downtime during cutover
  - Data loss tolerance (should be 0, but need confirmation)
  - Performance degradation tolerance during transition
```

---

## 🎯 Success Criteria

| Metric | Before (Pod) | After (Serverless) | Target |
|--------|--------------|-------------------|--------|
| **Latency P95** | ~30-50ms | ~50-100ms | <100ms ✅ |
| **Latency P99** | ~50-100ms | ~100-200ms | <200ms ✅ |
| **Cost** | ~$200/mo | ~$50-150/mo | -24% to -75% ✅ |
| **Max Namespaces** | 1,000 | 25,000 | +2400% ✅ |
| **Uptime** | 99.9% | 99.99% | +0.09% ✅ |
| **Cold Query** | N/A | <500ms | <500ms ✅ |

---

## 🚀 Immediate Next Steps (What I Need From You)

1. **Run the audit script** to get current vector counts:
   ```bash
   python audit_current_state.py
   ```

2. **Confirm Pinecone SDK version**:
   ```bash
   pip show pinecone | grep Version
   # Should be >= 3.0.0
   ```

3. **Provide test creator/twin IDs** for safe migration testing

4. **Schedule maintenance window** for migration (2-4 hours recommended)

5. **Approve the plan** and I'll start implementation

---

## 📚 Reference Materials

- [Pinecone Migration Guide](https://docs.pinecone.io/guides/indexes/pods/migrate-a-pod-based-index-to-serverless)
- [Pinecone Serverless Best Practices](https://docs.pinecone.io/guides/production/production-checklist)
- [Pinecone Error Handling](https://docs.pinecone.io/guides/production/error-handling)
- [Delphi.ai Case Study](https://www.pinecone.io/customers/delphi/)

---

**Ready to proceed?** Provide the information in "What You Need to Provide" and I'll begin implementation.
