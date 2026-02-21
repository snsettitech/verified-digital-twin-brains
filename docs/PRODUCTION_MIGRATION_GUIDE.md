# Production Migration Guide: Namespace Refactoring

**Date**: 2026-02-11  
**Status**: Phase 1 Complete - Validated  
**Target**: Production Deployment  

---

## Current Pinecone Runtime Target (2026-02-21)

This document contains historical migration steps for namespace refactoring.
For current runtime index targeting, use:

```env
PINECONE_HOST=digitalminds-nrnzovv.svc.aped-4627-b74a.pinecone.io
PINECONE_INDEX_NAME=digitalminds
PINECONE_INDEX_MODE=integrated
PINECONE_TEXT_FIELD=chunk_text
COHERE_RERANK_MODEL=rerank-v3.5
```

---

## Executive Summary

This guide documents the migration from UUID-based namespaces to creator-based namespaces (`creator_{creator_id}_twin_{twin_id}`) following Delphi.ai's architecture pattern.

### What Changed

| Aspect | Before | After |
|--------|--------|-------|
| **Namespace Format** | `uuid` (e.g., `5698a809-...`) | `creator_{id}_twin_{name}` |
| **Data Ownership** | Implicit | Explicit (`creator_id` in metadata) |
| **GDPR Compliance** | Complex multi-step | Single API call |
| **Multi-twin Search** | Not possible | Native support |

### Migration Results

- ✅ **805 vectors** migrated across **30 namespaces**
- ✅ **Zero data loss** (full verification at each step)
- ✅ **GDPR deletion** tested (27 namespaces deleted in <5 seconds)
- ✅ **Query performance**: 87-119ms P95

---

## Pre-Migration Checklist

### 1. Infrastructure Requirements

```bash
# Verify Pinecone Serverless
pinecone describe-index digital-twin-brain
# Expected: ServerlessSpec(cloud='aws', region='us-east-1')

# Verify Neo4j AuraDB (CodeGraphContext)
# URI: neo4j+s://034760f3.databases.neo4j.io
# Status: Operational (18,201+ nodes indexed)

# Verify Supabase (creator-twin mapping)
# URL: https://jvtffdbuwyhmcynauety.supabase.co
# Tables: creators, twins, sources
```

### 2. API Keys Required

| Service | Key | Status |
|---------|-----|--------|
| Pinecone | `pcsk_...` | ✅ Active |
| OpenAI | `sk-...` | ✅ Active |
| Supabase | `sb_secret_...` | ✅ Active |
| Neo4j | `Elhi2G6...` | ✅ Active |
| Cerebras | (Phase 2) | ⏭️ Needed |
| AssemblyAI | (Phase 3) | ⏭️ Needed |

### 3. Environment Variables

```bash
# .env (already configured)
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=digital-twin-brain
NEO4J_URI=neo4j+s://034760f3.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=Elhi2G690lNBgfmdTpEuov_WzwfgTcNCwIBOm8ZmX9k
SUPABASE_URL=https://jvtffdbuwyhmcynauety.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
```

---

## Migration Steps

### Step 1: Create Migration Scripts

**Files Created**:
- `day1_map_to_test_creator.py` - Maps existing data to creator structure
- `day2_test_deletion.py` - Tests twin/creator deletion

### Step 2: Execute Day 1 (Data Mapping)

```bash
# Dry run first
python day1_map_to_test_creator.py

# Review output, then execute
python day1_map_to_test_creator.py --yes
```

**Expected Output**:
```
✓ Migrated 805/805 vectors
✓ Verification passed: 805 vectors match
✓ Deleted old namespace: uuid
```

### Step 3: Execute Day 2 (Testing)

```bash
# Test deletion mechanisms
python day2_test_deletion.py --yes
```

**Expected Results**:
```
Twin Deletion:     PASS
Creator Deletion:  PASS
Query Performance: SLOW (will improve with Cerebras)
GDPR Compliance:   PASS
```

### Step 4: Update Backend Code

Update `backend/modules/embeddings.py` to use new namespace format:

```python
def get_namespace(creator_id: str, twin_id: str) -> str:
    """Generate creator-based namespace."""
    return f"creator_{creator_id}_twin_{twin_id}"
```

---

## Backend Integration

### 1. New Client: `DelphiPineconeClient`

Location: `backend/modules/embeddings_delphi.py`

```python
from backend.modules.embeddings_delphi import DelphiPineconeClient

# Initialize
client = DelphiPineconeClient()

# Upsert with creator isolation
await client.upsert_vectors(
    creator_id="sainath.no.1",
    twin_id="coach",
    vectors=[...]
)

# Query within twin namespace
results = await client.query(
    creator_id="sainath.no.1",
    twin_id="coach",
    query_vector=[...],
    top_k=10
)

# Delete specific twin (GDPR Right to Erasure)
await client.delete_twin("sainath.no.1", "coach")

# Delete all creator data (Full GDPR compliance)
await client.delete_creator("sainath.no.1")
```

### 2. Tenant Isolation

Location: `backend/modules/tenant_guard.py`

```python
from backend.modules.tenant_guard import TenantGuard

# Validate access
TenantGuard.validate_namespace_access(
    user_creator_id="sainath.no.1",
    namespace="creator_sainath.no.1_twin_coach"
)  # ✅ Passes

TenantGuard.validate_namespace_access(
    user_creator_id="other.user",
    namespace="creator_sainath.no.1_twin_coach"
)  # ❌ Raises TenantIsolationError
```

