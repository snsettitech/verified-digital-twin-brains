# Interaction Context V1

## Goal
Guarantee that training, owner chat, and public chat are never mixed in routing, memory writes, or trace semantics.

## Allowed Contexts
- `owner_training`
- `owner_chat`
- `public_share`
- `public_widget`

## Derivation Rules (server-owned)
- `/chat/{twin_id}` + owner auth:
  - active valid `training_session_id` -> `owner_training`
  - otherwise -> `owner_chat`
- `/chat/{twin_id}` + visitor auth -> `public_widget`
- `/chat-widget/{twin_id}` -> `public_widget`
- `/public/chat/{twin_id}/{token}` -> `public_share`

Client-provided `mode` is non-authoritative and ignored for policy decisions.

## Conversation Immutability
- Conversation has fixed `interaction_context`.
- If a request arrives with conversation context different from resolved context:
  - backend must force a new conversation
  - trace must include reset metadata:
    - `forced_new_conversation = true`
    - `previous_conversation_id`
    - `context_reset_reason`

## Training Session Contract
- Owner must explicitly start a training session.
- Only `owner_training` turns are eligible for training writes.
- Public contexts are hard-blocked from training writes.
- Training sessions are tenant-scoped and owner-scoped.

## Database Contract
- `training_sessions` table stores owner training windows.
- `conversations` stores:
  - `interaction_context`
  - `origin_endpoint`
  - `share_link_id`
  - `training_session_id`
- `messages` stores `interaction_context`.
- RLS is enabled on `training_sessions` with tenant isolation policy.

## Trace Contract
- Emit on metadata/answer payloads:
  - `interaction_context`
  - `origin_endpoint`
  - `share_link_id` (nullable)
  - `training_session_id` (nullable)
  - `forced_new_conversation`
  - `context_reset_reason`
  - `previous_conversation_id`
  - `effective_conversation_id`

## Validation
- Tests:
  - `backend/tests/test_interaction_context.py`
  - `backend/tests/test_training_sessions_router.py`
  - `backend/tests/test_chat_interaction_context.py`
- Proof:
  - `docs/ai/improvements/proof_outputs/interaction_context_guard_20260209.md`
