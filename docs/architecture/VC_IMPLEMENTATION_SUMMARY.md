# VC Specialization Integration Summary

This document is kept as a historical reference for the older VC-specialization rollout work.

## Current State

- VC specialization metadata still exists in the specialization registry.
- Active runtime behavior uses the shared specialization endpoints in `backend/routers/specializations.py`.
- The legacy VC-only `/api/vc/*` router is not registered in `backend/main.py`.
- `ENABLE_VC_ROUTES` is no longer part of the active runtime configuration surface.

## Historical Scope

The original implementation work in this area focused on:

- adding VC specialization registry entries
- keeping vanilla specialization fallback behavior safe
- documenting an env-gated VC-only router path that is no longer active

Refer to git history if you need the full implementation narrative for that retired router design.
