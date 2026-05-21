# VC Specialization Architecture - Historical Note

This file is a short historical reference for the VC specialization design.

Older versions of the system used a dedicated `/api/vc/*` router gated by `ENABLE_VC_ROUTES`. That routing model has been removed from the live app. VC-specific behavior now flows through the same shared specialization contracts used by other specializations:

- `GET /config/specialization`
- `GET /config/specializations`
- `GET /twins/{twin_id}/specialization`

The current architecture keeps the specialization assets under `backend/modules/specializations/vc` and resolves them through the shared registry and manifest loader rather than a VC-only router gate.

Use these documents for the current source of truth:

- `docs/restructure/BACKEND_ROUTE_INVENTORY.md`
- `docs/architecture/system-overview.md`
- `backend/routers/specializations.py`
