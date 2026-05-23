# VC Implementation Summary

This file is a historical summary of an earlier VC-specific routing design.

Current state:

- there is no live `backend/api/vc_routes.py`
- there is no live `ENABLE_VC_ROUTES` startup flag in `backend/main.py`
- VC specialization data is still supported through the shared specialization registry and config endpoints

Use the current architecture and operations docs for active behavior:

- `docs/architecture/system-overview.md`
- `docs/architecture/codebase-summary.md`
- `docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md`
