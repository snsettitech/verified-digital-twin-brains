# Persona Consistency Phased Plan

## Goal
Deliver stable, high-fidelity "owner voice + decision behavior" per twin by shifting from single-prompt persona to user-trained, versioned persona specs, structured procedural policies, intent-aware retrieval, deterministic + model-based enforcement, and regression gating.

This plan maps directly to your requested upgrades:
1. Versioned persona spec + enforcement
2. Decision-trace capture (SJT, pairwise, introspection)
3. Intent-aware procedural persona retrieval
4. Constitution layer
5. APO and optional DPO
6. Persona regression suite
7. High-fidelity architecture end state
8. Explicit interaction-channel separation (owner training vs owner chat vs public share/widget)

## Current Repo Baseline (already available)
- Prompt/version foundation: `backend/modules/prompt_manager.py`
- Online judges foundation: `backend/eval/judges.py`
- Runtime prompt assembly: `backend/modules/agent.py` (`build_system_prompt`)
- Identity routing and memory gating: `backend/modules/identity_gate.py`
- Interview capture and extraction pipeline: `backend/routers/interview.py`, `backend/modules/memory_extractor.py`
- Existing eval harness and datasets: `backend/eval/runner.py`, `backend/eval/dataset.json`

## Execution Status + Proof Ledger
- Last updated: `2026-02-09`
- Status:
  - `Completed`: interaction-context foundation, owner training session lifecycle, strict mid-thread context reset guard.
  - `Completed`: Phase 0 architecture/ops contract docs (`PERSONA_PIPELINE_V1`, `PERSONA_QUALITY_GATE`, `INTERACTION_CONTEXT_V1`).
  - `Completed`: Phase 0 baseline eval-harness capture (current baseline recorded).
  - `Completed`: Phase 1 foundation (`persona_specs` schema/validator/compiler/APIs + runtime hook + migration).
  - `Completed`: Phase 2 foundation (`decision-capture` APIs + owner-training gating + trace persistence + module derivation + migration).
  - `Completed`: Phase 3 foundation (intent taxonomy + runtime intent classification + intent-scoped procedural module retrieval + traceable module IDs + retrieval index migration).
  - `Completed`: Phase 4 foundation (deterministic fingerprint gate + structure/voice judges + clause-targeted rewrite + persisted judge traces + migration).
  - `Completed`: Phase 5 Track A foundation (prompt variant search + regression optimizer + runtime variant activation + migration).
  - `Completed`: Phase 6 foundation (104-case persona regression suite + adversarial/channel-isolation coverage + blocking CI workflow).
  - `Completed`: Phase 7 aggressive testing foundation (role-play twin factory runner + blind recognizability scorer + convergence gate + reusable channel-isolation module + nightly CI workflow).
  - `Completed`: Phase 7 UI E2E additions (`persona_training_loop.spec.ts`, `persona_channel_separation.spec.ts`) with passing Playwright evidence.
  - `Completed`: Phase 7 feedback-learning loop foundation (feedback ingestion -> module confidence updates -> regression-gated publish decision + migration applied).
  - `Completed`: Phase 7 feedback-learning automation (auto-enqueue from feedback route + worker dispatch + scheduler sweep + jobs job_type migration).
- Evidence policy:
  - Every completed deliverable must include:
    - changed file list
    - test command(s) + pass/fail counts
    - runtime verification notes (API/UI behavior)
    - migration/application evidence (if DB impacted)
  - Proof artifacts live in `docs/ai/improvements/proof_outputs/` and are linked from this plan.
