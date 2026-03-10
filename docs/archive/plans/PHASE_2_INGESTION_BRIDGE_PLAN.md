# Phase 2: Ingestion Bridge - Implementation Plan

> **Goal:** Crawl → Source → Pinecone with versioning and tombstones

## Status

| Item | Value |
|------|-------|
| **Current Phase** | Phase 2 |
| **Current Sub-Phase** | 2.5 - Integration Tests |
| **Previous Phase** | Phase 1B (COMPLETE - 264 tests passing) |
| **Started** | 2026-02-23 |
| **Updated** | 2026-02-23 |

## Completion Summary

### Completed Sub-phases

| Sub-phase | Status | Files Created/Modified |
|-----------|--------|------------------------|
| 2.1 Crawl→Source Adapter | ✅ | `crawl_ingestion_bridge.py` |
| 2.2 Versioned Chunk Metadata | ✅ | Updated `pinecone_adapter.py` |
| 2.3 Default Retrieval Filter | ✅ | Updated `retrieval.py` |
| 2.4 Tombstone Old Chunks | ✅ | `chunk_version_manager.py` |
| 2.5 Integration Tests | ✅ | 3 new test files, 40 tests |

### Test Results

| Test Suite | Tests | Passed | Failed |
|------------|-------|--------|--------|
| test_crawl_ingestion_bridge.py | 14 | 14 | 0 |
| test_chunk_version_manager.py | 17 | 17 | 0 |
| test_retrieval_tombstone_filter.py | 9 | 9 | 0 |
| **Phase 2 Total (Unit Tests)** | **40** | **40** | **0** |
| Phase 1B Tests (Unit) | 34 | 34 | 0 |
| Phase 1B Tests (Integration) | - | - | DB required |
| **Combined Unit Tests** | **74** | **74** | **0** |

## Sub-phase Overview

| Sub-phase | Name | Files Created/Modified | Tests |
|-----------|------|------------------------|-------|
| 2.1 | Crawl→Source Adapter | `crawl_ingestion_bridge.py` | Test bridge conversion |
| 2.2 | Versioned Chunk Metadata | Extend `pinecone_adapter.py` | Test metadata fields |
| 2.3 | Default Retrieval Filter | Modify `retrieval.py` | Test tombstone exclusion |
| 2.4 | Tombstone Old Chunks | `chunk_version_manager.py` | Test versioning logic |
| 2.5 | Integration Tests + Regressions | New test files | E2E pipeline tests |

## Architecture

### Data Flow

```
crawl_pages (DB)
    ↓ (artifact path)
Artifact Store
    ↓ (read normalized.md)
CrawlIngestionBridge
    ↓ (create source, chunk)
Source Record (DB)
    ↓ (chunk + metadata)
Pinecone (with version metadata)
    ↓ (retrieval with filter)
Retrieval (is_current=True only)
```

### Chunk Metadata Schema (Extended)

```python
CHUNK_METADATA_VERSIONED = {
    # Existing fields
    "text": str,
    "source_id": str,
    "twin_id": str,
    "chunk_id": str,
    "filename": str,
    # ... other existing fields
    
    # NEW: Versioning fields
    "crawl_id": str,           # Parent crawl run ID
    "crawl_page_id": str,      # Source crawl page ID
    "canonical_url": str,      # Normalized URL
    "content_hash": str,       # SHA-256 of content
    "chunk_version": int,      # Version number (1, 2, 3...)
    "is_current": bool,        # True = active, False = tombstoned
    "tombstoned_at": str,      # ISO timestamp (null if current)
}
```

### Tombstone Logic

```
On page CHANGED:
  1. Get previous_page_id from crawl_pages
  2. Find all chunks with that crawl_page_id and is_current=True
  3. Set is_current=False, tombstoned_at=now()
  4. Upsert new chunks with is_current=True, chunk_version=N+1

On page REMOVED:
  1. Find all chunks with crawl_page_id and is_current=True
  2. Set is_current=False, tombstoned_at=now()

On unchanged recrawl:
  1. Skip chunk ingestion entirely
  2. Reference prior artifacts
```

## Implementation Details

### Phase 2.1: Crawl→Source Adapter

