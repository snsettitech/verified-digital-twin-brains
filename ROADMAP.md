# Roadmap: Verified Digital Twin Brain → Delphi-Grade Upgrade

*Checkpoint system active: Phase completions are automatically tagged and released.*

This roadmap outlines the evolution from a grounded Q&A engine to a **Delphi-grade** digital twin platform with enterprise trust, operational control, and scalable distribution.

**Status Legend:**
- `[x]` = Fully implemented
- `[~]` = Partially implemented (needs upgrade)
- `[ ]` = Not implemented

---

## Baseline: Completed Phases (Strong Foundation)

### Phase 1 (MVP) - Grounded Answers
**Status: Completed**

- [x] Multi-tenant database schema (Supabase).
- [x] Document ingestion pipeline (PDF extraction -> Chunking -> OpenAI Embeddings -> Pinecone).
- [x] RAG-based chat API with citation support.
- [x] Confidence-based escalation logic.
- [x] Basic Next.js dashboard and chat interface.

---

### Phase 2 - Cloud Agents & Verified Memory
**Status: Completed**

The goal is to move from a local Q&A script to a **live, agentic cloud brain** that can reason and verify knowledge.

- [x] **Cloud Migration readiness**: Added `Procfile` and `railway.json` for cloud deployment.
- [x] **Agentic Reasoning Loop**: Transitioned from static RAG to a dynamic LangGraph reasoning loop.
- [x] **Verified Memory Injection**: Implemented logic to turn owner's manual responses into high-priority vector embeddings.
- [x] **Early Tool Framework**: Established `modules/tools.py` architecture for future cloud tool expansion.
- [x] **Advanced Reranking**: Implement a re-ranking layer (Cohere/BGE) to improve retrieval precision.
- [x] **Owner Escalation Inbox**: UI for owners to view and resolve low-confidence questions.
- [x] **Twin Personalization**: System instructions and basic persona configuration.

---

### Phase 3 - Digital Persona & Multi-Modal Mind
**Status: Completed**

Moving from a basic RAG bot to a high-fidelity digital mind that clones the owner's knowledge and style.

- [x] **HyDE & Query Expansion**: Generate hypothetical answers to improve vector search depth.
- [x] **Context Enrichment**: Ingest documents with hypothetical questions and opinion/fact metadata tags.
- [x] **Multi-Modal Ingestion**: Scrapers for YouTube transcripts, Podcast audio (Whisper), and Social Media (Twitter/X threads).
- [x] **Persona Encoding**: Analysis of owner's writing style, common phrases, and opinion vectors for high-fidelity responses.

---

## Delphi-Grade Upgrade Phases

### Phase 4: Verified-First Knowledge Layer
**Status: Completed ✅** | **Effort: Medium** | **Priority: High**

**Goal:** Make "verified" deterministic and stable. Prevent repeat hallucinations after an owner correction.

**Current State:**
- [x] Verified answers stored as high-priority vectors in Pinecone (`inject_verified_memory`)
- [x] Retrieval prioritizes verified results and is enforced in orchestrator
- [x] Escalation workflow exists with canonical answer storage

**Implementation Summary:**
- [x] Postgres tables: `verified_qna`, `answer_patches`, `citations` ✅
- [x] Retrieval order enforced in Orchestrator: 1) Verified QnA match, 2) Vector retrieval, 3) Tool calls ✅
- [x] Owner workflow: Approve escalation → publish to `verified_qna`, Edit answer → creates patch version ✅
- [x] Response policy: "I don't know" when no verified/strong retrieval, routes to inbox ✅
- [x] Optional "general knowledge allowed" toggle per tenant (implemented in agent system prompt) ✅

**Exit Criteria:**
- [x] A question corrected once never regresses in future sessions ✅
- [x] Verified answers can be served with minimal citations UI noise, but retain provenance in logs ✅

**Risk Assessment:**
- **Low Risk**: Building on existing escalation workflow
- **Migration Path**: Existing verified vectors can be migrated to `verified_qna` table
- **Dependency**: Requires orchestrator refactor to enforce retrieval order

---

### Phase 5: Access Groups as First-Class Primitive
**Status: Completed ✅** | **Effort: Large** | **Priority: High**

**Goal:** Delphi-style segmentation. Different audiences see different knowledge, limits, tone, and allowed actions.

**Current State:**
- [x] Full access group system implemented
- [x] Multi-group knowledge base per twin with content permissions
- [x] Complete audience segmentation with group-level controls

**Gap Analysis:**
- [x] All tables implemented: `access_groups`, `group_memberships`, `content_permissions`, `group_limits`, `group_overrides`
- [x] Enforcement points in retriever for group permissions
- [x] Full UI for creating/managing groups
- [x] Group-level limits and overrides implemented

