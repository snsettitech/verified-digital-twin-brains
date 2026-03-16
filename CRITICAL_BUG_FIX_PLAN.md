# CRITICAL BUG FIX PLAN: Persona → Ingestion → Retrieval → Chat

**Mission:** Fix all 28 bugs systematically across the critical user flow so the system is 100% functional for onboarding, persona creation, data ingestion, vector retrieval, and chat quality.

**Philosophy:** Solo founder - every feature must work perfectly or the product dies. No shortcuts.

---

## PHASE OVERVIEW

| Phase | Focus | Bugs | Status | Verification |
|-------|-------|------|--------|--------------|
| **0** | Foundation (Critical Security) | #1, #2, #5, #6 | 🔴 Pending | Auth isolation tests |
| **1** | Twin Management | #7, #15, #20 | 🔴 Pending | Concurrent creation test |
| **2** | Data Ingestion | #3, #4, #8, #9, #13, #22, #24 | 🔴 Pending | Full roundtrip ingestion test |
| **3** | Vector Retrieval | #2, #14 | 🔴 Pending | Cross-twin isolation test |
| **4** | Chat Pipeline | #10, #11, #12, #16, #17, #18, #19, #25 | 🔴 Pending | Full chat flow test |
| **5** | Hardening | #21, #23, #25 | 🔴 Pending | Edge case tests |

**Total Bugs:** 28
**Estimated Duration:** 40-60 hours (8-10 work days)
**Go/No-Go:** Must pass all verification checkpoints before production

---

## PHASE 0: CRITICAL SECURITY & ISOLATION (4 BUGS)

### Why First?
These bugs allow data loss, cross-tenant leakage, and unauthorized deletion. Everything else is built on this foundation.

### Bugs in This Phase

#### BUG #1: CRITICAL - Cross-Tenant Account Deletion
- **File:** `backend/routers/auth.py:757-919`
- **Current:** Account delete endpoint has no owner verification
- **Fix:** Add tenant owner check before any deletion
- **Verification:** Test that non-owner cannot delete tenant data

#### BUG #2: CRITICAL - Cross-Twin Data Leakage in Retrieval
- **File:** `backend/modules/retrieval.py:1674-1683`
- **Current:** Namespace merge deduplicates by ID only, ignores twin_id
- **Fix:** Validate twin_id in all dedup operations
- **Verification:** Create 2 twins with identical chunk IDs, verify no leakage

#### BUG #5: CRITICAL - Tenant Auto-Creation Weakens Isolation
- **File:** `backend/modules/auth_guard.py:484-492`
- **Current:** Read endpoints auto-create tenants
- **Fix:** Change `create_if_missing=True` → `False` on read-only endpoints
- **Verification:** Verify new users can't auto-join random tenants

#### BUG #6: HIGH - Account Delete Leaves Orphaned User Row
- **File:** `backend/routers/auth.py:866-870`
- **Current:** User row updated but not deleted
- **Fix:** Hard-delete user row after anonymization
- **Verification:** Verify user row is completely removed

#### BUG #20: MEDIUM - Unvalidated Email in User Sync
- **File:** `backend/routers/auth.py:262-338`
- **Current:** Email from JWT not validated
- **Fix:** Add email format validation
- **Verification:** Test invalid email format is rejected

### Execution Order (Dependencies)

```
BUG #5 (auth_guard.py)  ← Must be first, affects all auth
    ↓
BUG #1 (auth.py delete) ← Depends on #5 being fixed
    ↓
BUG #6 (auth.py cleanup) ← Depends on #1
    ↓
BUG #20 (email validation) ← Independent
    ↓
BUG #2 (retrieval.py) ← Independent but critical
```

### Phase 0 Verification Checkpoint

**Test Suite: `test_phase_0_security.py`**

```python
# Test 1: Tenant isolation
def test_non_owner_cannot_delete_account():
    # Create tenant with owner_id=user1
    # Login as user2 (member, not owner)
    # Call DELETE /account
    # Verify HTTPException 403
    # Verify all twins still exist

# Test 2: Auto-creation blocked
def test_new_user_cannot_auto_create_tenant():
    # Login new user without tenant
    # Call GET /auth/whoami
    # Verify tenant_id is None or raises error
    # Verify no new tenant was created

# Test 3: Cross-twin isolation
def test_chunk_with_same_id_from_different_twin():
    # Create twin1, ingest chunk with id="abc123"
    # Create twin2, ingest chunk with id="abc123"
    # Query for twin1, verify only twin1's chunk returned
    # Query for twin2, verify only twin2's chunk returned

# Test 4: Email validation
def test_invalid_email_rejected():
    # Sync user with email=""
    # Verify error
    # Sync user with email="notanemail"
    # Verify error
```

