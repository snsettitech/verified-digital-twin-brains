# VC Specialization Architecture

**Status:** Current reference
**Purpose:** Describe the active architecture for VC specialization support.

## Current State

- VC support is implemented as a specialization, not as a dedicated router family.
- Runtime behavior is loaded through the specialization registry and lazy specialization loading.
- The backend does not expose `/api/vc` endpoints.
- `ENABLE_VC_ROUTES` is no longer a supported runtime flag.

## Architecture Notes

### Loading Model

- `backend/modules/specializations/registry.json` lists the VC specialization.
- `backend/modules/specializations/registry_loader.py` applies vanilla fallback behavior if VC-specific loading fails.
- `get_specialization("vc")` resolves VC behavior only when that specialization is requested.

### Operational Guidance

- Use the standard specialization surfaces exposed by `backend/routers/specializations.py`.
- Do not expect a VC-only route toggle or a dedicated VC upload endpoint.
- Verify absence of the retired router surface with `backend/tests/test_route_contract_aliases.py`.

## Related Docs

- `docs/architecture/codebase-summary.md`
- `docs/architecture/system-overview.md`
- `backend/main.py`

## Historical Context

Older design notes for a dedicated `/api/vc` router were intentionally removed from this active page during stale flag cleanup. Consult git history if you need the retired design details.
