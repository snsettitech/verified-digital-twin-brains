"""Shared repository helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def is_empty_lookup_error(exc: Exception) -> bool:
    code = str(getattr(exc, "code", "") or "").strip()
    message = str(exc)
    return code in {"204", "404", "406"} or "Missing response" in message
