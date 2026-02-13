# One-User Pilot Checklist

Use this checklist to validate owner-training and public-chat separation before sharing with a pilot user.

## 1) Environment

- `ENABLE_REALTIME_INGESTION=true`
- `ENABLE_DELPHI_RETRIEVAL=true`
- `ENABLE_ENHANCED_INGESTION=false` (unless already validated in your environment)
- `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME` set

## 2) Database and Migrations

Run backend migrations before pilot:

```powershell
cd backend
# Use your normal migration command/path
```

Verify tables used by the adaptive flow exist:

- `owner_beliefs`
- `clarification_threads`
- `verified_qna`
- `twin_verifications`
- `conversations`
- `messages`

## 3) Pre-Pilot Smoke Tests (Owner)

1. Create a twin and upload at least one source.
2. Confirm ingestion job reaches completed state from `/ingestion-jobs`.
3. Start training chat (`owner_training` context) and ask owner-specific stance questions.
4. Resolve one clarification and verify memory write appears in `/twins/{twin_id}/owner-memory`.
5. Submit one owner correction via `/twins/{twin_id}/owner-corrections`.
6. Re-ask the same question and verify improved/consistent answer.

## 4) Pre-Pilot Smoke Tests (Public)

1. Open widget/public-share chat.
2. Ask owner-specific question without prior owner memory.
3. Verify response queues clarification for owner (no direct memory mutation).
4. Ask factual query with available sources and verify citations are returned.
5. Ask out-of-coverage question and verify uncertainty text:
   - `I don't know based on available sources.`

## 5) Retrieval Quality Check

1. Add one owner correction for a known question.
2. Ask the same question again.
3. Verify owner-approved memory is used before generic vector fallback.

## 6) Rollback Levers

- Disable real-time ingestion quickly with:
  - `ENABLE_REALTIME_INGESTION=false`
- Keep core chat online while debugging retrieval:
  - `RERANK_PROVIDER=none` (temporary fallback)
- If adaptive behavior must be minimized:
  - stop using training sessions while preserving regular owner chat

