# VC Specialization Architecture

This document is kept as a historical reference.

The live backend no longer contains a dedicated `backend/api/vc_routes.py` router or an `ENABLE_VC_ROUTES` gate in `backend/main.py`. VC-specific behavior now flows through the shared specialization system:

- manifests and specialization loading in `backend/modules/specializations/`
- fallback logic in `backend/modules/_core/registry_loader.py`
- shared config endpoints in `backend/routers/specializations.py`

For current runtime behavior, use these docs instead:

- `docs/architecture/system-overview.md`
- `docs/architecture/codebase-summary.md`
- `docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md`
