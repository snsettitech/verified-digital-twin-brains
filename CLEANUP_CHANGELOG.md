# Cleanup Changelog

## 2026-03-10

### Removed From Version Control

- `.agent/mcp.json` was untracked because it is local credentialed config; `.agent/mcp.example.json` is now the tracked template.
- deleted tracked cache, debug, proof, and temp outputs from `backend/`:
  - model cache files
  - eval result JSONs
  - chunking eval reports
  - system audit dumps
  - debug logs and debug JSON outputs
  - local test token and repro scratch files
- deleted tracked generated frontend residue:
  - `frontend/devserver.log`
  - `frontend/lint-output.json`
  - Playwright HTML/report output
  - `frontend/test-results/**`
  - temporary Playwright specs/config under `frontend/tests/tmp/` and `frontend/playwright.tmp.config.cjs`

### Removed Confirmed-Unused Frontend Code

- deleted unreferenced components:
  - `frontend/components/Brain/BrainGraph.tsx`
  - `frontend/components/Chat/ChatWidget.tsx`
  - `frontend/components/Chat/InterviewInterface.tsx`
  - `frontend/components/FeedbackWidget.tsx`
  - `frontend/components/TILFeed.tsx`
  - onboarding remnants under `frontend/components/onboarding/steps/`
- deleted unused barrel files under:
  - `frontend/components/`
  - `frontend/contexts/`
  - `frontend/lib/`
- deleted unused frontend helper/type files:
  - `frontend/lib/hooks/useChatGating.ts`
  - `frontend/lib/supabase/server.ts`
  - `frontend/lib/types/api.contract.ts`
  - `frontend/lib/types/link-first.ts`
- deleted obsolete `frontend/scripts/enforce-no-twin.js` and `frontend/scripts/enforce-no-twin.sh`

### Archived

- moved prior intermediate cleanup notes to `docs/archive/repo-cleanup/`:
  - `CLEANUP_INVENTORY.md`
  - `CLEANUP_RISKS.md`
  - `DEPENDENCY_NOTES.md`

### Documentation And Debugging

- rewrote `README.md` to point at canonical docs with relative links
- replaced stale `docs/quick-start.md`
- replaced `frontend/README.md` boilerplate with project-specific notes
- added:
  - `REPO_MAP.md`
  - `RUNTIME_ENTRYPOINTS.md`
  - `UNUSED_CODE_AUDIT.md`
  - `REPO_HYGIENE_PLAN.md`
  - `DEBUG_RUNBOOK.md`
  - `ENV_AUDIT.md`
  - `DEPENDENCY_AND_REFERENCE_NOTES.md`

### Startup And Guardrails

- updated `scripts/dev.ps1` and `scripts/dev.sh` to use repo-root `.env` and `frontend/.env.local`
- tightened `.gitignore` for backend audit outputs, frontend temp tests/config, lint output, and TS build state
- replaced `.github/workflows/repo-hygiene.yml` with a version that:
  - fails on tracked ignored files
  - fails on forbidden committed junk outside `docs/archive/`
  - warns on hardcoded local/deployment URLs in source
  - fails on unexpected root-level markdown clutter

### Left Untouched On Purpose

- backend modules and scripts that look unused but still require owner review
- `backend/routers/products.py`, because frontend still calls the route surface even though the router is not registered
- hardcoded URL fallbacks in `frontend/next.config.ts`, flagged but not changed in this cleanup
