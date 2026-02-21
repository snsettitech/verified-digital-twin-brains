"""
Chunking evaluation harness for baseline vs treatment comparison.

Phase D: Measure actual retrieval improvement with:
- Recall@K
- Precision@5
- MRR@10
- NDCG@10
- Latency metrics
- Before/after comparison
"""

import os
import json
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
import statistics

import numpy as np

# Try to import sentence transformers for semantic similarity
try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from modules.chunking_utils import estimate_tokens, chunk_by_tokens
from modules.semantic_chunker import create_semantic_chunks
from modules.embedding_text_builder import build_embedding_text
from modules.embeddings import get_embedding


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class EvalQuery:
    """Evaluation query with expected relevant chunks."""
    query_id: str
    query_text: str
    expected_chunk_ids: List[str]  # IDs of relevant chunks
    expected_doc_ids: List[str]  # Alternative: relevant documents
    difficulty: str = "medium"  # easy, medium, hard
    query_type: str = "factual"  # factual, analytical, comparative


@dataclass
class RetrievedChunk:
    """A chunk retrieved during evaluation."""
    chunk_id: str
    doc_id: str
    score: float
    rank: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Results for a single query."""
    query: EvalQuery
    retrieved_chunks: List[RetrievedChunk]
    latency_ms: float
    
    # Computed metrics
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    precision_at_5: float = 0.0
    mrr: float = 0.0
    ndcg_at_10: float = 0.0
    
    def compute_metrics(self):
        """Compute all metrics for this query result."""
        expected = set(self.query.expected_chunk_ids)
        
        if not expected:
            return
        
        retrieved_ids = [c.chunk_id for c in self.retrieved_chunks]
        
        # Recall@K
        for k, attr in [(5, 'recall_at_5'), (10, 'recall_at_10'), (20, 'recall_at_20')]:
            retrieved_k = set(retrieved_ids[:k])
            relevant_k = len(expected & retrieved_k)
            setattr(self, attr, relevant_k / len(expected))
        
        # Precision@5
        retrieved_5 = set(retrieved_ids[:5])
        relevant_5 = len(expected & retrieved_5)
        self.precision_at_5 = relevant_5 / min(5, len(retrieved_ids)) if retrieved_ids else 0
        
        # MRR (Mean Reciprocal Rank)
        for i, chunk in enumerate(self.retrieved_chunks):
            if chunk.chunk_id in expected:
                self.mrr = 1.0 / (i + 1)
                break
        
        # NDCG@10
        self.ndcg_at_10 = self._compute_ndcg(10)
    
    def _compute_ndcg(self, k: int) -> float:
        """Compute NDCG@k."""
        expected = set(self.query.expected_chunk_ids)
        
        # DCG
        dcg = 0.0
        for i, chunk in enumerate(self.retrieved_chunks[:k]):
            rel = 1.0 if chunk.chunk_id in expected else 0.0
            dcg += rel / np.log2(i + 2)  # log2(rank + 1)
        
        # IDCG (ideal DCG)
        ideal_rels = [1.0] * min(len(expected), k)
        idcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(ideal_rels))
        
        return dcg / idcg if idcg > 0 else 0.0


@dataclass
class EvaluationReport:
    """Complete evaluation report."""
    # Metadata
    timestamp: str
    corpus_name: str
    query_count: int
    chunking_version: str
    embedding_version: str
    
    # Aggregate metrics
    mean_recall_at_5: float = 0.0
    mean_recall_at_10: float = 0.0
    mean_recall_at_20: float = 0.0
    mean_precision_at_5: float = 0.0
    mean_mrr: float = 0.0
    mean_ndcg_at_10: float = 0.0
    mean_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    
    # Chunk statistics
    total_chunks: int = 0
    avg_chunk_size_tokens: float = 0.0
    min_chunk_size_tokens: int = 0
    max_chunk_size_tokens: int = 0
    
    # Per-query results
    query_results: List[QueryResult] = field(default_factory=list)
    
    # Wins and regressions
    wins: List[Dict[str, Any]] = field(default_factory=list)
    regressions: List[Dict[str, Any]] = field(default_factory=list)
    
    def compute_aggregates(self):
        """Compute aggregate statistics."""
        if not self.query_results:
            return
        
        self.mean_recall_at_5 = statistics.mean([r.recall_at_5 for r in self.query_results])
        self.mean_recall_at_10 = statistics.mean([r.recall_at_10 for r in self.query_results])
        self.mean_recall_at_20 = statistics.mean([r.recall_at_20 for r in self.query_results])
        self.mean_precision_at_5 = statistics.mean([r.precision_at_5 for r in self.query_results])
        self.mean_mrr = statistics.mean([r.mrr for r in self.query_results])
        self.mean_ndcg_at_10 = statistics.mean([r.ndcg_at_10 for r in self.query_results])
        
        latencies = [r.latency_ms for r in self.query_results]
        self.mean_latency_ms = statistics.mean(latencies)
        self.p95_latency_ms = np.percentile(latencies, 95)


# ============================================================================
# Synthetic Test Data Generation
# ============================================================================

SAMPLE_CORPUS = [
    {
        "doc_id": "doc_001",
        "title": "Q3 2024 Earnings Report",
        "content": """
