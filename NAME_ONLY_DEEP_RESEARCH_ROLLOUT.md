# Name-Only Deep Research Rollout Notes

## Migration Order
1. `backend/database/migrations/migration_name_only_deep_research.sql`

No existing table mutations are required; migration is additive-only.

## Runtime Flags
- `NAME_ONLY_DEEP_RESEARCH_ENABLED=false` (default)
- `OPENAI_DEEP_RESEARCH_MODEL=o3` (preferred, service falls back if unavailable)

## Safe Enablement Plan
1. Apply migration in staging.
2. Deploy backend + frontend with `NAME_ONLY_DEEP_RESEARCH_ENABLED=false`.
3. Run smoke test:
   - `AUTH_TOKEN=<token> BASE_URL=<staging-api> python scripts/smoke_test_name_only_deep_research.py`
4. Enable `NAME_ONLY_DEEP_RESEARCH_ENABLED=true` in staging.
5. Re-run smoke test and validate result JSON citations.
6. Promote same config to production.

## Rollback
1. Set `NAME_ONLY_DEEP_RESEARCH_ENABLED=false`.
2. Redeploy services.
3. Optional hard rollback (data-destructive):
   - Drop `name_deep_research_artifacts`, `name_deep_research_pages`, `name_deep_research_sources`, `name_deep_research_runs`.

Feature rollback does not require dropping tables.
