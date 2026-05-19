# VC Implementation Summary

This document is kept as a historical reference.

## Current Status

- The old VC-specific FastAPI router is no longer part of the live backend app.
- `ENABLE_VC_ROUTES` is not a current runtime flag.
- Shared specialization configuration endpoints remain available through `backend/routers/specializations.py`:
  - `GET /config/specialization`
  - `GET /config/specializations`
  - `GET /twins/{twin_id}/specialization`

## Historical Context

Earlier iterations of the product explored a VC-focused router and a dedicated rollout flag.
That implementation path has been retired in favor of the shared specialization surface.

## Operator Guidance

- Do not set or rely on `ENABLE_VC_ROUTES`.
- Use the shared specialization endpoints above for current backend behavior.
- Treat any remaining `api/vc_routes.py` references in archive documents as legacy design material only.
