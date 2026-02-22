#!/usr/bin/env python3
"""
Phase 3 Test: Abstractive Summarization
Tests the new summarization capability with the twin
"""
import os
import sys
import asyncio
import json
from dotenv import load_dotenv

load_dotenv('backend/.env')
sys.path.insert(0, 'backend')

from modules.clients import get_pinecone_index
from modules.delphi_namespace import get_namespace_candidates_for_twin
from modules.retrieval_intent import classify_retrieval_intent, RetrievalIntentType
from modules.abstractive_summarizer import (
    generate_abstractive_summary,
    should_use_abstractive_summary,
    format_chunks_for_summarization,
    determine_summary_type
)

TWIN_ID = "cf3ffed1-5d56-422b-8ce9-1bd99cd43b22"


async def retrieve_chunks(query: str, top_k: int = 15) -> list:
    """Retrieve chunks from Pinecone."""
    from modules.retrieval import retrieve_context_vectors
    
    try:
        chunks = await retrieve_context_vectors(
            query=query,
            twin_id=TWIN_ID,
            top_k=top_k
        )
        return chunks
    except Exception as e:
        print(f"Retrieval error: {e}")
        return []


async def test_phase3_summarization():
    """Test Phase 3 abstractive summarization."""
    
    print("=" * 80)
    print("PHASE 3: ABSTRACTIVE SUMMARIZATION TEST")
    print("=" * 80)
    print(f"Twin ID: {TWIN_ID}")
    print(f"Knowledge Base: Accounting Valuation Methods")
    print("=" * 80)
    
    # Test queries for summarization
    test_queries = [
        {
            "query": "Summarize your background",
            "type": "background_summary",
            "expected": "Coherent narrative about professional background"
        },
        {
            "query": "Tell me about yourself",
            "type": "self_introduction",
            "expected": "Natural self-introduction paragraph"
        },
        {
            "query": "What is your expertise in valuation?",
            "type": "expertise",
            "expected": "Description of valuation skills and methods"
        },
        {
            "query": "Summarize the key valuation methods",
            "type": "methods_summary",
            "expected": "Overview of DCF, P/E, Payback, etc."
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n{'-' * 80}")
        print(f"TEST {i}/{len(test_queries)}: {test['type'].upper()}")
        print(f"{'-' * 80}")
        print(f"Query: '{test['query']}'")
        print(f"Expected: {test['expected']}")
        
        # Step 1: Check intent classification
        intent = await classify_retrieval_intent(test['query'])
        print(f"\n[Phase 1] Intent: {intent.intent_type.value} (confidence: {intent.confidence:.2f})")
        
        # Step 2: Retrieve chunks
        print("\n[Phase 2] Retrieving chunks...")
        chunks = await retrieve_chunks(test['query'], top_k=15)
        print(f"Retrieved: {len(chunks)} chunks")
        
        if not chunks:
            print("[ERROR] No chunks retrieved")
            continue
        
        # Show sample chunks
        print("\nSample retrieved chunks:")
        for j, chunk in enumerate(chunks[:3], 1):
            text = chunk.get('text', '')[:100]
            print(f"  {j}. {text}...")
        
        # Step 3: Check if abstractive summary should be used
        should_use = await should_use_abstractive_summary(
            test['query'], 
            chunks, 
            intent.intent_type.value
        )
        print(f"\n[Phase 3] Should use abstractive summary: {should_use}")
        
        if should_use:
            # Determine summary type
            summary_type = determine_summary_type(test['query'], chunks)
            print(f"Summary type: {summary_type}")
            
            # Generate abstractive summary
            print("\nGenerating abstractive summary...")
            summary_result = await generate_abstractive_summary(
                query=test['query'],
                chunks=chunks,
                max_tokens=300,
                temperature=0.4
            )
            
            print(f"\n{'=' * 80}")
            print("GENERATED SUMMARY:")
            print('=' * 80)
            print(summary_result.summary)
            print(f"\n[Quality Score]: {summary_result.synthesis_quality:.2f}")
            print(f"[Key Points]: {len(summary_result.key_points)}")
            for kp in summary_result.key_points:
                print(f"  - {kp[:80]}...")
            print(f"[Citations]: {len(summary_result.citations)}")
            
            results.append({
                "query": test['query'],
                "type": test['type'],
                "intent": intent.intent_type.value,
                "chunks_count": len(chunks),
                "summary": summary_result.summary,
                "quality": summary_result.synthesis_quality,
                "key_points": summary_result.key_points
            })
        else:
            print("[SKIP] Abstractive summarization not triggered")
            results.append({
                "query": test['query'],
                "type": test['type'],
                "intent": intent.intent_type.value,
                "skipped": True
            })
        
        await asyncio.sleep(1)  # Brief pause between tests
    
    # Evaluation
    print("\n" + "=" * 80)
    print("EVALUATION")
    print("=" * 80)
    
    successful = sum(1 for r in results if not r.get('skipped') and r.get('quality', 0) > 0.5)
    total = len(results)
    
    print(f"\nTests run: {total}")
    print(f"Successful summaries: {successful}")
    print(f"Success rate: {successful/total*100:.1f}%")
    
    # Quality scores
    qualities = [r.get('quality', 0) for r in results if not r.get('skipped')]
    if qualities:
        avg_quality = sum(qualities) / len(qualities)
        print(f"Average synthesis quality: {avg_quality:.2f}")
    
    # Overall score
    score = (successful / total * 5) + (avg_quality * 5 if qualities else 0)
    score = min(score, 10)
    
    print(f"\n{'=' * 80}")
    print(f"PHASE 3 OVERALL SCORE: {score:.1f}/10")
    print(f"{'=' * 80}")
    
    if score >= 8:
        print("[RESULT]: EXCELLENT - Abstractive summarization working well")
        print("[RECOMMENDATION]: Feature ready for production")
    elif score >= 6:
        print("[RESULT]: GOOD - Minor improvements needed")
        print("[RECOMMENDATION]: Tune prompts and parameters")
    else:
        print("[RESULT]: NEEDS WORK - Significant issues")
        print("[RECOMMENDATION]: Debug summarization pipeline")
    
    # Save results
    with open("phase3_test_results.json", "w") as f:
        json.dump({
            "score": score,
            "successful": successful,
            "total": total,
            "results": results
        }, f, indent=2)
    
    print("\n[FILE] Results saved to phase3_test_results.json")
    
    return score


if __name__ == "__main__":
    score = asyncio.run(test_phase3_summarization())
    
    if score >= 6:
        print("\n✅ PHASE 3: PASSED")
    else:
        print("\n❌ PHASE 3: NEEDS IMPROVEMENT")
