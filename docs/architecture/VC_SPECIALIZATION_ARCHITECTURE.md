# VC Specialization Architecture - Historical Note

This file is intentionally reduced to a historical stub.

Current state:
- The repository still contains VC specialization concepts in the broader specialization system.
- The live backend does not mount a dedicated VC-only router.
- There is no current VC route-registration feature flag.

Use the current sources of truth when auditing behavior:
- `backend/main.py` for mounted routers
- `backend/modules/specializations/` for specialization loading
- `docs/restructure/BACKEND_ROUTE_INVENTORY.md` for the maintained route inventory
