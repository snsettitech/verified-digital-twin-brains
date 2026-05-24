# VC Specialization Implementation Summary

> Historical reference: this file summarizes an older rollout that included a dedicated VC router behind `ENABLE_VC_ROUTES`. That runtime gate has been removed.

## Current State

- VC specialization support still exists through the shared specialization system.
- VC-specific manifests and specialization classes remain in `backend/modules/specializations/vc/`.
- `backend/main.py` does not include a dedicated VC-only router, and the application does not mount `/api/vc` endpoints.

## Legacy Notes

- Older implementation notes about `backend/api/vc_routes.py`, `ENABLE_VC_ROUTES`, and `VC_ROUTES_ENABLED` should be treated as retired design history.
- Keeping this file as a stub prevents those older references from being mistaken for current operator guidance.

## Source Of Truth

For the live system, prefer:

- `backend/main.py`
- `backend/routers/specializations.py`
- `docs/architecture/system-overview.md`
- `docs/architecture/codebase-summary.md`
