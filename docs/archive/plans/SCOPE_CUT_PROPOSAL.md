# Scope Cut Proposal

Last updated: 2026-02-04

Goal: remove or disable features not required for the critical path so the team can ship a reliable twin creation, ingestion, and public retrieval flow. No deletions yet; this is a proposal with evidence and mitigation plans.

**Proposed Cuts (Prioritized)**

1. Enhanced ingestion pipelines

Feature: `backend/routers/enhanced_ingestion.py` endpoints for website crawling, RSS, Twitter, LinkedIn, and ingestion pipelines.

Why it adds complexity today: introduces parallel ingestion path and duplicate `/ingest/youtube/{twin_id}`; adds extra background crawl logic and source status handling.

How removing/disabling helps: eliminates route shadowing and clarifies the single ingestion pipeline for sources, chunks, vectors, and graphs.

Risks and mitigation: users relying on RSS/social ingestion lose features. Mitigate with feature flag `ENABLE_ENHANCED_INGESTION` and staged removal after a deprecation period.

Evidence: no FE usage in `frontend/` for `/ingest/website`, `/ingest/rss`, `/ingest/twitter`, `/ingest/linkedin`, `/pipelines`.

2. Actions engine

Feature: action triggers, drafts, connectors, executions in `backend/routers/actions.py` and actions UI in `frontend/app/dashboard/actions/*`.

Why it adds complexity today: extra event emission paths in chat/public endpoints and several admin UIs increase state surface and failure modes.

How removing/disabling helps: public and owner chat are simpler, fewer branching pathways in retrieval, fewer tables to keep consistent.

Risks and mitigation: users lose automation workflows. Mitigate with a feature flag and defer until core ingestion and retrieval stabilize.

Evidence: not required for twin creation, ingestion, or public chat; actions endpoints are separate from core flows.

3. Governance and deep scrub

Feature: governance policies, audit logs, deep scrub endpoints in `backend/routers/governance.py` and UI in `frontend/app/dashboard/governance/page.tsx`.

Why it adds complexity today: multiple policy types, duplicate schema definitions, and cross-cutting data access checks.

How removing/disabling helps: reduces tenant-level and twin-level branching and schema duplication; narrows auth paths.

Risks and mitigation: compliance/audit features unavailable. Mitigate with feature flag and keep read-only logs if needed.

Evidence: not required for critical path; no dependencies in onboarding or public chat.

4. Metrics and analytics

Feature: metrics dashboards and events in `backend/routers/metrics.py` and UI in `frontend/app/dashboard/metrics`, `frontend/app/dashboard/insights`, `frontend/app/dashboard/page.tsx`.

Why it adds complexity today: separate data model, auth rules, and frequent polling; multiple request paths without auth.

How removing/disabling helps: reduces backend surface, removes several unauthenticated fetch calls, and avoids blocking core flow on metrics failures.

Risks and mitigation: loses analytics. Mitigate by keeping a minimal health counter or a single aggregated endpoint for internal use.

Evidence: routes are not required for ingestion or chat; several UI calls are unauthenticated.

5. Audio TTS settings

Feature: `/audio/tts`, `/audio/settings`, `/audio/voices` and related UI in `frontend/app/dashboard/settings/page.tsx`.

Why it adds complexity today: additional dependency on external TTS service, more settings state to manage.

How removing/disabling helps: focuses on text-only retrieval until core path is reliable.

Risks and mitigation: users lose TTS. Mitigate by gating via feature flag and reintroduce after core stability.

Evidence: not used in critical path.

6. Cognitive interview and realtime interview APIs

Feature: `/cognitive/interview`, `/api/interview/*` and UI in `frontend/components/Chat/InterviewInterface.tsx`, `frontend/lib/hooks/useRealtimeInterview.ts`.

Why it adds complexity today: introduces parallel memory collection pipeline and additional realtime infra.

How removing/disabling helps: avoids competing ingestion of knowledge and reduces session management complexity.

Risks and mitigation: interview-based twin creation not available. Mitigate via hidden beta or separate branch.

Evidence: not required for basic twin creation + ingestion + public chat.
7. Escalations and verified QnA management UI

Feature: escalations endpoints in `backend/routers/escalations.py` and UI in `frontend/app/dashboard/escalations/page.tsx`, verified QnA UI in `frontend/app/dashboard/verified-qna/page.tsx`.

Why it adds complexity today: adds moderation workflow and QnA patching that are not required for basic ingestion and retrieval.

How removing/disabling helps: simplifies retrieval path to rely on ingested sources only.

Risks and mitigation: loss of escalation workflow. Mitigate by gating behind a feature flag and keeping backend tables intact.

Evidence: not required for creating a twin or performing public chat; no dependency in onboarding or ingestion.

8. Access groups management UI

Feature: access group CRUD, permissions, limits, overrides in `backend/routers/twins.py` and UI under `frontend/app/dashboard/access-groups/*`.

Why it adds complexity today: twin scoping, permissions, and limits add multiple branching paths and require more data integrity checks.

How removing/disabling helps: simplifies public retrieval to a default group and reduces scope-related FE/BE drift.

Risks and mitigation: loss of group-based access control. Mitigate by keeping default group auto-managed and add feature flag for UI.

Evidence: access-group endpoints are not required for ingestion or core chat; FE currently calls wrong paths, adding drift risk.

9. Reasoning engine

Feature: `/reason/predict/{twin_id}` and reasoning logic in `backend/routers/reasoning.py` and `backend/routers/chat.py`.

Why it adds complexity today: adds separate model inference path and failure modes.

How removing/disabling helps: reduces uncertainty in retrieval and simplifies chat response construction.

Risks and mitigation: loss of reasoning-based stance explanations. Mitigate with feature flag and reintroduce after core path stabilizes.

Evidence: no FE usage of `/reason/predict`.

10. Debug retrieval endpoints

Feature: `/debug/retrieval` in `backend/routers/debug_retrieval.py` and `frontend/components/console/tabs/ChatTab.tsx`.

Why it adds complexity today: separate code path with relaxed auth assumptions and manual debug UI.

How removing/disabling helps: removes security risk and reduces maintenance surface.

Risks and mitigation: loss of debugging UX. Mitigate by keeping internal-only tooling or CLI scripts.

Evidence: FE calls without auth; not needed for production critical path.

11. TIL and memory events UI

Feature: `/twins/{twin_id}/til` and memory event routes in `backend/routers/til.py` and UI in `frontend/components/TILFeed.tsx`.

Why it adds complexity today: separate event stream, confirm/delete operations, and additional data models.

How removing/disabling helps: reduces maintenance and avoids FE/BE mismatch on node ids.

Risks and mitigation: loss of TIL feed. Mitigate with feature flag or delayed reintroduction.

Evidence: not required for ingestion or public chat.

**Execution Note**

No deletions or refactors should occur until the critical path contracts and drift issues are resolved. These cuts are proposed for a later, staged removal with feature flags.
