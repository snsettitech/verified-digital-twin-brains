# Dependency And Reference Notes

## Frontend Packages

### Strong Candidate

- `@playwright/test` is currently in `dependencies`, but all references are in Playwright configs and tests.
  - Recommended follow-up: move it to `devDependencies`.
  - Not changed in this cleanup because it updates `package-lock.json` and deserves its own small review.

### No Other Obvious Safe Removals

- `next`, `react`, `react-dom`, `@supabase/*`, `react-markdown`, `remark-gfm`, and `zod` all have direct runtime references.

## Backend Packages

No dependency in `backend/requirements.txt` was removed in this cleanup.

Reasons:

- the backend mixes API runtime, worker runtime, ingestion, vector search, deep research, voice, and observability in one install surface
- many heavy providers are optional at runtime but still valid for supported features
- safe package reduction likely requires a deliberate split between runtime, worker, ML, and manual tooling requirements

## Packages That Probably Belong In Dev/Test Tooling

- frontend: `@playwright/test`
- backend follow-up candidate set if requirements are ever split:
  - evaluation-only/model-benchmark packages associated with manual harnesses
  - optional local embedding/runtime extras currently mixed into the main install surface

## Files Still Suspicious After Cleanup

- `backend/routers/products.py`
- `backend/modules/memory.py`
- `backend/modules/prompt_manager.py`
- `backend/modules/few_shot_prompting.py`
- `backend/modules/query_rewrite_evaluator.py`
- `backend/modules/chunking_evaluator.py`
- `backend/modules/chunking_integration.py`
- `backend/modules/exa_web_verification_integration.py`
- `backend/modules/graph_memory_metrics.py`
- manual verification clusters under `backend/scripts/`, backend root `verify_*.py`, and `frontend/scripts/*.mjs`

## Reference Scan Notes

- frontend cleanup targeted only files with zero import references plus no package/workflow wiring
- backend cleanup did not delete zero-reference modules automatically because many look like manual evaluation harnesses rather than accidental dead code
- the repo still has some hardcoded local/prod URL fallbacks in source; these are tracked as hygiene warnings rather than dependency issues