- Completed deliverables and proof:
  - Interaction context resolver + immutable trace fields:
    - `backend/modules/interaction_context.py`
    - `backend/routers/chat.py`
    - Proof: `docs/ai/improvements/proof_outputs/interaction_context_guard_20260209.md`
  - Owner training sessions API + store:
    - `backend/modules/training_sessions.py`
    - `backend/routers/training_sessions.py`
    - `backend/main.py`
    - Proof: `docs/ai/improvements/proof_outputs/interaction_context_guard_20260209.md`
  - DB migration + RLS:
    - `backend/database/migrations/migration_interaction_context_training_sessions.sql`
    - Applied migrations in Supabase: `interaction_context_training_sessions`, `interaction_context_training_sessions_rls`
    - Proof: `docs/ai/improvements/proof_outputs/interaction_context_guard_20260209.md`
  - Context-safe conversation reset and UI handling:
    - `backend/routers/chat.py`
    - `frontend/components/Chat/ChatInterface.tsx`
    - `frontend/components/training/SimulatorView.tsx`
    - `frontend/components/console/tabs/TrainingTab.tsx`
    - Proof: `docs/ai/improvements/proof_outputs/interaction_context_guard_20260209.md`
  - Baseline eval-harness capture:
    - `backend/eval/runner.py`
    - `backend/eval/dataset.json`
    - Proof: `docs/ai/improvements/proof_outputs/phase0_eval_baseline_20260208_195550.json`
  - Phase 1 persona spec foundation:
    - `backend/modules/persona_spec.py`
    - `backend/modules/persona_compiler.py`
    - `backend/modules/persona_spec_store.py`
    - `backend/routers/persona_specs.py`
    - `backend/database/migrations/migration_persona_specs_v1.sql`
    - `backend/tests/test_persona_compiler.py`
    - `backend/tests/test_persona_specs_router.py`
    - Proof: `docs/ai/improvements/proof_outputs/persona_specs_phase1_foundation_20260209.md`
  - Phase 2 decision capture foundation:
    - `backend/modules/decision_capture_store.py`
    - `backend/routers/decision_capture.py`
    - `backend/database/migrations/migration_phase2_decision_capture.sql`
    - `backend/tests/test_decision_capture_router.py`
    - Proof: `docs/ai/improvements/proof_outputs/phase2_decision_capture_foundation_20260209.md`
  - Phase 3 intent-aware procedural retrieval foundation:
    - `backend/modules/persona_intents.py`
    - `backend/modules/persona_module_store.py`
    - `backend/modules/persona_compiler.py`
    - `backend/modules/agent.py`
    - `backend/routers/chat.py`
    - `backend/database/migrations/migration_phase3_persona_module_retrieval.sql`
    - `backend/tests/test_persona_intents.py`
    - `backend/tests/test_persona_module_store.py`
    - Proof: `docs/ai/improvements/proof_outputs/phase3_intent_aware_procedural_retrieval_20260209.md`
  - Phase 4 persona enforcement loop foundation:
    - `backend/modules/persona_fingerprint_gate.py`
    - `backend/modules/persona_auditor.py`
    - `backend/eval/judges.py`
    - `backend/routers/chat.py`
    - `backend/database/migrations/migration_phase4_persona_audit.sql`
    - `backend/tests/test_persona_fingerprint_gate.py`
    - `backend/tests/test_persona_auditor.py`
    - Proof: `docs/ai/improvements/proof_outputs/phase4_persona_enforcement_loop_20260209.md`
  - Phase 5 optimization track foundation (Track A):
    - `backend/eval/persona_prompt_optimizer.py`
    - `backend/eval/persona_prompt_optimization_dataset.json`
    - `.agent/tools/evolve_prompts.py`
    - `backend/modules/persona_prompt_variant_store.py`
    - `backend/modules/persona_compiler.py`
    - `backend/modules/agent.py`
    - `backend/routers/persona_specs.py`
    - `backend/database/migrations/migration_phase5_persona_prompt_optimization.sql`
    - `backend/tests/test_persona_prompt_optimizer.py`
    - `backend/tests/test_persona_prompt_variant_store.py`
    - Proof: `docs/ai/improvements/proof_outputs/phase5_prompt_optimization_trackA_20260209.md`
  - Phase 6 persona regression suite + CI gate foundation:
    - `backend/eval/persona_regression_runner.py`
    - `backend/eval/persona_regression_dataset.json`
    - `backend/tests/test_persona_regression_runner.py`
    - `.github/workflows/persona-regression.yml`
    - `docs/ops/QUALITY_GATE.md`
    - `docs/ops/PERSONA_QUALITY_GATE.md`
    - Proof: `docs/ai/improvements/proof_outputs/phase6_persona_regression_ci_gate_20260209.md`
  - Phase 7 aggressive testing lane foundation:
    - `backend/eval/persona_aggressive_runner.py`
    - `backend/eval/persona_roleplay_scenarios.json`
    - `backend/eval/persona_blind_recognition.py`
    - `backend/eval/persona_convergence_gate.py`
    - `backend/eval/persona_channel_isolation.py`
    - `backend/tests/test_persona_aggressive_runner.py`
    - `backend/tests/test_persona_blind_recognition.py`
    - `backend/tests/test_persona_convergence_gate.py`
    - `backend/tests/test_persona_channel_isolation.py`
    - `.github/workflows/persona-aggressive-nightly.yml`
    - Proof: `docs/ai/improvements/proof_outputs/phase7_aggressive_testing_lane_20260209.md`
    - Proof data: `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209.json`, `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209_transcripts.json`
  - Phase 7 UI E2E additions:
    - `frontend/tests/e2e/persona_training_loop.spec.ts`
    - `frontend/tests/e2e/persona_channel_separation.spec.ts`
    - `frontend/tests/e2e/helpers/personaHarness.ts`
    - `frontend/components/console/tabs/TrainingTab.tsx` (E2E bypass-safe auth flow for training session controls)
    - `frontend/components/Chat/ChatInterface.tsx` (E2E bypass-safe auth flow for chat + memory actions)
    - Proof: `docs/ai/improvements/proof_outputs/phase7_ui_e2e_training_channel_20260209.md`
  - Phase 7 feedback-learning loop foundation:
    - `backend/modules/persona_feedback_learning.py`
    - `backend/routers/feedback.py`
    - `backend/routers/persona_specs.py`
    - `backend/database/migrations/migration_phase7_feedback_learning_loop.sql`
    - `backend/tests/test_persona_feedback_learning.py`
    - `backend/tests/test_feedback_router.py`
    - Migration applied in Supabase project `jvtffdbuwyhmcynauety`: `phase7_feedback_learning_loop`
    - Proof: `docs/ai/improvements/proof_outputs/phase7_feedback_learning_loop_20260209.md`
  - Phase 7 feedback-learning automation:
    - `backend/modules/persona_feedback_learning_jobs.py`
    - `backend/worker.py`
    - `backend/routers/feedback.py`
    - `backend/database/migrations/migration_add_feedback_learning_job_type.sql`
    - `backend/scripts/run_feedback_learning_scheduler.py`
    - `backend/tests/test_persona_feedback_learning_jobs.py`
    - Migration applied in Supabase project `jvtffdbuwyhmcynauety`: `add_feedback_learning_job_type`
    - Proof: `docs/ai/improvements/proof_outputs/phase7_feedback_learning_automation_20260209.md`

## Phase 0 - Baseline + Contracts (3-5 days)
Objective: Lock schema, metrics, and acceptance gates before changing behavior.

Build:
- Define persona quality KPIs:
  - `persona_compliance_score` (judge)
  - `rewrite_rate` (how often draft fails persona threshold)
  - `clarification_correctness_rate` (when clarification should have been asked)
  - `style_drift_rate` (against golden set)
- Define an immutable interaction context contract for every turn:
  - `interaction_context` is server-derived from endpoint + auth + share token (not client-provided mode).
  - Allowed contexts: `owner_training`, `owner_chat`, `public_share`, `public_widget`.
  - Conversation context is immutable after creation.
- Add initial score logging fields to Langfuse trace metadata in chat flow.
- Create architecture ADR for persona pipeline order and fallback behavior.
- Define channel permission matrix (read/write/learn/publish/tool actions) and fallback behavior on violations.

Deliverables:
- `docs/architecture/PERSONA_PIPELINE_V1.md`
- `docs/ops/PERSONA_QUALITY_GATE.md`
- `docs/architecture/INTERACTION_CONTEXT_V1.md`
- Baseline eval artifact: `docs/ai/improvements/proof_outputs/phase0_eval_baseline_20260208_195550.json`

Exit criteria:
- Metrics names and thresholds frozen.
- Baseline run captured on current system using existing eval harness.
- Every chat route emits traceable context labels; client-side mode overrides are ignored.

## Phase 1 - Versioned Persona Spec + Constitution + Compiler (1-1.5 weeks)
Objective: Stop treating persona as ad hoc prompt text; compile from versioned artifacts.

