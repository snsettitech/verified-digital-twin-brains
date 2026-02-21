# PR6-A Deployment Summary: Widget Safety Parity

## Executive Summary
**Status:** ✅ DEPLOYED  
**Scope:** Security fix for widget endpoint to enforce publish controls  
**Risk Level:** Medium (behavior change for widget users)

## Changes Made

### 1. Code Changes (3 edits to `backend/routers/chat.py`)

#### Edit 1: Load Publish Controls (lines 2149-2156)
```python
# Load publish controls for widget safety parity with public-share (PR6-A)
publish_controls = _load_public_publish_controls(twin_id)
published_identity_topics = publish_controls.get("published_identity_topics", set())
published_policy_topics = publish_controls.get("published_policy_topics", set())
published_source_ids = publish_controls.get("published_source_ids", set())
context_trace["published_identity_topics_count"] = len(published_identity_topics)
context_trace["published_policy_topics_count"] = len(published_policy_topics)
context_trace["published_source_ids_count"] = len(published_source_ids)
```

#### Edit 2: Filter Owner Memories (lines 2253-2264)
```python
# Filter owner memories by publish controls (parity with public-share) (PR6-A)
owner_memory_candidates = _filter_public_owner_memory_candidates(
    gate.get("owner_memory") or [],
    published_identity_topics=published_identity_topics,
    published_policy_topics=published_policy_topics,
)
owner_memory_refs = [m.get("id") for m in owner_memory_candidates if isinstance(m, dict) and m.get("id")]
owner_memory_topics = [
    (m.get("topic_normalized") or m.get("topic"))
    for m in owner_memory_candidates
    if (m.get("topic_normalized") or m.get("topic"))
]
owner_memory_context = format_owner_memory_context(owner_memory_candidates) if owner_memory_candidates else ""
```

#### Edit 3: Filter Contexts & Citations (lines 2334-2342)
```python
# Filter contexts and citations by published sources (parity with public-share) (PR6-A)
retrieved_context_snippets, removed_context_count = _filter_contexts_to_allowed_sources(
    retrieved_context_snippets,
    published_source_ids,
)
citations = _filter_citations_to_allowed_sources(citations, published_source_ids)
if removed_context_count > 0:
    context_trace["public_scope_removed_context_count"] = removed_context_count
    context_trace["public_scope_violation"] = True
```

### 2. Test Suite Added (`backend/tests/test_widget_publish_controls.py`)
- 15 tests covering:
  - Memory filtering by publish controls
  - Citation filtering by source IDs
  - Context filtering with violation tracking
  - Code inspection (verifying changes are in place)
  - Parity checks with public-share endpoint

## Test Results
```
============================= test session starts =============================
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_public_owner_memory_candidates_basic PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_public_owner_memory_candidates_empty_published PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_public_owner_memory_candidates_empty_candidates PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_public_owner_memory_candidates_policy_types PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_citations_to_allowed_sources PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_citations_empty_allowed PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_contexts_to_allowed_sources PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_filter_contexts_empty_allowed PASSED
tests/test_widget_publish_controls.py::TestWidgetPublishControls::test_load_public_publish_controls_returns_defaults_on_error PASSED
tests/test_widget_publish_controls.py::TestWidgetCodeChanges::test_widget_loads_publish_controls PASSED
tests/test_widget_publish_controls.py::TestWidgetCodeChanges::test_widget_filters_owner_memory PASSED
tests/test_widget_publish_controls.py::TestWidgetCodeChanges::test_filter_citations_and_contexts PASSED
tests/test_widget_publish_controls.py::TestWidgetCodeChanges::test_widget_trace_includes_publish_counts PASSED
tests/test_widget_publish_controls.py::TestParityWithPublicShare::test_both_use_same_filter_functions PASSED
tests/test_widget_publish_controls.py::TestParityWithPublicShare::test_both_emit_violation_metrics PASSED
======================= 15 passed, 16 warnings in 3.91s =======================

Existing tests (test_public_share_filters.py): 3 passed
```

## Security Impact

### Before PR6-A
- Widget users could see ALL owner memories (not just published)
- Widget citations showed ALL sources (not just published)
- Widget contexts included ALL retrieved content (not just published)

### After PR6-A
- Widget enforces same publish controls as public-share endpoint
- Owner memories filtered by `published_identity_topics` and `published_policy_topics`
- Citations filtered by `published_source_ids`
- Contexts filtered by `published_source_ids`
- Violations tracked in `context_trace` for monitoring

## Behavior Change Notice

**⚠️ Widget users may see less content after this deploy**

If a twin has:
- Owner memories that were never published
- Sources that were never published

Widget users will no longer see these. They will still see:
- General knowledge responses (no owner memory needed)
- Published memories (explicitly approved for public)
- Published sources (explicitly approved for public)

## Rollback Plan

If issues arise, revert these 3 code blocks in `backend/routers/chat.py`:
1. Lines 2149-2156 (publish controls loading)
2. Lines 2253-2264 (memory filtering)
3. Lines 2334-2342 (context/citation filtering)

No database migration needed.

## Monitoring

Watch for:
- `public_scope_violation: true` in logs (indicates filtering is active)
- `public_scope_removed_context_count > 0` (indicates content being filtered)
- Increased 4xx errors from widget endpoint (users expecting more content)

## Acceptance Criteria Checklist

- [x] Widget loads `_load_public_publish_controls()`
- [x] Widget calls `_filter_public_owner_memory_candidates()`
- [x] Widget calls `_filter_contexts_to_allowed_sources()`
- [x] Widget calls `_filter_citations_to_allowed_sources()`
- [x] Tests pass: 15 new tests
- [x] Tests pass: 3 existing public-share tests (no regression)
- [x] NDJSON format unchanged
- [x] No retrieval ranking changes
- [x] No prompt modifications

## Deployment Status

**DEPLOYED:** Code changes applied and tested  
**NEXT STEPS:** 
1. Monitor widget usage for 24 hours
2. Document publish_controls setup for widget users
3. Consider PR6-B (locked-only memories for identity queries) for next sprint

---

## Operational Update: Pinecone Index Cutover

As of this sprint, runtime configuration has been prepared for the new Pinecone index:

```env
PINECONE_HOST=digitalminds-nrnzovv.svc.aped-4627-b74a.pinecone.io
PINECONE_INDEX_NAME=digitalminds
PINECONE_INDEX_MODE=integrated
PINECONE_TEXT_FIELD=chunk_text
COHERE_RERANK_MODEL=rerank-v3.5
```

Notes:
- Retrieval/ingestion now support both `vector` and `integrated` modes via adapter.
- Default code path remains backward-compatible (`vector`) when mode is not set.