**Deliverables:**
- [x] Postgres tables: `access_groups`, `group_memberships`, `content_permissions`, `group_limits`, `group_overrides` ✅
- [x] Enforcement points: Retriever filters context by group permissions, Verified QnA filters by group, Tool access scoped by group ✅
- [x] UI: Create group, assign content, assign members, simulate group conversation in console ✅

**Exit Criteria:**
- [x] Same question asked by two groups produces different allowed answers based on configured permissions ✅
- [x] Group limits are configured per group and visible in admin UI ✅

**Risk Assessment:**
- **Medium Risk**: Requires significant refactoring of retrieval and agent logic
- **Migration Path**: Default "public" group for existing twins
- **Dependency**: Should follow Phase 4 (verified QnA) for content permission model

---

### Phase 6: Mind Ops Layer (Content Loading Dock + Training State Machine)
**Status: Completed ✅** | **Effort: Large** | **Priority: Medium**

**Goal:** Operational reliability. Scale ingestion without corrupting the brain with low-quality content.

**Current State:**
- [x] Staging dock (`staging_status`) for sources
- [x] Training jobs queue and state machine
- [x] Content health checks (duplicates, empty, etc.)
- [x] Bulk metadata management
- [x] Ingestion observability logs

**Implementation Summary:**
- [x] Content loading dock: Staged sources with metadata before indexing/training ✅
- [x] Training jobs: `training_jobs` table and background worker logic ✅
- [x] Health checks: Duplicate detection, empty extraction verification ✅
- [x] Bulk actions: Metadata updates and approval workflows ✅
- [x] Observability: Detailed ingestion logs per source ✅

**Deliverables:**
- [x] Content loading dock: Staged sources with metadata before indexing/training ✅
- [x] Bulk actions: Assign access group, set visibility, bulk approve ✅
- [x] Training jobs: `training_jobs` table and state machine logic ✅
- [x] Content health checks: Duplicate detection, empty extraction, chunk anomalies ✅
- [x] Metadata hygiene: Citation URL, publish date tracking ✅
- [x] Observability: Ingestion logs per source available in UI ✅

**Exit Criteria:**
- [x] Every source has a visible lifecycle and health status ✅
- [x] Ingestion failures are diagnosable via ingestion logs ✅
- [x] Content audit available via staging view ✅

**Risk Assessment:**
- **Medium Risk**: Requires new worker infrastructure and job queue
- **Migration Path**: Existing sources can be backfilled with health status
- **Dependency**: Can be built in parallel with Phase 4/5

---

### Phase 7: Omnichannel Distribution (Embed Widget + Share Link)
**Status: Completed ✅** | **Effort: Medium** | **Priority: High**

**Goal:** Delphi-style distribution while keeping trust boundaries intact.

**Current State:**
- [x] Production-ready widget with standalone `widget.js`
- [x] Full API key system with domain allowlists
- [x] Public share links with token validation
- [x] Session model for anonymous/authenticated users
- [x] Complete UI for all distribution features

**Implementation Summary:**
- [x] API Keys: Creation, revocation, domain allowlists, usage tracking ✅
- [x] Share Links: Token generation, public sharing toggle, validation ✅
- [x] Sessions: Anonymous session creation, activity tracking, expiration ✅
- [x] Rate Limiting: Sliding window rate limiting per session/API key ✅
- [x] User Management: Invitation workflow, role management ✅

**Deliverables:**
- [x] Embeddable web widget: Domain allow-list, API keys scoped to tenant and group, rate limiting ✅
- [x] Shareable twin links: Public share page with chat interface, token validation ✅
- [x] Session model: Anonymous sessions for public, authenticated sessions for private ✅
- [x] User invitations: Generate invitation links with manual sharing (email integration optional) ✅
- [x] Premium UI: Delphi-inspired dark sidebar, gradient hero sections, modern components ✅

**Exit Criteria:**
- [x] A creator can embed the twin on a website with restricted domains ✅
- [x] Public users can only access explicitly public content, never private sources ✅
- [x] Share links allow anonymous chat with validated tokens ✅

**Risk Assessment:**
- **Low Risk**: Building on existing widget component
- **Migration Path**: Existing widget can be upgraded incrementally
- **Dependency**: Requires Phase 5 (Access Groups) for public/private content separation

---

### Phase 8: Actions Engine (Trigger → Plan → Draft → Approve → Execute)
**Status: Research & Development** | **Effort: Large** | **Priority: Medium**

**Goal:** Move from Q&A to outcomes, while preserving accountability.

