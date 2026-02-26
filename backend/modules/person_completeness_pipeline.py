"""
Person Completeness Pipeline v1 - Main Orchestrator

Orchestrates the structured person modeling pipeline:
1. SOURCE_REGISTRY_BUILT
2. CLAIMS_EXTRACTED
3. TIMELINE_BUILT
4. TOPIC_GRAPH_BUILT
5. STYLE_PROFILE_BUILT
6. CONTRADICTIONS_DETECTED
7. ANSWERABILITY_SCORED

Usage:
    pipeline = PersonCompletenessPipeline()
    result = await pipeline.run_for_twin(twin_id="...", research_run_id="...")
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from modules.observability import supabase
from modules.person_completeness_config import get_config, PersonCompletenessConfig

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """Pipeline stages in order of execution."""
    SOURCE_REGISTRY_BUILT = "source_registry_built"
    CLAIMS_EXTRACTED = "claims_extracted"
    TIMELINE_BUILT = "timeline_built"
    TOPIC_GRAPH_BUILT = "topic_graph_built"
    STYLE_PROFILE_BUILT = "style_profile_built"
    CONTRADICTIONS_DETECTED = "contradictions_detected"
    ANSWERABILITY_SCORED = "answerability_scored"


STAGE_ORDER = [
    PipelineStage.SOURCE_REGISTRY_BUILT,
    PipelineStage.CLAIMS_EXTRACTED,
    PipelineStage.TIMELINE_BUILT,
    PipelineStage.TOPIC_GRAPH_BUILT,
    PipelineStage.STYLE_PROFILE_BUILT,
    PipelineStage.CONTRADICTIONS_DETECTED,
    PipelineStage.ANSWERABILITY_SCORED,
]

RUN_METRIC_FIELDS_BY_STAGE: Dict[PipelineStage, List[str]] = {
    PipelineStage.SOURCE_REGISTRY_BUILT: ["source_registry_count"],
    PipelineStage.CLAIMS_EXTRACTED: ["claims_extracted_count", "evidence_spans_count"],
    PipelineStage.TIMELINE_BUILT: ["timeline_events_count"],
    PipelineStage.TOPIC_GRAPH_BUILT: ["topic_profiles_count"],
    PipelineStage.STYLE_PROFILE_BUILT: [],
    PipelineStage.CONTRADICTIONS_DETECTED: ["contradictions_detected_count"],
    PipelineStage.ANSWERABILITY_SCORED: [],
}


@dataclass
class StageResult:
    """Result of a single pipeline stage."""
    stage: str
    success: bool
    item_count: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of the complete pipeline run."""
    run_id: str
    twin_id: str
    success: bool
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class PipelineRunRepository:
    """Data access layer for pipeline runs."""
    
    @staticmethod
    def create_run(twin_id: str, research_run_id: Optional[str] = None, 
                   run_fingerprint: Optional[str] = None) -> str:
        """Create a new pipeline run record."""
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        insert_data = {
            "id": run_id,
            "twin_id": twin_id,
            "research_run_id": research_run_id,
            "status": "pending",
            "run_fingerprint": run_fingerprint,
            "created_at": now,
            "updated_at": now,
        }
        
        try:
            supabase.table("person_completeness_runs").insert(insert_data).execute()
            return run_id
        except Exception as e:
            logger.error(f"Error creating pipeline run: {e}")
            raise
    
    @staticmethod
    def update_run_status(run_id: str, status: str, 
                          current_stage: Optional[str] = None,
                          completed_stages: Optional[List[str]] = None,
                          metrics: Optional[Dict[str, Any]] = None,
                          error_message: Optional[str] = None,
                          error_stage: Optional[str] = None):
        """Update pipeline run status and metrics."""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        if current_stage:
            update_data["current_stage"] = current_stage
        
        if completed_stages:
            update_data["completed_stages"] = completed_stages
        
        if metrics:
            for key, value in metrics.items():
                if key in ["source_registry_count", "claims_extracted_count", 
                          "evidence_spans_count", "timeline_events_count",
                          "topic_profiles_count", "contradictions_detected_count"]:
                    update_data[key] = value
        
        if error_message:
            update_data["error_message"] = error_message
        
        if error_stage:
            update_data["error_stage"] = error_stage
        
        if status in ["completed", "failed", "partial"]:
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        if status == "running" and not completed_stages:
            update_data["started_at"] = datetime.utcnow().isoformat()
        
        try:
            supabase.table("person_completeness_runs").update(update_data).eq("id", run_id).execute()
        except Exception as e:
            logger.error(f"Error updating pipeline run: {e}")
    
    @staticmethod
    def get_latest_run(twin_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent pipeline run for a twin."""
        try:
            response = supabase.table("person_completeness_runs") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching latest run: {e}")
            return None


class PersonCompletenessPipeline:
    """
    Main orchestrator for the person completeness pipeline.
    
    Runs idempotent stages in sequence, tracking progress and metrics.
    """
    
    def __init__(self, config: Optional[PersonCompletenessConfig] = None):
        self.config = config or get_config()
        self.repository = PipelineRunRepository()
        self._stage_handlers: Dict[str, Any] = {}

    def _promote_twin_to_active(self, twin_id: str) -> None:
        """
        Best-effort promotion so owner chat is unblocked after successful builds.
        """
        update_payload: Dict[str, Any] = {
            "status": "active",
            "is_active": True,
            "updated_at": datetime.utcnow().isoformat(),
        }
        removable_columns = {"status", "is_active"}

        while True:
            try:
                supabase.table("twins").update(update_payload).eq("id", twin_id).execute()
                return
            except Exception as e:
                err = str(e).lower()
                removed = None
                for column in list(removable_columns):
                    if column in update_payload and column in err and (
                        "column" in err or "does not exist" in err or "pgrst204" in err
                    ):
                        removed = column
                        break
                if removed:
                    update_payload.pop(removed, None)
                    removable_columns.discard(removed)
                    continue
                logger.warning("Failed to promote twin %s to active: %s", twin_id, e)
                return
    
    def _get_stage_handler(self, stage: PipelineStage):
        """Lazy load stage handler to avoid circular imports."""
        if stage.value not in self._stage_handlers:
            if stage == PipelineStage.SOURCE_REGISTRY_BUILT:
                from modules.source_registry_builder import SourceRegistryBuilder
                self._stage_handlers[stage.value] = SourceRegistryBuilder(self.config.source_registry)
            elif stage == PipelineStage.CLAIMS_EXTRACTED:
                from modules.claim_extraction_service import ClaimExtractionService
                self._stage_handlers[stage.value] = ClaimExtractionService(self.config.claim_extraction)
            elif stage == PipelineStage.TIMELINE_BUILT:
                from modules.timeline_builder import TimelineBuilder
                self._stage_handlers[stage.value] = TimelineBuilder(self.config.timeline_builder)
            elif stage == PipelineStage.TOPIC_GRAPH_BUILT:
                from modules.topic_graph_builder import TopicGraphBuilder
                self._stage_handlers[stage.value] = TopicGraphBuilder(self.config.topic_graph)
            elif stage == PipelineStage.STYLE_PROFILE_BUILT:
                from modules.style_profile_builder import StyleProfileBuilder
                self._stage_handlers[stage.value] = StyleProfileBuilder(self.config.style_profile)
            elif stage == PipelineStage.CONTRADICTIONS_DETECTED:
                from modules.contradiction_detector import ContradictionDetector
                self._stage_handlers[stage.value] = ContradictionDetector(self.config.contradiction_detection)
            elif stage == PipelineStage.ANSWERABILITY_SCORED:
                from modules.answerability_scorer import AnswerabilityScorer
                self._stage_handlers[stage.value] = AnswerabilityScorer(self.config.answerability_scoring)
        
        return self._stage_handlers.get(stage.value)

    def _extract_item_count(self, stage: PipelineStage, stage_result: Any) -> int:
        """Extract a primary count from stage result object in a backward-compatible way."""
        # Preferred, standardized contract.
        if hasattr(stage_result, "item_count"):
            try:
                return int(getattr(stage_result, "item_count") or 0)
            except Exception:
                return 0

        # Stage-specific fallback for older result objects.
        fallback_attrs: Dict[PipelineStage, List[str]] = {
            PipelineStage.SOURCE_REGISTRY_BUILT: ["sources_added", "sources_updated"],
            PipelineStage.CLAIMS_EXTRACTED: ["claims_extracted"],
            PipelineStage.TIMELINE_BUILT: ["events_created"],
            PipelineStage.TOPIC_GRAPH_BUILT: ["topics_created"],
            PipelineStage.STYLE_PROFILE_BUILT: ["profile_version"],
            PipelineStage.CONTRADICTIONS_DETECTED: ["contradictions_found"],
            PipelineStage.ANSWERABILITY_SCORED: ["scores_computed"],
        }

        total = 0
        for attr in fallback_attrs.get(stage, []):
            value = getattr(stage_result, attr, 0) or 0
            try:
                total += int(value)
            except Exception:
                continue
        return total

    def _build_run_metrics(self, stage: PipelineStage, stage_result: Any, item_count: int) -> Dict[str, int]:
        """Build DB run metrics payload for a stage."""
        metrics: Dict[str, int] = {}
        fields = RUN_METRIC_FIELDS_BY_STAGE.get(stage, [])
        if not fields:
            return metrics

        if stage == PipelineStage.CLAIMS_EXTRACTED:
            metrics["claims_extracted_count"] = int(getattr(stage_result, "claims_extracted", item_count) or 0)
            metrics["evidence_spans_count"] = int(getattr(stage_result, "evidence_spans_attached", 0) or 0)
            return metrics

        # Single-value stages.
        metrics[fields[0]] = int(item_count)
        return metrics
    
    async def run_for_twin(
        self,
        twin_id: str,
        research_run_id: Optional[str] = None,
        force_rebuild: bool = False,
        run_fingerprint: Optional[str] = None,
    ) -> PipelineResult:
        """
        Run the complete pipeline for a twin.
        
        Args:
            twin_id: The twin to process
            research_run_id: Optional associated research run
            force_rebuild: If True, reprocess even if recently run
            run_fingerprint: Hash of input params for idempotency
            
        Returns:
            PipelineResult with status and metrics
        """
        import time
        start_time = time.time()
        
        # Check if enabled for this twin
        if not self.config.is_enabled_for_twin(twin_id):
            logger.info(f"Person completeness disabled for twin {twin_id}")
            return PipelineResult(
                run_id="",
                twin_id=twin_id,
                success=False,
                error_message="Person completeness not enabled for this twin"
            )
        
        # Check for existing recent run (unless force_rebuild)
        if not force_rebuild:
            latest_run = self.repository.get_latest_run(twin_id)
            if latest_run and latest_run.get("status") in ["running", "pending"]:
                logger.info(f"Pipeline already running for twin {twin_id}")
                return PipelineResult(
                    run_id=latest_run["id"],
                    twin_id=twin_id,
                    success=False,
                    error_message="Pipeline already in progress"
                )
        
        # Create run record
        run_id = self.repository.create_run(twin_id, research_run_id, run_fingerprint)
        logger.info(f"Starting person completeness pipeline for twin {twin_id}, run {run_id}")
        
        # Update status to running
        self.repository.update_run_status(run_id, "running")
        
        completed_stages: List[str] = []
        failed_stages: List[str] = []
        stage_metrics: Dict[str, Any] = {}
        
        try:
            # Get enabled stages in order
            enabled_stages = self._get_enabled_stages()
            
            for stage in enabled_stages:
                stage_start = time.time()
                
                try:
                    handler = self._get_stage_handler(stage)
                    if not handler:
                        logger.warning(f"No handler for stage {stage.value}, skipping")
                        continue
                    
                    # Execute stage
                    logger.info(f"Running stage {stage.value} for twin {twin_id}")
                    stage_result = await handler.run(twin_id, research_run_id)
                    
                    stage_duration = time.time() - stage_start
                    
                    if stage_result.success:
                        item_count = self._extract_item_count(stage, stage_result)
                        run_metrics = self._build_run_metrics(stage, stage_result, item_count)

                        completed_stages.append(stage.value)
                        stage_metrics[f"{stage.value}_count"] = item_count
                        stage_metrics[f"{stage.value}_duration"] = round(stage_duration, 2)
                        for key, value in run_metrics.items():
                            stage_metrics[key] = value
                        
                        # Update run with progress
                        self.repository.update_run_status(
                            run_id, 
                            "running",
                            current_stage=stage.value,
                            completed_stages=completed_stages,
                            metrics=run_metrics,
                        )
                        
                        logger.info(f"Stage {stage.value} completed: {item_count} items in {stage_duration:.2f}s")
                    else:
                        if stage.value not in failed_stages:
                            failed_stages.append(stage.value)
                        logger.error(f"Stage {stage.value} failed: {stage_result.error_message}")
                        
                        if self.config.fail_fast:
                            raise Exception(f"Stage {stage.value} failed: {stage_result.error_message}")
                        
                        if not self.config.continue_on_stage_failure:
                            break
                
                except Exception as e:
                    if stage.value not in failed_stages:
                        failed_stages.append(stage.value)
                    if stage.value in completed_stages:
                        completed_stages.remove(stage.value)
                    logger.exception(f"Exception in stage {stage.value}: {e}")
                    
                    if self.config.fail_fast:
                        raise
                    
                    if not self.config.continue_on_stage_failure:
                        break
            
            # Determine final status
            total_duration = time.time() - start_time
            
            if not failed_stages:
                final_status = "completed"
                success = True
            elif completed_stages:
                final_status = "partial"
                success = True
            else:
                final_status = "failed"
                success = False
            
            # Update final status
            self.repository.update_run_status(
                run_id,
                final_status,
                completed_stages=completed_stages,
                metrics=stage_metrics
            )

            if success and final_status in {"completed", "partial"}:
                self._promote_twin_to_active(twin_id)
            
            return PipelineResult(
                run_id=run_id,
                twin_id=twin_id,
                success=success,
                stages_completed=completed_stages,
                stages_failed=failed_stages,
                total_duration_seconds=round(total_duration, 2),
                metrics=stage_metrics
            )
        
        except Exception as e:
            total_duration = time.time() - start_time
            logger.exception(f"Pipeline failed for twin {twin_id}: {e}")
            
            self.repository.update_run_status(
                run_id,
                "failed",
                error_message=str(e),
                error_stage=failed_stages[-1] if failed_stages else None
            )
            
            return PipelineResult(
                run_id=run_id,
                twin_id=twin_id,
                success=False,
                stages_completed=completed_stages,
                stages_failed=failed_stages + [s.value for s in enabled_stages if s.value not in completed_stages],
                total_duration_seconds=round(total_duration, 2),
                error_message=str(e)
            )
    
    def _get_enabled_stages(self) -> List[PipelineStage]:
        """Get list of enabled stages in execution order."""
        enabled = self.config.get_enabled_stages()
        return [s for s in STAGE_ORDER if s.value in enabled]
    
    async def run_stage_only(
        self,
        twin_id: str,
        stage: PipelineStage,
        research_run_id: Optional[str] = None,
    ) -> StageResult:
        """
        Run a single stage only (for manual reprocessing).
        
        Args:
            twin_id: The twin to process
            stage: Specific stage to run
            research_run_id: Optional associated research run
            
        Returns:
            StageResult
        """
        handler = self._get_stage_handler(stage)
        if not handler:
            return StageResult(
                stage=stage.value,
                success=False,
                error_message=f"No handler for stage {stage.value}"
            )
        
        return await handler.run(twin_id, research_run_id)


# Convenience functions

async def run_person_completeness_pipeline(
    twin_id: str,
    research_run_id: Optional[str] = None,
    force_rebuild: bool = False,
) -> PipelineResult:
    """
    Convenience function to run the pipeline.
    
    Usage:
        result = await run_person_completeness_pipeline(twin_id="...")
    """
    pipeline = PersonCompletenessPipeline()
    return await pipeline.run_for_twin(twin_id, research_run_id, force_rebuild)


def is_person_completeness_enabled(twin_id: str) -> bool:
    """Check if person completeness is enabled for a twin."""
    return get_config().is_enabled_for_twin(twin_id)
