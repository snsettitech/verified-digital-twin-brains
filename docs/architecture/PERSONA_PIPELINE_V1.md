# Persona Pipeline V1

## Purpose
Define the production runtime contract for persona-consistent responses with explicit context separation and auditable enforcement.

## Runtime Order (authoritative)
1. Resolve immutable interaction context (`owner_training`, `owner_chat`, `public_share`, `public_widget`).
2. Validate/rotate conversation if context mismatch is detected.
3. Resolve identity gate mode from context (`owner` or `public`).
4. Load or materialize the canonical persona artifact (`public_profile`, `persona_identity_pack`, `public_profile_meta`).
5. Load intent or policy modules and memory context.
6. Build prompt plan (constitution + decision policy + style + intent modules + evidence constraints).
7. Assemble grounding context in this order: canonical profile, verified facts, featured resources or top sources, vector retrieval, graph or memory context.
8. Generate draft response.
9. Run deterministic checks.
10. Run policy or structure judge.
11. Run voice judge (conditional by risk/sample/failure).
12. Rewrite with clause-targeted directives when needed.
13. Emit final response and trace metadata.

## Determinism and Safety Contracts
- Context derivation is server-owned; client `mode` is non-authoritative.
- Conversation context is immutable.
- If context differs from conversation context, backend must force a new conversation.
- Public contexts cannot write training artifacts.
- Training artifact writes require active owner training session.

## Prompt Assembly Contract
Prompt fragments are assembled in this order:
1. Governance and constitution
2. Persona decision policy
3. Interaction/style policy
4. Intent path and procedural modules
5. Canonical persona profile
6. Verified facts and approved structured profile fields
7. Featured resources or top sources
8. Vector retrieval evidence
9. Graph or memory context
10. Tool/source policy
11. User message

## Canonical Persona Artifact Contract
- Canonical user-facing artifact: `twins.settings.public_profile`
- Canonical prompt/runtime companion: `twins.settings.persona_identity_pack`
- Canonical materialization metadata: `twins.settings.public_profile_meta`
- `public_profile_meta` tracks at minimum: `version`, `source_flow`, `materialized_at`, `completeness_score`, `image_status`, `image_source_type`, `image_source_url`, `image_confidence`
- Persona readiness for polished rendering depends on canonical profile materialization, not only on vector compilation

## Trace Contract (minimum)
- `interaction_context`
- `origin_endpoint`
- `share_link_id` (nullable)
- `training_session_id` (nullable)
- `forced_new_conversation`
- `context_reset_reason` (nullable)
- `previous_conversation_id` (nullable)
- `effective_conversation_id`

## Fallback Rules
- If conversation validation fails: reset to new conversation and continue.
- If training session validation fails: downgrade to `owner_chat`.
- If policy judge fails post-rewrite: return safe fallback response.

## Current Implementation Coverage
- Context resolution and immutable reset: implemented.
- Training session lifecycle: implemented.
- Full two-judge persona enforcement: pending Phase 4.
- PromptPlan compiler: pending Phase 1.
