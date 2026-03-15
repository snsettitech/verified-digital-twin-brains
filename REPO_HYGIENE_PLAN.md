# Repo Hygiene Plan

## Objectives

- keep the root focused on canonical docs and runtime/config directories
- stop tracking generated/debug/proof residue
- separate stable source from manual verification utilities
- make local startup paths obvious
- add CI guardrails that catch the categories of clutter removed here

## Executed

### Tracked junk removed from version control

- backend model cache files under `backend/.model_cache/`
- backend eval outputs, audit dumps, debug logs, test token, chunking eval outputs
- frontend dev log, lint output, Playwright HTML report, test-result residue, temporary Playwright config/specs
- `.agent/mcp.json` untracked and replaced with `.agent/mcp.example.json`

### Confirmed-unused code removed

- unimported frontend components, barrel files, unused hook/types helper, unused server Supabase helper
- obsolete `frontend/scripts/enforce-no-twin.*`, superseded by `frontend/scripts/enforce-single-twin.js`

### Root/doc cleanup

- archived intermediate cleanup notes under `docs/archive/repo-cleanup/`
- replaced stale boilerplate/stale-link docs with canonical repo docs

### Guardrails tightened

- `.gitignore` expanded for backend audit outputs, temporary frontend specs/config, lint output, and TS build state
- `.github/workflows/repo-hygiene.yml` rewritten to:
  - fail on tracked ignored files
  - fail on forbidden committed junk outside `docs/archive/`
  - warn on hardcoded local/deployment URLs in source
  - fail on unexpected root-level markdown clutter

## Left Intentionally Untouched

- `backend/scripts/` manual/admin utilities
- backend root `verify_*.py` and quick-check scripts
- backend modules with zero reverse references but plausible manual/eval use
- frontend probe scripts under `frontend/scripts/` that still appear to support manual verification

## Remaining Follow-Up

1. Decide whether `backend/scripts/` should be split into `tools/manual_verify/backend/` and `scripts/automation/`.
2. Decide whether unused backend evaluation/legacy modules should be archived out of `backend/modules/`.
3. Decide whether to remove hardcoded public URL fallbacks from `frontend/next.config.ts`.
