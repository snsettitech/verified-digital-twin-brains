#!/usr/bin/env python3
"""
Phase 1 Evaluation: Test intent classification with real twin
Uses Gemini to judge quality and friendliness
"""
import os
import sys
import asyncio
import json
from dotenv import load_dotenv

load_dotenv('backend/.env')

# Add backend to path
sys.path.insert(0, 'backend')

import httpx
# Test configuration

def get_gemini_client():
    """Get Gemini client."""
    from google import genai
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")
    return genai.Client(api_key=api_key)
TWIN_ID = "88289f30-a068-4350-8c95-4c228f436fee"
BASE_URL = "https://verified-digital-twin-brains.onrender.com"
TEST_TOKEN = os.getenv("TEST_TOKEN", "")

# Test queries covering different intents
TEST_QUERIES = [
    # Greeting - should skip retrieval
    {
        "query": "Hello! How are you doing today?",
        "expected_intent": "greeting",
        "expected_behavior": "Should respond warmly without retrieving documents"
    },
    # Opinion
    {
        "query": "What do you think about artificial intelligence?",
        "expected_intent": "opinion",
        "expected_behavior": "Should give personal opinion, prioritizing OPINION-labeled chunks"
    },
    # Entity lookup
    {
        "query": "Tell me about your work experience",
        "expected_intent": "entity_lookup", 
        "expected_behavior": "Should retrieve and summarize relevant experience"
    },
    # Summarization
    {
        "query": "Can you summarize your background?",
        "expected_intent": "summarization",
        "expected_behavior": "Should provide broad summary from multiple sources"
    },
    # Follow-up (context test)
    {
        "query": "Tell me more about that",
        "expected_intent": "followup",
        "expected_behavior": "Should understand context from previous message and elaborate"
    }
]


async def get_twin_info():
    """Get twin details."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/twins/{TWIN_ID}",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        if resp.status_code == 200:
            return resp.json()
        return None


async def get_twin_sources():
    """Get twin's knowledge sources."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/twins/{TWIN_ID}/sources",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        if resp.status_code == 200:
            return resp.json()
        return []


async def chat_with_twin(message: str, conversation_id: str = None) -> dict:
    """Send message to twin and get response."""
    async with httpx.AsyncClient() as client:
        url = f"{BASE_URL}/chat/{TWIN_ID}"
        if conversation_id:
            url += f"?conversation_id={conversation_id}"
            
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
            json={"message": message},
            timeout=60.0
        )
        
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  Error {resp.status_code}: {resp.text[:200]}")
            return None


def evaluate_with_gemini_sync(conversation: list, twin_name: str) -> dict:
    """Use Gemini to evaluate conversation quality (synchronous)."""
    
    # Format conversation for evaluation
    convo_text = "\n\n".join([
        f"User: {turn['user']}\nTwin: {turn['twin'][:500]}"
        for turn in conversation
    ])
    
    evaluation_prompt = f"""You are an expert evaluator of AI conversational systems. Evaluate the following conversation between a user and a Digital Twin.

TWIN NAME: {twin_name}

CONVERSATION:
{convo_text}

Evaluate the following aspects (score 1-10, provide reasoning):

1. **Intent Understanding** (Did the twin correctly understand different query types: greeting, opinion, entity lookup, summarization, follow-up?)

2. **Retrieval Appropriateness** (Did the twin retrieve knowledge when needed and skip retrieval for greetings?)

3. **Response Quality** (Are responses accurate, relevant, and well-formed?)

4. **Conversational Flow** (Does the conversation feel natural? Is context maintained?)

5. **Friendliness/Persona** (Is the twin warm, engaging, and maintaining consistent personality?)

6. **Improvement Over Baseline** (Compared to a basic RAG system, is this better at handling different query types?)

Return your evaluation as JSON:
{{
  "intent_understanding": {{"score": 8, "reasoning": "..."}},
  "retrieval_appropriateness": {{"score": 9, "reasoning": "..."}},
  "response_quality": {{"score": 8, "reasoning": "..."}},
  "conversational_flow": {{"score": 7, "reasoning": "..."}},
  "friendliness": {{"score": 8, "reasoning": "..."}},
  "improvement_over_baseline": {{"score": 8, "reasoning": "..."}},
  "overall_score": 8.0,
  "phase1_success": true,
  "recommendations": ["..."],
  "proceed_to_phase2": true
}}"""

    try:
        client = get_gemini_client()
        model = "gemini-2.0-flash"  # Latest fast model
        
        response = client.models.generate_content(
            model=model,
            contents=evaluation_prompt,
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            }
        )
        
        # Parse JSON response
        text = response.text
        # Extract JSON if wrapped in markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        return json.loads(text.strip())
        
    except Exception as e:
        print(f"Gemini evaluation error: {e}")
        return {
            "error": str(e),
            "overall_score": 0,
            "phase1_success": False
        }


