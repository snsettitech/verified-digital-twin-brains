# VC Specialization Integration Summary

**Status:** Historical reference only

## Current Runtime State

- `ENABLE_VC_ROUTES` is no longer part of the live backend configuration surface.
- `backend/api/vc_routes.py` is not registered by the current FastAPI app.
- The active backend keeps the shared specialization manifest endpoints and vanilla fallback behavior only.

## Historical Summary

Earlier iterations of the VC specialization work explored three ideas:

1. Registry-based specialization metadata.
2. Lazy specialization loading for non-default paths.
3. A dedicated VC router protected by `ENABLE_VC_ROUTES`.

Only the shared specialization infrastructure remains relevant today. The dedicated VC route gate was removed because no live VC router surface remained behind it.

## How To Use This Document

- Use this file as a short historical note when reading older commits or archived design discussions.
- Do not use it as operator guidance for environment variables, route checks, or deployment behavior.
- If a VC-specific route surface is reintroduced later, document it with a new spec and rollout plan instead of restoring the retired flag contract described in old history.
