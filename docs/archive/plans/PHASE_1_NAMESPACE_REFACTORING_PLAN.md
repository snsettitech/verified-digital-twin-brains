# Phase 1: Namespace Strategy Refactoring Plan
## Twin-Based → Creator-Based (Delphi Pattern)

**Status:** Planning Complete → Ready for Implementation  
**Creator ID for Testing:** `sainath.no.1`  
**Estimated Duration:** 1 week  
**Risk Level:** Medium (data migration required)  

---

## 📊 Current State Analysis

### Your Current Pinecone Serverless Setup
| Attribute | Current Value |
|-----------|---------------|
| **Index Name** | `digital-twin-brain` |
| **Index Type** | ✅ Serverless (AWS us-east-1) |
| **Dimension** | 3072 (text-embedding-3-large) |
| **Total Vectors** | 805 |
| **Current Namespaces** | 30 |
| **Namespace Pattern** | UUID-based (e.g., `5698a809-87a5-4169-ab9b-c4a6222ae2dd`) |

### Current Namespace Breakdown
```
__default__                              : 376 vectors  (47%)
eeeed554-9180-4229-a9af-0f8dd2c69e9b     :  87 vectors  (11%)
d080d547-5aac-4a92-91b2-6d3ff728af4c     :  73 vectors   (9%)
5698a809-87a5-4169-ab9b-c4a6222ae2dd     :  68 vectors   (8%)
ad1eeace-26d1-4eff-9560-39643832d0f2     :  47 vectors   (6%)
[25 more namespaces]                     : 154 vectors  (19%)
```

### Problem Identification

**Issue 1: No Creator Association**
- Current UUID namespaces don't link to creators
- Cannot delete all data for a creator (GDPR compliance issue)
- Cannot query across all twins of a creator

**Issue 2: Default Namespace Overload**
- 376 vectors (47%) in `__default__` namespace
- No isolation between creators in default namespace
- Risk of data leakage between tenants

**Issue 3: Not Delphi-Compatible**
- Delphi uses `creator_{id}` or `creator_{id}_twin_{twin_id}` pattern
- Current pattern doesn't support multi-twin search
- Limits scalability to 12,000+ namespaces

---

## 🎯 Target State (Delphi Pattern)

### Namespace Naming Convention

| Scenario | Namespace Format | Example |
|----------|------------------|---------|
| **Twin-specific** | `creator_{creator_id}_twin_{twin_id}` | `creator_sainath.no.1_twin_abc123` |
| **Creator-wide** | `creator_{creator_id}` | `creator_sainath.no.1` |
| **Public/Shared** | `public` | `public` |

### Benefits

| Benefit | Description |
|---------|-------------|
| **GDPR Compliance** | Delete all creator data with single `delete_all` call |
| **Multi-Twin Search** | Query `creator_sainath.no.1_*` pattern across twins |
| **Scalability** | 25,000 namespaces per index (Delphi has 12,000+) |
| **Cost Optimization** | Inactive namespaces don't consume compute |
| **Data Isolation** | Clear tenant boundaries |

### Delphi.ai Reference
- **100M+ vectors** across **12,000+ namespaces**
- **<100ms P95 latency**
- **20 QPS globally**
- Creator-centric namespace strategy enables this scale

---

## 🗂️ Migration Strategy

### Option A: In-Place Migration (Recommended)
**Approach:** Migrate vectors to new namespaces within same index

**Pros:**
- No new index creation needed
- Lower cost
- Faster execution
- Easier rollback

**Cons:**
- Temporary data duplication
- Requires careful orchestration

**Steps:**
1. Create new namespaces with creator prefix
2. Copy vectors to new namespaces
3. Update application code
4. Gradual cutover
5. Delete old namespaces

### Option B: New Index Migration
**Approach:** Create new index with proper namespaces

**Pros:**
- Clean slate
- Can test thoroughly
- No data duplication

**Cons:**
- Higher cost (two indexes during migration)
- More complex
- Longer execution time

**Decision:** Use **Option A** (In-Place) due to smaller dataset (805 vectors)

---

## 📋 Detailed Implementation Plan

### Pre-Migration Checklist

- [ ] Backup current index (create collection)
- [ ] Identify all creator → twin mappings from Supabase
- [ ] Document current query patterns in codebase
- [ ] Set up monitoring/alerting
- [ ] Prepare rollback script

### Week 1: Implementation Schedule

#### Day 1: Preparation & Backup

