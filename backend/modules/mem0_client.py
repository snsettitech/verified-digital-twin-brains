from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.request
from typing import Any, Dict, List, Optional

from modules.memory_provider import MemoryRecallItem, MemoryProvider, NoopMemoryProvider


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y"}


MEM0_ENABLED = _flag("MEM0_ENABLED", "false")
MEM0_READ_ENABLED = _flag("MEM0_READ_ENABLED", "false")
MEM0_PREFS_ONLY_ENABLED = _flag("MEM0_PREFS_ONLY_ENABLED", "true")
MEM0_ENDPOINT = os.getenv("MEM0_ENDPOINT", "").strip()
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "").strip()
MEM0_TIMEOUT_SECONDS = float(os.getenv("MEM0_TIMEOUT_SECONDS", "3.0"))
MEM0_BREAKER_FAILURE_THRESHOLD = int(os.getenv("MEM0_BREAKER_FAILURE_THRESHOLD", "3"))
MEM0_BREAKER_COOLDOWN_SECONDS = float(os.getenv("MEM0_BREAKER_COOLDOWN_SECONDS", "45"))

_MEM0_CLIENT_SINGLETON: Optional["Mem0Client"] = None


class Mem0Client(MemoryProvider):
    provider_name = "mem0"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str = "",
        timeout_seconds: float = MEM0_TIMEOUT_SECONDS,
        failure_threshold: int = MEM0_BREAKER_FAILURE_THRESHOLD,
        cooldown_seconds: float = MEM0_BREAKER_COOLDOWN_SECONDS,
    ) -> None:
        self._endpoint = endpoint.strip()
        self._api_key = api_key.strip()
        self._timeout_seconds = max(0.5, float(timeout_seconds))
        self._failure_threshold = max(1, int(failure_threshold))
        self._cooldown_seconds = max(5.0, float(cooldown_seconds))
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _circuit_open(self) -> bool:
        return time.time() < self._circuit_open_until

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._circuit_open_until = time.time() + self._cooldown_seconds

    def _build_request_payload(self, *, twin_id: str, query: str, limit: int) -> Dict[str, Any]:
        return {
            "twin_id": twin_id,
            "query": query,
            "limit": max(1, min(limit, 10)),
            "memory_type": "preference" if MEM0_PREFS_ONLY_ENABLED else None,
        }

    def _parse_items(self, payload: Any, *, limit: int) -> List[MemoryRecallItem]:
        if not isinstance(payload, dict):
            return []
        values = payload.get("items")
        if not isinstance(values, list):
            values = payload.get("memories")
        if not isinstance(values, list):
            return []

        items: List[MemoryRecallItem] = []
        for raw in values:
            if not isinstance(raw, dict):
                continue
            memory_type = str(raw.get("memory_type") or raw.get("type") or "").strip().lower()
            if not memory_type:
                memory_type = "preference"
            if MEM0_PREFS_ONLY_ENABLED and memory_type != "preference":
                continue
            value = str(raw.get("value") or raw.get("text") or "").strip()
            if not value:
                continue
            source_label = str(raw.get("source_label") or "mem0").strip().lower()
            items.append(
                MemoryRecallItem(
                    memory_type=memory_type,
                    value=value,
                    source_label=source_label or "mem0",
                    metadata=dict(raw.get("metadata") or {}),
                )
            )
            if len(items) >= max(1, limit):
                break
        return items

    def _http_recall(self, *, twin_id: str, query: str, limit: int) -> List[MemoryRecallItem]:
        payload = self._build_request_payload(twin_id=twin_id, query=query, limit=limit)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            method="POST",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
            },
        )
        with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
            raw_body = resp.read().decode("utf-8")
        decoded = json.loads(raw_body) if raw_body else {}
        return self._parse_items(decoded, limit=limit)

    async def recall_preferences(
        self,
        *,
        twin_id: str,
        query: str,
        limit: int = 3,
    ) -> List[MemoryRecallItem]:
        if not MEM0_ENABLED or not MEM0_READ_ENABLED:
            return []
        if not self._endpoint:
            return []
        if self._circuit_open():
            return []

        try:
            items = await asyncio.to_thread(
                self._http_recall,
                twin_id=twin_id,
                query=query,
                limit=limit,
            )
            self._record_success()
            return items
        except Exception:
            self._record_failure()
            return []


def get_memory_provider() -> MemoryProvider:
    global _MEM0_CLIENT_SINGLETON
    if not MEM0_ENABLED or not MEM0_READ_ENABLED:
        return NoopMemoryProvider()
    if _MEM0_CLIENT_SINGLETON is None:
        _MEM0_CLIENT_SINGLETON = Mem0Client(
            endpoint=MEM0_ENDPOINT,
            api_key=MEM0_API_KEY,
        )
    return _MEM0_CLIENT_SINGLETON