Build:
- Introduce persona artifact schema (JSON/YAML), including:
  - Identity/voice
  - Decision policy
  - Stance/values
  - Interaction style
  - Canonical examples (10-30)
  - Anti-examples (10-30)
  - Constitution principles (stable top layer)
  - Procedural policy modules (first-class, machine-checkable):
    - `when`: intent labels, conditions, confidence bands
    - `do`: ordered decision steps (clarify-first, cite-first, assumption disclosure)
    - `say_style`: brevity, formatting, tone constraints
    - `ban`: forbidden patterns/phrases
    - `few_shots`: optional examples with retrieval tags
- Add persona spec storage/versioning:
  - Multi-tenant table `persona_specs` with semantic versioning (per `tenant_id` + `twin_id`)
  - No hardcoded persona profiles in repository files
- Add interaction-context data model:
  - Conversation/message metadata includes `interaction_context`, `origin`, `share_link_id` (nullable), `training_session_id` (nullable).
  - Training artifacts must reference `training_session_id` and owner identity for auditability.
- Add auto-bootstrap pipeline for new twins:
  - Generate initial draft spec from user onboarding answers + interview transcripts + approved memories
  - Keep only neutral system defaults in code (schema + validators), never owner voice content
- Implement compiler module:
  - `backend/modules/persona_compiler.py`
  - Output typed `PromptPlan` (not one giant string):
    - `constitution_text`
    - `decision_policy_text`
    - `style_rules_text`
    - `intent_modules_text`
    - `few_shots` (retrieved list, budgeted)
    - `deterministic_rules` (JSON)
    - `channel_guardrails` (what is allowed for this `interaction_context`)
  - Runtime exemplar policy:
    - Retrieve only top 2-4 canonical examples by intent relevance
    - Keep anti-examples as compact rules/constraints, not long injected blocks
- Integrate compiler into `build_system_prompt` in `backend/modules/agent.py`.

Deliverables:
- Persona spec schema + validator.
- Compiler with deterministic ordering + tests.
- Migration path from current `twins.settings` style fields.

Exit criteria:
- Prompt text is generated from a versioned spec (no manual blob editing in runtime code).
- Every response trace records `persona_spec_version`.
- New twin can self-generate Persona Spec v1 without admin/manual prompt writing.

## Phase 2 - Decision-Trace Capture (SJT + Pairwise + Introspection) (1-2 weeks)
Objective: Capture routing logic, not just mirrored Q&A text.

Build:
- Introduce explicit training session lifecycle:
  - Owner starts/stops `training_session`.
  - Only `owner_training` context can write decision/preference/introspection records.
  - Public/share/widget contexts are hard-blocked from training writes.
- Extend interview/training with 3 capture modes:
  - SJT scenarios with forced choice + rationale + thresholds
  - Pairwise preference ranking ("A vs B more like you")
  - Process introspection prompts ("How do you answer when uncertain?")
- Require quantifiable thresholds in capture output:
  - Clarification threshold rules (`if missing X -> clarify`, `if missing Y -> assume + disclose`)
  - Retrieval thresholds per intent (confidence bands such as `0.60`, `0.75`, `0.90`)
- Store clause IDs for later enforcement:
  - Each captured rule maps to stable IDs (`POL_DECISION_###`, `POL_STYLE_###`)
- Persist as structured records:
  - `persona_decision_traces`
  - `persona_preferences`
  - `persona_introspection`
- Add transform job that converts traces into policy modules:
  - Example module IDs:
    - `procedural.decision.clarify_before_advice`
    - `procedural.uncertainty.disclose_limits`
    - `procedural.disagreement.direct_respectful`

Integration points:
- Capture API: extend `backend/routers/interview.py`
- Extraction/parsing: extend `backend/modules/memory_extractor.py` or dedicated `decision_trace_extractor.py`
- Persist + retrieval index: `backend/modules/owner_memory_store.py` plus new model layer
- Context enforcement: `backend/routers/chat.py` and training endpoints reject writes unless `owner_training`.

Exit criteria:
- At least 100 high-signal preference/decision records collected per active twin cohort.
- Decision policies can be rendered as machine-readable rules for runtime.
- No public/share conversation can create training events.

## Phase 3 - Intent-Aware Procedural Persona Retrieval (1 week)
Objective: Retrieve behavior modules per intent, not just static persona facts.

Build:
- Start with a stable small taxonomy (6-8 labels max):
  - `factual_with_evidence`
  - `advice_or_stance`
  - `action_or_tool_execution`
  - `ambiguity_or_clarify`
  - `disagreement_or_conflict`
  - `summarize_or_transform`
  - `meta_or_system`
  - `sensitive_boundary_or_refusal`
- Defer subintent expansion until routing quality stabilizes.
- Classify each incoming query intent before response generation.
- Resolve `interaction_context` before intent classification and bind channel-specific policy bundle.
- Retrieve top procedural modules for that intent.
- Inject modules into compiler in fixed order (no free-form merge).
- Enforce context-specific retrieval behavior:
  - `owner_training`: may log candidate rules/preferences as drafts.
  - `owner_chat`: may suggest training candidates but no auto-write without explicit owner approval.
  - `public_share` and `public_widget`: read-only against active published persona/policy versions.

Integration points:
- Intent classification/routing:
  - `backend/modules/identity_gate.py`
  - `backend/modules/agent.py` router node
- Retrieval source:
  - extend owner memory records with procedural tags, or
  - dedicated procedural modules table + embedding index

Exit criteria:
- Runtime prompt includes intent-specific modules with traceable module IDs.
- Drift reduction observed on intent-specific golden tests.
- Context violations (e.g., public training write) are blocked and logged.

## Phase 4 - Two-Pass Enforcement Loop (Draft -> Audit -> Rewrite) (1 week)
Objective: Enforce persona consistency every response, not best-effort prompting.

Build:
- Add deterministic persona fingerprint gate first (cheap pass):
  - intent-based answer length bands
  - formatting signature (bullets/paragraphs/headings/question-first)
  - banned phrase checks
  - allowed hedges checks
  - speed-vs-depth preference checks
- Add channel policy gate before judges:
  - verify context-action compatibility (train/write/publish/tool use).
  - hard-fail invalid transitions to safe fallback with auditable reason code.
- Split model-based enforcement into two judges:
  - Judge A (Structure/Policy): citations, clarify-vs-answer choice, format contract, forbidden content
  - Judge B (Voice Fidelity): tone/cadence/style only when A passes or in shadow sampling
