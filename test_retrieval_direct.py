#!/usr/bin/env python3
"""
Direct retrieval testing - bypasses auth
Tests Phase 1 (Intent) and Phase 2 (Context) directly
"""
import os
import sys
import asyncio
from dotenv import load_dotenv
load_dotenv('backend/.env')

sys.path.insert(0, 'backend')

from modules.retrieval_intent import classify_retrieval_intent, get_strategy_config
from modules.conversation_context import get_contextualized_query, ConversationContext

TWIN_ID = "cf3ffed1-5d56-422b-8ce9-1bd99cd43b22"

# Test queries based on the actual KB content (Accounting Valuation)
TEST_CASES = [
    {
        "turn": 1,
        "type": "greeting",
        "query": "Hi there!",
        "history": []
    },
    {
        "turn": 2,
        "type": "entity_lookup",
        "query": "What is Discounted Cash Flow?",
        "history": [{"role": "user", "content": "Hi there!"}, {"role": "assistant", "content": "Hello! How can I help you today?"}]
    },
    {
        "turn": 3,
        "type": "opinion",
        "query": "What do you think is the best valuation method?",
        "history": [
            {"role": "user", "content": "Hi there!"},
            {"role": "assistant", "content": "Hello! How can I help you today?"},
            {"role": "user", "content": "What is Discounted Cash Flow?"},
            {"role": "assistant", "content": "DCF is a valuation method that estimates the value of an investment based on its expected future cash flows."}
        ]
    },
    {
        "turn": 4,
        "type": "followup",
        "query": "Can you explain more about it?",
        "history": [
            {"role": "user", "content": "Hi there!"},
            {"role": "assistant", "content": "Hello! How can I help you today?"},
            {"role": "user", "content": "What is Discounted Cash Flow?"},
            {"role": "assistant", "content": "DCF is a valuation method that estimates the value of an investment based on its expected future cash flows."},
            {"role": "user", "content": "What do you think is the best valuation method?"},
            {"role": "assistant", "content": "I believe DCF is one of the most robust methods when you have reliable projections."}
        ]
    },
    {
        "turn": 5,
        "type": "comparison",
        "query": "How does DCF compare to P/E ratio?",
        "history": [
            {"role": "user", "content": "Hi there!"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "What is Discounted Cash Flow?"},
            {"role": "assistant", "content": "DCF is a valuation method..."},
            {"role": "user", "content": "Can you explain more about it?"},
            {"role": "assistant", "content": "Sure! DCF involves forecasting..."}
        ]
    },
    {
        "turn": 6,
        "type": "procedural",
        "query": "How do you calculate the Payback period?",
        "history": []
    },
    {
        "turn": 7,
        "type": "summarization",
        "query": "Summarize the key valuation methods",
        "history": []
    },
    {
        "turn": 8,
        "type": "followup_with_that",
        "query": "What are the risks with that?",
        "history": [
            {"role": "user", "content": "Summarize the key valuation methods"},
            {"role": "assistant", "content": "The main valuation methods are DCF, P/E ratio, Payback period, and Asset-based valuation."}
        ]
    }
]


async def test_phase1_intent_classification():
    """Test Phase 1: Intent Classification."""
    print("=" * 80)
    print("PHASE 1: INTENT CLASSIFICATION TEST")
    print("=" * 80)
    
    results = []
    
    for test in TEST_CASES:
        print(f"\nTurn {test['turn']} [{test['type'].upper()}]")
        print(f"Query: '{test['query']}'")
        
        # Classify intent
        intent = await classify_retrieval_intent(test['query'], test['history'])
        
        print(f"  Classified Intent: {intent.intent_type.value}")
        print(f"  Confidence: {intent.confidence:.2f}")
        print(f"  Is Followup: {intent.is_followup}")
        print(f"  Strategy: {intent.retrieval_strategy}")
        
        # Get strategy config
        strategy = get_strategy_config(intent.intent_type)
        print(f"  Top K: {strategy.get('top_k', 5)}")
        print(f"  Use HyDE: {strategy.get('use_hyde', True)}")
        print(f"  Metadata Filter: {strategy.get('metadata_filter', 'None')}")
        
        results.append({
            "turn": test['turn'],
            "type": test['type'],
            "query": test['query'],
            "intent": intent.intent_type.value,
            "confidence": intent.confidence,
            "strategy": intent.retrieval_strategy
        })
    
    return results