**Task 1.1: Create Collection (Backup)**
```python
# backup_index.py
from pinecone import Pinecone
import os

pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])

# Create collection backup
collection_name = "digital-twin-brain-backup-2026-02-11"

try:
    pc.create_collection(
        name=collection_name,
        source_index="digital-twin-brain"
    )
    print(f"✓ Collection created: {collection_name}")
    print("  Backup will be ready in ~10 minutes")
except Exception as e:
    print(f"✗ Error: {e}")
```

**Task 1.2: Map Creators to Twins**
```python
# map_creators_twins.py
"""
Query Supabase to get creator → twin mappings
"""
from supabase import create_client
import os

def get_creator_twin_mappings():
    supabase = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_KEY']
    )
    
    # Query twins table
    result = supabase.table('twins').select(
        'id, creator_id, name'
    ).execute()
    
    mappings = {}
    for twin in result.data:
        creator_id = twin['creator_id']
        twin_id = twin['id']
        
        if creator_id not in mappings:
            mappings[creator_id] = []
        mappings[creator_id].append({
            'twin_id': twin_id,
            'name': twin['name']
        })
    
    return mappings

# Expected output:
# {
#   "sainath.no.1": [
#     {"twin_id": "5698a809-87a5-4169-ab9b-c4a6222ae2dd", "name": "Twin A"},
#     {"twin_id": "d080d547-5aac-4a92-91b2-6d3ff728af4c", "name": "Twin B"}
#   ]
# }
```

**Deliverables:**
- [ ] Collection backup created
- [ ] Creator-twin mapping document
- [ ] Rollback plan documented

---

#### Day 2-3: Migration Script Development

**Task 2.1: Namespace Migration Script**
```python
# migrate_namespaces.py
"""
Migrate vectors from old namespaces to new creator-based namespaces.
"""
from pinecone import Pinecone
from typing import Dict, List
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NamespaceMigrator:
    def __init__(self, index_name: str):
        self.pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
        self.index = self.pc.Index(index_name)
        
    def migrate_namespace(
        self,
        old_namespace: str,
        creator_id: str,
        twin_id: str = None,
        dry_run: bool = False
    ) -> Dict:
        """
        Migrate one namespace to new creator-based format.
        
        Args:
            old_namespace: Current namespace (UUID or __default__)
            creator_id: Creator identifier (e.g., "sainath.no.1")
            twin_id: Twin identifier (optional for creator-wide namespace)
            dry_run: If True, only count vectors without migrating
        
        Returns:
            Migration statistics
        """
        # Determine new namespace name
        if twin_id:
            new_namespace = f"creator_{creator_id}_twin_{twin_id}"
        else:
            new_namespace = f"creator_{creator_id}"
        
        logger.info(f"Migrating: {old_namespace} → {new_namespace}")
        
        # Get all vectors from old namespace
        vector_ids = self._get_all_vector_ids(old_namespace)
        total_vectors = len(vector_ids)
        
        if dry_run:
            return {
                "old_namespace": old_namespace,
                "new_namespace": new_namespace,
                "total_vectors": total_vectors,
                "migrated": 0,
                "status": "dry_run"
            }
        
        # Migrate in batches
        batch_size = 100
        migrated = 0
        
        for i in tqdm(range(0, len(vector_ids), batch_size)):
            batch_ids = vector_ids[i:i + batch_size]
            
            # Fetch from old namespace
            fetch_response = self.index.fetch(
                ids=batch_ids,
                namespace=old_namespace
            )
            
            if not fetch_response.vectors:
                continue
            
            # Prepare for upsert with updated metadata
            vectors_to_upsert = []
            for vid, vector in fetch_response.vectors.items():
                # Add creator/twin metadata
                metadata = vector.metadata or {}
                metadata['creator_id'] = creator_id
                if twin_id:
                    metadata['twin_id'] = twin_id
                metadata['migrated_from'] = old_namespace
                
                vectors_to_upsert.append({
                    "id": vid,
                    "values": vector.values,
                    "metadata": metadata
                })
            
            # Upsert to new namespace
            self.index.upsert(
                vectors=vectors_to_upsert,
                namespace=new_namespace
            )
            migrated += len(vectors_to_upsert)
        
        logger.info(f"✓ Migrated {migrated} vectors to {new_namespace}")
        
        return {
            "old_namespace": old_namespace,
            "new_namespace": new_namespace,
            "total_vectors": total_vectors,
            "migrated": migrated,
            "status": "completed"
        }
    
    def _get_all_vector_ids(self, namespace: str) -> List[str]:
        """Get all vector IDs in a namespace."""
        ids = []
        pagination_token = None
        
        while True:
            response = self.index.list_paginated(
                namespace=namespace,
                limit=100,
                pagination_token=pagination_token
            )
            
            ids.extend([v.id for v in response.vectors])
            
            pagination_token = response.pagination.next
            if not pagination_token:
                break
        
        return ids
    
    def verify_migration(
        self,
        old_namespace: str,
        new_namespace: str
    ) -> bool:
        """Verify vectors were migrated correctly."""
        old_stats = self.index.describe_index_stats()
        old_count = old_stats.namespaces.get(old_namespace, {}).vector_count
        
        new_stats = self.index.describe_index_stats()
        new_count = new_stats.namespaces.get(new_namespace, {}).vector_count
        
        if old_count == new_count:
            logger.info(f"✓ Verification passed: {old_count} vectors match")
            return True
        else:
            logger.error(
                f"✗ Verification failed: "
                f"old={old_count}, new={new_count}"
            )
            return False
    
    def cleanup_old_namespace(self, namespace: str):
        """Delete all vectors from old namespace after verification."""
        logger.info(f"Cleaning up old namespace: {namespace}")
        self.index.delete(delete_all=True, namespace=namespace)
        logger.info(f"✓ Deleted namespace: {namespace}")

# Usage
if __name__ == "__main__":
    migrator = NamespaceMigrator("digital-twin-brain")
    
    # Migration mapping from Day 1
    migrations = [
        {
            "old_ns": "5698a809-87a5-4169-ab9b-c4a6222ae2dd",
            "creator_id": "sainath.no.1",
            "twin_id": "5698a809-87a5-4169-ab9b-c4a6222ae2dd"
        },
        # ... more mappings
    ]
    
    # Dry run first
    for m in migrations:
        result = migrator.migrate_namespace(
            old_namespace=m["old_ns"],
            creator_id=m["creator_id"],
            twin_id=m.get("twin_id"),
            dry_run=True
        )
        print(f"Dry run: {result}")
    
    # Actual migration
    # for m in migrations:
    #     migrator.migrate_namespace(**m)
    #     migrator.verify_migration(m["old_ns"], f"creator_{m['creator_id']}_twin_{m['twin_id']}")
    #     migrator.cleanup_old_namespace(m["old_ns"])
```

