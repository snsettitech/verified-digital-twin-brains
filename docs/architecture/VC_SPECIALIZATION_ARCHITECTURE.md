# VC Specialization Architecture

This file is now a historical reference for the retired VC-only route gate.

## Current Runtime Behavior

- `backend/main.py` no longer exposes an `ENABLE_VC_ROUTES` flag.
- No dedicated `/api/vc/*` endpoints are mounted at startup.
- Shared specialization endpoints such as `/config/specialization`,
  `/config/specializations`, and `/twins/{twin_id}/specialization` remain the
  supported route surface for specialization metadata.

## Historical Context

Earlier versions of the product used a dedicated `backend/api/vc_routes.py`
module plus an `ENABLE_VC_ROUTES` rollout flag to protect VC-specific
endpoints. That conditional route surface was removed after rollout cleanup
because the gate no longer controlled any live behavior.

If you need the original implementation details, review git history rather
than relying on this document as current runtime guidance.