**Current State:**
- [~] Tool framework exists (`modules/tools.py`)
- [~] Basic Composio integration scaffold
- [ ] No event model or triggers
- [ ] No draft/approve/execute pipeline
- [ ] No action execution logs

**Gap Analysis:**
- Missing `events` table for tracking (message_received, answer_sent, escalation_created, idle_timeout)
- No `action_triggers` with conditions (intent, keywords, confidence, channel, group)
- No draft-only mode or approval workflow
- No execution logs with tool inputs/outputs
- No tool connectors v1 (Gmail read, Calendar read, Draft email/event creation)

**Deliverables:**
- [ ] Event model: `events` table (message_received, answer_sent, escalation_created, idle_timeout)
- [ ] Triggers and rules: `action_triggers` with conditions (intent, keywords, confidence, channel, group)
- [ ] Action execution pipeline: Draft-only mode by default, approvals required for write actions, execution logs include tool inputs and outputs
- [ ] Tool connectors v1: Gmail read, Calendar read, Draft email and draft event creation, No autonomous writes without explicit approval

**Exit Criteria:**
- A user request can produce a draft action, route for approval, then execute with full audit trail
- You can replay an action decision with complete context and provenance

**Risk Assessment:**
- **High Risk**: Complex integration with external tools, requires careful security model
- **Migration Path**: Can start with read-only tools, add write actions incrementally
- **Dependency**: Requires Phase 5 (Access Groups) for group-scoped tool access

---

### Phase 9: Verification & Governance (Trust Layer)
**Status: Completed ✅** | **Effort: Medium** | **Priority: High**

**Goal:** Delphi-grade trust posture. Verified identity, consent controls, and immutable auditability.

**Current State:**
- [x] Identity verification workflow with status tracking ✅
- [x] Immutable audit log with centralized logger ✅
- [x] Consent and deletion workflows (deep scrub) ✅
- [x] Safety guardrails with prompt injection defense ✅

**Implementation Summary:**
- [x] Database: `audit_logs`, `governance_policies`, `twin_verification` tables ✅
- [x] AuditLogger: Centralized logging for all critical system events ✅
- [x] GuardrailEngine: Prompt injection detection, refusal rules enforcement ✅
- [x] Deep Scrub: Permanent deletion from database AND vector index ✅
- [x] Governance Portal: Full UI for audit trails, policies, and verification ✅

**Deliverables:**
- [x] Identity verification workflow: Owner verification steps, verification status and badge logic ✅
- [x] Consent and deletion workflows: Deep scrub removes raw content and vectors ✅
- [x] Immutable audit log: Append-only event store with metadata ✅
- [x] Policy enforcement: Refusal rules per group, prompt injection defenses ✅

**Exit Criteria:**
- [x] You can prove who approved what, when, and why ✅
- [x] Deletion requests remove raw content and vectors, and stop future use ✅

**Risk Assessment:**
- **Medium Risk**: Requires careful data retention and deletion logic
- **Migration Path**: Existing escalations can be backfilled into audit log
- **Dependency**: Requires Phase 5 (Access Groups) for group-level policies


---

### Phase 10: Enterprise Scale & Reliability
**Status: Vision** | **Effort: Large** | **Priority: Low (for MVP)**

**Goal:** High availability, cost controls, and operations readiness.

**Current State:**
- [~] Basic health check endpoint exists
- [ ] No comprehensive observability
- [ ] No cost controls or quotas
- [ ] No background job queue
- [ ] No autoscaling or disaster recovery

**Gap Analysis:**
- Missing observability (metrics: retrieval latency, answer latency, tool latency, token usage, escalations; tracing across components)
- No cost controls (quotas per tenant and group, caching where safe, batching for embeddings and reranking)
- No deployment hardening (background job queue, worker autoscaling, backups, disaster recovery runbook)

**Deliverables:**
- [ ] Observability: Metrics (retrieval latency, answer latency, tool latency, token usage, escalations), tracing across Orchestrator, retrieval, tools, workers
- [ ] Cost controls: Quotas per tenant and group, caching where safe, batching for embeddings and reranking
- [ ] Deployment hardening: Background job queue (Redis, SQS, or equivalent), worker autoscaling, backups, disaster recovery runbook

**Exit Criteria:**
- System continues operating under partial failures
- You can onboard multiple creators with predictable costs and stable performance

**Risk Assessment:**
- **Low Risk**: Can be built incrementally as scale demands
- **Migration Path**: Existing system can be instrumented first, then optimized
- **Dependency**: Should follow all core feature phases

---

## Quick Wins (High Impact, Low Effort)

These can be implemented quickly to improve the platform:

