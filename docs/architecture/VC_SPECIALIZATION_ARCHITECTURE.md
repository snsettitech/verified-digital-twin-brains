# VC Specialization Architecture

This document is a historical architecture note, not the current runtime contract.

## Current Runtime Behavior

- VC-specialized twins are handled through the shared specialization system.
- There is no active `ENABLE_VC_ROUTES` feature flag.
- There is no dedicated `/api/vc/*` router registered in `backend/main.py`.
- Current specialization routes live in `backend/routers/specializations.py`.

## Historical Context

The repository previously explored a VC-only route surface behind a dedicated rollout flag.
That route model has been retired in favor of shared specialization endpoints, while the VC specialization content itself remains available through the standard specialization runtime.

## Current References

Use these files for the live architecture:

- `backend/main.py`
- `backend/routers/specializations.py`
- `docs/architecture/system-overview.md`
- `docs/architecture/codebase-summary.md`
- `docs/restructure/BACKEND_ROUTE_INVENTORY.md`