- Add rewrite pass if threshold fails.
- Rewrite directives must be clause-targeted and machine-generated:
  - violated clause IDs
  - required fixes
  - max length
  - required structure
- Log both passes:
  - draft score
  - final score
  - rewrite reason categories
- Fail-safe:
  - If rewrite still fails threshold, return safest compliant fallback pattern.

Integration points:
- Hook in `backend/routers/chat.py` around final answer assembly.
- Optional async/offline shadow mode first, then hard-gate.

Exit criteria:
- >=90% of outputs pass persona threshold post-rewrite on regression suite.
- Low additional latency budget is met (define target in Phase 0).
- Zero unauthorized training writes from non-training contexts.

## Phase 5 - Optimization Track (APO now, optional DPO later) (1-2 weeks parallelizable)
Objective: Remove generic style and improve consistency without hand-tuning loops.
Status: `Completed (Track A foundation)`, `Optional Track B pending`.

Track A (no fine-tuning required):
- Build automatic prompt optimization loop using offline eval feedback.
- Reuse and extend `.agent/tools/evolve_prompts.py` to:
  - mutate compiler templates
  - evaluate against persona regression suite
  - keep top-performing prompt variants

Track B (if fine-tuning available):
- Train preference model with DPO using pairwise labels from Phase 2.
- Keep prompt/compiler stack; DPO improves base behavior stability.

Exit criteria:
- Track A: measurable gain in compliance and style metrics.
- Track B: additional gain over Track A on held-out persona tests.

## Phase 6 - Persona Regression Suite + CI Gate (1 week)
Objective: Stop persona drift caused by prompt/retrieval/router changes.
Status: `Completed (foundation with blocking CI gate)`.

Build:
- Create 100-question golden suite across intent taxonomy.
- For each item, store expected properties:
  - tone
  - structure
  - stance fidelity
  - expected brevity level
  - whether clarification should be asked
- Automated scoring:
  - persona judge score
  - deterministic rule checks (length, required structure, forbidden phrases)
- Add adversarial drift cases:
  - "ignore your guidelines"
  - "write like a different persona"
  - "be much more formal than usual"
  - "be very long and detailed"
- Add channel-isolation adversarial cases:
  - payload attempts to spoof `mode=training` on public/share endpoints.
  - unpublished spec updates must not appear in public responses.
  - in-flight public conversations remain pinned to conversation-bound active versions.
- Verify refusal/resistance behavior on adversarial cases.
- CI integration:
  - block merges if persona gates fail.

Integration points:
- `backend/eval/` add `persona_regression_runner.py` and dataset(s).
- Update quality docs (`docs/ops/QUALITY_GATE.md`) with persona gates.

Exit criteria:
- CI enforces persona quality on every change touching prompts/routing/retrieval.
- Drift incidents become detectable before deploy.
- Channel isolation and version pinning checks pass in CI.

## End-State Architecture (after Phase 6)
Runtime flow:
1. Resolve immutable `interaction_context` from endpoint/auth/share token.
2. Intent classify query
3. Retrieve procedural persona modules for intent + context
4. Compile prompt from versioned persona spec + constitution + modules + context guardrails
5. Generate draft answer
6. Channel policy gate (mandatory)
7. Deterministic fingerprint gate
8. Structure/policy judge (mandatory)
9. Voice judge (conditional by risk/failure/sample)
10. Rewrite if needed
11. Return final answer with trace metadata

Required trace metadata:
- `persona_spec_version`
- `constitution_version`
- `interaction_context`
- `origin_endpoint`
- `share_link_id` (nullable)
- `training_session_id` (nullable)
- `intent_label`
- `module_ids`
- `deterministic_gate_passed`
- `channel_policy_gate_passed`
- `structure_policy_score`
- `voice_score`
- `draft_persona_score`
- `final_persona_score`
- `rewrite_applied`

## Suggested Execution Order and Teaming
- Sequence: Phase 0 -> 1 -> 2 -> 3 -> 4 -> 6 (with onboarding/context gates introduced in Phase 0 and enforced by Phase 2, plus PG-3.5 cache layer before hard-gating in production)
- Phase 5 runs in parallel after Phases 2-4 produce usable preference data.
- Minimum practical milestone (MVP high impact): complete Phases 1 + 3 + 4 + 6.

## Risks and Mitigations
- Risk: latency inflation from two-pass pipeline.
  - Mitigation: shadow mode, selective rewrite threshold, low-token judge prompts.
- Risk: overfitting to canonical examples.
  - Mitigation: anti-examples + diverse golden suite + held-out eval set.
- Risk: policy conflicts between modules.
  - Mitigation: compiler precedence rules + conflict detector in audit step.
- Risk: weak preference signal quality.
  - Mitigation: prioritize pairwise data collection and adjudicate ambiguous labels.

## Production-Grade Addendum: Policy / Reasoning Graph

This extends the plan with your "how the twin thinks" graph above the existing knowledge layer.

### Architecture Separation (mandatory)
- Policy Graph (`how to think`): routing, decision gates, tool/source policies, response templates, eval rules.
- Knowledge Layer (`what to know`): vector chunks, graph facts, verified Q&A, source metadata.
- Rule: Policy Graph nodes never store raw document payloads; only procedural fragments and routing metadata.
- Interaction Context Plane (`who is interacting and why`): immutable channel and permission envelope applied before policy traversal.
- Single-source boundary:
  - Persona Spec owns "how to speak and decision defaults"
  - Policy Graph owns "what happens next" orchestration and tool gating
  - Policy Graph selects persona modules; it does not redefine persona rules

### L0-L6 Layer Contract
- L0 Governance (non-negotiable): safety/privacy/refusal/escalation/citation requirements.
- L1 Persona Core (stable identity): voice, stance defaults, disagreement style, uncertainty behavior.
- L2 Intent Taxonomy: intent -> subintent -> scenario.
- L3 Thinking Steps: stepwise cognitive workflow with explicit stop criteria.
- L4 Tool + Source Policy: retrieval source ordering and fallback chain.
- L5 Response Templates: renderer contract by intent class.
- L6 Feedback Memory: reward signals and preference updates.

