# System Invariants: Non-Negotiable Rules

All AI-generated code must adhere to these invariants. Violations will be blocked by the AI Stop-Hook.

## 1. Tenant Isolation
- **Rule**: No query or operation may cross tenant boundaries.
- **Enforcement**: Mandatory `tenant_id` filter on every Supabase call.
- **Exception**: Global system configurations or migrations (must be clearly marked).

## 2. Twin Ownership
- **Rule**: Users can only interact with or modify twins within their authorized tenant.
- **Enforcement**: Mandatory use of `verify_twin_ownership(twin_id, user)` in all router endpoints.

## 3. Verification & Provenance
- **Rule**: All answers from the twin must cite a source from the Knowledge Base.
- **Enforcement**: Response generation logic must include `citation_metadata`.

## 4. Human-in-the-Loop (Actions)
- **Rule**: Destructive or high-regret actions (Email, DB Delete, Asset Transfer) MUST be drafted and require owner approval.
- **Enforcement**: `ActionDraftSchema` must be used; never execute immediately unless explicitly white-listed.

## 5. Audit Compliance
- **Rule**: All state changes must be captured in the `audit_logs` table.
- **Enforcement**: Use `log_audit_event()` helper in business logic.