**Task 2.2: Handle Default Namespace**
```python
# handle_default_namespace.py
"""
Special handling for __default__ namespace which contains
vectors from multiple creators.
"""

class DefaultNamespaceHandler:
    """
    The __default__ namespace has 376 vectors (47% of data).
    These need to be analyzed and redistributed to creator namespaces.
    """
    
    def analyze_default_namespace(self):
        """
        Query vectors in __default__ to determine creator ownership.
        
        Strategy options:
        1. If metadata has creator_id: Move to creator_{id} namespace
        2. If no creator metadata: Query Supabase by vector ID to find owner
        3. If orphaned: Move to creator_sainath.no.1 (test creator) for manual review
        """
        pass
    
    def redistribute_by_metadata(self):
        """Redistribute vectors based on existing metadata."""
        pass
    
    def redistribute_by_source_lookup(self):
        """Query source database to find owners."""
        pass
```

**Deliverables:**
- [ ] Migration script complete
- [ ] Dry-run tested
- [ ] Default namespace strategy defined

---

#### Day 4: Application Code Updates

**Task 3.1: New Embedding Module**
```python
# modules/embeddings_delphi.py
"""
Delphi-style Pinecone client with creator-based namespaces.
Drop-in replacement for current embeddings module.
"""
from pinecone import Pinecone
from typing import Optional, List, Dict
import os

class PineconeDelphiClient:
    """
    Pinecone client using Delphi namespace strategy.
    
    Naming convention:
    - Twin-specific: creator_{creator_id}_twin_{twin_id}
    - Creator-wide: creator_{creator_id}
    """
    
    def __init__(self, index_name: str = "digital-twin-brain"):
        self.pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
        self.index = self.pc.Index(index_name)
    
    def _get_namespace(
        self,
        creator_id: str,
        twin_id: Optional[str] = None
    ) -> str:
        """Generate namespace name."""
        if twin_id:
            return f"creator_{creator_id}_twin_{twin_id}"
        return f"creator_{creator_id}"
    
    def upsert_vectors(
        self,
        vectors: List[Dict],
        creator_id: str,
        twin_id: Optional[str] = None
    ):
        """
        Upsert vectors with creator/twin metadata.
        
        Args:
            vectors: List of {"id": str, "values": List[float], "metadata": dict}
            creator_id: Creator identifier (e.g., "sainath.no.1")
            twin_id: Optional twin identifier
        """
        namespace = self._get_namespace(creator_id, twin_id)
        
        # Enrich metadata
        for vector in vectors:
            if not vector.get("metadata"):
                vector["metadata"] = {}
            vector["metadata"]["creator_id"] = creator_id
            if twin_id:
                vector["metadata"]["twin_id"] = twin_id
        
        self.index.upsert(vectors=vectors, namespace=namespace)
    
    def query(
        self,
        vector: List[float],
        creator_id: str,
        twin_id: Optional[str] = None,
        top_k: int = 10,
        filter: Optional[Dict] = None,
        include_metadata: bool = True
    ):
        """
        Query vectors in creator's namespace.
        
        Args:
            vector: Query embedding
            creator_id: Creator identifier
            twin_id: If None, queries creator-wide namespace
            top_k: Number of results
            filter: Metadata filter
        """
        namespace = self._get_namespace(creator_id, twin_id)
        
        return self.index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_metadata=include_metadata
        )
    
    def query_across_twins(
        self,
        vector: List[float],
        creator_id: str,
        twin_ids: List[str],
        top_k: int = 10
    ):
        """
        Query across multiple twins for a creator.
        Merges results from multiple namespaces.
        """
        all_results = []
        
        for twin_id in twin_ids:
            results = self.query(
                vector=vector,
                creator_id=creator_id,
                twin_id=twin_id,
                top_k=top_k
            )
            all_results.extend(results.matches)
        
        # Re-rank by score
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:top_k]
    
    def delete_creator_data(self, creator_id: str):
        """
        Delete all data for a creator (GDPR compliance).
        
        This is the key advantage of creator-based namespaces.
        """
        # Delete creator-wide namespace
        try:
            self.index.delete(
                delete_all=True,
                namespace=f"creator_{creator_id}"
            )
        except:
            pass
        
        # Find and delete all twin namespaces
        stats = self.index.describe_index_stats()
        for namespace in stats.namespaces.keys():
            if namespace.startswith(f"creator_{creator_id}_twin_"):
                self.index.delete(delete_all=True, namespace=namespace)
    
    def list_creator_twins(self, creator_id: str) -> List[str]:
        """List all twin namespaces for a creator."""
        stats = self.index.describe_index_stats()
        twins = []
        
        for namespace in stats.namespaces.keys():
            prefix = f"creator_{creator_id}_twin_"
            if namespace.startswith(prefix):
                twin_id = namespace[len(prefix):]
                twins.append(twin_id)
        
        return twins

# Singleton instance
_delphi_client = None

def get_delphi_client() -> PineconeDelphiClient:
    """Get singleton Delphi client."""
    global _delphi_client
    if _delphi_client is None:
        _delphi_client = PineconeDelphiClient()
    return _delphi_client
```