**Success Criteria:**
- ✅ All 4 tests pass
- ✅ No data leakage between tenants
- ✅ Unauthorized operations blocked
- ✅ All auth flows maintain isolation

---

## PHASE 1: TWIN MANAGEMENT (3 BUGS)

### Why Here?
Twins are the unit of ownership. Once auth is solid, we fix twin creation/deletion.

### Bugs in This Phase

#### BUG #15: MEDIUM - Race Condition in Twin Creation
- **File:** `backend/modules/twin_service.py:174-213`
- **Current:** Concurrent creates can reuse another user's twin
- **Fix:** Re-verify ownership after catching duplicate key error
- **Verification:** Concurrent creates with same name, verify each user gets own twin

#### BUG #7: HIGH - Twin Deletion Missing Tenant Boundary
- **File:** `backend/routers/twins.py:1316-1380`
- **Current:** Delete uses only twin_id, not tenant_id
- **Fix:** Add `eq("tenant_id", tenant_id)` to all 15 delete queries
- **Verification:** Attempt cross-tenant twin deletion, verify blocked

#### BUG #20 (covered above): Email validation

### Phase 1 Verification Checkpoint

**Test Suite: `test_phase_1_twins.py`**

```python
# Test 1: Concurrent creation
def test_concurrent_twin_creation_isolation():
    # User A and User B concurrently create "Narendra Modi"
    # Both should get their own twin
    # Verify twin_a != twin_b
    # Verify user_a owns only twin_a

# Test 2: Tenant-scoped deletion
def test_cannot_delete_twin_from_different_tenant():
    # Create tenant1 with user1
    # Create tenant2 with user2
    # Create twin1 in tenant1
    # Login as user2 (tenant2)
    # Attempt to DELETE /twins/{twin1_id}
    # Verify 403 Forbidden
    # Verify twin1 still exists
```

**Success Criteria:**
- ✅ Concurrent creates don't collide
- ✅ Cross-tenant deletion blocked
- ✅ All twin metadata consistent

---

## PHASE 2: DATA INGESTION (7 BUGS)

### Why Here?
Auth and twin management are solid. Now we fix data flow without risking data loss.

### Bugs in This Phase

#### BUG #3: CRITICAL - Partial Ingestion Without Rollback
- **File:** `backend/modules/ingestion.py:2505-2691`
- **Current:** Chunks deleted BEFORE embeddings succeed
- **Fix:** Reverse order - embed/persist FIRST, then delete old
- **Verification:** Simulate embedding failure mid-process, verify no data loss

#### BUG #4: CRITICAL - Metadata Mutation
- **File:** `backend/modules/ingestion.py:2641-2648`
- **Current:** Dict mutated in-place
- **Fix:** Create copy: `md = dict(vector.get("metadata") or {})`
- **Verification:** Retry ingestion, verify metadata consistent

#### BUG #8: HIGH - No Bounds on Chunk Override
- **File:** `backend/modules/ingestion.py:2464-2468`
- **Current:** Can pass unlimited chunks
- **Fix:** Add `MAX_CHUNKS = 5000` limit and validation
- **Verification:** Pass 10k chunks, verify rejected

#### BUG #9: HIGH - Missing Null Embedding Validation
- **File:** `backend/modules/ingestion.py:2575-2577`
- **Current:** Null embeddings cause silent failures
- **Fix:** Check for None, skip or retry
- **Verification:** Mock embedding failure, verify graceful handling

#### BUG #13: HIGH - Metadata Override Timing
- **File:** `backend/modules/ingestion.py:2568-2569`
- **Current:** Override happens after embedding text built
- **Fix:** Move override before `_build_embedding_text()`
- **Verification:** Verify metadata fields appear in embeddings

#### BUG #22: MEDIUM - Prompt Questions Lose Text
- **File:** `backend/modules/ingestion.py:2341-2354`
- **Current:** Only indexes title, not actual question
- **Fix:** Include both title and question text
- **Verification:** Index prepared questions, verify full text searchable

#### BUG #24: MEDIUM - Stale Chunk References
- **File:** `backend/modules/ingestion.py:2633-2648`
- **Current:** Chunks inserted before vectors upserted
- **Fix:** Upsert vectors FIRST, then insert chunks
- **Verification:** Simulate vector upsert failure, verify no orphaned chunks

### Phase 2 Execution Order

