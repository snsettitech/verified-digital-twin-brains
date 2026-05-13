# VC Specialization Architecture

**Status:** Historical reference only

## Current State

- VC-only specialization assets are no longer present in the current repository.
- Shared specialization routes remain available through `backend/routers/specializations.py`.
- The older VC-only router flow is not part of the live backend registration path.

## Notes

Older versions of this document described a conditional VC router env gate. That runtime flag and router registration are no longer part of the active backend startup sequence.

For current behavior, use:

- `backend/main.py`
- `docs/restructure/BACKEND_ROUTE_INVENTORY.md`
- `docs/architecture/system-overview.md`
