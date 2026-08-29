# VC Specialization Historical Summary

This document is retained as historical context for an older VC-specific route
surface.

## Current Status

- `backend/main.py` no longer reads `ENABLE_VC_ROUTES`.
- The backend no longer registers `/api/vc/*` routes.
- VC specialization logic, if still used, is reached through the shared
  specialization APIs instead of a dedicated VC router.

## Historical Note

Earlier implementations described a conditional `backend/api/vc_routes.py`
mount and a rollout flag for VC-only endpoints. That route gate has been
removed as stale cleanup. Use git history if you need the original rollout
design details.
