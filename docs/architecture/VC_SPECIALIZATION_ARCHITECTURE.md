# VC Specialization Architecture

Historical reference for the original VC-specific rollout design.

## Current State

- The live backend no longer exposes a separate VC router.
- The retired VC-only route gate is gone from `backend/main.py`.
- VC twins use the shared specialization manifests and standard twin routes:
  - `/specializations`
  - `/specializations/{id}/manifest`
  - `/twins/{twin_id}/specialization`

## What Still Matters

- VC specialization assets still live under `backend/modules/specializations/vc/`.
- Specialization loading remains lazy and falls back safely to vanilla behavior.
- Shared specialization routes are the canonical integration surface for VC-specific behavior.

## Where To Look Instead

- `docs/architecture/system-overview.md`
- `docs/architecture/codebase-summary.md`
- `backend/modules/specializations/`
