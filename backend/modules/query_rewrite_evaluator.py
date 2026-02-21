"""
Query Rewrite Evaluation Framework

Measures the quality of conversational query rewrites using multiple metrics:
1. Semantic similarity to expected rewrites
2. Retrieval quality improvement (NDCG@5)
3. LLM-as-judge scoring
4. Intent classification accuracy

Usage:
    python -m modules.query_rewrite_evaluator
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from modules.query_rewriter import (
    ConversationalQueryRewriter,
    QueryRewriteResult,
    QUERY_REWRITING_ENABLED,
)
from modules.clients import get_openai_client

# Try to import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

# Try to import retrieval for NDCG calculation
try:
    from modules.retrieval import retrieve_context
    RETRIEVAL_AVAILABLE = True
except ImportError:
    RETRIEVAL_AVAILABLE = False


@dataclass
class EvaluatedRewrite:
    """Result of evaluating a single query rewrite."""
    original_query: str
    expected_rewrite: str
    actual_rewrite: str
    semantic_similarity: float
    retrieval_improvement: float
    llm_judge_score: float
    intent_match: bool
    latency_ms: float
    passed: bool


@dataclass
class EvaluationSummary:
    """Summary of evaluation run."""
    total_queries: int
    passed_queries: int
    avg_semantic_similarity: float
    avg_retrieval_improvement: float
    avg_llm_judge_score: float
    intent_accuracy: float
    avg_latency_ms: float
    pass_rate: float


class QueryRewriteEvaluator:
    """Evaluates the quality of query rewrites."""
    
    def __init__(self):
        self.rewriter = ConversationalQueryRewriter()
        self._embedding_model = None
        self._llm_client = None
    
    def _get_embedding_model(self):
        """Lazy load embedding model."""
        if self._embedding_model is None and EMBEDDINGS_AVAILABLE:
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model
    
    def _get_llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            self._llm_client = get_openai_client()
        return self._llm_client
    
    def calculate_semantic_similarity(
        self,
        expected: str,
        actual: str,
    ) -> float:
        """
        Calculate semantic similarity between expected and actual rewrite.
        
        Uses sentence embeddings and cosine similarity.
        """
        if not EMBEDDINGS_AVAILABLE:
            # Fallback to simple string similarity
            return self._simple_similarity(expected, actual)
        
        model = self._get_embedding_model()
        if model is None:
            return self._simple_similarity(expected, actual)
        
        try:
            embeddings = model.encode([expected, actual])
            # Cosine similarity
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception as e:
            print(f"Embedding similarity failed: {e}")
            return self._simple_similarity(expected, actual)
    
    def _simple_similarity(self, expected: str, actual: str) -> float:
        """Simple word overlap similarity as fallback."""
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())
        
        if not expected_words:
            return 0.0
        
        intersection = expected_words & actual_words
        return len(intersection) / len(expected_words)
    
    async def calculate_retrieval_improvement(
        self,
        original_query: str,
        rewritten_query: str,
        twin_id: str,
    ) -> float:
        """
        Calculate retrieval quality improvement.
        
        Compares NDCG@5 scores between original and rewritten queries.
        Returns improvement ratio (positive = better).
        """
        if not RETRIEVAL_AVAILABLE:
            return 0.0
        
        try:
            # Retrieve with original query
            original_results = await retrieve_context(
                query=original_query,
                twin_id=twin_id,
                top_k=5,
            )
            
            # Retrieve with rewritten query
            rewritten_results = await retrieve_context(
                query=rewritten_query,
                twin_id=twin_id,
                top_k=5,
            )
            
            # Calculate scores (use vector scores as proxy for relevance)
            original_scores = [
                float(r.get("score", 0.0) or 0.0)
                for r in original_results
            ]
            rewritten_scores = [
                float(r.get("score", 0.0) or 0.0)
                for r in rewritten_results
            ]
            
            # Calculate DCG
            def dcg(scores):
                return sum(
                    (2 ** score - 1) / np.log2(i + 2)
                    for i, score in enumerate(scores)
                )
            
            original_dcg = dcg(original_scores)
            rewritten_dcg = dcg(rewritten_scores)
            
            # Improvement ratio
            if original_dcg == 0:
                return 1.0 if rewritten_dcg > 0 else 0.0
            
            return (rewritten_dcg - original_dcg) / original_dcg
            
        except Exception as e:
            print(f"Retrieval improvement calculation failed: {e}")
            return 0.0
    
    async def llm_judge_score(
        self,
        original_query: str,
        rewritten_query: str,
        conversation_history: List[Dict[str, str]],
    ) -> float:
        """
        Use LLM as a judge to score rewrite quality.
        
        Returns score from 1-5 where:
        1 = Completely wrong
        2 = Major issues
        3 = Acceptable
        4 = Good
        5 = Perfect
        """
        client = self._get_llm_client()
        
        # Format history
        history_str = ""
        for msg in conversation_history[-5:]:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            history_str += f"{role}: {content}\n"
        
        prompt = f"""Rate the quality of this query rewrite:

