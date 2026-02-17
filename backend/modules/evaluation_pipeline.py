# backend/modules/evaluation_pipeline.py
"""Evaluation Pipeline for Automatic LLM Judge Scoring

Runs LLM judges after each chat response and logs scores to Langfuse.
Designed to be non-blocking to response generation.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from modules.langfuse_sdk import flush_client, log_score

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of evaluation pipeline."""
    trace_id: str
    scores: Dict[str, Any]
    overall_score: float
    needs_review: bool
    flags: List[str]


class EvaluationPipeline:
    """Pipeline for running LLM judges and logging scores to Langfuse."""
    
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self._langfuse_available = False
        self._init_langfuse()
    
    def _init_langfuse(self):
        """Check if Langfuse is available."""
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        if not (public_key and secret_key):
            self._langfuse_available = False
            self._client = None
            return

        try:
            from langfuse import get_client
            self._client = get_client()
            self._langfuse_available = True
        except Exception:
            self._langfuse_available = False
            self._client = None
            try:
                from langfuse import Langfuse
                host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                self._langfuse_available = True
            except Exception:
                self._client = None
    
    async def evaluate_response(
        self,
        trace_id: str,
        query: str,
        response: str,
        context: str,
        citations: List[Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Run full evaluation pipeline on a response.
        
        Args:
            trace_id: Langfuse trace ID to attach scores to
            query: User query
            response: Generated response
            context: Retrieved context used for generation
            citations: List of citations
            metadata: Additional metadata
        
        Returns:
            EvaluationResult with scores and flags
        """
        scores = {}
        flags = []
        
        try:
            # Import judges
            from eval.judges import (
                judge_faithfulness,
                judge_citation_alignment,
                judge_response_completeness,
            )
            
            # Run judges in parallel
            faithfulness_task = judge_faithfulness(response, context)
            citation_task = judge_citation_alignment(response, citations)
            completeness_task = judge_response_completeness(query, response)
            
            faithfulness_result, citation_result, completeness_result = await asyncio.gather(
                faithfulness_task,
                citation_task,
                completeness_task,
                return_exceptions=True
            )
            
            # Process faithfulness result
            if isinstance(faithfulness_result, Exception):
                logger.warning(f"Faithfulness judge failed: {faithfulness_result}")
                scores["faithfulness"] = None
            else:
                scores["faithfulness"] = {
                    "score": faithfulness_result.get("score"),
                    "verdict": faithfulness_result.get("verdict"),
                    "reasoning": faithfulness_result.get("reasoning"),
                }
                if faithfulness_result.get("score", 1.0) < self.threshold:
                    flags.append("low_faithfulness")
            
            # Process citation result
            if isinstance(citation_result, Exception):
                logger.warning(f"Citation judge failed: {citation_result}")
                scores["citation_alignment"] = None
            else:
                scores["citation_alignment"] = {
                    "score": citation_result.get("score"),
                    "aligned": citation_result.get("aligned"),
                    "reasoning": citation_result.get("reasoning"),
                }
                if citation_result.get("score", 1.0) < self.threshold:
                    flags.append("low_citation_alignment")
            
            # Process completeness result
            if isinstance(completeness_result, Exception):
                logger.warning(f"Completeness judge failed: {completeness_result}")
                scores["completeness"] = None
            else:
                scores["completeness"] = {
                    "score": completeness_result.get("score"),
                    "reasoning": completeness_result.get("reasoning"),
                }
                if completeness_result.get("score", 1.0) < self.threshold:
                    flags.append("low_completeness")
            
            # Calculate overall score
            valid_scores = [
                s["score"] for s in scores.values() 
                if s is not None and s.get("score") is not None
            ]
            overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 1.0
            
            # Determine if needs review
            needs_review = overall_score < self.threshold or len(flags) > 0
            
            # Log scores to Langfuse
            await self._log_scores(trace_id, scores, overall_score, needs_review, flags)
            
            # Collect to dataset based on quality
            try:
                from modules.dataset_builder import collect_response
                collect_response(
                    trace_id=trace_id,
                    query=query,
                    response=response,
                    context=context,
                    citations=citations,
                    scores=scores,
                    overall_score=overall_score,
                    metadata={"auto_collected": True}
                )
            except Exception as e:
                logger.debug(f"Dataset collection failed (non-critical): {e}")
            
            return EvaluationResult(
                trace_id=trace_id,
                scores=scores,
                overall_score=overall_score,
                needs_review=needs_review,
                flags=flags
            )
            
        except Exception as e:
            logger.error(f"Evaluation pipeline failed: {e}")
            return EvaluationResult(
                trace_id=trace_id,
                scores={},
                overall_score=0.0,
                needs_review=True,
                flags=["evaluation_failed"]
            )
    
    async def _log_scores(
        self,
        trace_id: str,
        scores: Dict[str, Any],
        overall_score: float,
        needs_review: bool,
        flags: List[str]
    ):
        """Log scores to Langfuse."""
        if not self._langfuse_available:
            return
        
        try:
            # Log individual scores
            for name, result in scores.items():
                if result and result.get("score") is not None:
                    log_score(
                        self._client,
                        trace_id=trace_id,
                        name=name,
                        value=result["score"],
                        comment=result.get("reasoning", "")[:255],
                        data_type="NUMERIC",
                    )
            
            # Log overall score
            log_score(
                self._client,
                trace_id=trace_id,
                name="overall_quality",
                value=overall_score,
                data_type="NUMERIC",
            )
            
            # Flag for review if needed
            if needs_review:
                log_score(
                    self._client,
                    trace_id=trace_id,
                    name="needs_review",
                    value=1,
                    comment=f"Flags: {', '.join(flags)}",
                    data_type="BOOLEAN",
                )
            
            # Flush to ensure scores are sent
            flush_client(self._client)
            
        except Exception as e:
            logger.error(f"Failed to log scores to Langfuse: {e}")
    
    def evaluate_async(
        self,
        trace_id: str,
        query: str,
        response: str,
        context: str,
        citations: List[Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Fire-and-forget evaluation (non-blocking).
        
        Usage:
            pipeline.evaluate_async(trace_id, query, response, context, citations)
        """
        try:
            # Create task but don't await it
            asyncio.create_task(
                self.evaluate_response(
                    trace_id=trace_id,
                    query=query,
                    response=response,
                    context=context,
                    citations=citations,
                    metadata=metadata
                )
            )
        except Exception as e:
            logger.error(f"Failed to start async evaluation: {e}")


# Singleton instance
_pipeline: Optional[EvaluationPipeline] = None


def get_evaluation_pipeline(threshold: float = 0.7) -> EvaluationPipeline:
    """Get or create the singleton evaluation pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = EvaluationPipeline(threshold=threshold)
    return _pipeline


# Convenience function for fire-and-forget evaluation
def evaluate_response_async(
    trace_id: str,
    query: str,
    response: str,
    context: str,
    citations: List[Any],
    threshold: float = 0.7
):
    """
    Fire-and-forget evaluation (convenience function).
    
    Usage in chat handler:
        from modules.evaluation_pipeline import evaluate_response_async
        evaluate_response_async(
            trace_id=trace_id,
            query=query,
            response=full_response,
            context=retrieved_context_text,
            citations=citations
        )
    """
    pipeline = get_evaluation_pipeline(threshold=threshold)
    pipeline.evaluate_async(
        trace_id=trace_id,
        query=query,
        response=response,
        context=context,
        citations=citations
    )
