# VC Specialization Implementation Summary

**Status:** Current reference
**Purpose:** Summarize the active VC specialization shape after stale route-flag cleanup.

## Current State

- VC behavior is specialization-driven through `backend/modules/specializations/vc/`.
- The backend does not mount a dedicated `/api/vc` router.
- `ENABLE_VC_ROUTES` and `VC_ROUTES_ENABLED` are not live runtime controls.
- VC loading is handled through the specialization registry and lazy loading.

## Why This Changed

- Repository cleanup confirmed there is no live `backend/api/vc_routes.py` surface.
- The remaining `ENABLE_VC_ROUTES` wiring in `backend/main.py` was dead startup-summary plumbing only.
- Active docs now describe the current runtime contract instead of the removed router design.

## Verification Pointers

- `backend/main.py`
- `backend/tests/test_route_contract_aliases.py`
- `docs/architecture/codebase-summary.md`
- `docs/architecture/system-overview.md`

## Historical Context

Older VC-router design details have been intentionally removed from this active architecture page. Use git history if you need to inspect the retired `/api/vc` design.