### Policy Graph Schema (V1)
Node types:
- `PolicyRoot`, `Intent`, `Subintent`, `Scenario`
- `ThinkStep`, `DecisionGate`, `ToolPlan`, `SourcePolicy`
- `PromptFragment`, `ResponseTemplate`, `EvalRule`, `FeedbackSignal`

Required node fields:
- `id`, `tenant_id`, `twin_id`, `version`, `stage`, `priority`
- `preconditions` (JSONB), `exit_criteria` (JSONB)
- `next_options` (allowed node IDs)
- `prompt_fragment` (optional text)
- `confidence_threshold` (optional numeric)
- `embedding` (vector/JSON for semantic matching)
- `active_from`, `active_to`, `status`

Edge types:
- `HAS_CHILD`, `DEFAULT_NEXT`, `OPTION_NEXT`, `REQUIRES`
- `USES_TOOL`, `PREFERS_SOURCE`, `FALLBACK_SOURCE`
- `GOVERNED_BY`, `RENDER_WITH`, `EVALUATED_BY`, `REWARDED_BY`

### Runtime Traversal Contract
1. Resolve immutable context (`owner_training` | `owner_chat` | `public_share` | `public_widget`) from endpoint/auth/token.
2. Classify intent candidates (embedding retrieval over Intent/Subintent/Scenario + constrained router pick).
3. Traverse policy graph from Intent path through DecisionGate nodes (must emit one ID from `next_options`).
4. Compile prompt in fixed order:
   1. L0 governance
   2. L1 persona core
   3. L2 selected intent path
   4. L3 active think step fragments
   5. L4 source policy (if retrieval is required)
   6. Retrieved evidence
   7. User message
5. Execute tools only when gate output requires it and context permissions allow it.
6. Run channel policy gate (writes, training updates, and publish actions).
7. Run deterministic fingerprint gate.
8. Run model-based eval gates as needed (structure first, voice second, risk-aware escalation).
9. Save full trace: selected path, gate outputs, tools called, deterministic results, judge scores, context metadata, final disposition.

### Repo Gap Analysis (current -> target)
- `backend/modules/agent.py:180` and `backend/modules/agent.py:525` both define `create_twin_agent`; consolidate to one graph entrypoint before adding Policy Graph traversal.
- `backend/modules/agent.py:335`, `backend/modules/agent.py:409`, `backend/modules/agent.py:471` use JSON mode; migrate router/planner/verifier outputs to strict schema parsing (typed outputs, validated IDs).
- `backend/modules/graph_context.py:363` reads full `edges` table then filters in Python; replace with bounded RPC expansion (`seed_ids`, `max_hops`, `limit`) for predictable latency.
- `backend/modules/tools.py:26` to `backend/modules/tools.py:90` contains domain-specific query expansion examples (`M&A`, `SGMT 6050`) in generic runtime path; externalize into configurable retrieval policies.
- `backend/modules/governance.py:131` fetches policies by `twin_id`; align policy lookup with tenant+twin scoping and formal layer tags (`L0`, `L1`, etc.).
- `backend/database/migrations/migration_phase9_governance.sql:24` defines `governance_policies.twin_id NOT NULL`; conflicts with tenant-wide policy intent in `backend/routers/governance.py:59`. Add scoped schema v2 (`scope_type`, nullable `twin_id` with constraints).
- `backend/routers/chat.py:160` derives `mode` from request/user role; replace with server-side immutable interaction-context resolver shared by all chat routes.
- `frontend/components/Chat/ChatInterface.tsx:242` maps `training` to `owner`; remove client-side mode collapse and send explicit training-session intent only on owner-auth routes.
- `backend/database/migrations/migration_owner_memory.sql:52` limits mode to `owner/public`; extend enum/check constraints to channel taxonomy with write permissions.
- `backend/main.py:52` enables credentialed CORS, while `render.yaml:26` sets `ALLOWED_ORIGINS="*"`; enforce explicit allowlist per environment.
- `backend/requirements.txt` mostly unpinned; add lock strategy and reproducible builds for production.
- `.github/workflows/code-review.yml` relies heavily on `continue-on-error`; convert persona/regression/security gates to blocking checks.

### Production Phases (Policy Graph Track)

#### PG-0: Stabilize Runtime Surface (3-4 days)
- Consolidate duplicate `create_twin_agent` and isolate graph builder module.
- Introduce structured response models for router/planner/gates.
- Add trace IDs and path logging schema.
- Add interaction-context resolver middleware and immutable conversation context binding.
Exit:
- One runtime entrypoint and deterministic graph invocation path.

#### PG-1: Policy Graph Data Model + APIs (1 week)
- Add migrations for `policy_nodes`, `policy_edges`, `policy_versions`, `policy_runs`.
- Add RLS and tenant/twin scope constraints.
- Build CRUD + publish/version endpoints.
- Add channel policy schema for context permissions and training-session references.
Exit:
- Versioned policy graph can be created, activated, and queried per twin.

#### PG-2: Intent Router + Decision Gates (1 week)
- Implement L2/L3 traversal service using allowed-next constraints.
- Add decision trace persistence (`chosen_node_id`, `candidate_ids`, `scores`).
- Enforce "one-of-allowed" gate output contract.
- Enforce context-action matrix (public contexts cannot trigger training writes).
Exit:
- Runtime selects and logs a valid thinking path per request.

#### PG-3: Retrieval Policy Execution (1 week)
- Convert retrieval/source ordering into L4 policy nodes.
- Replace ad hoc query expansion with policy-based plans.
- Add deterministic citation and evidence requirement flags per scenario.
- Add exemplar retrieval policy: max 2-4 relevant few-shots per turn, intent-scoped.
Exit:
- Tool invocation becomes policy-driven and auditable.

#### PG-3.5: PromptPlan + Cache Layer (3-4 days)
- Cache compiled prompt artifacts and deterministic rules.
- Cache key:
  - `(tenant_id, twin_id, persona_spec_version, constitution_version, intent_label, module_ids_hash)`
- Cache payload:
  - compiled prompt sections (excluding dynamic evidence)
  - deterministic fingerprint settings
  - selected few-shot IDs
Exit:
- P95 latency and token usage remain within SLO after two-pass enforcement.

