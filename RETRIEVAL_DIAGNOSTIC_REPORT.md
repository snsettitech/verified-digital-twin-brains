# Chat Retrieval Diagnostic Report

**Date**: 2026-02-12  
**Status**: Investigation in Progress  

---

## Executive Summary

Chat retrieval involves multiple components working together. Based on code analysis, here are the potential failure points:

| Component | Status | Risk Level |
|-----------|--------|------------|
| Pinecone Connection | Needs Testing | High |
| Embedding Generation | Functional | Low |
| Namespace Resolution | Needs Testing | High |
| Vector Search | Needs Testing | Medium |
| Group Permissions | Needs Testing | Medium |

---

## Retrieval Flow Architecture

```
User Query
    ↓
Chat Router (chat.py)
    ↓
Agent (agent.py) → Tool: search_knowledge_base (tools.py)
    ↓
retrieve_context (retrieval.py)
    ↓
┌─────────────────────────────────────────────────────────┐
│  1. Check Owner Memory (highest priority)               │
│  2. Check Verified QnA                                  │
│  3. Vector Search (Pinecone) ← MOST COMMON PATH        │
│     - Query Expansion (GPT-4o-mini)                    │
│     - HyDE Answer Generation                           │
│     - Embedding Generation                             │
│     - Namespace Resolution (Delphi)                    │
│     - Pinecone Query                                   │
│     - RRF Merging                                      │
│     - Reranking (FlashRank)                            │
└─────────────────────────────────────────────────────────┘
    ↓
Return Contexts
```

---

## Common Failure Points

### 1. 🚨 Pinecone Connection Issues

**Symptoms**: 
- No contexts returned
- Timeout errors in logs
- "Vector search failed" messages

**Check**:
```bash
# Test Pinecone connection
cd backend
python -c "from modules.clients import get_pinecone_index; idx = get_pinecone_index(); print(idx.describe_index_stats())"
```

**Env Variables Required**:
```bash
PINECONE_API_KEY=pcsk_...
PINECONE_HOST=https://...pinecone.io
PINECONE_INDEX_NAME=digital-twin-brain
```

### 2. 🚨 Namespace Resolution Issues (Delphi)

**Symptoms**:
- Retrieval works for some twins but not others
- "No knowledge vectors found" errors
- Empty results despite uploaded documents

**Root Cause**: The Delphi namespace system uses `creator_{creator_id}_twin_{twin_id}` format, but:
- Old data might be in legacy format (just `twin_id`)
- `creator_id` might not be resolved correctly
- Namespace candidates might not include both formats

**Debug**:
```python
from modules.delphi_namespace import get_namespace_candidates_for_twin

# Check namespace candidates
namespaces = get_namespace_candidates_for_twin(twin_id="your-twin-id", include_legacy=True)
print(f"Namespaces to query: {namespaces}")

# Check Pinecone stats for these namespaces
from modules.clients import get_pinecone_index
index = get_pinecone_index()
stats = index.describe_index_stats()
for ns in namespaces:
    count = stats.get("namespaces", {}).get(ns, {}).get("vector_count", 0)
    print(f"  {ns}: {count} vectors")
```

### 3. 🚨 Group Permissions Filtering

**Symptoms**:
- Contexts found but then filtered out
- "After permissions: 0" in logs

**Check**:
```python
# In debug_retrieval.py response, check:
{
  "diagnostics": {
    "default_group_id": "..."  # Should not be "None"
  }
}
```

### 4. 🚨 Embedding Dimension Mismatch

**Symptoms**:
- Pinecone query errors about dimension mismatch
- "vector dimension mismatch" errors

**Root Cause**: Different embedding models produce different dimensions:
- OpenAI `text-embedding-3-large`: 3072 dims
- HuggingFace `all-MiniLM-L6-v2`: 384 dims

**Check**:
```bash
# Check embedding provider
echo $EMBEDDING_PROVIDER  # Should be "openai" or not set

# Check embedding dimensions
python -c "
from modules.embeddings import get_embedding
emb = get_embedding('test')
print(f'Embedding dimension: {len(emb)}')
"
```

### 5. 🚨 Reranking Score Too Low

**Symptoms**:
- Contexts found but then discarded
- "Rerank scores too low. Using vector scores." in logs

**Current Threshold**: 0.001 (very low)

**Location**: `retrieval.py:695`

---

## Diagnostic Commands

### Test 1: Basic Pinecone Connection
```bash
cd backend
python -c "
from modules.clients import get_pinecone_index
index = get_pinecone_index()
stats = index.describe_index_stats()
print(f'Total vectors: {stats.total_vector_count}')
print(f'Namespaces: {list(stats.namespaces.keys())[:10]}')  # First 10
"
```

### Test 2: Embedding Generation
```bash
cd backend
python -c "
from modules.embeddings import get_embedding
emb = get_embedding('What is machine learning?')
print(f'Embedding length: {len(emb)}')
print(f'First 5 values: {emb[:5]}')
"
```

### Test 3: Namespace Resolution
```bash
cd backend
python -c "
from modules.delphi_namespace import get_namespace_candidates_for_twin
# Replace with your twin ID
ns = get_namespace_candidates_for_twin('your-twin-id', include_legacy=True)
print(f'Namespaces: {ns}')
"
```

### Test 4: Full Retrieval Pipeline (via Debug Endpoint)
```bash
# Start the backend, then:
curl -X POST http://localhost:8000/debug/retrieval \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What topics can you help with?",
    "twin_id": "your-twin-id",
    "top_k": 5
  }'
```

