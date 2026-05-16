# VC Specialization Architecture

This document is preserved as a short historical note so active architecture docs do not describe a retired VC-only router path as current behavior.

## Current Architecture

- Specialization selection still flows through the shared specialization system under `backend/modules/specializations/`.
- Runtime specialization endpoints are mounted by `backend/routers/specializations.py`.
- There is no active `/api/vc/*` router registration in `backend/main.py`.
- VC-specific behavior, where still relevant, must be expressed through the shared specialization surfaces rather than a separate env-gated route family.

## Historical Context

Earlier architecture drafts described:

- lazy loading for the VC specialization
- a dedicated `/api/vc/*` router
- the `ENABLE_VC_ROUTES` environment flag

Those details are no longer part of the active runtime contract. Use current route inventories and `backend/main.py` as the source of truth.
