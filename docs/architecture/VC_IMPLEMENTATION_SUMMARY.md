# VC Specialization Implementation Summary

**Status:** Current reference
**Purpose:** Summarize the retired state of the old VC-specific surface after stale flag cleanup.

## Current State

- There is no active VC specialization implementation in the current backend.
- The backend does not mount a dedicated `/api/vc` router.
- `ENABLE_VC_ROUTES` and `VC_ROUTES_ENABLED` are not live runtime controls.
- `backend/modules/specializations/registry.json` currently lists only `vanilla`.
- Non-`vanilla` specialization requests normalize back to `vanilla`.

## Why This Changed

- Repository cleanup confirmed there is no live `backend/api/vc_routes.py` surface.
- The remaining `ENABLE_VC_ROUTES` wiring in `backend/main.py` was dead startup-summary plumbing only.
- Active docs now describe the current vanilla-only runtime instead of the removed VC router design.

## Verification Pointers

- `backend/main.py`
- `backend/tests/test_route_contract_aliases.py`
- `docs/architecture/codebase-summary.md`
- `docs/architecture/system-overview.md`

## Historical Context

Older VC-router design details have been intentionally removed from this active architecture page. Use git history if you need to inspect the retired `/api/vc` design.