```
BUG #3 (rollback order)  ← MUST be first
    ↓
BUG #24 (upsert order)   ← Depends on #3
    ↓
BUG #4 (metadata mutation) ← Independent
    ↓
BUG #13 (timing) ← Depends on understanding chunk flow
    ↓
BUG #22 (embedding text) ← Depends on #13
    ↓
BUG #8 (bounds) ← Independent
    ↓
BUG #9 (null validation) ← Independent
```

### Phase 2 Verification Checkpoint

**Test Suite: `test_phase_2_ingestion.py`**

```python
# Test 1: No data loss on embedding failure
def test_embedding_failure_preserves_old_chunks():
    # Ingest document v1 successfully (5 chunks)
    # Ingest document v2, simulate embedding failure at chunk 3
    # Verify v1 chunks still exist
    # Verify v2 partial chunks not persisted

# Test 2: Metadata consistency on retry
def test_metadata_consistent_on_retry():
    # Ingest with metadata {"type": "policy"}
    # Retry same ingestion
    # Verify metadata not duplicated/corrupted

# Test 3: Bounds enforcement
def test_chunk_override_limit_enforced():
    # POST with 6000 chunks in chunk_entries_override
    # Verify 400/413 error
    # Verify only 5000 chunks processed (if allowed)

# Test 4: Null embeddings handled
def test_null_embeddings_skipped():
    # Mock get_embedding to return None
    # Ingest document
    # Verify chunk skipped, no error, ingestion continues

# Test 5: Full document roundtrip
def test_full_ingestion_roundtrip():
    # Upload 10-page PDF
    # Verify all chunks stored in Supabase
    # Verify all vectors in Pinecone
    # Verify chunk.vector_id matches Pinecone ID
    # Verify metadata correct
```

**Success Criteria:**
- ✅ No data loss on any failure
- ✅ Metadata consistent on retries
- ✅ Bounds enforced
- ✅ Null embeddings handled gracefully
- ✅ Full roundtrip verified

---

## PHASE 3: VECTOR RETRIEVAL (2 BUGS)

### Why Here?
Data is safely ingested. Now we fix retrieval without risking data loss.

### Bugs in This Phase

#### BUG #2: CRITICAL - Cross-Twin Data Leakage (Revisited in Retrieval)
- **File:** `backend/modules/retrieval.py:1674-1683, 1789-1800`
- **Current:** Merge doesn't validate twin_id consistency
- **Fix:** Add twin_id validation in dedup and merge
- **Verification:** Already tested in Phase 0, verify again in retrieval context

#### BUG #14: HIGH - Partial Namespace Failures Not Detected
- **File:** `backend/modules/retrieval.py:1774-1777`
- **Current:** `asyncio.gather(..., return_exceptions=True)` returns partial failures silently
- **Fix:** Log and track partial failures, return confidence score
- **Verification:** Simulate 1 of 3 namespaces failing, verify error logged and handled

### Phase 3 Verification Checkpoint

**Test Suite: `test_phase_3_retrieval.py`**

```python
# Test 1: Cross-twin isolation in retrieval
def test_retrieve_only_owns_twin_data():
    # Twin A has 10 chunks from document1
    # Twin B has 10 chunks from document2 (identical vector IDs)
    # Query twin A for [similar to document2]
    # Verify only document1 chunks returned
    # Verify no document2 content leaked

# Test 2: Partial namespace failure handling
def test_partial_namespace_failure_logged():
    # Configure 3 namespaces
    # Mock namespace2 to fail
    # Call retrieve()
    # Verify results from namespace1 and namespace3 returned
    # Verify error logged for namespace2
    # Verify confidence score reflects partial data

# Test 3: Full retrieval roundtrip
def test_query_returns_correct_context():
    # Ingest document about "Narendra Modi's education"
    # Query "where did Modi go to school"
    # Verify education section returned
    # Verify source_id correct
    # Verify confidence score reasonable
```

**Success Criteria:**
- ✅ No cross-twin leakage in retrieval
- ✅ Partial failures detected and logged
- ✅ Correct contexts returned for queries

---

## PHASE 4: CHAT PIPELINE (8 BUGS)

### Why Here?
Data safely ingested and retrieved. Now we fix conversation/streaming.

### Bugs in This Phase

#### BUG #10: HIGH - Message Ordering Not Guaranteed
- **File:** `backend/modules/observability.py:241`
- **Current:** Order by created_at only, same timestamp = random order
- **Fix:** Add secondary order by message ID
- **Verification:** Create 2 messages with same timestamp, verify consistent order