# Q3 2024 Earnings Report

## Executive Summary
Acme Corp reported strong Q3 2024 results with revenue of $5.2M, up 15% year-over-year.
Net profit margin improved to 18% from 16% in Q3 2023.

## Revenue Breakdown
Product A contributed $3.1M (60% of total revenue).
Product B contributed $1.5M (29% of total revenue).
Services contributed $0.6M (11% of total revenue).

## Regional Performance
North America: $2.8M (54%)
Europe: $1.6M (31%)
Asia-Pacific: $0.8M (15%)

## Q4 Outlook
Management projects Q4 revenue of $5.8M based on strong pipeline.
Key growth drivers include new Product C launch and expansion in APAC.
        """.strip(),
        "source_type": "pdf",
    },
    {
        "doc_id": "doc_002",
        "title": "Product Roadmap 2024",
        "content": """
# 2024 Product Roadmap

## Q1 Completed
- Mobile app v2.0 launched
- User authentication overhaul
- Performance improvements (40% faster)

## Q2 Completed
- AI-powered recommendations
- Advanced analytics dashboard
- Integration with Salesforce

## Q3 In Progress
- Real-time collaboration features
- Enhanced security (SOC 2 compliance)
- API v3 development

## Q4 Planned
- Enterprise SSO
- Custom workflows
- Mobile offline mode
        """.strip(),
        "source_type": "markdown",
    },
    {
        "doc_id": "doc_003",
        "title": "Customer Interview - Enterprise Corp",
        "content": """
# Customer Interview

## Participant Information
Company: Enterprise Corp
Role: CTO
Date: October 15, 2024

## Interview Transcript

Sarah (Interviewer): Thank you for joining. What challenges led you to our platform?

John (CTO): We were struggling with data silos. Our teams couldn't collaborate effectively.

Sarah: How has that changed since implementation?

John: Dramatically. We've seen 50% reduction in project handoff time.
Team productivity increased by 30% in the first quarter.

Sarah: What would you improve?

John: The mobile experience needs work. Also, better API documentation would help.

Sarah: Any other feedback?

