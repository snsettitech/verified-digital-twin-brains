# VC Specialization Implementation Summary

## Status

Historical reference. The dedicated VC route gate described in older implementation notes is no longer part of the live backend startup path.

## Current Runtime Summary

- `backend/main.py` no longer reads `ENABLE_VC_ROUTES`.
- There is no live VC-only router registration in the current app bootstrap.
- Specialization behavior is served through the shared `specializations` router and specialization manifests.
- VC-specific assets remain in the specialization module tree for historical and potential future reuse.

## Migration Note

If you are auditing older rollout work, interpret any mention of `ENABLE_VC_ROUTES` or `backend/api/vc_routes.py` as retired implementation detail rather than a current deployment requirement.

## Source Of Truth

- `backend/main.py`
- `backend/routers/specializations.py`
- `docs/restructure/BACKEND_ROUTE_INVENTORY.md`
