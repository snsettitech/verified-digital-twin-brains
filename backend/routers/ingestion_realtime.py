"""
Realtime ingestion compatibility router.

This module keeps the realtime-ingestion feature flag path valid even when
full streaming ingestion infrastructure is not deployed in the environment.
"""

from __future__ import annotations

import os
from fastapi import APIRouter


router = APIRouter(tags=["ingestion-realtime"])


@router.get("/ingestion/realtime/health")
async def realtime_ingestion_health() -> dict:
    """Lightweight health endpoint for realtime ingestion feature wiring."""
    return {
        "status": "ok",
        "feature": "realtime_ingestion",
        "enabled": os.getenv("ENABLE_REALTIME_INGESTION", "true").lower() == "true",
        "mode": "compat",
    }


@router.get("/ingestion/realtime/config")
async def realtime_ingestion_config() -> dict:
    """Expose minimal realtime ingestion runtime config for diagnostics."""
    return {
        "enabled": os.getenv("ENABLE_REALTIME_INGESTION", "true").lower() == "true",
        "compat_router": True,
    }

