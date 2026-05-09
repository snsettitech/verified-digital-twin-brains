# VC Specialization Architecture

**Status:** Historical reference only

## Current Runtime State

- The live backend does not expose `ENABLE_VC_ROUTES`.
- The live backend does not register `backend/api/vc_routes.py`.
- Shared specialization behavior is served through `backend/routers/specializations.py`.
- Runtime specialization lookup falls back to the vanilla path when a VC-specific runtime surface is not present.

## What This Document Covers

This file preserves high-level context about an earlier VC-specific design direction. Older revisions used:

- a dedicated VC specialization entry in the registry layer
- lazy specialization loading so non-VC requests stayed on the vanilla path
- a separate VC route surface that was guarded behind `ENABLE_VC_ROUTES`

That dedicated VC router has since been retired as part of feature-flag cleanup and product simplification.

## Guidance

- Treat any remaining VC route examples in git history as implementation history, not current deployment guidance.
- If a VC-specific route surface needs to return, create a new design and rollout plan rather than reusing the retired flag contract.