#### BUG #11: HIGH - Async Tasks Not Cancelled
- **File:** `backend/routers/chat.py:2336-2354`
- **Current:** Stream disconnect leaves tasks running
- **Fix:** Add `pending_task.cancel()` in finally
- **Verification:** Disconnect mid-stream, verify task cancels

#### BUG #12: HIGH - Stream Missing Done Event on Error
- **File:** `backend/routers/chat.py:2884-2910`
- **Current:** Error doesn't emit "done" event
- **Fix:** Always emit terminal event
- **Verification:** Trigger error mid-stream, verify done event received

#### BUG #16: MEDIUM - Prompt Injection in Coreference
- **File:** `backend/modules/conversation_context.py:178-181`
- **Current:** User query not escaped
- **Fix:** Use `json.dumps(query)` to escape
- **Verification:** Query with `{injection}` syntax, verify handled safely

#### BUG #17: MEDIUM - Unescaped History in Prompts
- **File:** `backend/modules/conversation_context.py:64-74`
- **Current:** History not escaped before format string
- **Fix:** Escape braces: `.replace('{', '{{').replace('}', '}}')`
- **Verification:** History with `{variable}` patterns handled safely

#### BUG #18: MEDIUM - Missing Query Input Validation
- **File:** `backend/routers/chat.py` (entry point)
- **Current:** Empty/huge queries not validated
- **Fix:** Add min length check and max length check
- **Verification:** Test empty query, 10k char query

#### BUG #19: MEDIUM - Citation/Context Mismatch
- **File:** `backend/routers/chat.py:2364-2369`
- **Current:** Contexts merged but citations not re-extracted
- **Fix:** Validate citations match final context set
- **Verification:** Verify all cited sources in final context

#### BUG #25: LOW - Missing Connection Cleanup
- **File:** `backend/routers/chat.py:2925-2930`
- **Current:** DB connections not explicitly closed
- **Fix:** Add connection cleanup (architectural, document limitation)
- **Verification:** Monitor connection pool under sustained chat load

### Phase 4 Execution Order

```
BUG #10 (message order) ← MUST be first
    ↓
BUG #11 (cancel tasks) ← Independent
    ↓
BUG #12 (done event) ← Independent
    ↓
BUG #16, #17 (injection) ← Depends on #10
    ↓
BUG #18 (validation) ← Independent
    ↓
BUG #19 (citations) ← Depends on #10
    ↓
BUG #25 (cleanup) ← Independent
```

### Phase 4 Verification Checkpoint

**Test Suite: `test_phase_4_chat.py`**

```python
# Test 1: Message ordering
def test_messages_ordered_consistently():
    # Create conversation
    # Add 2 messages with same created_at timestamp
    # Query history 5 times
    # Verify same order every time

# Test 2: Stream disconnect cleanup
def test_stream_cleanup_on_disconnect():
    # Start streaming chat
    # Close connection mid-stream after 3 chunks
    # Wait 2 seconds
    # Verify pending task is cancelled
    # Verify no hanging connections

# Test 3: Error termination
def test_stream_emits_done_on_error():
    # Start streaming chat
    # Trigger error in agent (e.g., retrieval timeout)
    # Verify stream emits: {"type": "error", ...}
    # Verify stream emits: {"type": "done", "error": true}
    # Verify no further chunks

# Test 4: Prompt injection prevention
def test_query_with_injection_syntax_safe():
    # Query = "Tell me about {system_prompt}"
    # Verify handled safely, no variable substitution
    # Verify response doesn't leak prompts

# Test 5: History injection prevention
def test_history_with_braces_safe():
    # Previous message = "Response with {placeholder}"
    # Use in coreference resolution
    # Verify no format string interpretation

# Test 6: Input validation
def test_empty_query_rejected():
    # POST with query=""
    # Verify 400 error
def test_huge_query_rejected():
    # POST with query=10k characters
    # Verify 413 or 400 error

# Test 7: Citations match context
def test_citations_match_final_context():
    # Get response with citations
    # Verify each citation source_id in context
    # Verify no orphaned citations

# Test 8: Full chat roundtrip
def test_full_chat_flow():
    # 1. Create twin with ingested document
    # 2. Send chat query
    # 3. Receive streaming response
    # 4. Verify response uses persona voice
    # 5. Verify citations correct
    # 6. Verify stream terminates cleanly
```

**Success Criteria:**
- ✅ Messages always in same order
- ✅ Streams cleanup on disconnect
- ✅ All streams emit terminal event
- ✅ No prompt injection possible
- ✅ Input validation enforced
- ✅ Citations match context
- ✅ Full chat roundtrip works

