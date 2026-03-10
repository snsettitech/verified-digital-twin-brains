# Simplification Changelog

Date: 2026-02-04
Scope: Phase 5 scope cuts and de-duplication (post-proof).

**Applied Simplifications**

1. Enhanced ingestion routes gated by default
- Change: `ENABLE_ENHANCED_INGESTION=false` keeps `backend/routers/enhanced_ingestion.py` disabled.
- Why: avoids duplicate `/ingest/youtube/{twin_id}` and parallel ingestion pipelines.
- Risk: Enhanced sources (RSS/social) unavailable unless explicitly enabled.
- Mitigation: Feature flag can be turned on per env without code changes.

2. Dashboard navigation trimmed to critical path
- Change: removed sidebar links for Interview Mode, Right Brain, Verified Q&A, Escalations, Actions Hub, Access Groups, Governance.
- Why: these modules are not required for create twin ? ingest ? public share chat.
- Risk: direct URLs still accessible but not discoverable in nav.
- Mitigation: endpoints and pages remain intact; can re-enable by restoring `frontend/lib/navigation/config.ts` entries.

**Deferred (not removed)**

- Backend routers for actions, governance, metrics, interview, and verified Q&A remain intact to avoid breaking existing integrations.
- Share page placeholders (`/dashboard/share`) remain but are hidden from navigation.

**Notes**

- No destructive deletions were performed. This change only reduces UI surface area and route ambiguity.
