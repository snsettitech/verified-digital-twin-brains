# Chat Retrieval Investigation Summary

**Date**: 2026-02-12  
**Status**: Investigation Complete - Root Cause Analysis Provided  

---

## Problem Statement
"Chat retrieval is not working"

---

## How Chat Retrieval Works (The Full Flow)

```
1. User sends message via /chat/{twin_id} endpoint
         ↓
2. Chat Router (chat.py) receives the request
         ↓
3. Agent (agent.py) processes with LangGraph
         ↓
4. Agent calls Tool: search_knowledge_base (tools.py)
         ↓
5. Tool calls retrieve_context() (retrieval.py)
         ↓
6. Retrieval Pipeline:
   a. Check owner memory (highest priority)
   b. Check verified Q&A
   c. Vector Search:
      - Expand query using GPT-4o-mini
      - Generate HyDE answer
      - Create embeddings
      - Query Pinecone (with namespace resolution)
      - Merge results with RRF
      - Rerank with FlashRank
         ↓
7. Results returned to Agent
         ↓
8. Agent generates response with context
         ↓
9. Response streamed to user
```

---

## Most Likely Root Causes

### 1. **Namespace Mismatch (Highest Probability)**

**The Issue**: The system uses "Delphi" namespaces (`creator_{id}_twin_{twin_id}`) but:
- Old data might be in legacy format (`{twin_id}` only)
- The `creator_id` resolution might fail
- Dual-read mode might not be enabled

**Evidence from Code**:
```python
# From delphi_namespace.py
DELPHI_DUAL_READ = os.getenv("DELPHI_DUAL_READ", "true").lower() == "true"
```

If `DELPHI_DUAL_READ` is not set to `true`, the system only queries the new format namespaces, missing legacy data.

**Fix**:
```bash
export DELPHI_DUAL_READ=true
```

---

### 2. **Missing or Mismatched Embeddings**

**The Issue**: The embedding provider configuration might be mismatched:

| Provider | Dimension | Use Case |
|----------|-----------|----------|
| OpenAI `text-embedding-3-large` | 3072 | Default, production |
| HuggingFace `all-MiniLM-L6-v2` | 384 | Local, faster |

If vectors were created with one provider but retrieval uses another, **dimension mismatch** will occur.

**Check**:
```bash
# Check current provider
export EMBEDDING_PROVIDER=openai  # or huggingface
```

---

### 3. **Pinecone Connection Issues**

**Required Environment Variables**:
```bash
PINECONE_API_KEY=pcsk_...
PINECONE_HOST=https://...pinecone.io
PINECONE_INDEX_NAME=digital-twin-brain
```

**Note**: I found a Pinecone API key in `.env` but the host/index need to be verified.

---

### 4. **Group Permissions Filtering**

**The Issue**: Retrieved contexts are filtered by group permissions. If:
- No default group exists
- Group resolution fails
- Contexts don't have matching group IDs

The result is **0 contexts after filtering** even if vectors exist.

**Code Location**: `retrieval.py:491-528`

---

### 5. **Reranking Threshold Too Strict**

**The Issue**: FlashRank reranking might discard valid results:

```python
# retrieval.py:695-696
max_rerank_score = max((float(res.get("score", 0) or 0) for res in results), default=0)
if max_rerank_score < 0.001:  # Very low threshold!
    print("[Retrieval] Rerank scores too low. Using vector scores.")
```

While the threshold is low (0.001), if FlashRank fails to load, this could cause issues.

---

## Diagnostic Script Created

I've created `diagnose_retrieval.py` that checks:

1. ✓ Environment variables
2. ✓ Pinecone connection
3. ✓ Embedding generation
4. ✓ Namespace resolution
5. ✓ Actual retrieval test

**Run it**:
```bash
cd backend
python ..\diagnose_retrieval.py <twin-id>
```

---

## Debug Endpoint Available

The system has a built-in debug endpoint:

```bash
POST /debug/retrieval
{
  "query": "What can you help with?",
  "twin_id": "your-twin-id",
  "top_k": 5
}
```

**Response includes**:
- Results count
- Diagnostics (default group ID)
- Full contexts with source filenames

---

## Quick Fixes to Try

### Fix 1: Enable Dual-Read Mode
```bash
export DELPHI_DUAL_READ=true
# Or in .env file
DELPHI_DUAL_READ=true
```

This ensures both legacy and new namespaces are queried.

### Fix 2: Clear Namespace Cache
```python
from modules.delphi_namespace import clear_creator_namespace_cache
clear_creator_namespace_cache()
```

If `creator_id` was recently added, the cache might have stale data.

### Fix 3: Verify Pinecone Index Stats
```python
from modules.clients import get_pinecone_index
index = get_pinecone_index()
stats = index.describe_index_stats()
print(stats)
```

Check if namespaces match what the code expects.

### Fix 4: Check Group Configuration
```python
from modules.access_groups import get_default_group
group = await get_default_group("your-twin-id")
print(group)
```

Ensure a default group exists.

---

## Code Issues Found During Investigation

### Issue 1: LRU Cache Might Cache None
**File**: `delphi_namespace.py:39`

```python
@lru_cache(maxsize=4096)
def resolve_creator_id_for_twin(twin_id: str) -> Optional[str]:
```

If the first lookup fails (e.g., DB not ready), `None` is cached indefinitely.

**Workaround**: Clear cache after DB setup
```python
clear_creator_namespace_cache()
```

### Issue 2: Silent Failures in Namespace Query
**File**: `retrieval.py:401-406`

```python
for ns, ns_result in zip(namespace_candidates, namespace_results):
    if isinstance(ns_result, Exception):
        print(f"[Retrieval] Namespace query failed ({ns}): {ns_result}")
        continue  # Silently continues!
```

Namespace errors are logged but not propagated.

### Issue 3: Group Resolution Failure Silenced
**File**: `retrieval.py:576-582`

```python
try:
    default_group = await get_default_group(twin_id)
    group_id = default_group["id"]
except Exception:
    group_id = None  # Silently continues
```

If group resolution fails, filtering might behave unexpectedly.

---

## What I Need From You

To provide a specific fix, please run:

```bash
cd backend
python ..\diagnose_retrieval.py <your-twin-id>
```

**And share**:
1. The output of the diagnostic script
2. Any error logs from the backend when chat fails
3. The twin ID that's having issues
4. Output of this command:
   ```python
   from modules.clients import get_pinecone_index
   index = get_pinecone_index()
   print(index.describe_index_stats())
   ```

---

## Summary of Findings

| Component | Likely Issue | Quick Fix |
|-----------|--------------|-----------|
| Namespaces | Legacy vs Delphi format mismatch | Set `DELPHI_DUAL_READ=true` |
| Embeddings | Dimension mismatch | Verify `EMBEDDING_PROVIDER` |
| Pinecone | Connection/auth issues | Check env vars |
| Groups | Missing default group | Create default access group |
| Reranking | FlashRank not loading | Check model cache |

**Most likely cause**: Namespace mismatch between legacy (`twin_id`) and Delphi (`creator_*_twin_*`) formats.

**Recommended immediate action**: 
1. Set `DELPHI_DUAL_READ=true`
2. Run diagnostic script
3. Share output for specific diagnosis
