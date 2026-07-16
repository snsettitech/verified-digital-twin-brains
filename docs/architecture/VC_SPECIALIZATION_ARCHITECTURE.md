# VC Specialization Architecture (Historical Reference)

## Status

This repository no longer exposes a dedicated VC-only router or a VC-specific route rollout gate.

## What Still Exists

- VC specialization assets still live under `backend/modules/specializations/vc/`.
- VC twins still resolve through the shared specialization router mounted from `backend/routers/specializations.py`.
- Specialization manifests and runtime behavior still rely on lazy loading and vanilla-safe fallback patterns.

## Why This Document Was Reduced

An older version of this document described a separate VC route surface that could be toggled independently from the rest of the backend. That route surface has been removed as stale plumbing, so keeping the old design narrative would misstate current runtime behavior.

## Current Source Of Truth

- `backend/main.py`
- `backend/routers/specializations.py`
- `docs/architecture/codebase-summary.md`
