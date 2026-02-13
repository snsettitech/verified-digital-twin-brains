# ISSUE-009: [P0] Prioritize Owner-Approved Knowledge in Retrieval

## Metadata

- Priority: `P0`
- Type: `Retrieval policy / ranking`
- Source: owner-adaptive assistant upgrade objective
- Suggested labels: `backend`, `retrieval`, `priority:P0`
- Status: `Completed`

## Problem Statement

Retrieval is verified-first, then vector search, but owner memory artifacts and approved corrections are not consistently prioritized as authoritative across all answer paths.

## Why This Matters

- Owner-approved answers must override ambiguous retrieved snippets.
- Priority ordering is required to make conversational teaching visibly effective.
- Without deterministic precedence, system may regress to generic RAG behavior.

## Evidence

- `backend/modules/retrieval.py:566`
- `backend/modules/retrieval.py:588`
- `backend/modules/retrieval.py:598`
- `backend/modules/identity_gate.py:168`
- `backend/modules/identity_gate.py:232`
- `backend/modules/owner_memory_store.py:228`

## Scope

In scope:

- Define authoritative retrieval order:
  - approved owner correction memory / promoted verified answer
  - verified QnA
  - vector retrieval results
- Ensure conflict handling uses recency + confidence + status.
- Return source metadata so UI can explain why an answer was selected.

Out of scope:

- Replacing Pinecone or graph storage.
- Adding external ranking services.

## Implementation Checklist

- [x] Add retrieval step for approved owner correction artifacts before vector fallback.
- [x] Normalize promotion path from approved correction to retrieval-accessible format.
- [x] Implement deterministic tie-break rules for conflicting approved records.
- [x] Include source provenance (`owner_memory`, `verified_qna`, `vector`) in metadata.
- [x] Add integration tests for precedence and conflict scenarios.

## Acceptance Criteria

- [x] When an approved owner correction exists, it is selected before generic vector evidence.
- [x] Responses expose source type indicating owner-approved precedence.
- [x] Conflicting records follow deterministic tie-break behavior.

## Verification Plan

- [x] Seed twin with conflicting vector docs and one approved correction; verify answer uses approved record.
- [x] Verify metadata tags source as owner-approved path.
- [x] Test fallback to vector retrieval when no approved artifacts exist.

## Risks and Mitigations

- Risk: Over-prioritizing stale owner corrections.
  Mitigation: Apply recency windows and owner re-approval mechanics.
- Risk: Retrieval latency increase from extra lookup.
  Mitigation: Keep approved memory lookup indexed and bounded by timeout.

