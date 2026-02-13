# Forensic Audit Issue Backlog

Source:
- `FORENSIC_AUDIT_REPORT.md` section `8.2 GitHub Issues Backlog` (dated 2026-02-12)
- Owner-adaptive assistant upgrade planning and forensic code evidence (2026-02-12)

This folder converts the high-level backlog into implementation-ready issue specs.

## Issue Index

| ID | Priority | Title | Area | Status | File |
| --- | --- | --- | --- | --- | --- |
| ISSUE-001 | P0 | Rename "Training" to "Knowledge Ingestion" throughout product | Frontend + API terminology | Completed | `docs/audit/issues/ISSUE-001-rename-training-to-ingestion.md` |
| ISSUE-002 | P0 | Add real verification gate before publish | Backend verification + Publish UX | Completed | `docs/audit/issues/ISSUE-002-add-real-verification-before-publish.md` |
| ISSUE-003 | P1 | Enable stable features by default | Backend configuration | Completed | `docs/audit/issues/ISSUE-003-enable-stable-features-by-default.md` |
| ISSUE-004 | P1 | Remove or implement stubbed dashboard pages | Frontend IA and routing | Completed | `docs/audit/issues/ISSUE-004-resolve-stubbed-dashboard-pages.md` |
| ISSUE-005 | P1 | Add citations display to chat UI | Frontend chat trust UX | Completed | `docs/audit/issues/ISSUE-005-add-chat-citation-display.md` |
| ISSUE-006 | P0 | Enforce owner/public mode in identity gate and chat policy | Backend behavior gating | Completed | `docs/audit/issues/ISSUE-006-enforce-owner-public-mode-in-identity-gate.md` |
| ISSUE-007 | P0 | Standardize uncertainty response to "I don't know based on available sources" | Backend response policy | Completed | `docs/audit/issues/ISSUE-007-standardize-uncertainty-response.md` |
| ISSUE-008 | P0 | Capture owner corrections as structured knowledge candidates | Backend + frontend learning UX | Completed | `docs/audit/issues/ISSUE-008-capture-owner-corrections-as-knowledge-candidates.md` |
| ISSUE-009 | P0 | Prioritize owner-approved knowledge in retrieval | Retrieval ranking and grounding | Completed | `docs/audit/issues/ISSUE-009-prioritize-owner-approved-knowledge.md` |
| ISSUE-010 | P0 | Harden feedback endpoint and learning job triggers | API security + data integrity | Completed | `docs/audit/issues/ISSUE-010-harden-feedback-endpoint.md` |
| ISSUE-011 | P1 | Fix escalation to verified QnA contract mismatch | Backend correctness | Completed | `docs/audit/issues/ISSUE-011-fix-escalation-verified-qna-contract.md` |
| ISSUE-012 | P1 | Complete teaching UX wiring in chat surfaces | Frontend adaptive UX | Completed | `docs/audit/issues/ISSUE-012-complete-teaching-ux-wiring.md` |
| ISSUE-013 | P1 | Add adaptive behavior regression suite | Test coverage and release safety | Completed | `docs/audit/issues/ISSUE-013-add-adaptive-behavior-regression-suite.md` |

## Usage

1. Create a GitHub issue from each file (copy title, context, checklist, AC).
2. Keep the checklist and status in sync with PRs.
3. Link PRs back to the issue file path for traceability.