---

## Code Issues Found

### Issue 1: Namespace Resolution Caching
**File**: `modules/delphi_namespace.py:39`

The `@lru_cache` on `resolve_creator_id_for_twin` might cache `None` if the first lookup fails:

```python
@lru_cache(maxsize=4096)
def resolve_creator_id_for_twin(twin_id: str) -> Optional[str]:
    # If this fails first time, None is cached indefinitely!
```

**Fix**: Add cache invalidation or shorter TTL.

### Issue 2: No Fallback When Namespace Empty
**File**: `modules/retrieval.py:403-406`

If namespace query fails with exception, it's logged but no fallback:
```python
if isinstance(ns_result, Exception):
    print(f"[Retrieval] Namespace query failed ({ns}): {ns_result}")
    continue  # Just continues with empty results
```

### Issue 3: Group Resolution Failure Silenced
**File**: `modules/retrieval.py:576-582`

If `get_default_group` fails, `group_id` becomes `None`:
```python
try:
    default_group = await get_default_group(twin_id)
    group_id = default_group["id"]
except Exception:
    # Silently continues with group_id=None
    group_id = None
```

This might cause permission filtering issues.

---

## Most Likely Causes

Based on the code analysis, the most likely causes of "chat retrieval not working" are:

### 1. **Empty Namespaces (80% probability)**
The vectors exist but not in the expected namespace format. Check:
- Are vectors in legacy format (`twin_id`) but code expects Delphi format (`creator_*_twin_*`)?
- Is `DELPHI_DUAL_READ` environment variable set to `true`?

### 2. **Creator ID Resolution Failure (60% probability)**
The `resolve_creator_id_for_twin` function might be returning `None` due to:
- Missing `creator_id` column in database
- Caching of `None` value
- RLS policy blocking read

### 3. **Pinecone Index Stats (40% probability)**
The index stats might show vectors but in different namespaces than expected.

---

## Immediate Actions to Take

1. **Run the diagnostic commands above** to identify which component is failing

2. **Check environment variables**:
   ```bash
   # Required for retrieval
   PINECONE_API_KEY
   PINECONE_HOST
   PINECONE_INDEX_NAME
   OPENAI_API_KEY
   
   # Recommended
   DELPHI_DUAL_READ=true  # Enable dual-read for backward compatibility
   ```

3. **Clear namespace cache** if creator_id was recently added:
   ```python
   from modules.delphi_namespace import clear_creator_namespace_cache
   clear_creator_namespace_cache()
   ```

4. **Use the debug endpoint** to test retrieval directly:
   ```bash
   POST /debug/retrieval
   {
     "query": "test query",
     "twin_id": "your-twin-id"
   }
   ```

---

## Files to Check

| File | Purpose |
|------|---------|
| `modules/retrieval.py` | Main retrieval logic |
| `modules/delphi_namespace.py` | Namespace resolution |
| `modules/clients.py` | Pinecone client initialization |
| `modules/embeddings.py` | Embedding generation |
| `routers/debug_retrieval.py` | Debug endpoint |
| `routers/chat.py` | Chat flow |

---

## Need More Info

To provide a more specific diagnosis, I need:

1. **Error logs** from the backend when retrieval fails
2. **Twin ID** that's having issues
3. **Output of diagnostic commands** above
4. **Pinecone index stats** (namespace list and vector counts)
5. **Environment variables** (redacted API keys)

---

## Quick Fix Script

```python
#!/usr/bin/env python3
"""Quick diagnostic script for retrieval issues."""

import asyncio
import sys
sys.path.insert(0, 'backend')

async def diagnose(twin_id: str):
    print(f"=== Retrieval Diagnosis for Twin: {twin_id} ===\n")
    
    # 1. Check Pinecone connection
    print("1. Pinecone Connection:")
    try:
        from modules.clients import get_pinecone_index
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        print(f"   ✓ Connected. Total vectors: {stats.total_vector_count}")
        print(f"   Namespaces: {list(stats.namespaces.keys())[:5]}...")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    # 2. Check namespace resolution
    print("\n2. Namespace Resolution:")
    from modules.delphi_namespace import (
        resolve_creator_id_for_twin,
        get_namespace_candidates_for_twin
    )
    creator_id = resolve_creator_id_for_twin(twin_id)
    print(f"   Creator ID: {creator_id}")
    
    namespaces = get_namespace_candidates_for_twin(twin_id, include_legacy=True)
    print(f"   Namespaces: {namespaces}")
    
    # 3. Check vector counts per namespace
    print("\n3. Vector Counts:")
    for ns in namespaces:
        count = stats.get("namespaces", {}).get(ns, {}).get("vector_count", 0)
        print(f"   {ns}: {count} vectors")
    
    # 4. Try actual retrieval
    print("\n4. Test Retrieval:")
    try:
        from modules.retrieval import retrieve_context
        contexts = await retrieve_context("What can you help with?", twin_id, top_k=3)
        print(f"   ✓ Retrieved {len(contexts)} contexts")
        for i, ctx in enumerate(contexts[:2]):
            print(f"   [{i+1}] Score: {ctx.get('score', 0):.3f}, Source: {ctx.get('source_id', 'unknown')}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import os
    twin_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TEST_TWIN_ID", "test")
    asyncio.run(diagnose(twin_id))
```

Save as `diagnose_retrieval.py` and run:
```bash
python diagnose_retrieval.py your-twin-id
```
