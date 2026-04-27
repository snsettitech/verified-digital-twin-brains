"""
Realtime ingestion compatibility router.

This module exposes the lightweight realtime-ingestion diagnostics surface used
by operators even when the full streaming ingestion infrastructure is absent.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(tags=["ingestion-realtime"])


@router.get("/ingestion/realtime/health")
async def realtime_ingestion_health() -> dict:
    """Lightweight health endpoint for realtime ingestion wiring."""
    return {
        "status": "ok",
        "feature": "realtime_ingestion",
        # This surface is a compat shim, not proof that full streaming ingestion is live.
        "enabled": False,
        "mode": "compat",
        "route_registered": True,
    }


@router.get("/ingestion/realtime/config")
async def realtime_ingestion_config() -> dict:
    """Expose minimal realtime ingestion runtime config for diagnostics."""
    return {
        "enabled": False,
        "compat_router": True,
        "route_registered": True,
    }

