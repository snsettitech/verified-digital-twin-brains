"""ADK-backed deep research service."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from adk_core.app import get_research_repository
from adk_core.runtime import run_research_pipeline
from adk_core.schemas.artifacts import ResearchArtifact

logger = logging.getLogger(__name__)


def is_name_only_deep_research_enabled() -> bool:
    return os.getenv("NAME_ONLY_DEEP_RESEARCH_ENABLED", "true").lower() == "true"


class NameDeepResearchService:
    """Creates and executes research runs against the new ADK runtime."""

    def __init__(self) -> None:
        self._repository = get_research_repository()

    def parse_artifact(self, payload: Dict[str, Any]) -> ResearchArtifact:
        return ResearchArtifact.model_validate(payload)

    async def create_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        name: str,
        hints: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        twin_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = self._repository.create_run(
            tenant_id=tenant_id,
            user_id=user_id,
            subject_name=name,
            twin_id=twin_id,
            hints=hints or {},
            idempotency_key=idempotency_key,
        )
        if row.get("status") in {"queued", "running"}:
            asyncio.create_task(
                self._execute_run(
                    run_id=row["id"],
                    tenant_id=tenant_id,
                    user_id=user_id,
                    subject_name=name,
                    twin_id=twin_id,
                    hints=hints or {},
                )
            )
        return row

    async def _execute_run(
        self,
        *,
        run_id: str,
        tenant_id: str,
        user_id: str,
        subject_name: str,
        twin_id: Optional[str],
        hints: Dict[str, Any],
    ) -> None:
        try:
            await run_research_pipeline(
                run_id=run_id,
                tenant_id=tenant_id,
                user_id=user_id,
                subject_name=subject_name,
                twin_id=twin_id,
                hints=hints,
            )
        except Exception as exc:
            logger.exception("ADK research run failed: %s", exc)

    async def get_run(self, *, run_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        return self._repository.get_run(run_id=run_id, tenant_id=tenant_id)

    async def get_result(self, *, run_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        row = self._repository.get_artifact(run_id=run_id, tenant_id=tenant_id)
        if not row:
            return None
        return row.get("artifact_json")

    def _build_graph_memory_text(self, artifact: Dict[str, Any]) -> str:
        parsed = self.parse_artifact(artifact)
        lines = [parsed.synthesis_summary]
        for claim in parsed.extracted_claims[:20]:
            lines.append(f"Claim: {claim.text}")
        for item in parsed.timeline[:12]:
            lines.append(f"Timeline: {item.date_or_range} - {item.event}")
        for quote in parsed.verified_quote_candidates[:8]:
            lines.append(f"Quote: {quote.quote}")
        return "\n".join(line for line in lines if line).strip()


@lru_cache(maxsize=1)
def get_name_deep_research_service() -> NameDeepResearchService:
    return NameDeepResearchService()