1. **Enhanced Health Check** (Phase 10, partial)
   - Add detailed service status (Pinecone, OpenAI, Supabase connectivity)
   - Add basic metrics endpoint (request count, average latency)
   - **Effort: Small** | **Impact: Medium**

2. **Basic Content Health Checks** (Phase 6, partial)
   - Add duplicate detection via content hash during ingestion
   - Add empty extraction detection
   - **Effort: Small** | **Impact: Medium**

3. **Improved Escalation UI** (Phase 4, partial)
   - Add "Approve as Verified Answer" button directly in escalation inbox
   - Pre-populate verified QnA form with escalation context
   - **Effort: Small** | **Impact: High**

4. **Widget Domain Allowlist** (Phase 7, partial)
   - Add simple domain validation in widget API endpoint
   - Store allowed domains in twin settings
   - **Effort: Small** | **Impact: Medium**

5. **Basic Audit Log** (Phase 9, partial)
   - Add `audit_events` table with basic event logging
   - Log all escalations, verified answer approvals, source deletions
   - **Effort: Small** | **Impact: High**

---

## Implementation Priority Matrix

### Immediate Next Steps (Strict Priority Order)

1. **Phase 4: Verified-First Knowledge Layer** ⭐
   - **Why First**: Prevents regression, foundation for all other phases
   - **Blocks**: Phase 5 (Access Groups needs verified QnA for permissions)
   - **Quick Win**: Enhanced escalation UI can be done in parallel

2. **Phase 5: Access Groups** ✅ **COMPLETED**
   - **Why Second**: Enables B2B use cases, required for Phase 7 (Omnichannel)
   - **Status**: All deliverables completed - full access group system with permissions, limits, and UI
   - **Blocks**: Phase 7 (Public/private content separation) - now unblocked
   - **Dependencies**: Phase 4 (verified QnA for content permissions) - completed

3. **Phase 7: Omnichannel Distribution** ✅ **COMPLETED**
   - **Status**: All deliverables completed - widget, share links, API keys, sessions, user management
   - **Dependencies**: Phase 5 (Access Groups for public/private) - completed
   - **Exit Criteria**: All met - widget embedding, share links, domain restrictions working

4. **Phase 6: Mind Ops Layer** ✅ **COMPLETED**
   - **Status**: All deliverables completed - loading dock, training jobs, health checks, logs
   - **Exit Criteria**: All met - operational visibility and control over content ingestion working

5. **Phase 9: Verification & Governance**
   - **Why Fifth**: Trust posture, required before scale
   - **Dependencies**: Phase 5 (Access Groups for group policies)
   - **Quick Win**: Basic audit log can be done first

6. **Phase 8: Actions Engine**
   - **Why Sixth**: Complex, requires solid foundation
   - **Dependencies**: Phase 5 (Access Groups for tool access scoping)
   - **Can Start**: Read-only tool connectors can begin early

7. **Phase 10: Enterprise Scale**
   - **Why Last**: Only needed at scale
   - **Dependencies**: All core features should be stable first
   - **Can Start**: Observability can be added incrementally

---

## Gap Analysis Summary

| Feature | Current State | Delphi-Grade State | Gap | Phase |
|---------|--------------|-------------------|-----|-------|
| Verified Answers | Vectors in Pinecone | Postgres `verified_qna` table | Canonical storage, versioning | Phase 4 |
| Access Groups | Full segmentation system | Full segmentation system | ✅ Completed | Phase 5 ✅ |
| Content Staging | Staging dock + health checks | Staging dock + health checks | ✅ Completed | Phase 6 ✅ |
| Embed Widget | Production-ready with allowlists | Production-ready with allowlists | ✅ Completed | Phase 7 ✅ |
| Actions Engine | Tool framework | Draft → Approve → Execute | Event model, triggers, approval workflow | Phase 8 |
| Identity Verification | Basic JWT | Full verification workflow | Verification steps, badges | Phase 9 |
| Audit Log | None | Immutable append-only | Event store, WORM storage | Phase 9 |
| Observability | Basic health check | Full metrics + tracing | Metrics, tracing, cost controls | Phase 10 |

---

## Release Strategy

Every phase ships with:
- ✅ A demo script
- ✅ A rollback plan
- ✅ Test coverage for tenant isolation and group permissions
- ✅ Instrumentation for usage and failure modes

---

## Notes

- **Phase 1-3**: Strong foundation completed ✅
- **Phase 4-10**: Delphi-grade upgrade path
- **Quick Wins**: Can be implemented in parallel with main phases
- **Priority Order**: Based on dependencies and user value
- **Risk Mitigation**: Each phase includes migration paths for existing data
