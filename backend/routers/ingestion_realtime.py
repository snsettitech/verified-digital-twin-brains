"""
Realtime ingestion compatibility router.

This module provides always-on compatibility diagnostics for the launched
realtime-ingestion surface without requiring the full streaming pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(tags=["ingestion-realtime"])


@router.get("/ingestion/realtime/health")
async def realtime_ingestion_health() -> dict:
    """Lightweight health endpoint for realtime ingestion feature wiring."""
    return {
        "status": "ok",
        "feature": "realtime_ingestion",
        "enabled": True,
        "mode": "compat",
        "route_registered": True,
    }


@router.get("/ingestion/realtime/config")
async def realtime_ingestion_config() -> dict:
    """Expose minimal realtime ingestion runtime config for diagnostics."""
    return {
        "enabled": True,
        "compat_router": True,
        "route_registered": True,
    }

