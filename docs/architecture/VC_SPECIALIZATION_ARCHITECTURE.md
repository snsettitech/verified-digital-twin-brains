# VC Specialization Architecture

This document is retained as historical reference.

## Current Status

- The shared specialization registry still exists.
- The dedicated VC-only route surface is no longer part of the live backend.
- Active backend behavior is documented in `backend/main.py`, `docs/architecture/system-overview.md`, and `docs/restructure/BACKEND_ROUTE_INVENTORY.md`.

## Historical Note

Earlier revisions described a dedicated VC upload router and its rollout flag. That route surface has been removed as part of feature-flag cleanup, so this file should not be used as an operator guide for current deployments.
