# VC Specialization Integration Summary

Historical reference for the earlier VC-specific route rollout work.

## Current State

- The live application does not register a dedicated VC router.
- `backend/main.py` no longer reads the retired VC-only route gate.
- VC specialization behavior is served through shared specialization manifests and twin configuration routes.

## Surviving Integration Points

- `backend/modules/specializations/registry.json`
- `backend/modules/specializations/vc/`
- `backend/modules/specializations/registry_loader.py`
- Shared specialization endpoints in `backend/routers/specializations.py`

## Notes

- Keep this document only as historical context for how VC assets were introduced.
- For current runtime behavior, prefer `docs/architecture/system-overview.md` and `docs/architecture/codebase-summary.md`.