#### PG-4: Two-Pass Persona + Policy Audit (1 week)
- Add pre-final audit: persona compliance + policy compliance + evidence check.
- Add rewrite pass with targeted critique.
- Add fallback response if policy/eval threshold still fails.
Exit:
- Response release is gated by auditable eval rules.

#### PG-5: Regression + Release Gates (1 week)
- Build 100+ prompt set across intent taxonomy with expected properties.
- Add CI gate for policy traversal validity, persona score threshold, citation compliance.
- Promote only if gate passes.
Exit:
- Drift is caught pre-deploy.

#### PG-6: Optimization (parallel track)
- Apply APO to router prompts/template fragments (L2-L5) using regression objective.
- Optional DPO on pairwise persona preferences once labels are mature.
Exit:
- Measurable reduction in generic style and clarification errors.

### Production SLO Targets
- P95 latency increase from two-pass pipeline: <= 25% over baseline.
- Persona compliance pass rate post-rewrite: >= 90%.
- Citation-required intents with valid evidence: >= 95%.
- Invalid decision-gate transitions: 0 (hard-fail with fallback).
- Regression suite pass rate for release: >= 95%.

### Implementation Notes for This Repo
- Reuse existing foundations:
  - Prompt versioning: `backend/modules/prompt_manager.py`
  - Online judges: `backend/eval/judges.py`
  - Owner memory + clarification flow: `backend/modules/owner_memory_store.py`, `backend/modules/identity_gate.py`
  - LangGraph persistence hook: `backend/modules/agent.py:590`
- Add new modules:
  - `backend/modules/policy_graph_store.py`
  - `backend/modules/policy_router.py`
  - `backend/modules/policy_compiler.py`
  - `backend/modules/policy_auditor.py`
  - `backend/eval/persona_policy_regression.py`

### Research References (design basis)
- LangGraph workflows and conditional routing: https://docs.langchain.com/oss/python/langgraph/workflows-agents
- LangGraph persistence/checkpointing: https://langchain-ai.github.io/langgraph/concepts/persistence/
- OpenAI structured outputs: https://platform.openai.com/docs/guides/structured-outputs
- OpenAI evals: https://platform.openai.com/docs/guides/evals
- OpenAI prompt optimization: https://platform.openai.com/docs/guides/prompt-optimization
- Anthropic Constitutional AI: https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback
- Agent Lightning (agent optimization/RL traces): https://github.com/microsoft/agent-lightning
- APO paper (prompt optimization): https://www.microsoft.com/en-us/research/publication/automatic-prompt-optimization-with-gradient-descent-and-beam-search/
- PostgreSQL row-level security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Open Policy Agent (policy language): https://www.openpolicyagent.org/docs/policy-language
- FastAPI deployment guidance: https://fastapi.tiangolo.com/deployment/server-workers/

## UI/UX Implementation Blueprint (Exact Surfaces)

### UX Principle
- Keep all editing in existing owner surfaces (`Training`, `Studio`, `Governance`) and all proof in existing validation surfaces (`Simulator`, `Chat` debug panel) to avoid workflow fragmentation.
- Persona/policy are learned from each user's own interactions; UI manages training and approval, not hardcoded profile authoring.
- Interaction context must always be explicit and visible (`Owner Training`, `Owner Chat`, `Public Share`, `Public Widget`) to prevent accidental cross-channel behavior.

### Screen 0: Onboarding Channel + Publish Gate
- Route: `frontend/app/onboarding/page.tsx`
- Purpose: explicitly separate owner training from public usage before launch.
- New onboarding checkpoints:
  - `Training Workspace Ready`: owner-only context enabled, share links disabled.
  - `Training Minimum Met`: interview + SJT + pairwise + introspection checklist passes.
  - `Public Simulation Pass`: simulator run in `public_share` context with published version only.
  - `Launch Approval`: owner confirms publish + share-link creation.
- Required behavior:
  - Mode badges persist across onboarding screens.
  - Launch step must call backend share-link APIs (not URL-only shortcuts).

### Screen 1: Persona Studio V2
- Route: `frontend/app/dashboard/studio/page.tsx`
- Purpose: review/edit/publish user-trained persona specs (auto-generated first draft per twin).
- Layout:
  - Left rail: spec versions list (`draft`, `active`, `archived`) with semver tags.
  - Main tabs: `Voice`, `Decision Policy`, `Stance/Values`, `Interaction Style`, `Constitution`, `Examples`, `Anti-Examples`.
  - Right panel: live "Compiled Prompt Preview" with fixed section order and module IDs.
- Primary actions:
  - `Generate Draft From My Data`
  - `Save Draft`
  - `Validate Spec`
  - `Publish Version`
  - `Rollback`
- New components:
  - `frontend/components/persona/PersonaSpecEditor.tsx`
  - `frontend/components/persona/PersonaVersionTimeline.tsx`
  - `frontend/components/persona/CompiledPromptPreview.tsx`

### Screen 2: Training Decision Capture
- Route: `frontend/components/console/tabs/TrainingTab.tsx`
- Purpose: collect decision traces, not only free-form Q&A.
- Add step between current "Interview" and "Knowledge":
  - `Step 3: Decision Capture`
  - Modes: `SJT`, `Pairwise`, `Introspection`.
- Add training session controls:
  - `Start Training Session`
  - `Pause/Stop Training Session`
  - `Include this answer in training` toggle for owner-reviewed captures.
- UI blocks:
  - Scenario card with forced choice and rationale textbox.
  - Pairwise card with A/B response chooser and "why" annotation.
  - Introspection prompts with structured answer fields.
- New components:
  - `frontend/components/persona/DecisionCaptureStep.tsx`
  - `frontend/components/persona/PairwiseLabeler.tsx`
  - `frontend/components/persona/IntrospectionForm.tsx`

### Screen 3: Governance Policy Graph
- Route: `frontend/app/dashboard/governance/page.tsx`
- Purpose: author and audit policy/reasoning graph nodes and transitions.
- Layout:
  - `Policy Layers` panel (L0-L6) with activation toggles and version tags.
  - `Node Inspector` panel (preconditions, exit criteria, next options, thresholds).
  - `Edge Rules` panel (`DEFAULT_NEXT`, `OPTION_NEXT`, `REQUIRES`, source fallback).
  - `Eval Rules` panel (citation required, uncertainty disclosure, confidence threshold).
