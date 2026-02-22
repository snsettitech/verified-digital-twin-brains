#!/usr/bin/env python3
"""
Phase 1 Local Evaluation: Test intent classification without needing API auth
Uses Gemini to evaluate the intent classification quality
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv('backend/.env')

sys.path.insert(0, 'backend')

from modules.retrieval_intent import classify_retrieval_intent, RetrievalIntentType

# Test queries with expected intents
TEST_CASES = [
    # Greeting
    {"query": "Hello!", "expected": "greeting", "description": "Simple greeting"},
    {"query": "Hi there, how are you?", "expected": "greeting", "description": "Greeting with question"},
    
    # Opinion
    {"query": "What do you think about AI?", "expected": "opinion", "description": "Opinion on topic"},
    {"query": "What's your view on remote work?", "expected": "opinion", "description": "View on topic"},
    
    # Entity lookup
    {"query": "What is machine learning?", "expected": "entity_lookup", "description": "Definition question"},
    {"query": "Tell me about your experience at Google", "expected": "entity_lookup", "description": "Experience question"},
    
    # Comparison
    {"query": "Compare Python and JavaScript", "expected": "comparison", "description": "Direct comparison"},
    {"query": "What's the difference between REST and GraphQL?", "expected": "comparison", "description": "Difference question"},
    
    # Procedural
    {"query": "How do you build a startup?", "expected": "procedural", "description": "How-to question"},
    {"query": "What are the steps to learn data science?", "expected": "procedural", "description": "Steps question"},
    
    # Summarization
    {"query": "Summarize your career", "expected": "summarization", "description": "Direct summary"},
    {"query": "Give me an overview of your expertise", "expected": "summarization", "description": "Overview request"},
    
    # Followup (these will be marked as entity_lookup by heuristic, but context would help)
    {"query": "What about that?", "expected": "followup", "description": "Ambiguous followup"},
    {"query": "Tell me more", "expected": "followup", "description": "Vague followup"},
    
    # Temporal
    {"query": "What did you do in 2023?", "expected": "temporal", "description": "Time-specific"},
    
    # Causal
    {"query": "Why did you choose this career?", "expected": "causal", "description": "Why question"},
]


def get_gemini_client():
    """Get Gemini client."""
    from google import genai
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")
    return genai.Client(api_key=api_key)


def evaluate_with_gemini(results: list) -> dict:
    """Use Gemini to evaluate intent classification quality."""
    
    # Format results for evaluation
    results_text = "\n".join([
        f"Query: '{r['query']}' | Classified: {r['classified']} | Expected: {r['expected']} | Match: {r['match']}"
        for r in results
    ])
    
    evaluation_prompt = f"""You are an expert evaluator of NLP classification systems.

Evaluate this intent classification system for a chat retrieval pipeline.

TEST RESULTS:
{results_text}

Evaluate:
1. **Accuracy** (What % of classifications match expected?)
2. **Coverage** (Does it handle all major intent types?)
3. **False Positives** (Any concerning misclassifications?)
4. **Usefulness for Retrieval** (Will these classifications improve retrieval?)
5. **Edge Cases** (How well does it handle ambiguous queries?)

Return JSON:
{{
  "accuracy_score": 8.5,
  "coverage_score": 9.0,
  "usefulness_score": 8.0,
  "edge_case_handling": 7.0,
  "overall_score": 8.0,
  "classification_accuracy_pct": 85,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "recommendations": ["..."],
  "phase1_success": true,
  "proceed_to_phase2": true
}}"""

    try:
        client = get_gemini_client()
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=evaluation_prompt,
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            }
        )
        
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        return json.loads(text.strip())
        
    except Exception as e:
        print(f"Gemini evaluation error: {e}")
        return {"error": str(e)}


async def run_evaluation():
    """Run Phase 1 evaluation."""
    
    print("=" * 70)
    print("PHASE 1: INTENT CLASSIFICATION - LOCAL EVALUATION")
    print("=" * 70)
    
    results = []
    correct = 0
    
    print("\n[*] Running intent classification tests...\n")
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"Test {i}/{len(TEST_CASES)}: {test['description']}")
        print(f"  Query: '{test['query']}'")
        
        # Classify
        intent = await classify_retrieval_intent(test['query'])
        classified = intent.intent_type.value
        
        # Check match
        match = classified == test['expected']
        if match:
            correct += 1
            status = "[OK]"
        else:
            status = "[MISMATCH]"
        
        print(f"  Expected: {test['expected']}")
        print(f"  Classified: {classified} {status}")
        print(f"  Confidence: {intent.confidence:.2f}")
        print(f"  Strategy: {intent.retrieval_strategy}")
        print()
        
        results.append({
            "query": test['query'],
            "expected": test['expected'],
            "classified": classified,
            "confidence": intent.confidence,
            "strategy": intent.retrieval_strategy,
            "match": match
        })
    
    # Calculate metrics
    accuracy = correct / len(TEST_CASES) * 100
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {len(TEST_CASES)}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.1f}%")
    print()
    
    # Gemini evaluation
    print("[*] Running Gemini evaluation...\n")
    gemini_eval = evaluate_with_gemini(results)
    
    if "error" not in gemini_eval:
        print("[AI] GEMINI EVALUATION:")
        print("-" * 50)
        
        print(f"\nOverall Score: {gemini_eval.get('overall_score', 0)}/10")
        print(f"Classification Accuracy: {gemini_eval.get('classification_accuracy_pct', 0)}%")
        
        print("\nScores:")
        for metric in ['accuracy_score', 'coverage_score', 'usefulness_score', 'edge_case_handling']:
            if metric in gemini_eval:
                print(f"  {metric.replace('_', ' ').title()}: {gemini_eval[metric]}/10")
        
        print("\nStrengths:")
        for s in gemini_eval.get('strengths', []):
            print(f"  + {s}")
        
        print("\nWeaknesses:")
        for w in gemini_eval.get('weaknesses', []):
            print(f"  - {w}")
        
        print("\nRecommendations:")
        for r in gemini_eval.get('recommendations', []):
            print(f"  > {r}")
        
        print()
        
        # Final verdict
        if gemini_eval.get('phase1_success') and gemini_eval.get('proceed_to_phase2'):
            print("=" * 50)
            print("[OK] PHASE 1: PASSED")
            print("[OK] Recommendation: PROCEED to Phase 2")
            print("=" * 50)
        elif gemini_eval.get('phase1_success'):
            print("[OK] PHASE 1: PASSED (with reservations)")
            print("[WARN] Consider refining before Phase 2")
        else:
            print("[FAIL] PHASE 1: NEEDS IMPROVEMENT")
            print("[WARN] Address issues before proceeding")
    
    # Save results
    output = {
        "test_results": results,
        "accuracy_pct": accuracy,
        "gemini_evaluation": gemini_eval,
        "phase1_success": gemini_eval.get('phase1_success', accuracy >= 70),
        "proceed_to_phase2": gemini_eval.get('proceed_to_phase2', accuracy >= 75)
    }
    
    with open("phase1_evaluation_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("\n[FILE] Results saved to phase1_evaluation_results.json")
    
    return output


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(run_evaluation())
