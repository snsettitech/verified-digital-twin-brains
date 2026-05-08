# VC Specialization Architecture

**Status:** Current reference
**Purpose:** Describe the retired state of the old VC-specific architecture surface.

## Current State

- No active VC specialization implementation ships in the current backend.
- The runtime is effectively vanilla-only.
- The backend does not expose `/api/vc` endpoints.
- `ENABLE_VC_ROUTES` is no longer a supported runtime flag.
- `backend/modules/specializations/registry.json` currently lists only `vanilla`.
- Non-`vanilla` specialization requests normalize back to vanilla.

## Architecture Notes

### Current Runtime Model

- `backend/modules/specializations/registry.json` lists only the vanilla specialization.
- `backend/modules/_core/registry_loader.py` normalizes non-`vanilla` requests back to the vanilla manifest.
- `backend/modules/specializations/registry.py` returns the vanilla specialization instance for all requests.

### Operational Guidance

- Use the standard specialization surfaces exposed by `backend/routers/specializations.py`.
- Do not expect a VC-only route toggle, a VC specialization directory, or a dedicated VC upload endpoint.
- Verify absence of the retired router surface with `backend/tests/test_route_contract_aliases.py`.

## Related Docs

- `docs/architecture/codebase-summary.md`
- `docs/architecture/system-overview.md`
- `backend/main.py`

## Historical Context

Older design notes for a dedicated `/api/vc` router were intentionally removed from this active page during stale flag cleanup. Consult git history if you need the retired design details.
