# VC Specialization Integration - Historical Note

This document is retained as a historical reference for the earlier VC specialization workstream.

Current state:
- The current `backend/main.py` does not mount a dedicated VC-only router.
- There is no live VC route-registration feature flag in the current backend.
- VC specialization behavior that still exists is represented through specialization metadata and lazy loading, not a separate VC-only route surface.

If VC-specific runtime behavior is reintroduced, document it against the live router inventory in `docs/restructure/BACKEND_ROUTE_INVENTORY.md` and the current backend entrypoint in `backend/main.py`.
