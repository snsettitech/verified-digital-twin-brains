# VC Specialization Integration - Historical Note

This document is preserved as historical context for the original VC specialization rollout.

The dedicated `ENABLE_VC_ROUTES` flag and `/api/vc/*` router described in older implementation notes are no longer part of the live backend. Current VC behavior relies on the shared specialization surface that stays mounted for all deployments:

- `GET /config/specialization`
- `GET /config/specializations`
- `GET /twins/{twin_id}/specialization`

The VC specialization itself still lives under `backend/modules/specializations/vc` and is loaded through the shared specialization registry and manifest flow.

For the current backend route surface, see `docs/restructure/BACKEND_ROUTE_INVENTORY.md`.
For the current platform overview, see `docs/architecture/system-overview.md`.
