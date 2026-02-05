# Governance & Security

The platform's safety is managed through a layered approach of codebase-level guards and automated AI safety hooks.

## 1. Security Decorators (Guards)
Most endpoints in `backend/routers` use FastAPI `Depends()` for security:
- `get_current_user`: Base authentication (JWT/API Key).
- `verify_tenant_access`: Checks if the user belongs to the requested `tenant_id`.
- `verify_twin_ownership`: Verifies the requested `twin_id` is owned by the user's tenant.
- `verify_owner`: Restricts endpoints to tenant administrators.

## 2. AI Safety Gate (Stop-Hook)
Before any AI-generated change is committed, the `scripts/ai-stop-hook.py` orchestrator runs:
- **Quality Gate**: Runs linting and unit tests to prevent regression.
- **Governance Gate**: Static analysis to ensure:
  - All router endpoints use mandatory security guards.
  - No Supabase queries lack `tenant_id` or `twin_id` filters.
  - No unsafe direct DB access is introduced.

## 3. Deployment Safety
- **Isolation**: Tenant data is logically isolated via `tenant_id` filters in Postgres.
- **Secrets**: API keys and database credentials are managed via environment variables and never committed.
- **Audit**: The `/metrics/audit` endpoints provide visibility into all governed activities.
