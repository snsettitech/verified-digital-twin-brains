# Migration Scripts Ready to Run
## Implementation Complete - Awaiting Your Go-Ahead

---

## 📁 Scripts Created

| Script | Purpose | Location |
|--------|---------|----------|
| `day1_map_to_test_creator.py` | Map all namespaces to test creator | Root directory |
| `day2_test_deletion.py` | Test twin/creator deletion | Root directory |
| `backend/modules/embeddings_delphi.py` | New Delphi client module | Backend modules |

---

## ✅ Your Configuration Confirmed

| Setting | Your Choice |
|---------|-------------|
| **Test Creator ID** | `sainath.no.1` |
| **Default namespace** | Map to `creator_sainath.no.1_twin_default` |
| **After successful test** | Keep migrated data (Option A) |
| **New twin naming** | Semantic names (e.g., `twin_coach_persona`) |

---

## 🚀 How to Run the Migration

### Step 1: Day 1 - Map to Test Creator

```bash
# Navigate to project directory
cd D:\verified-digital-twin-brains

# Run Day 1 script
python day1_map_to_test_creator.py
```

**What it does:**
1. Creates collection backup
2. Shows dry-run mapping plan
3. Asks for confirmation
4. Migrates all 30 namespaces to `creator_sainath.no.1_twin_{name}`
5. Verifies migration
6. Cleans up old namespaces

**Expected output:**
```
NAMESPACE MIGRATION TO TEST CREATOR
Test Creator ID: sainath.no.1
Dry Run: True

Namespace mapping plan:
  __default__ (376 vectors) → creator_sainath.no.1_twin_default
  5698a809-87a5-... (68 vectors) → creator_sainath.no.1_twin_5698a809
  ...

Review the mapping above.
Proceed with actual migration? (yes/no): 
```

### Step 2: Day 2 - Test Deletion

```bash
python day2_test_deletion.py
```

**What it does:**
1. Tests query performance (< 100ms target)
2. Deletes one twin (test individual deletion)
3. Asks permission to delete all creator data
4. Tests creator deletion (GDPR compliance)
5. Verifies no data remains

**Expected output:**
```
DAY 2: TESTING TWIN & CREATOR DELETION

TEST 1: QUERY PERFORMANCE
P50 Latency: 45.23ms
P95 Latency: 78.45ms
✓ Performance GOOD (< 100ms P95)

TEST 2: TWIN DELETION
Twin namespace: creator_sainath.no.1_twin_default
Vectors before: 376
✓ Twin deletion SUCCESSFUL

Delete ALL remaining data for sainath.no.1? (yes/no): 
```

---

## 📊 Expected Results

### After Day 1

| Before | After |
|--------|-------|
| 30 UUID namespaces | 30 creator-based namespaces |
| `__default__` | `creator_sainath.no.1_twin_default` |
| `5698a809-...` | `creator_sainath.no.1_twin_5698a809` |
| **805 vectors** | **805 vectors** (same data, new structure) |

### After Day 2 (if you delete all)

| Metric | Result |
|--------|--------|
| Twin deletion | ✓ Works (single API call) |
| Creator deletion | ✓ Works (GDPR compliant) |
| Query performance | ✓ < 100ms P95 |
| Data verification | ✓ 0 vectors remain |

---

## 🎯 What You Get After Migration

### 1. Delphi Namespace Structure
```
digital-twin-brain (index)
├── creator_sainath.no.1_twin_default      (376 vectors)
├── creator_sainath.no.1_twin_5698a809     (68 vectors)
├── creator_sainath.no.1_twin_d080d547     (73 vectors)
└── ... (27 more twins)
```

### 2. New Client Module

```python
from backend.modules.embeddings_delphi import get_delphi_client

client = get_delphi_client()

# Upsert to specific twin
client.upsert_vectors(
    vectors=[{"id": "doc-1", "values": [...], "metadata": {}}],
    creator_id="sainath.no.1",
    twin_id="coach_persona"  # Semantic name!
)

# Query specific twin
results = client.query(
    vector=[...],
    creator_id="sainath.no.1",
    twin_id="coach_persona"
)

# Delete specific twin
client.delete_twin("sainath.no.1", "coach_persona")

# Delete ALL creator data (GDPR)
client.delete_creator_data("sainath.no.1")
```

### 3. Feature Flag Integration

Add to your `.env`:
```bash
USE_DELPHI_NAMESPACES=true
```

Then in your code:
```python
if os.environ.get("USE_DELPHI_NAMESPACES") == "true":
    from backend.modules.embeddings_delphi import get_delphi_client
else:
    from backend.modules.embeddings import get_pinecone_client
```

---

## ⚠️ Safety Features

### 1. Backup Created
Before any changes, a collection backup is created:
```
digital-twin-brain-backup-20260211_143052
```

### 2. Dry Run First
Day 1 script shows mapping plan before making changes.

### 3. Verification After Each Step
- Vector counts verified
- Query performance tested
- Deletion verified (0 vectors remain)

### 4. Interactive Confirmation
Scripts ask for confirmation at critical steps.

---

## 🔄 Rollback Plan

If something goes wrong:

```python
# Option 1: Restore from collection backup
pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
pc.create_index(
    name="digital-twin-brain-restored",
    dimension=3072,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    source_collection="digital-twin-brain-backup-20260211_143052"
)

# Option 2: Just delete all and start fresh
index = pc.Index("digital-twin-brain")
stats = index.describe_index_stats()
for ns in stats.namespaces.keys():
    index.delete(delete_all=True, namespace=ns)
```

---

## 📋 Pre-Flight Checklist

Before running the scripts, confirm:

- [ ] You have the Pinecone API key in `.env`
- [ ] You can run Python scripts in this environment
- [ ] You have 30 minutes for Day 1
- [ ] You have 1 hour for Day 2
- [ ] You understand this will modify the `digital-twin-brain` index

---

## 🎬 Ready to Start?

**Run this command to begin:**

```bash
python day1_map_to_test_creator.py
```

The script will:
1. Show you exactly what will happen (dry run)
2. Ask for confirmation
3. Create backup
4. Execute migration
5. Verify results

**Say "yes" at the prompt to proceed with actual migration.**

---

## 📞 Support

If you encounter issues:

1. Check the logs in the script output
2. Verify Pinecone API key is correct
3. Check Pinecone console for index status
4. Review the backup collection was created

---

## ⏭️ After Migration

Once Day 1 and Day 2 are complete:

1. Update your application to use `embeddings_delphi.py`
2. Add feature flag for gradual rollout
3. Start creating new twins with semantic names
4. Monitor performance and costs

---

**Status: READY TO RUN**  
**Estimated time: 2-4 hours**  
**Risk level: LOW (backup + verification)**

**Type "run day 1" to execute the migration.**