async def evaluate_with_gemini(conversation: list, twin_name: str) -> dict:
    """Async wrapper for Gemini evaluation."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, evaluate_with_gemini_sync, conversation, twin_name)


async def run_phase1_test():
    """Run complete Phase 1 test."""
    
    print("=" * 70)
    print("PHASE 1: INTENT CLASSIFICATION - EVALUATION")
    print("=" * 70)
    
    # 1. Get twin info
    print("\n[+] Fetching twin info...")
    twin_info = await get_twin_info()
    if not twin_info:
        print("[FAIL] Failed to get twin info")
        return
    
    twin_name = twin_info.get("name", "Unknown")
    print(f"[OK] Twin: {twin_name}")
    
    # 2. Get sources
    print("\n[+] Fetching knowledge sources...")
    sources = await get_twin_sources()
    print(f"[OK] Found {len(sources)} sources:")
    for src in sources[:5]:
        print(f"   - {src.get('filename', 'Unknown')} ({src.get('status', 'unknown')})")
    
    # 3. Run test conversations
    print("\n" + "=" * 70)
    print("[*]  TESTING CONVERSATIONS")
    print("=" * 70)
    
    conversation = []
    conversation_id = None
    
    for i, test in enumerate(TEST_QUERIES, 1):
        print(f"\n--- Test {i}/{len(TEST_QUERIES)} ---")
        print(f"Query: \"{test['query']}\"")
        print(f"Expected Intent: {test['expected_intent']}")
        print(f"Expected Behavior: {test['expected_behavior']}")
        
        # Send message
        response = await chat_with_twin(test['query'], conversation_id)
        
        if not response:
            print("[FAIL] No response from twin")
            continue
            
        # Extract response info
        twin_response = response.get('response', 'No response')
        citations = response.get('citations', [])
        conversation_id = response.get('conversation_id', conversation_id)
        
        print(f"\nTwin Response: {twin_response[:300]}...")
        print(f"Citations: {len(citations)} documents")
        
        # Store for evaluation
        conversation.append({
            "user": test['query'],
            "twin": twin_response,
            "expected_intent": test['expected_intent'],
            "citations_count": len(citations)
        })
        
        await asyncio.sleep(1)  # Brief pause between messages
    
    # 4. Evaluate with Gemini
    print("\n" + "=" * 70)
    print("[AI] GEMINI EVALUATION")
    print("=" * 70)
    
    evaluation = await evaluate_with_gemini(conversation, twin_name)
    
    # Print evaluation results
    print("\n[STATS] EVALUATION RESULTS:")
    print("-" * 50)
    
    if "error" in evaluation:
        print(f"[FAIL] Evaluation failed: {evaluation['error']}")
        return
    
    # Print detailed scores
    for category in ["intent_understanding", "retrieval_appropriateness", 
                     "response_quality", "conversational_flow", 
                     "friendliness", "improvement_over_baseline"]:
        if category in evaluation:
            score = evaluation[category].get("score", 0)
            reasoning = evaluation[category].get("reasoning", "")
            print(f"\n{category.replace('_', ' ').title()}:")
            print(f"  Score: {score}/10")
            print(f"  Reasoning: {reasoning[:200]}...")
    
    # Overall score
    overall = evaluation.get("overall_score", 0)
    print(f"\n{'='*50}")
    print(f"[SCORE] OVERALL SCORE: {overall}/10")
    print(f"{'='*50}")
    
    # Success determination
    phase1_success = evaluation.get("phase1_success", overall >= 6.0)
    proceed = evaluation.get("proceed_to_phase2", overall >= 7.0)
    
    if phase1_success:
        print("\n[OK] Phase 1: INTENT CLASSIFICATION - PASSED")
    else:
        print("\n[FAIL] Phase 1: INTENT CLASSIFICATION - NEEDS IMPROVEMENT")
    
    if proceed:
        print("[OK] Recommendation: PROCEED to Phase 2")
    else:
        print("[WARN]  Recommendation: REFINE Phase 1 before proceeding")
    
    # Recommendations
    recommendations = evaluation.get("recommendations", [])
    if recommendations:
        print("\n[TIP] Recommendations:")
        for rec in recommendations:
            print(f"   - {rec}")
    
    return {
        "phase1_success": phase1_success,
        "proceed_to_phase2": proceed,
        "overall_score": overall,
        "evaluation": evaluation,
        "conversation": conversation
    }


if __name__ == "__main__":
    result = asyncio.run(run_phase1_test())
    
    # Save results
    with open("phase1_evaluation_results.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print("\n\n[FILE] Results saved to phase1_evaluation_results.json")