**Task 3.2: Feature Flag Integration**
```python
# modules/feature_flags.py
import os

def use_delphi_namespaces() -> bool:
    """
    Feature flag for Delphi namespace strategy.
    Set USE_DELPHI_NAMESPACES=true to enable.
    """
    return os.environ.get(
        "USE_DELPHI_NAMESPACES",
        "false"
    ).lower() == "true"

# Usage in code:
# if use_delphi_namespaces():
#     from modules.embeddings_delphi import get_delphi_client
#     client = get_delphi_client()
# else:
#     from modules.embeddings import get_pinecone_client
#     client = get_pinecone_client()
```

**Deliverables:**
- [ ] New embedding module created
- [ ] Feature flags configured
- [ ] Backward compatibility maintained

---

#### Day 5: Testing & Validation

**Task 4.1: Test Plan**
```python
# tests/test_namespace_migration.py
import pytest
from modules.embeddings_delphi import PineconeDelphiClient

class TestDelphiNamespaceStrategy:
    """Test suite for Delphi namespace refactoring."""
    
    @pytest.fixture
    def client(self):
        return PineconeDelphiClient()
    
    def test_namespace_generation(self, client):
        """Test correct namespace naming."""
        # Twin-specific
        ns = client._get_namespace("sainath.no.1", "twin_abc123")
        assert ns == "creator_sainath.no.1_twin_twin_abc123"
        
        # Creator-wide
        ns = client._get_namespace("sainath.no.1")
        assert ns == "creator_sainath.no.1"
    
    def test_upsert_and_query(self, client):
        """Test basic upsert and query flow."""
        test_vector = [0.1] * 3072
        
        # Upsert
        client.upsert_vectors(
            vectors=[{
                "id": "test-doc-1",
                "values": test_vector,
                "metadata": {"text": "test content"}
            }],
            creator_id="sainath.no.1",
            twin_id="test_twin"
        )
        
        # Query
        results = client.query(
            vector=test_vector,
            creator_id="sainath.no.1",
            twin_id="test_twin",
            top_k=1
        )
        
        assert len(results.matches) == 1
        assert results.matches[0].id == "test-doc-1"
        assert results.matches[0].metadata["creator_id"] == "sainath.no.1"
    
    def test_query_across_twins(self, client):
        """Test multi-twin query."""
        # Setup: Create vectors in two twins
        # Query across both
        # Verify merged results
        pass
    
    def test_delete_creator_data(self, client):
        """Test GDPR-compliant deletion."""
        # Create test data
        # Delete creator data
        # Verify deletion
        pass
    
    def test_latency_requirements(self, client):
        """Verify <100ms P95 latency."""
        import time
        
        latencies = []
        test_vector = [0.1] * 3072
        
        for _ in range(100):
            start = time.time()
            client.query(
                vector=test_vector,
                creator_id="sainath.no.1",
                twin_id="test_twin",
                top_k=10
            )
            latencies.append((time.time() - start) * 1000)
        
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 100, f"P95 latency {p95}ms exceeds 100ms"
```

