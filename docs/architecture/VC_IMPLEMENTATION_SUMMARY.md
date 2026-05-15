# VC Implementation Summary

This document is kept as a historical reference only.

## Current Status

- There is no dedicated VC-only router mounted in `backend/main.py`.
- The legacy `ENABLE_VC_ROUTES` rollout flag has been removed.
- VC-specialized twins use the shared specialization routes, including:
  - `/specializations`
  - `/config/specialization`
  - `/config/specializations`
  - `/twins/{twin_id}/specialization`

## Why This File Still Exists

Earlier iterations of the product explored a separate `/api/vc/*` surface behind a dedicated rollout flag.
That implementation is no longer the live architecture, but the historical notes remain useful for understanding past design decisions.

## Source Of Truth

For current backend routing and specialization behavior, use:

- `backend/main.py`
- `backend/routers/specializations.py`
- `docs/architecture/codebase-summary.md`
- `docs/architecture/system-overview.md`
