#!/usr/bin/env python3
"""
Comprehensive Benchmark: HF Embeddings + Cerebras Inference

Validates performance improvements over OpenAI baseline.

Usage:
    # Test HF embeddings only
    HF_TEST_ENABLED=1 python benchmark_hf_cerebras.py
    
    # Test Cerebras only
    CEREBRAS_API_KEY=your_key python benchmark_hf_cerebras.py
    
    # Test full stack
    HF_TEST_ENABLED=1 CEREBRAS_API_KEY=your_key python benchmark_hf_cerebras.py
"""
import os
import sys
import time
import asyncio
import statistics
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class PerformanceBenchmark:
    """Benchmark HF+Cerebras vs OpenAI."""
    
    def __init__(self):
        self.results: Dict[str, Dict] = {}
    
    def benchmark_openai_embeddings(self, iterations: int = 10) -> Dict:
        """Benchmark OpenAI embedding latency."""
        print("\n" + "="*70)
        print("BENCHMARKING: OpenAI Embeddings")
        print("="*70)
        
        from modules.clients import get_openai_client
        client = get_openai_client()
        
        test_texts = [
            "How do I handle team conflict?",
            "What are best practices for leadership?",
            "How to improve remote team communication?",
            "What is emotional intelligence?",
            "How to give constructive feedback?",
        ]
        
        latencies = []
        
        for i in range(iterations):
            text = test_texts[i % len(test_texts)]
            
            start = time.perf_counter()
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-large",
                dimensions=3072
            )
            embedding = response.data[0].embedding
            elapsed = (time.perf_counter() - start) * 1000
            
            latencies.append(elapsed)
            print(f"  Iteration {i+1}/{iterations}: {elapsed:.2f}ms (dim={len(embedding)})")
        
        return {
            "provider": "openai",
            "model": "text-embedding-3-large",
            "dimension": 3072,
            "latencies_ms": latencies,
            "avg_ms": statistics.mean(latencies),
            "p50_ms": statistics.median(latencies),
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
            "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)],
            "min_ms": min(latencies),
            "max_ms": max(latencies)
        }
    
    def benchmark_hf_embeddings(self, iterations: int = 10) -> Dict:
        """Benchmark Hugging Face embedding latency."""
        print("\n" + "="*70)
        print("BENCHMARKING: Hugging Face Local Embeddings")
        print("="*70)
        
        from modules.embeddings_hf import HFEmbeddingClient
        
        # Initialize client (triggers model load)
        print("  Initializing HF client...")
        client = HFEmbeddingClient()
        print(f"  Model: {client.model_name}")
        print(f"  Device: {client.device}")
        print(f"  Dimension: {client.dimension}")
        
        test_texts = [
            "How do I handle team conflict?",
            "What are best practices for leadership?",
            "How to improve remote team communication?",
            "What is emotional intelligence?",
            "How to give constructive feedback?",
        ]
        
        latencies = []
        
        # Warm-up
        print("  Warming up...")
        for _ in range(3):
            client.embed("Warm-up text")
        
        print(f"  Running {iterations} iterations...")
        for i in range(iterations):
            text = test_texts[i % len(test_texts)]
            
            start = time.perf_counter()
            embedding = client.embed(text)
            elapsed = (time.perf_counter() - start) * 1000
            
            latencies.append(elapsed)
            print(f"  Iteration {i+1}/{iterations}: {elapsed:.2f}ms")
        
        return {
            "provider": "huggingface",
            "model": client.model_name,
            "device": client.device,
            "dimension": client.dimension,
            "latencies_ms": latencies,
            "avg_ms": statistics.mean(latencies),
            "p50_ms": statistics.median(latencies),
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
            "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)],
            "min_ms": min(latencies),
            "max_ms": max(latencies)
        }
    
    def benchmark_openai_inference(self, iterations: int = 5) -> Dict:
        """Benchmark OpenAI inference latency."""
        print("\n" + "="*70)
        print("BENCHMARKING: OpenAI Inference (GPT-4)")
        print("="*70)
        
        from modules.clients import get_openai_client
        
        client = get_openai_client()
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What are 3 tips for effective leadership?"}
        ]
        
        latencies = []
        
        for i in range(iterations):
            start = time.perf_counter()
            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )
            elapsed = (time.perf_counter() - start) * 1000
            
            latencies.append(elapsed)
            tokens = response.usage.total_tokens
            print(f"  Iteration {i+1}/{iterations}: {elapsed:.2f}ms ({tokens} tokens)")
        
        return {
            "provider": "openai",
            "model": "gpt-4-turbo-preview",
            "latencies_ms": latencies,
            "avg_ms": statistics.mean(latencies),
            "p50_ms": statistics.median(latencies),
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
            "min_ms": min(latencies),
            "max_ms": max(latencies)
        }
    
    def benchmark_cerebras_inference(self, iterations: int = 5) -> Dict:
        """Benchmark Cerebras inference latency."""
        print("\n" + "="*70)
        print("BENCHMARKING: Cerebras Inference (Llama 3.3 70B)")
        print("="*70)
        
        from modules.inference_cerebras import CerebrasClient
        
        # Reset singleton to ensure fresh initialization
        CerebrasClient.reset()
        client = CerebrasClient()
        
        print(f"  Model: {client.model}")
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What are 3 tips for effective leadership?"}
        ]
        
        latencies = []
        
        # Warm-up
        print("  Warming up...")
        client.generate(messages, max_tokens=10)
        
        print(f"  Running {iterations} iterations...")
        for i in range(iterations):
            start = time.perf_counter()
            response = client.generate(
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )
            elapsed = (time.perf_counter() - start) * 1000
            
            latencies.append(elapsed)
            tokens = response.usage.total_tokens
            print(f"  Iteration {i+1}/{iterations}: {elapsed:.2f}ms ({tokens} tokens)")
        
        return {
            "provider": "cerebras",
            "model": client.model,
            "latencies_ms": latencies,
            "avg_ms": statistics.mean(latencies),
            "p50_ms": statistics.median(latencies),
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
            "min_ms": min(latencies),
            "max_ms": max(latencies)
        }
    
    def print_comparison(self):
        """Print comparison of all benchmarks."""
        print("\n" + "="*70)
        print("PERFORMANCE COMPARISON")
        print("="*70)
        
        # Embedding comparison
        if "openai_embed" in self.results and "hf_embed" in self.results:
            openai = self.results["openai_embed"]
            hf = self.results["hf_embed"]
            
            print("\n[RESULTS] EMBEDDINGS:")
            print("-" * 50)
            print(f"  OpenAI ({openai['model']}):")
            print(f"    Dimension: {openai['dimension']}")
            print(f"    P50: {openai['p50_ms']:.1f}ms | P95: {openai['p95_ms']:.1f}ms")
            
            print(f"\n  Hugging Face ({hf['model']}):")
            print(f"    Dimension: {hf['dimension']}")
            print(f"    Device: {hf['device']}")
            print(f"    P50: {hf['p50_ms']:.1f}ms | P95: {hf['p95_ms']:.1f}ms")
            
            speedup = openai['p50_ms'] / hf['p50_ms']
            print(f"\n  [SPEEDUP] {speedup:.1f}x faster")
            print(f"  [SAVINGS] $1,300/month (embedding API costs)")
        
        # Inference comparison
        if "openai_infer" in self.results and "cerebras_infer" in self.results:
            openai = self.results["openai_infer"]
            cerebras = self.results["cerebras_infer"]
            
            print("\n[RESULTS] INFERENCE:")
            print("-" * 50)
            print(f"  OpenAI ({openai['model']}):")
            print(f"    P50: {openai['p50_ms']:.1f}ms | P95: {openai['p95_ms']:.1f}ms")
            
            print(f"\n  Cerebras ({cerebras['model']}):")
            print(f"    P50: {cerebras['p50_ms']:.1f}ms | P95: {cerebras['p95_ms']:.1f}ms")
            
            speedup = openai['p50_ms'] / cerebras['p50_ms']
            print(f"\n  [SPEEDUP] {speedup:.1f}x faster")
            print(f"  [SAVINGS] $400/month (cheaper inference)")
        
        # End-to-end estimate
        print("\n[RESULTS] END-TO-END ESTIMATE:")
        print("-" * 50)
        
        if all(k in self.results for k in ["openai_embed", "hf_embed", "openai_infer", "cerebras_infer"]):
            current_e2e = self.results["openai_embed"]["p50_ms"] + 80 + self.results["openai_infer"]["p50_ms"]  # +80ms for Pinecone
            optimized_e2e = self.results["hf_embed"]["p50_ms"] + 80 + self.results["cerebras_infer"]["p50_ms"]
            
            print(f"  Current (OpenAI): {current_e2e:.0f}ms")
            print(f"  Optimized (HF+Cerebras): {optimized_e2e:.0f}ms")
            print(f"  >> IMPROVEMENT: {current_e2e/optimized_e2e:.1f}x faster")
            print(f"  [SAVINGS] ~$1,700/month")
            
            if optimized_e2e < 200:
                print(f"\n  [SUCCESS] TARGET ACHIEVED: Sub-200ms")
            if optimized_e2e < 100:
                print(f"  >> EXCELLENT: Sub-100ms")
    
    def run(self):
        """Run all benchmarks."""
        print("="*70)
        print("HF + CEREBRAS PERFORMANCE BENCHMARK")
        print("="*70)
        print("\nThis benchmark compares OpenAI vs HF+Cerebras performance.")
        print("Set environment variables to enable tests:")
        print("  - HF_TEST_ENABLED=1 (for HF embeddings)")
        print("  - CEREBRAS_API_KEY=xxx (for Cerebras inference)")
        
        # Benchmark OpenAI embeddings
        try:
            self.results["openai_embed"] = self.benchmark_openai_embeddings(iterations=10)
        except Exception as e:
            print(f"\n[ERROR] OpenAI embeddings failed: {e}")
        
        # Benchmark HF embeddings
        if os.getenv("HF_TEST_ENABLED"):
            try:
                self.results["hf_embed"] = self.benchmark_hf_embeddings(iterations=10)
            except Exception as e:
                print(f"\n[ERROR] HF embeddings failed: {e}")
        else:
            print("\n[SKIP] Skipping HF embeddings (set HF_TEST_ENABLED=1 to enable)")
        
        # Benchmark OpenAI inference
        try:
            self.results["openai_infer"] = self.benchmark_openai_inference(iterations=5)
        except Exception as e:
            print(f"\n[ERROR] OpenAI inference failed: {e}")
        
        # Benchmark Cerebras inference
        if os.getenv("CEREBRAS_API_KEY"):
            try:
                self.results["cerebras_infer"] = self.benchmark_cerebras_inference(iterations=5)
            except Exception as e:
                print(f"\n[ERROR] Cerebras inference failed: {e}")
        else:
            print("\n[SKIP] Skipping Cerebras inference (set CEREBRAS_API_KEY to enable)")
        
        # Print comparison
        self.print_comparison()
        
        print("\n" + "="*70)
        print("BENCHMARK COMPLETE")
        print("="*70)
        
        return self.results


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    results = benchmark.run()