**Task 4.2: Validation Checklist**
- [ ] All existing namespaces migrated
- [ ] Vector counts match (source vs target)
- [ ] Query results identical
- [ ] Latency <100ms P95
- [ ] No data loss
- [ ] Rollback tested

---

## 🚨 Risk Mitigation

### Risk 1: Data Loss
**Mitigation:**
- Collection backup before migration
- Dry-run validation
- Verification after each namespace
- Rollback script ready

### Risk 2: Query Downtime
**Mitigation:**
- Dual-write during transition
- Feature flags for gradual cutover
- Read from old, write to both, then switch

### Risk 3: Performance Regression
**Mitigation:**
- Latency benchmarking
- Load testing
- Rollback if P95 > 100ms

### Risk 4: Application Breakage
**Mitigation:**
- Backward compatibility layer
- Feature flags
- Gradual rollout (5% → 25% → 50% → 100%)

---

## 📊 Success Criteria

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| **Namespace Count** | 30 | ~15-20 (consolidated) | Organized |
| **GDPR Compliance** | ❌ Hard | ✅ Easy (single delete) | ✅ |
| **Multi-Twin Search** | ❌ Not possible | ✅ Native | ✅ |
| **Query Latency P95** | ~30-50ms | ~50-100ms | <100ms ✅ |
| **Data Loss** | 0 | 0 | 0 ✅ |
| **Creator Isolation** | ❌ Mixed | ✅ Clear | ✅ |

---

## 📁 Files to be Created

| File | Purpose |
|------|---------|
| `migrate_namespaces.py` | Main migration script |
| `modules/embeddings_delphi.py` | New Delphi client |
| `modules/feature_flags.py` | Feature toggle |
| `tests/test_namespace_migration.py` | Test suite |
| `rollback_namespaces.py` | Rollback script |

---

## ✅ Pre-Implementation Checklist

Before starting implementation, confirm:

- [ ] **Creator-twin mappings** from Supabase provided
- [ ] **Maintenance window** scheduled (2-4 hours recommended)
- [ ] **Test creator ID** confirmed: `sainath.no.1`
- [ ] **Backup strategy** approved (collection creation)
- [ ] **Rollback plan** reviewed
- [ ] **Monitoring** in place (alerts for errors/latency)
- [ ] **Go/no-go decision** made

---

## 🚀 Ready to Implement?

**Confirm the following to proceed:**

1. ✅ Approve the namespace naming convention
2. ✅ Provide creator-twin mapping from Supabase
3. ✅ Schedule maintenance window
4. ✅ Confirm test creator: `sainath.no.1`

**Once confirmed, I'll begin Day 1 implementation.**

---

## 📚 References

- [Delphi.ai Pinecone Case Study](https://www.pinecone.io/customers/delphi/)
- [Pinecone Serverless Best Practices](https://docs.pinecone.io/guides/production/production-checklist)
- [GDPR Right to Erasure](https://gdpr.eu/article-17-right-to-be-forgotten/)
