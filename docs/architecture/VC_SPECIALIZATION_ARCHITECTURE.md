# VC Specialization Architecture

**Status:** Current runtime behavior

## Summary

VC support exists as a specialization surfaced through the shared specialization registry and shared specialization endpoints. There is no dedicated VC-only router or `ENABLE_VC_ROUTES` startup gate in the live backend.

## Current Design

### Specialization Loading

- VC remains an optional specialization selected by `twins.specialization_id`.
- The backend resolves specialization behavior through the shared registry and manifest system.
- VC-specific code is loaded only when VC specialization data is requested.

### API Surface

- Shared specialization endpoints remain the public contract:
  - `GET /config/specialization`
  - `GET /config/specializations`
  - `GET /twins/{twin_id}/specialization`
- These endpoints work for both vanilla and VC twins.
- There is no separate `/api/vc/...` route family in the current backend.

### Reliability Properties

- Vanilla behavior is not coupled to a VC-only router import path.
- VC failures can still fall back through the shared specialization loading path.
- Startup configuration is simpler because there is no VC route toggle to keep aligned across environments.

## Operational Notes

- Deployments do not need an `ENABLE_VC_ROUTES` environment variable.
- Verification for VC should focus on specialization resolution and manifest loading, not route registration.

## Recommended Verification

1. Request `/config/specializations` and confirm VC is present in the specialization catalog if expected.
2. Request `/twins/{twin_id}/specialization` for a VC twin and confirm the VC manifest resolves correctly.
3. Request the same endpoint for a vanilla twin and confirm vanilla behavior is unchanged.

## Related Files

- `backend/routers/specializations.py`
- `backend/modules/specializations/registry.json`
- `backend/modules/specializations/registry.py`
- `backend/modules/_core/registry_loader.py`
