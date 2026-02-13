# ISSUE-007: [P0] Standardize Uncertainty Response to "I don't know based on available sources"

## Metadata

- Priority: `P0`
- Type: `Response policy / trust UX`
- Source: owner-adaptive assistant upgrade objective
- Suggested labels: `backend`, `chat`, `trust`, `priority:P0`
- Status: `Completed`

## Problem Statement

Uncertainty fallback copy is inconsistent across chat surfaces and persona auditing, while the target behavior requires a clear and explicit uncertainty statement grounded in available sources.

## Why This Matters

- Consistent uncertainty language is central to anti-hallucination trust.
- Inconsistent fallbacks make behavior appear random and reduce confidence.
- Product requirement explicitly mandates a standard uncertainty phrase.

## Evidence

- `backend/routers/chat.py:596`
- `backend/routers/chat.py:1039`
- `backend/routers/chat.py:1269`
- `backend/modules/persona_auditor.py:103`
- `backend/modules/persona_auditor.py:106`

## Scope

In scope:

- Define one canonical uncertainty message constant:
  - `I don't know based on available sources.`
- Use it across owner chat, widget chat, public share chat, and audit fallback.
- Add optional owner-only teaching guidance sentence after canonical message.

Out of scope:

- Retrieval algorithm redesign.
- New personalization model behavior.

## Implementation Checklist

- [x] Create a shared uncertainty constant in one backend module.
- [x] Replace hardcoded fallback strings in chat routes and persona auditor.
- [x] Ensure message appears only when evidence threshold is not met.
- [x] Add tests for fallback behavior by route/context.

## Acceptance Criteria

- [x] All uncertainty fallbacks include exact phrase: `I don't know based on available sources.`
- [x] No conflicting fallback copy remains in chat and persona audit paths.
- [x] Owner/public/widget routes all pass uncertainty copy tests.

## Verification Plan

- [x] `rg -n "I don't have this specific information in my knowledge base|I do not have enough verified evidence" backend`
- [x] Route tests for `/chat/{twin_id}`, `/widget/{twin_id}/chat`, and `/public/chat/{twin_id}/{token}`.
- [x] Manual check that uncertainty appears only when retrieval evidence is absent/insufficient.

## Risks and Mitigations

- Risk: Overly rigid copy in contexts where clarification is better.
  Mitigation: Keep clarification path separate; use canonical copy only for uncertainty-final responses.
- Risk: Legacy client snapshots expecting old text.
  Mitigation: Version changelog and client-side snapshot updates.

