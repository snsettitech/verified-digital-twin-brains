# VC Specialization Architecture

## Status

Historical reference. This document used to describe a dedicated VC-only route surface gated by `ENABLE_VC_ROUTES`.

## Current State

- The dedicated `ENABLE_VC_ROUTES` gate has been removed from `backend/main.py`.
- The shared `specializations` router remains the live specialization entrypoint.
- VC specialization assets still live under `backend/modules/specializations/vc/`.
- Specialization loading still relies on lazy loading plus vanilla fallback behavior.

## Why This Stub Exists

The original design notes are still useful for understanding how VC specialization assets were organized, but they no longer describe the live route-registration model. Treat any older references to `backend/api/vc_routes.py` or `ENABLE_VC_ROUTES` as historical only.

## Source Of Truth

Use these files for current behavior:

- `backend/main.py`
- `backend/routers/specializations.py`
- `backend/modules/_core/registry_loader.py`
- `backend/modules/specializations/registry.json`