**File:** `backend/modules/crawl_ingestion_bridge.py`

**Key Methods:**
- `process_crawl_for_ingestion(crawl_id, twin_id)` - Main entry point
- `create_source_from_crawl_page(page, twin_id)` - Convert page to source
- `should_skip_ingestion(page)` - Check if page should be skipped

**Skip Conditions:**
- Page classification = UNCHANGED
- Page status = failed/blocked
- No normalized artifact exists

**Twin Isolation:**
- All queries filtered by twin_id
- Source creation uses twin_id from crawl_run

### Phase 2.2: Versioned Chunk Metadata

**File:** `backend/modules/pinecone_adapter.py`

**Changes:**
- Add new metadata fields to DEFAULT_METADATA_FIELDS
- Ensure all vector upserts include version metadata when available
- Backward compatible (existing chunks work without new fields)

### Phase 2.3: Default Retrieval Filter

**File:** `backend/modules/retrieval.py`

**Changes:**
- Add default filter `{"is_current": True}` to all queries
- Allow override via parameter for debug/admin use
- Existing chunks without `is_current` field are treated as current

### Phase 2.4: Tombstone Old Chunks

**File:** `backend/modules/chunk_version_manager.py`

**Key Methods:**
- `tombstone_previous_version(crawl_page_id)` - Tombstone old chunks
- `tombstone_removed_page(crawl_page_id)` - Tombstone all chunks for removed page
- `get_current_chunks(crawl_page_id)` - Get active chunks for a page

**Design Decision:**
- Use metadata update (set is_current=False) not vector deletion
- This preserves audit trail and allows recovery

### Phase 2.5: Integration Tests

**Files:**
- `backend/tests/test_crawl_ingestion_bridge.py`
- `backend/tests/test_chunk_version_manager.py`
- `backend/tests/test_retrieval_tombstone_filter.py`

**Test Scenarios:**
1. End-to-end: crawl → ingest → retrieve
2. Changed page creates new version, old version tombstoned
3. Unchanged recrawl skips ingestion, no duplicate chunks
4. Retrieval excludes tombstoned chunks
5. Backward compatibility: existing chat/retrieval works

## Migration Requirements

### Database Migration

```sql
-- No schema changes needed for Phase 2
-- All versioning metadata stored in Pinecone vector metadata
-- Tracking columns already exist from Phase 1B:
--   - crawl_pages.content_hash
--   - crawl_pages.canonical_url
--   - crawl_pages.previous_page_id
```

### Backward Compatibility

- Existing chunks without version metadata are treated as current
- Existing sources without crawl metadata work normally
- Chat retrieval unchanged for non-crawl sources

## Test Plan

### Unit Tests

| Test | Description |
|------|-------------|
| test_bridge_creates_source | Bridge creates source from crawl page |
| test_bridge_skips_unchanged | Unchanged pages are skipped |
| test_bridge_loads_artifact | Content loaded from artifact store |
| test_version_metadata_upsert | Version metadata included in vectors |
| test_tombstone_on_change | Old chunks tombstoned when page changes |
| test_retrieval_excludes_tombstoned | Default retrieval filters tombstoned |

### Integration Tests

| Test | Description |
|------|-------------|
| test_e2e_crawl_to_retrieval | Full pipeline test |
| test_recrawl_no_duplicates | Unchanged recrawl doesn't create duplicates |
| test_changed_page_versioning | Changed page creates new chunk version |
| test_chat_regression | Existing chat functionality preserved |

### Regression Tests

| Test | Description |
|------|-------------|
| test_existing_source_ingestion | Standard ingestion still works |
| test_existing_retrieval | Standard retrieval still works |
| test_chat_context | Chat with context still works |

## Deliverables

After Phase 2 complete:
- [ ] `backend/modules/crawl_ingestion_bridge.py`
- [ ] `backend/modules/chunk_version_manager.py`
- [ ] Updated `backend/modules/pinecone_adapter.py`
- [ ] Updated `backend/modules/retrieval.py`
- [ ] Test suite with 50+ new tests
- [ ] All existing tests still passing

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-23 | 1.0 | Initial plan |