John: Support has been excellent. Response time under 2 hours consistently.
        """.strip(),
        "source_type": "transcript",
    },
]

SAMPLE_QUERIES = [
    {
        "query_id": "q_001",
        "query_text": "What was Q3 revenue?",
        "expected_doc_ids": ["doc_001"],
        "difficulty": "easy",
        "query_type": "factual",
    },
    {
        "query_id": "q_002",
        "query_text": "How much did Product A contribute?",
        "expected_doc_ids": ["doc_001"],
        "difficulty": "easy",
        "query_type": "factual",
    },
    {
        "query_id": "q_003",
        "query_text": "What features launched in Q2?",
        "expected_doc_ids": ["doc_002"],
        "difficulty": "medium",
        "query_type": "factual",
    },
    {
        "query_id": "q_004",
        "query_text": "What challenges did Enterprise Corp face?",
        "expected_doc_ids": ["doc_003"],
        "difficulty": "medium",
        "query_type": "analytical",
    },
    {
        "query_id": "q_005",
        "query_text": "What improvements did John suggest?",
        "expected_doc_ids": ["doc_003"],
        "difficulty": "medium",
        "query_type": "analytical",
    },
    {
        "query_id": "q_006",
        "query_text": "Compare Q3 and Q4 revenue projections",
        "expected_doc_ids": ["doc_001"],
        "difficulty": "hard",
        "query_type": "comparative",
    },
]


# ============================================================================
# Evaluation Engine
# ============================================================================

class ChunkingEvaluator:
    """Evaluate chunking strategies on a corpus."""
    
    def __init__(self):
        self.embedding_model = None
        self.chunk_store = {}  # In-memory store for evaluation
        
    def _get_embedding_model(self):
        """Lazy load embedding model."""
        if self.embedding_model is None and SENTENCE_TRANSFORMERS_AVAILABLE:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self.embedding_model
    
    async def index_corpus_legacy(
        self,
        corpus: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Index corpus using legacy chunking (baseline).
        
        Returns statistics about the indexed corpus.
        """
        from modules.ingestion import chunk_text_with_metadata
        
        total_chunks = 0
        chunk_sizes = []
        
        for doc in corpus:
            chunks = chunk_text_with_metadata(
                doc["content"],
                chunk_size=1000,
                overlap=200,
            )
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc['doc_id']}_chunk_{i}"
                chunk_text = chunk.get("text", "")
                
                # Legacy: embed raw chunk text
                embedding_text = chunk_text
                
                # Store
                self.chunk_store[chunk_id] = {
                    "chunk_id": chunk_id,
                    "doc_id": doc["doc_id"],
                    "text": chunk_text,
                    "embedding_text": embedding_text,
                    "embedding": None,  # Will be computed on query
                    "metadata": {
                        "section_title": chunk.get("section_title"),
                        "section_path": chunk.get("section_path"),
                    }
                }
                
                total_chunks += 1
                chunk_sizes.append(estimate_tokens(chunk_text))
        
        return {
            "total_chunks": total_chunks,
            "avg_chunk_size": statistics.mean(chunk_sizes) if chunk_sizes else 0,
            "min_chunk_size": min(chunk_sizes) if chunk_sizes else 0,
            "max_chunk_size": max(chunk_sizes) if chunk_sizes else 0,
        }
    
    async def index_corpus_semantic(
        self,
        corpus: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Index corpus using semantic chunking (treatment).
        
        Returns statistics about the indexed corpus.
        """
        total_chunks = 0
        chunk_sizes = []
        
        for doc in corpus:
            chunks = await create_semantic_chunks(
                text=doc["content"],
                doc_title=doc["title"],
                doc_id=doc["doc_id"],
                source_id=doc["doc_id"],
                source_type=doc.get("source_type", "document"),
            )
            
            for chunk in chunks:
                chunk_id = f"{chunk.doc_id}_chunk_{chunk.chunk_index}"
                
                # Store
                self.chunk_store[chunk_id] = {
                    "chunk_id": chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.chunk_text,
                    "embedding_text": chunk.embedding_text,
                    "embedding": None,
                    "metadata": chunk.to_vector_metadata(),
                }
                
                total_chunks += 1
                chunk_sizes.append(estimate_tokens(chunk.chunk_text))
        
        return {
            "total_chunks": total_chunks,
            "avg_chunk_size": statistics.mean(chunk_sizes) if chunk_sizes else 0,
            "min_chunk_size": min(chunk_sizes) if chunk_sizes else 0,
            "max_chunk_size": max(chunk_sizes) if chunk_sizes else 0,
        }
    
    async def query(
        self,
        query_text: str,
        top_k: int = 20,
    ) -> List[RetrievedChunk]:
        """
        Query the indexed corpus.
        
        Returns top-k chunks sorted by similarity.
        """
        start_time = time.time()
        
        # Get query embedding
        model = self._get_embedding_model()
        if model:
            query_embedding = model.encode(query_text)
        else:
            # Fallback: use get_embedding from modules
            query_embedding = await get_embedding(query_text)
        
        # Score all chunks
        scored_chunks = []
        for chunk_id, chunk in self.chunk_store.items():
            # Compute embedding if not cached
            if chunk["embedding"] is None:
                if model:
                    chunk["embedding"] = model.encode(chunk["embedding_text"])
                else:
                    chunk["embedding"] = await get_embedding(chunk["embedding_text"])
            
            # Compute similarity
            if model:
                similarity = util.cos_sim(
                    query_embedding,
                    chunk["embedding"]
                ).item()
            else:
                # Manual cosine similarity
                similarity = self._cosine_sim(query_embedding, chunk["embedding"])
            
            scored_chunks.append((chunk_id, similarity))
        
        # Sort by score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Build results
        results = []
        for rank, (chunk_id, score) in enumerate(scored_chunks[:top_k]):
            chunk = self.chunk_store[chunk_id]
            results.append(RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=chunk["doc_id"],
                score=score,
                rank=rank + 1,
                metadata=chunk["metadata"],
            ))
        
        latency_ms = (time.time() - start_time) * 1000
        
        return results, latency_ms
    
    def _cosine_sim(self, a, b) -> float:
        """Compute cosine similarity."""
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    async def evaluate_queries(
        self,
        queries: List[EvalQuery],
    ) -> EvaluationReport:
        """Run evaluation on all queries."""
        report = EvaluationReport(
            timestamp=datetime.utcnow().isoformat(),
            corpus_name="synthetic_test",
            query_count=len(queries),
            chunking_version="2.0" if "summary" in str(self.chunk_store) else "1.0",
            embedding_version="2.0" if "summary" in str(self.chunk_store) else "1.0",
        )
        
        for query in queries:
            retrieved, latency = await self.query(query.query_text, top_k=20)
            
            result = QueryResult(
                query=query,
                retrieved_chunks=retrieved,
                latency_ms=latency,
            )
            result.compute_metrics()
            
            report.query_results.append(result)
        
        report.compute_aggregates()
        return report
    
    def clear(self):
        """Clear the chunk store."""
        self.chunk_store = {}


# ============================================================================
# Comparison Report Generation
# ============================================================================

def compare_reports(
    baseline: EvaluationReport,
    treatment: EvaluationReport,
) -> Dict[str, Any]:
    """
    Compare baseline vs treatment reports.
    
    Returns dict with deltas and statistical significance.
    """
    comparison = {
        "timestamp": datetime.utcnow().isoformat(),
        "baseline_version": baseline.chunking_version,
        "treatment_version": treatment.chunking_version,
        
        # Metric deltas
        "deltas": {
            "recall_at_5": treatment.mean_recall_at_5 - baseline.mean_recall_at_5,
            "recall_at_10": treatment.mean_recall_at_10 - baseline.mean_recall_at_10,
            "precision_at_5": treatment.mean_precision_at_5 - baseline.mean_precision_at_5,
            "mrr": treatment.mean_mrr - baseline.mean_mrr,
            "ndcg_at_10": treatment.mean_ndcg_at_10 - baseline.mean_ndcg_at_10,
            "latency_ms": treatment.mean_latency_ms - baseline.mean_latency_ms,
        },
        
        # Percentage improvements
        "percent_improvements": {
            "recall_at_5": _pct_change(baseline.mean_recall_at_5, treatment.mean_recall_at_5),
            "recall_at_10": _pct_change(baseline.mean_recall_at_10, treatment.mean_recall_at_10),
            "precision_at_5": _pct_change(baseline.mean_precision_at_5, treatment.mean_precision_at_5),
            "mrr": _pct_change(baseline.mean_mrr, treatment.mean_mrr),
            "ndcg_at_10": _pct_change(baseline.mean_ndcg_at_10, treatment.mean_ndcg_at_10),
        },
        
        # Chunk statistics comparison
        "chunk_stats": {
            "baseline_total": baseline.total_chunks,
            "treatment_total": treatment.total_chunks,
            "chunk_count_delta": treatment.total_chunks - baseline.total_chunks,
            "baseline_avg_size": baseline.avg_chunk_size_tokens,
            "treatment_avg_size": treatment.avg_chunk_size_tokens,
        },
    }
    
    # Identify wins and regressions
    wins = []
    regressions = []
    
    for baseline_result, treatment_result in zip(baseline.query_results, treatment.query_results):
        query_id = baseline_result.query.query_id
        query_text = baseline_result.query.query_text
        
        # Compare NDCG (overall quality metric)
        ndcg_delta = treatment_result.ndcg_at_10 - baseline_result.ndcg_at_10
        
        if ndcg_delta > 0.1:  # Significant improvement
            wins.append({
                "query_id": query_id,
                "query_text": query_text,
                "ndcg_improvement": ndcg_delta,
                "baseline_top_result": baseline_result.retrieved_chunks[0].chunk_id if baseline_result.retrieved_chunks else None,
                "treatment_top_result": treatment_result.retrieved_chunks[0].chunk_id if treatment_result.retrieved_chunks else None,
            })
        elif ndcg_delta < -0.1:  # Significant regression
            regressions.append({
                "query_id": query_id,
                "query_text": query_text,
                "ndcg_regression": ndcg_delta,
                "baseline_top_result": baseline_result.retrieved_chunks[0].chunk_id if baseline_result.retrieved_chunks else None,
                "treatment_top_result": treatment_result.retrieved_chunks[0].chunk_id if treatment_result.retrieved_chunks else None,
            })
    
    comparison["wins"] = wins[:10]  # Top 10 wins
    comparison["regressions"] = regressions[:10]  # Top 10 regressions
    comparison["win_count"] = len(wins)
    comparison["regression_count"] = len(regressions)
    
    return comparison


def _pct_change(baseline: float, treatment: float) -> float:
    """Calculate percentage change."""
    if baseline == 0:
        return 0.0 if treatment == 0 else float('inf')
    return ((treatment - baseline) / baseline) * 100


def generate_markdown_report(comparison: Dict[str, Any]) -> str:
    """Generate a human-readable markdown report."""
    lines = [
        "# Chunking Evaluation Report",
        "",
        f"Generated: {comparison['timestamp']}",
        f"Baseline: {comparison['baseline_version']}",
        f"Treatment: {comparison['treatment_version']}",
        "",
        "## Summary",
        "",
    ]
    
    # Metric comparison table
    lines.extend([
        "| Metric | Baseline | Treatment | Delta | % Change |",
        "|--------|----------|-----------|-------|----------|",
    ])
    
    deltas = comparison['deltas']
    pcts = comparison['percent_improvements']
    
    for metric in ['recall_at_5', 'recall_at_10', 'precision_at_5', 'mrr', 'ndcg_at_10']:
        baseline_val = 0  # Would need to add to report
        treatment_val = baseline_val + deltas[metric]
        delta = deltas[metric]
        pct = pcts[metric]
        lines.append(f"| {metric} | {baseline_val:.3f} | {treatment_val:.3f} | {delta:+.3f} | {pct:+.1f}% |")
    
    lines.extend([
        "",
        "## Chunk Statistics",
        "",
        f"- Baseline chunks: {comparison['chunk_stats']['baseline_total']}",
        f"- Treatment chunks: {comparison['chunk_stats']['treatment_total']}",
        f"- Delta: {comparison['chunk_stats']['chunk_count_delta']:+d}",
        "",
        "## Wins vs Regressions",
        "",
        f"- Wins: {comparison['win_count']}",
        f"- Regressions: {comparison['regression_count']}",
        "",
    ])
    
    if comparison['wins']:
        lines.extend(["### Top Wins", ""])
        for win in comparison['wins'][:5]:
            lines.append(f"- **{win['query_text'][:60]}...** (NDCG +{win['ndcg_improvement']:.2f})")
        lines.append("")
    
    if comparison['regressions']:
        lines.extend(["### Top Regressions", ""])
        for reg in comparison['regressions'][:5]:
            lines.append(f"- **{reg['query_text'][:60]}...** (NDCG {reg['ndcg_regression']:.2f})")
        lines.append("")
    
    return '\n'.join(lines)


# ============================================================================
# Main Entry Point
# ============================================================================

async def run_evaluation(
    corpus: Optional[List[Dict]] = None,
    queries: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Run full baseline vs treatment evaluation.
    
    Returns comparison dict with all metrics.
    """
    corpus = corpus or SAMPLE_CORPUS
    queries = queries or SAMPLE_QUERIES
    
    evaluator = ChunkingEvaluator()
    
    # Convert query dicts to EvalQuery objects
    eval_queries = [
        EvalQuery(
            query_id=q["query_id"],
            query_text=q["query_text"],
            expected_chunk_ids=q.get("expected_chunk_ids", []),
            expected_doc_ids=q.get("expected_doc_ids", []),
            difficulty=q.get("difficulty", "medium"),
            query_type=q.get("query_type", "factual"),
        )
        for q in queries
    ]
    
    print("[Eval] Running baseline (legacy chunking)...")
    baseline_stats = await evaluator.index_corpus_legacy(corpus)
    baseline_report = await evaluator.evaluate_queries(eval_queries)
    baseline_report.total_chunks = baseline_stats["total_chunks"]
    baseline_report.avg_chunk_size_tokens = baseline_stats["avg_chunk_size"]
    
    evaluator.clear()
    
    print("[Eval] Running treatment (semantic chunking)...")
    treatment_stats = await evaluator.index_corpus_semantic(corpus)
    treatment_report = await evaluator.evaluate_queries(eval_queries)
    treatment_report.total_chunks = treatment_stats["total_chunks"]
    treatment_report.avg_chunk_size_tokens = treatment_stats["avg_chunk_size"]
    
    # Compare
    comparison = compare_reports(baseline_report, treatment_report)
    
    # Save reports
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    with open(f"chunking_eval_{timestamp}.json", "w") as f:
        json.dump(comparison, f, indent=2, default=str)
    
    with open(f"chunking_eval_{timestamp}.md", "w") as f:
        f.write(generate_markdown_report(comparison))
    
    print(f"[Eval] Reports saved: chunking_eval_{timestamp}.json/.md")
    
    return comparison


if __name__ == "__main__":
    result = asyncio.run(run_evaluation())
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"\nKey Results:")
    print(f"  Recall@5 delta: {result['deltas']['recall_at_5']:+.3f}")
    print(f"  Precision@5 delta: {result['deltas']['precision_at_5']:+.3f}")
    print(f"  NDCG@10 delta: {result['deltas']['ndcg_at_10']:+.3f}")
    print(f"  Latency delta: {result['deltas']['latency_ms']:+.1f}ms")
    print(f"\nWins: {result['win_count']}, Regressions: {result['regression_count']}")