async def test_phase2_conversation_context():
    """Test Phase 2: Conversation Context."""
    print("\n" + "=" * 80)
    print("PHASE 2: CONVERSATION CONTEXT TEST")
    print("=" * 80)
    
    # Test coreference resolution
    print("\n--- Coreference Resolution Tests ---")
    
    coref_tests = [
        {
            "name": "Follow-up with 'it'",
            "query": "Can you explain more about it?",
            "history": [
                {"role": "user", "content": "What is Discounted Cash Flow?"},
                {"role": "assistant", "content": "DCF is a valuation method that estimates value based on future cash flows."}
            ],
            "expected_resolution": "Should resolve 'it' to 'DCF' or 'Discounted Cash Flow'"
        },
        {
            "name": "Follow-up with 'that'",
            "query": "What are the risks with that?",
            "history": [
                {"role": "user", "content": "Tell me about P/E ratio"},
                {"role": "assistant", "content": "P/E ratio compares a company's stock price to its earnings."}
            ],
            "expected_resolution": "Should resolve 'that' to 'P/E ratio'"
        },
        {
            "name": "Standalone query (no coreference)",
            "query": "What is the Payback period?",
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi! How can I help?"}
            ],
            "expected_resolution": "Should remain unchanged"
        }
    ]
    
    results = []
    
    for test in coref_tests:
        print(f"\nTest: {test['name']}")
        print(f"Query: '{test['query']}'")
        print(f"Expected: {test['expected_resolution']}")
        
        # Resolve coreferences
        resolved, context, mappings = await get_contextualized_query(
            test['query'], 
            test['history']
        )
        
        print(f"Resolved Query: '{resolved}'")
        print(f"Pronoun Mappings: {mappings}")
        print(f"Themes Detected: {context.themes}")
        print(f"Current Topic: {context.current_topic}")
        
        changed = resolved != test['query']
        print(f"Changed: {changed}")
        
        results.append({
            "test": test['name'],
            "original": test['query'],
            "resolved": resolved,
            "changed": changed,
            "mappings": mappings
        })
    
    return results


def evaluate_results(phase1_results, phase2_results):
    """Evaluate both phases."""
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    
    # Phase 1 evaluation
    print("\n[PHASE 1 - INTENT CLASSIFICATION]")
    intent_distribution = {}
    for r in phase1_results:
        intent = r['intent']
        intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
    
    print("Intent Distribution:")
    for intent, count in intent_distribution.items():
        print(f"  - {intent}: {count}")
    
    # Check coverage
    expected_intents = ['greeting', 'entity_lookup', 'opinion', 'followup', 'comparison', 'procedural', 'summarization']
    print("\nIntent Coverage:")
    for intent in expected_intents:
        if intent in intent_distribution:
            print(f"  [OK] {intent}")
        else:
            print(f"  [MISSING] {intent}")
    
    # Phase 2 evaluation
    print("\n[PHASE 2 - CONVERSATION CONTEXT]")
    coref_success = sum(1 for r in phase2_results if r['changed'])
    print(f"Coreference Resolutions: {coref_success}/{len(phase2_results)}")
    
    for r in phase2_results:
        status = "[OK]" if r['changed'] else "[UNCHANGED]"
        print(f"  {status} {r['test']}: '{r['original'][:30]}...' -> '{r['resolved'][:30]}...'")
    
    # Overall
    print("\n" + "=" * 80)
    phase1_score = 8.0 if len(intent_distribution) >= 5 else 6.0
    phase2_score = 8.0 if coref_success >= 2 else 5.0
    overall = (phase1_score + phase2_score) / 2
    
    print(f"Phase 1 Score: {phase1_score}/10")
    print(f"Phase 2 Score: {phase2_score}/10")
    print(f"Overall Score: {overall}/10")
    print("=" * 80)
    
    if overall >= 7:
        print("[RESULT]: PASSED - Both phases working")
        print("[RECOMMENDATION]: Proceed to Phase 3")
    elif overall >= 5:
        print("[RESULT]: PARTIAL - Some improvements needed")
        print("[RECOMMENDATION]: Address issues before Phase 3")
    else:
        print("[RESULT]: FAILED - Significant issues")
        print("[RECOMMENDATION]: Debug both phases")
    
    return {
        "phase1_score": phase1_score,
        "phase2_score": phase2_score,
        "overall_score": overall,
        "phase1_results": phase1_results,
        "phase2_results": phase2_results
    }


async def main():
    # Run Phase 1 tests
    phase1_results = await test_phase1_intent_classification()
    
    # Run Phase 2 tests
    phase2_results = await test_phase2_conversation_context()
    
    # Evaluate
    evaluation = evaluate_results(phase1_results, phase2_results)
    
    # Save results
    import json
    with open("phase1_2_test_results.json", "w") as f:
        json.dump(evaluation, f, indent=2)
    
    print("\n[FILE] Results saved to phase1_2_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
