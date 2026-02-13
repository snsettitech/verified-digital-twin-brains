# ISSUE-001: [P0] Rename "Training" to "Knowledge Ingestion" Throughout Product

## Metadata

- Priority: `P0`
- Type: `Product clarity / terminology`
- Source: `FORENSIC_AUDIT_REPORT.md` issue #1
- Suggested labels: `enhancement`, `ux`, `backend`, `frontend`, `priority:P0`
- Status: `Completed`

## Problem Statement

The product currently uses "Training" to describe both knowledge ingestion/indexing and interview workflows. This creates a trust gap because users interpret "training" as model learning or fine-tuning.

## Why This Matters

- Reduces user trust when behavior does not match "training" expectations.
- Creates support burden and onboarding confusion.
- Makes docs and API semantics harder to reason about.

## Evidence

- `frontend/app/dashboard/page.tsx:277`
- `frontend/app/page.tsx:344`
- `frontend/components/ingestion/UnifiedIngestion.tsx:455`
- `frontend/components/console/tabs/KnowledgeTab.tsx:410`
- `backend/modules/training_jobs.py`
- `backend/routers/training_sessions.py`
- `frontend/app/dashboard/training-jobs/page.tsx`

## Scope

In scope:

- User-facing copy changes: "Training" -> "Knowledge Ingestion" or "Indexing" where applicable.
- API naming transition plan for `/training-jobs` endpoint family.
- Docs updates for terminology.

Out of scope:

- Any new model fine-tuning capability.
- Changing interview feature names when "Interview" is the accurate term.

## Implementation Checklist

- [x] Run terminology audit across frontend/backend/docs.
- [x] Replace user-facing labels in UI where the feature is ingestion/indexing.
- [x] Add `/ingestion-jobs` endpoint aliases while keeping `/training-jobs` backward compatible.
- [x] Add deprecation note in API docs for legacy `/training-jobs` naming.
- [x] Update dashboard and onboarding copy to avoid implying model learning.
- [x] Update runbooks and architecture docs to reflect new terms.

## Acceptance Criteria (from audit report)

- [x] All user-facing "Training" labels changed to "Knowledge Ingestion" or "Indexing".
- [x] API endpoints remain backward-compatible (or versioned).
- [x] Documentation updated.

## Verification Plan

- [x] `rg -n "Train Your Twin|Training Jobs|/training-jobs" frontend docs backend`
- [x] Manually validate dashboard cards and ingestion flows.
- [x] Confirm existing clients calling `/training-jobs` continue to work.
- [x] Confirm docs consistently use updated terminology.

## Risks and Mitigations

- Risk: Breaking API consumers that use `/training-jobs`.
  Mitigation: Keep alias + deprecation window.
- Risk: Over-renaming true interview flows.
  Mitigation: Limit scope to ingestion/indexing semantics.