Conversation History:
{history_str}

Original Query: {original_query}
Rewritten Query: {rewritten_query}

Score 1-5:
1: Completely wrong or nonsensical - rewrite contradicts intent
2: Major issues - missing critical context or wrong entity
3: Acceptable but incomplete - captures basic intent but vague
4: Good - captures intent well, specific and standalone
5: Perfect - fully standalone, captures all nuances

Provide ONLY a JSON response:
{{"score": 4, "reasoning": "brief explanation"}}"""

        try:
            loop = asyncio.get_event_loop()
            
            def _call():
                return client.chat.completions.create(
                    model="gpt-4o",  # Using latest model for evaluation
                    messages=[
                        {"role": "system", "content": "You are an expert evaluator of query rewriting systems."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
            
            response = await loop.run_in_executor(None, _call)
            content = response.choices[0].message.content
            parsed = json.loads(content)
            
            score = float(parsed.get("score", 3.0))
            # Normalize to 0-1
            return min(1.0, max(0.0, (score - 1) / 4))
            
        except Exception as e:
            print(f"LLM judge failed: {e}")
            return 0.5  # Neutral score on failure
    
    async def evaluate_single(
        self,
        test_case: Dict[str, Any],
        twin_id: Optional[str] = None,
    ) -> EvaluatedRewrite:
        """Evaluate a single test case."""
        original = test_case["current_query"]
        expected = test_case["expected_rewrite"]
        history = test_case.get("conversation", [])
        expected_intent = test_case.get("expected_intent")
        
        # Perform rewrite
        start_time = datetime.utcnow()
        result = await self.rewriter.rewrite(original, history)
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Calculate metrics
        semantic_sim = self.calculate_semantic_similarity(expected, result.standalone_query)
        
        retrieval_imp = 0.0
        if twin_id:
            retrieval_imp = await self.calculate_retrieval_improvement(
                original, result.standalone_query, twin_id
            )
        
        llm_score = await self.llm_judge_score(original, result.standalone_query, history)
        
        intent_match = True
        if expected_intent:
            intent_match = result.intent == expected_intent
        
        # Determine if passed
        passed = (
            semantic_sim >= 0.7 and
            llm_score >= 0.6 and
            intent_match
        )
        
        return EvaluatedRewrite(
            original_query=original,
            expected_rewrite=expected,
            actual_rewrite=result.standalone_query,
            semantic_similarity=semantic_sim,
            retrieval_improvement=retrieval_imp,
            llm_judge_score=llm_score,
            intent_match=intent_match,
            latency_ms=latency_ms,
            passed=passed,
        )
    
    async def evaluate_batch(
        self,
        test_cases: List[Dict[str, Any]],
        twin_id: Optional[str] = None,
    ) -> EvaluationSummary:
        """Evaluate a batch of test cases."""
        results = []
        
        for test_case in test_cases:
            try:
                result = await self.evaluate_single(test_case, twin_id)
                results.append(result)
            except Exception as e:
                print(f"Failed to evaluate test case: {e}")
        
        if not results:
            return EvaluationSummary(
                total_queries=0,
                passed_queries=0,
                avg_semantic_similarity=0.0,
                avg_retrieval_improvement=0.0,
                avg_llm_judge_score=0.0,
                intent_accuracy=0.0,
                avg_latency_ms=0.0,
                pass_rate=0.0,
            )
        
        return EvaluationSummary(
            total_queries=len(results),
            passed_queries=sum(1 for r in results if r.passed),
            avg_semantic_similarity=np.mean([r.semantic_similarity for r in results]),
            avg_retrieval_improvement=np.mean([r.retrieval_improvement for r in results]),
            avg_llm_judge_score=np.mean([r.llm_judge_score for r in results]),
            intent_accuracy=np.mean([r.intent_match for r in results]),
            avg_latency_ms=np.mean([r.latency_ms for r in results]),
            pass_rate=sum(1 for r in results if r.passed) / len(results),
        )
    
    def print_report(self, summary: EvaluationSummary, detailed_results: List[EvaluatedRewrite]):
        """Print evaluation report."""
        print("\n" + "=" * 60)
        print("QUERY REWRITE EVALUATION REPORT")
        print("=" * 60)
        print(f"\nTotal Queries: {summary.total_queries}")
        print(f"Passed: {summary.passed_queries} ({summary.pass_rate:.1%})")
        print(f"\nMetrics:")
        print(f"  Semantic Similarity: {summary.avg_semantic_similarity:.3f}")
        print(f"  Retrieval Improvement: {summary.avg_retrieval_improvement:+.1%}")
        print(f"  LLM Judge Score: {summary.avg_llm_judge_score:.3f}")
        print(f"  Intent Accuracy: {summary.intent_accuracy:.1%}")
        print(f"  Avg Latency: {summary.avg_latency_ms:.0f}ms")
        
        print("\n" + "-" * 60)
        print("DETAILED RESULTS")
        print("-" * 60)
        
        for i, result in enumerate(detailed_results, 1):
            status = "PASS" if result.passed else "FAIL"
            print(f"\n{i}. [{status}] {result.original_query[:50]}...")
            print(f"   Expected: {result.expected_rewrite[:60]}...")
            print(f"   Actual:   {result.actual_rewrite[:60]}...")
            print(f"   Similarity: {result.semantic_similarity:.2f}, "
                  f"LLM: {result.llm_judge_score:.2f}, "
                  f"Latency: {result.latency_ms:.0f}ms")


# Test dataset
TEST_DATASET = [
    {
        "conversation": [
            {"role": "user", "content": "What's our Q3 revenue?"},
            {"role": "assistant", "content": "Q3 revenue was $5.2M, up 15% year over year."},
        ],
        "current_query": "What about Q4?",
        "expected_rewrite": "What was the Q4 revenue?",
        "expected_intent": "follow_up",
        "difficulty": "easy",
    },
    {
        "conversation": [
            {"role": "user", "content": "Show me the roadmap for 2024."},
            {"role": "assistant", "content": "The roadmap includes: Q1 - mobile app, Q2 - AI features, Q3 - enterprise."},
        ],
        "current_query": "When is the AI feature shipping?",
        "expected_rewrite": "When is the AI feature shipping according to the 2024 roadmap?",
        "expected_intent": "temporal_analysis",
        "difficulty": "medium",
    },
    {
        "conversation": [
            {"role": "user", "content": "Tell me about our pricing."},
            {"role": "assistant", "content": "We have three tiers: Starter at $99/mo, Pro at $299/mo, Enterprise custom."},
        ],
        "current_query": "Is that competitive?",
        "expected_rewrite": "Is our pricing competitive?",
        "expected_intent": "comparison",
        "difficulty": "medium",
    },
    {
        "conversation": [
            {"role": "user", "content": "Revenue dropped in Q2."},
            {"role": "assistant", "content": "Yes, Q2 revenue was $4.1M, down from $5.2M in Q1."},
        ],
        "current_query": "Why?",
        "expected_rewrite": "Why did revenue drop in Q2?",
        "expected_intent": "causal_analysis",
        "difficulty": "hard",
    },
    {
        "conversation": [
            {"role": "user", "content": "How do I reset my password?"},
            {"role": "assistant", "content": "Go to Settings > Security > Change Password."},
        ],
        "current_query": "What about 2FA?",
        "expected_rewrite": "How do I set up or reset 2FA?",
        "expected_intent": "procedural",
        "difficulty": "medium",
    },
]


async def main():
    """Run evaluation on test dataset."""
    print("Query Rewrite Evaluation")
    print("=" * 60)
    
    if not QUERY_REWRITING_ENABLED:
        print("WARNING: Query rewriting is disabled. Set QUERY_REWRITING_ENABLED=true")
    
    evaluator = QueryRewriteEvaluator()
    
    # Run evaluation
    summary = await evaluator.evaluate_batch(TEST_DATASET)
    
    # Get detailed results for printing
    detailed_results = []
    for test_case in TEST_DATASET:
        result = await evaluator.evaluate_single(test_case)
        detailed_results.append(result)
    
    # Print report
    evaluator.print_report(summary, detailed_results)
    
    # Save results to file
    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_queries": summary.total_queries,
            "passed_queries": summary.passed_queries,
            "pass_rate": summary.pass_rate,
            "avg_semantic_similarity": summary.avg_semantic_similarity,
            "avg_retrieval_improvement": summary.avg_retrieval_improvement,
            "avg_llm_judge_score": summary.avg_llm_judge_score,
            "intent_accuracy": summary.intent_accuracy,
            "avg_latency_ms": summary.avg_latency_ms,
        },
        "details": [
            {
                "original": r.original_query,
                "expected": r.expected_rewrite,
                "actual": r.actual_rewrite,
                "semantic_similarity": r.semantic_similarity,
                "llm_judge_score": r.llm_judge_score,
                "passed": r.passed,
            }
            for r in detailed_results
        ],
    }
    
    with open("query_rewrite_eval_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to query_rewrite_eval_results.json")
    
    # Return exit code based on pass rate
    return 0 if summary.pass_rate >= 0.7 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
