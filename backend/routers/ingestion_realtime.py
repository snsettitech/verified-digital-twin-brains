"""
Realtime ingestion compatibility router.

This module keeps the realtime-ingestion feature flag path valid even when
full streaming ingestion infrastructure is not deployed in the environment.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(tags=["ingestion-realtime"])


@router.get("/ingestion/realtime/health")
async def realtime_ingestion_health() -> dict:
    """Lightweight health endpoint for the always-on realtime route surface."""
    return {
        "status": "ok",
        "feature": "realtime_ingestion",
        "enabled": True,
        "mode": "compat",
    }


@router.get("/ingestion/realtime/config")
async def realtime_ingestion_config() -> dict:
    """Expose minimal realtime ingestion runtime config for diagnostics."""
    return {
        "enabled": True,
        "compat_router": True,
    }

