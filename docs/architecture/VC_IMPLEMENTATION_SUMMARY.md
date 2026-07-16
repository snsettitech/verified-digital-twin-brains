# VC Specialization Integration Summary (Historical Reference)

## Status

The VC specialization still exists, but it now relies on the same shared specialization route surface as the rest of the product.

## Current Behavior

- VC manifests and specialization classes remain part of the specialization registry.
- Shared specialization endpoints stay mounted without any VC-only startup toggle.
- VC behavior is selected by specialization data, not by mounting a separate router.

## Why This Summary Changed

Earlier drafts documented a dedicated VC-only route path and an independent rollout mechanism. Those no longer exist in the live backend, so this file now serves only as historical context for the specialization module itself.

## Current Source Of Truth

- `backend/main.py`
- `backend/routers/specializations.py`
- `docs/architecture/codebase-summary.md`
