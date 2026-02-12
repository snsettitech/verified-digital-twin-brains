#!/usr/bin/env python3
"""Quick test of HF embeddings."""
import sys
sys.path.insert(0, '..')

print("Testing HF Embeddings...")

try:
    from modules.embeddings_hf import HFEmbeddingClient
    import time
    
    print("Loading model via HFEmbeddingClient...")
    start = time.time()
    client = HFEmbeddingClient()
    load_time = (time.time() - start)
    
    print(f"Model loaded in {load_time:.1f}s")
    print(f"Model: {client.model_name}")
    print(f"Device: {client.device}")
    print(f"Dimension: {client.dimension}")
    
    print("\nTesting embedding...")
    start = time.time()
    emb = client.embed("Test text")
    elapsed = (time.time() - start) * 1000
    
    print(f"Embedding generated in {elapsed:.1f}ms")
    print(f"Vector length: {len(emb)}")
    print("\nSUCCESS!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