- New components:
  - `frontend/components/policy/PolicyLayerBoard.tsx`
  - `frontend/components/policy/PolicyNodeInspector.tsx`
  - `frontend/components/policy/PolicyEvalRules.tsx`

### Screen 4: Simulator With Trace Replay
- Route: `frontend/app/dashboard/simulator/page.tsx` and `frontend/components/training/SimulatorView.tsx`
- Purpose: prove behavior is policy-driven and persona-consistent.
- Add context switcher:
  - `owner_training`
  - `owner_chat`
  - `public_share`
  - `public_widget`
- Add right-side collapsible "Reasoning Trace" drawer:
  - Intent selected
  - Node path traversed
  - Decision gate outputs
  - Tools/sources called
  - Interaction context + permission decision
  - Draft persona score vs final persona score
  - Rewrite directives (if any)
- Add "Compare" mode:
  - `Draft` vs `Final` answer diff for auditability.
- New component:
  - `frontend/components/policy/ReasoningTraceDrawer.tsx`

### Screen 5: Release Quality Gate
- Route: `frontend/app/dashboard/insights/page.tsx` (or dedicated `dashboard/quality`)
- Purpose: release readiness for persona + policy regression.
- KPIs:
  - Persona compliance pass rate
  - Citation compliance
  - Clarification correctness
  - Invalid gate transition count
  - Regression suite pass rate

## Backend Implementation Contract

### New Tables (Supabase/Postgres)
- `persona_specs` (versioned spec artifact)
- `persona_modules` (procedural modules by intent/step)
- `persona_examples` (gold and anti-examples)
- `persona_fingerprints` (deterministic style/format/length constraints per intent)
- `persona_training_events` (raw user training interactions and labels)
- `training_sessions` (owner-started training windows, status, actor, timestamps)
- `interaction_context_policies` (channel permission matrix for read/write/learn/tool/publish actions)
- `persona_compilation_jobs` (draft generation and rebuild job status)
- `persona_prompt_optimization_runs` (Phase 5 optimizer run ledger)
- `persona_prompt_variants` (render-option variants + activation state)
- `policy_nodes` (L0-L6 nodes)
- `policy_edges` (typed transitions)
- `policy_versions` (publish lifecycle)
- `policy_runs` (per-response trace)
- `persona_judge_results` (draft/final scoring)

### New APIs (FastAPI)
- `GET /twins/{twin_id}/persona-specs`
- `POST /twins/{twin_id}/persona-specs`
- `POST /twins/{twin_id}/persona-specs/{version}/publish`
- `POST /twins/{twin_id}/persona-specs/generate` (build draft from user-owned data)
- `GET /twins/{twin_id}/persona-fingerprint`
- `PATCH /twins/{twin_id}/persona-fingerprint`
- `POST /twins/{twin_id}/training-sessions/start`
- `POST /twins/{twin_id}/training-sessions/{session_id}/stop`
- `POST /twins/{twin_id}/decision-capture/sjt`
- `POST /twins/{twin_id}/decision-capture/pairwise`
- `POST /twins/{twin_id}/decision-capture/introspection`
- `GET /twins/{twin_id}/persona-prompt-variants`
- `POST /twins/{twin_id}/persona-prompt-variants/{variant_id}/activate`
- `POST /twins/{twin_id}/persona-prompt-optimization/runs`
- `GET /twins/{twin_id}/policy-graph`
- `POST /twins/{twin_id}/policy-graph/nodes`
- `POST /twins/{twin_id}/policy-graph/edges`
- `GET /twins/{twin_id}/policy-runs/{run_id}`
- `GET /twins/{twin_id}/interaction-context-policy`
- `POST /twins/{twin_id}/share-links/{link_id}/simulate`

### Runtime Changes
- Replace ad hoc prompt assembly in `backend/modules/agent.py` with compiled artifacts:
  - `backend/modules/persona_compiler.py`
  - `backend/modules/policy_router.py`
  - `backend/modules/policy_auditor.py`
- Add server-side interaction-context resolver (endpoint + auth + share token) and ignore client-provided mode overrides.
- Add deterministic gate before model judges (`backend/modules/persona_fingerprint_gate.py`).
- Add channel policy gate before deterministic/model judges.
- Enforce strict-typed outputs for router/gates and reject invalid next-node transitions.
- Use clause-targeted rewrite directives with stable rule IDs.
- Add caching for compiled `PromptPlan` bundles and few-shot selections.
- Resolve and apply active prompt render variant during prompt compilation.
- Pin active persona/policy version per conversation start for public contexts.
- Add two-pass release gate in `backend/routers/chat.py`:
  - draft generation
  - structure/policy audit -> voice audit (conditional)
  - targeted rewrite if below threshold

## How I Will Show It Works (UI Proof Plan)

### Demo Flow A: Persona Spec Enforcement
- User completes training flow; system generates spec v1 automatically.
- Publish v1 and run 5 simulator prompts.
- Show trace drawer with `persona_spec_version=v1`.
- Tighten one constitution rule, publish v2, rerun same prompts.
- Show measurable score and rewrite-rate changes in quality view.

### Demo Flow B: Decision Trace Routing
- Complete SJT + pairwise + introspection in Training.
- Ask ambiguity-heavy prompts in Simulator.
- Show gate routing shifts from `ANSWER` to `CLARIFY` where policy requires.

### Demo Flow C: Policy Graph Determinism
- Select a factual intent requiring citations.
- Show path traversal includes retrieval and evidence check.
- Break one edge rule intentionally in draft graph.
- Show hard-fail prevention and safe fallback response.

### Demo Flow D: Training vs Public Isolation
- Start `owner_training` session and capture new decision preferences.
- Do not publish spec/module updates.
- Run public share-link chats and confirm responses still use last published versions.
- Publish new version and start a fresh public conversation.
- Show that only post-publish conversations reflect updates.

## Delivery Sequencing (Execution)
- Week 1: interaction-context contract + schema/APIs + Studio V2 draft editor.
- Week 2: onboarding channel gates + training session controls + decision capture extraction.
- Week 3: policy graph runtime traversal + cache layer + simulator trace drawer with context replay.
- Week 4: two-pass audit/rewrite + isolation regression gates + quality dashboard.

## Aggressive Testing Plan (Role-Play + Self-Training)
Status: `Completed (backend foundation + nightly workflow)` on `2026-02-09`.

