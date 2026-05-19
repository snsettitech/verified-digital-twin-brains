# VC Specialization Architecture

This document is a historical note for a retired implementation path.

## Current Runtime Behavior

- The backend does not mount a dedicated VC router.
- `ENABLE_VC_ROUTES` has been removed from the live runtime configuration.
- Specialization-related behavior now flows through shared backend surfaces such as `backend/routers/specializations.py` and the specialization manifests under `backend/modules/specializations/`.

## Live Endpoints

Current specialization configuration endpoints:

- `GET /config/specialization`
- `GET /config/specializations`
- `GET /twins/{twin_id}/specialization`

## Historical Scope

Older plans described a VC-only route family and environment-gated rollout steps.
Those notes are retained only to explain prior architecture discussions and should not be used as current deployment guidance.
