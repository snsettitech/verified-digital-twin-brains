"""Compatibility wrapper for the new ADK compiler runtime."""

from __future__ import annotations

from typing import Any, Dict

from adk_core.runtime import run_compiler_pipeline
from adk_core.schemas.artifacts import ResearchArtifact


async def compile_run_to_twin(
    *,
    run_id: str,
    twin_id: str,
    tenant_id: str,
    result: Dict[str, Any],
    db=None,
) -> Dict[str, Any]:
    del db
    research_artifact = ResearchArtifact.model_validate(result)
    return await run_compiler_pipeline(
        run_id=run_id,
        tenant_id=tenant_id,
        twin_id=twin_id,
        user_id=str(research_artifact.compile_metadata.get("user_id") or "compiler"),
        research_artifact=research_artifact,
        publish=True,
    )