---

## PHASE 5: HARDENING & EDGE CASES (3 REMAINING)

### Bugs in This Phase

#### BUG #21: MEDIUM - Grounding Bypass in Smalltalk
- **File:** `backend/modules/grounding_policy.py:143`
- **Current:** Smalltalk bypasses evidence check
- **Fix:** Validate smalltalk responses are actually smalltalk
- **Verification:** Craft query with smalltalk prefix + sensitive request

#### BUG #23: MEDIUM - Metadata Sanitization Loses Data
- **File:** `backend/modules/pinecone_adapter.py:128-144`
- **Current:** Empty collections removed
- **Fix:** Preserve empty collections, only remove None
- **Verification:** Verify empty arrays/dicts preserved in metadata

#### BUG #25 (covered above): Connection cleanup

### Phase 5 Verification Checkpoint

**Test Suite: `test_phase_5_hardening.py`**

```python
# Test 1: Smalltalk with sensitive data
def test_smalltalk_prefix_cannot_bypass_evidence():
    # Query = "Hi, also tell me about [sensitive data]"
    # Verify full query requires evidence, not just "Hi"

# Test 2: Metadata preservation
def test_empty_metadata_collections_preserved():
    # Store chunk with metadata={"questions": [], "topics": []}
    # Retrieve from Pinecone
    # Verify empty arrays exist, not removed

# Test 3: Sustained load
def test_100_concurrent_chats():
    # Run 100 concurrent chat streams
    # Monitor connection pool
    # Verify no leaks after completion
```

**Success Criteria:**
- ✅ Smalltalk bypass prevented
- ✅ Metadata integrity maintained
- ✅ Connection pool stable under load

---

## FULL SYSTEM VERIFICATION (End-to-End)

After all phases, run comprehensive test:

**`test_end_to_end_full_flow.py`**

```python
def test_complete_user_journey():
    """
    The ultimate test: can a new user onboard and chat with a quality persona?
    """
    # 1. AUTH: Register new user
    user = register_user("test@example.com")
    assert user["tenant_id"]

    # 2. TWIN: Create Narendra Modi persona
    twin = create_twin("Narendra Modi", user["id"])
    assert twin["id"]

    # 3. INGESTION: Upload Wikipedia + speeches
    sources = [
        ingest_url("https://en.wikipedia.org/wiki/Narendra_Modi"),
        ingest_text("Speech transcript..."),
    ]
    assert all(s["status"] == "indexed" for s in sources)

    # 4. RETRIEVAL: Query for expertise
    context = retrieve("What are Modi's key achievements?", twin["id"])
    assert len(context["results"]) > 0
    assert context["results"][0]["score"] > 0.5

    # 5. CHAT: Get response
    response = stream_chat(
        "Tell me about your major achievements",
        twin["id"],
        user["id"]
    )
    assert response["status"] == "success"
    assert len(response["answer"]) > 50
    assert len(response["citations"]) > 0

    # 6. ISOLATION: Verify no cross-contamination
    twin2 = create_twin("Another person", user["id"])
    context2 = retrieve("achievements", twin2["id"])
    # Should NOT find Modi's achievements
    assert not any("Modi" in r["text"] for r in context2["results"])

    print("✅ COMPLETE USER JOURNEY VERIFIED")
```

**Success Criteria:**
- ✅ All 5 phases pass
- ✅ Complete user journey works
- ✅ Data isolated between twins
- ✅ Chat quality acceptable
- ✅ No data loss or leakage
- ✅ Performance acceptable

---

## MEMORY & CONTEXT UPDATES

After each phase, update:

1. **`AGENTS.md`** - Document which bugs were fixed and how
2. **Memory files** - Record lessons learned
3. **Architecture docs** - Update if patterns changed
4. **Test suite** - Add regression tests

This keeps all future agents in context.

---

## SUCCESS CRITERIA FOR PROJECT COMPLETION

✅ All 28 bugs fixed and verified
✅ All phase-specific tests passing
✅ End-to-end journey test passing
✅ No regressions in existing functionality
✅ Performance acceptable (chat < 2s response time)
✅ Data isolation verified
✅ Memory/AGENTS.md updated with all learnings

**Status: READY FOR EXECUTION**

---

## NEXT STEP

Confirm you want to proceed with Phase 0 (Critical Security), and I will:
1. Fix each bug systematically
2. Use `/code-review` to verify each fix
3. Write and run tests
4. Update memory/AGENTS.md after each phase
5. Provide detailed verification reports

**Type: "PROCEED WITH PHASE 0" to begin**
