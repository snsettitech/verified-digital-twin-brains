# VC Specialization Implementation Summary

**Status:** Historical reference only

## Current State

- The earlier VC-only router and VC-specific specialization assets have been removed from the current repository.
- Shared specialization support remains limited to the active vanilla specialization path.
- There is no live VC-route runtime flag in the active backend startup path.

## Why This File Exists

This document is retained to preserve historical context about the earlier VC specialization effort without presenting it as current runtime behavior.

## Current Guidance

- Treat VC-specific route wiring here as superseded.
- Use `docs/restructure/BACKEND_ROUTE_INVENTORY.md` and `backend/main.py` as the source of truth for current router registration.
