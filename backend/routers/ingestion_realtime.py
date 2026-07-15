"""
Realtime ingestion compatibility router.

This module keeps the launched realtime-ingestion route surface mounted even
when full streaming ingestion infrastructure is not deployed in the environment.
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