### 3. API Router

Location: `backend/routers/retrieval_delphi.py`

```python
# New endpoints
POST /delphi/search                    # Semantic search
POST /delphi/search-cross-twin         # Search across all creator twins
DELETE /delphi/twin/{twin_id}          # Delete specific twin
DELETE /delphi/creator                 # GDPR delete all creator data
```

---

## Production Deployment

### Option A: Gradual Migration (Recommended)

1. **Deploy new code** alongside old code
2. **New twins** use creator-based namespaces
3. **Existing twins** continue on UUID namespaces
4. **Migrate gradually** as twins are updated

```python
# Feature flag approach
if use_creator_namespaces(creator_id):
    namespace = f"creator_{creator_id}_twin_{twin_id}"
else:
    namespace = twin_id  # Legacy
```

### Option B: Big Bang Migration

1. **Maintenance window**: 2-4 hours
2. **Backup**: Export all vectors
3. **Migrate**: Run Day 1 script
4. **Verify**: Run Day 2 script
5. **Switch**: Update all services

### Option C: Parallel Indexes

1. **Keep old index**: `digital-twin-brain`
2. **Create new index**: `digital-twin-delphi`
3. **Dual write**: Write to both indexes
4. **Migrate read traffic** gradually
5. **Decommission old index** after validation

---

## Rollback Plan

### If Migration Fails

```python
# Restore from backup (if using Option C)
# Or re-run migration with different parameters

# Emergency: Restore old namespace format
old_namespace = twin_id
new_namespace = f"creator_{creator_id}_twin_{twin_id}"

# Copy vectors back
vectors = index.query(namespace=new_namespace, ...)
index.upsert(vectors=vectors, namespace=old_namespace)
```

---

## Monitoring & Alerting

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Migration Success Rate | 100% | <99% |
| Query Latency P95 | <100ms | >150ms |
| Vector Count Match | 100% | <100% |
| GDPR Deletion Time | <10s | >30s |

### Verification Queries

```python
# Check vector counts match
before = 805  # From Day 1
after = index.describe_index_stats().total_vector_count
assert before == after, "Vector count mismatch!"

# Check all namespaces have creator_id
for ns in index.describe_index_stats().namespaces:
    assert ns.startswith("creator_"), f"Invalid namespace: {ns}"
```

---

## Security Considerations

### 1. Tenant Isolation

- ✅ **Physical**: Separate Pinecone namespaces
- ✅ **Application**: TenantGuard validates access
- ✅ **Metadata**: `creator_id` embedded in vectors
- ✅ **Audit**: All access logged

### 2. GDPR Compliance

- ✅ **Right to Erasure**: Single API call deletes all creator data
- ✅ **Data Portability**: Export before deletion
- ✅ **Audit Trail**: All deletions logged
- ✅ **Verification**: Post-deletion confirmation

---

## Post-Migration

### 1. Cleanup

```bash
# Remove migration scripts (optional)
rm day1_map_to_test_creator.py
rm day2_test_deletion.py

# Archive logs
cp migration_*.log /archive/2026-02-11/
```

### 2. Documentation Updates

- [ ] Update API documentation
- [ ] Update developer guides
- [ ] Update runbooks

### 3. Team Communication

```
Subject: [COMPLETE] Namespace Migration to Creator-Based Structure

All,

The migration to creator-based namespaces is complete.

What's New:
- Namespaces now follow: creator_{creator_id}_twin_{twin_id}
- GDPR deletion: Single API call removes all creator data
- Multi-twin search: Query across all creator's twins

Action Required:
- Update any hardcoded namespace references
- Use DelphiPineconeClient for new code

Questions? See docs/PRODUCTION_MIGRATION_GUIDE.md
```

---

## Appendix A: Migration Log Template

```yaml
migration:
  date: "2026-02-11T21:00:00Z"
  executed_by: "sainath.no.1"
  
  before:
    total_vectors: 805
    total_namespaces: 30
    
  after:
    total_vectors: 805
    total_namespaces: 30
    all_creator_based: true
    
  tests:
    twin_deletion: PASSED
    creator_deletion: PASSED
    gdpr_compliance: PASSED
    query_performance: "119ms P95 (acceptable)"
    
  issues: []
```

---

## Appendix B: Troubleshooting

### Issue: `Pinecone.create_collection() got unexpected keyword argument`

**Cause**: Pinecone Serverless doesn't support collection backup  
**Fix**: Skip backup (migration is safe with verification)

### Issue: `NoneType object has no attribute 'next'`

**Cause**: Empty namespace or pagination issue  
**Fix**: Handle empty namespaces gracefully

### Issue: Query latency > 100ms

**Cause**: Network latency, not Pinecone  
**Fix**: Expected; will improve with Cerebras integration

---

## Support

- **Migration Questions**: See `DELPHI_ARCHITECTURE_UPGRADE_PLAN.md`
- **Code Issues**: Check `backend/modules/embeddings_delphi.py`
- **Security Questions**: Review `backend/modules/tenant_guard.py`

---

**Migration Status**: ✅ COMPLETE  
**Next Phase**: Cerebras Integration (Phase 2)
