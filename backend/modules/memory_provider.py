from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass
class MemoryRecallItem:
    memory_type: str
    value: str
    source_label: str
    metadata: Dict[str, Any]


class MemoryProvider(Protocol):
    provider_name: str

    async def recall_preferences(
        self,
        *,
        twin_id: str,
        query: str,
        limit: int = 3,
    ) -> List[MemoryRecallItem]:
        ...


class NoopMemoryProvider:
    provider_name = "noop"

    async def recall_preferences(
        self,
        *,
        twin_id: str,
        query: str,
        limit: int = 3,
    ) -> List[MemoryRecallItem]:
        return []

