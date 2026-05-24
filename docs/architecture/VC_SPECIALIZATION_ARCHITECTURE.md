# VC Specialization Architecture

> Historical reference: this document used to describe a dedicated VC router gated by `ENABLE_VC_ROUTES`. That router and flag have been removed.

## Current Runtime Model

- VC remains a specialization implemented under `backend/modules/specializations/vc/`.
- VC manifests and classes are still resolved through the specialization registry and lazy loading path.
- Shared specialization endpoints from `backend/routers/specializations.py` provide the live route surface for specialization config and manifests.
- `backend/main.py` no longer mounts any dedicated `/api/vc` router.

## What Changed

- Earlier iterations documented a conditional `backend/api/vc_routes.py` router behind `ENABLE_VC_ROUTES`.
- The repository no longer contains that router file.
- Feature-flag cleanup removed the dead startup flag plumbing once code usage showed the dedicated VC route branch was obsolete.

## How To Read Older References

- Mentions of `ENABLE_VC_ROUTES` or `VC_ROUTES_ENABLED` are legacy-only.
- Mentions of `/api/vc/*` endpoints describe a retired route surface, not the current application contract.
- For current architecture guidance, use `docs/architecture/system-overview.md`, `docs/architecture/codebase-summary.md`, `backend/main.py`, and `backend/routers/specializations.py`.