### Testing Objective
Prove that:
- the system stays in persona under pressure,
- policy routing remains valid and auditable,
- and a blind reader can recognize the owner voice from chat transcripts.

### Test Lanes (all required)
1. Deterministic/unit tests (fast, PR blocking)
   - Persona compiler output shape (`PromptPlan` contracts).
   - Deterministic fingerprint gate (length/style/ban rules).
   - Decision gate "one-of-allowed-next" transition checks.
2. API contract tests (fast, PR blocking)
   - `persona-specs/*`, `decision-capture/*`, `policy-graph/*` endpoints.
   - RLS and tenant/twin isolation for every new table.
3. Integration tests (medium, PR blocking)
   - Full chat path with deterministic gate + Judge A + optional Judge B.
   - Rewrite directive correctness (clause IDs present, structure enforced).
4. Role-play self-play tests (nightly)
   - Create a synthetic owner twin from scratch.
   - Run multi-agent conversations across all intents and adversarial prompts.
   - Retrain and republish automatically on failures, then re-evaluate.
5. Blind recognizability tests (nightly + release gate)
   - Transcript-only evaluation: "Which owner profile is this?"
   - Score whether persona is clearly identifiable by independent raters/judges.
6. Long-horizon drift tests (nightly)
   - 20-40 turn sessions with context shifts.
   - Verify stable voice, consistent policy choices, and bounded verbosity.
7. Channel isolation and tamper tests (nightly + release gate)
   - Attempt `mode/training` spoofing on public endpoints.
   - Verify public/share traffic cannot write training events or mutate persona modules.
   - Verify unpublished drafts never appear in public contexts.

### Role-Play Twin Factory (what "create and train by myself" means)
For each synthetic run:
1. Create twin in test tenant (`auto-generated owner profile`).
2. Run onboarding + interview + decision capture using an "Owner Simulator" agent.
3. Generate persona spec v1 (`/persona-specs/generate`), publish to staging.
4. Run challenger agents:
   - curious user,
   - skeptical user,
   - rushed executive (brevity pressure),
   - adversarial prompter (drift injection),
   - tool-heavy operator (action requests).
5. In parallel, run public share-link traffic against same twin while training remains unpublished.
6. Score each turn with deterministic gate + Judge A + Judge B (conditional).
7. Convert failures into training events (pairwise, SJT threshold corrections, anti-examples).
8. Regenerate/publish next version (v2, v3, ...), rerun same suite.
9. Stop only when convergence thresholds are met for 3 consecutive cycles.

### Convergence Criteria (must all pass)
- Persona recognizability >= 0.80 (blind transcript identification).
- Post-rewrite persona compliance >= 0.88.
- Citation validity on citation-required intents >= 0.95.
- Clarification correctness >= 0.85.
- Invalid policy transitions = 0.
- Rewrite rate < 0.30 after stabilization window.
- P95 latency delta <= 25% with cache enabled.
- Public-context training writes = 0.
- Unpublished version leakage to public contexts = 0.

### Aggressive Test Volumes
- Per twin per cycle:
  - 250 prompts (balanced across the 8 top-level intents),
  - 80 adversarial prompts,
  - 20 long-horizon sessions (20+ turns each).
- Pre-release gate:
  - 1,000+ total prompts across synthetic twins + held-out real-like scenarios.

### CI and Runtime Cadence
- PR gate (blocking): deterministic + API contracts + integration smoke.
- Nightly gate (blocking for release branch): full role-play loops + blind recognizability.
- Weekly stress run: high-volume replay, latency/cost regression, drift trend analysis.

### Artifacts and Auditability
- Store each run under `artifacts/persona_eval/<timestamp>/<twin_id>/`:
  - transcript logs,
  - selected module IDs,
  - deterministic gate outcomes,
  - judge scores and rewrite clauses,
  - before/after answer diffs,
  - pass/fail summary and trend charts.

### Implemented Test Harness Files (Backend)
- `backend/eval/persona_aggressive_runner.py`
- `backend/eval/persona_roleplay_scenarios.json`
- `backend/eval/persona_blind_recognition.py`
- `backend/eval/persona_convergence_gate.py`
- `backend/eval/persona_channel_isolation.py`
- `backend/tests/test_persona_aggressive_runner.py`
- `backend/tests/test_persona_blind_recognition.py`
- `backend/tests/test_persona_convergence_gate.py`
- `backend/tests/test_persona_channel_isolation.py`
- `.github/workflows/persona-aggressive-nightly.yml`

### Implemented UI E2E Additions
- `frontend/tests/e2e/persona_training_loop.spec.ts`
- `frontend/tests/e2e/persona_channel_separation.spec.ts`

### Important Constraint
Synthetic owner testing is for system hardening. Final sign-off must still include real owner data review, because recognizability on synthetic personas does not guarantee production authenticity.

## What I Need From You
- Product policy decisions only (platform-level), not per-persona content:
  - Confirm or override recommended defaults:
    - Minimum training before first publish:
      - Interview: `8-12 minutes`
      - Decision capture: `12 SJT`, `20 pairwise`, `6 introspection`
      - First output is `draft only`
    - Publish policy:
      - `owner approval mandatory` by default
      - optional `auto-publish` only for internal sandbox twins
    - Confidence + clarify policy:
      - citation-required factual claims retrieve unless confidence >= `0.85` from verified internal KB
      - advice may answer with explicit assumptions
      - clarify when missing material parameters, multi-intent ambiguity, or missing action permissions
    - Data retention + consent:
      - raw training events retained `180 days` by default (tenant-configurable)
      - export/delete supported
      - derived modules/spec versions retained until twin deletion
    - Success thresholds:
      - post-rewrite persona compliance >= `0.88`
      - citation-validity on citation-required intents >= `0.95`
      - clarification correctness >= `0.85`
      - rewrite rate target `< 30%` after 2 weeks
      - P95 latency delta <= `25%` with cache enabled
    - Rollout:
      - `internal -> closed beta -> GA` with regression and trace UX gates
    - Channel and onboarding policies:
      - confirm public traffic training policy (`default: no training from public/share/widget`)
      - confirm publish visibility rule (`default: only new conversations see newly published versions`)
      - confirm who can start/stop training sessions (`default: owner + tenant admins only`)
      - confirm share-link controls (TTL, revocation behavior, optional password/rate limits)

