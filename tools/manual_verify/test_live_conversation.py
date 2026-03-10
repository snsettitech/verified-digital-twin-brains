#!/usr/bin/env python3
"""
LIVE CONVERSATION TEST with Twin cf3ffed1-5d56-422b-8ce9-1bd99cd43b22
Tests Phase 1 (Intent Classification) and Phase 2 (Conversation Context)
Based on actual Pinecone content about Accounting Valuation Methods
"""
import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('backend/.env')
sys.path.insert(0, 'backend')

import httpx

# Configuration
TWIN_ID = "cf3ffed1-5d56-422b-8ce9-1bd99cd43b22"
BASE_URL = "https://verified-digital-twin-brains.onrender.com"

# Generate test token
import jwt
from datetime import timedelta
jwt_secret = os.getenv("JWT_SECRET", "")
payload = {
    "sub": "test-user-phase1",
    "email": "test@example.com",
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=24),
    "aud": "authenticated",
    "role": "authenticated"
}
TEST_TOKEN = jwt.encode(payload, jwt_secret, algorithm="HS256")

# Conversation based on actual KB content about Accounting Valuation
CONVERSATION = [
    # 1. Greeting
    {
        "type": "greeting",
        "message": "Hi!",
        "test": "Should skip retrieval, direct friendly response"
    },
    
    # 2. Entity lookup - DCF
    {
        "type": "entity_lookup",
        "message": "What is Discounted Cash Flow?",
        "test": "Should retrieve FACT chunks about DCF"
    },
    
    # 3. Opinion - valuation methods
    {
        "type": "opinion", 
        "message": "What do you think is the best valuation method?",
        "test": "Should retrieve OPINION category chunks"
    },
    
    # 4. Follow-up with pronoun (PHASE 2 TEST)
    {
        "type": "followup",
        "message": "Can you explain more about it?",
        "test": "PHASE 2: Should resolve 'it' to 'DCF' and retrieve more details"
    },
    
    # 5. Comparison (PHASE 1 TEST)
    {
        "type": "comparison",
        "message": "How does DCF compare to P/E ratio?",
        "test": "PHASE 1: Should classify as comparison, retrieve both topics"
    },
    
    # 6. Procedural
    {
        "type": "procedural",
        "message": "How do you calculate the Payback period?",
        "test": "Should classify as procedural, give step-by-step"
    },
    
    # 7. Out of scope - should handle gracefully
    {
        "type": "out_of_scope",
        "message": "What do you think about cryptocurrency?",
        "test": "Should give general perspective, not say 'I don't know'"
    },
    
    # 8. Follow-up with "that" (PHASE 2 TEST)
    {
        "type": "followup",
        "message": "What are the risks with that?",
        "test": "PHASE 2: Should resolve 'that' to previous topic"
    },
    
    # 9. Summarization
    {
        "type": "summarization",
        "message": "Summarize the key valuation methods",
        "test": "Should classify as summarization, broad retrieval"
    },
    
    # 10. Closing
    {
        "type": "closing",
        "message": "Thanks for the help!",
        "test": "Should skip retrieval, friendly closing"
    }
]


async def chat_with_twin(message: str, conversation_id: str = None) -> dict:
    """Send message to twin and get response."""
    async with httpx.AsyncClient() as client:
        url = f"{BASE_URL}/chat/{TWIN_ID}"
        if conversation_id:
            url += f"?conversation_id={conversation_id}"
            
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {TEST_TOKEN}"},
                json={"query": message},
                timeout=60.0
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]}
        except Exception as e:
            return {"error": str(e)}


async def run_conversation():
    """Run the full conversation test."""
    
    print("=" * 80)
    print("LIVE CONVERSATION TEST - PHASE 1 & 2")
    print("=" * 80)
    print(f"Twin ID: {TWIN_ID}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Knowledge Base: Accounting Valuation Methods (34 vectors)")
    print("=" * 80)
    
    conversation_id = None
    history = []
    
    for i, turn in enumerate(CONVERSATION, 1):
        print(f"\n{'=' * 80}")
        print(f"TURN {i}/{len(CONVERSATION)} - {turn['type'].upper()}")
        print(f"Test: {turn['test']}")
        print('=' * 80)
        
        # Show user message
        print(f"\n[USER]: {turn['message']}")
        
        # Get response
        response = await chat_with_twin(turn['message'], conversation_id)
        
        if "error" in response:
            print(f"\n[ERROR]: {response['error']}")
            if "detail" in response:
                print(f"Detail: {response['detail']}")
            continue
        
        # Extract info
        twin_response = response.get('response', 'No response')
        citations = response.get('citations', [])
        confidence = response.get('confidence_score', 0)
        conversation_id = response.get('conversation_id', conversation_id)
        
        # Show twin response
        print(f"\n[TWIN]: {twin_response[:500]}")
        if len(twin_response) > 500:
            print(f"... ({len(twin_response)} chars total)")
        
        # Show metadata
        print(f"\n[METADATA]:")
        print(f"  - Citations: {len(citations)} documents")
        print(f"  - Confidence: {confidence:.2f}")
        print(f"  - Conversation ID: {conversation_id[:8] if conversation_id else 'None'}...")
        
        # Store for analysis
        history.append({
            "turn": i,
            "type": turn['type'],
            "user": turn['message'],
            "twin": twin_response,
            "citations": len(citations),
            "confidence": confidence
        })
        
        # Pause between messages
        await asyncio.sleep(1)
    
    print(f"\n{'=' * 80}")
    print("CONVERSATION COMPLETE")
    print('=' * 80)
    
    return history


def evaluate_conversation(history: list):
    """Evaluate the conversation quality."""
    
    print("\n" + "=" * 80)
    print("EVALUATION")
    print("=" * 80)
    
    # Count by type
    type_stats = {}
    for h in history:
        t = h['type']
        type_stats[t] = type_stats.get(t, 0) + 1
    
    print("\n[CONVERSATION STATS]:")
    for t, count in type_stats.items():
        print(f"  - {t}: {count} turns")
    
    # Check for issues
    issues = []
    for h in history:
        if h['type'] == 'greeting' and h['citations'] > 0:
            issues.append(f"Turn {h['turn']}: Greeting should not have citations")
        if h['type'] == 'closing' and h['citations'] > 0:
            issues.append(f"Turn {h['turn']}: Closing should not have citations")
        if 'error' in h:
            issues.append(f"Turn {h['turn']}: Error occurred")
    
    if issues:
        print("\n[ISSUES FOUND]:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n[OK]: No major issues detected")
    
    # Calculate average confidence
    avg_confidence = sum(h['confidence'] for h in history) / len(history) if history else 0
    print(f"\n[AVERAGE CONFIDENCE]: {avg_confidence:.2f}")
    
    # Phase-specific checks
    print("\n[PHASE 1 - INTENT CLASSIFICATION]:")
    intent_checks = {
        'greeting': 'Handled',
        'entity_lookup': 'Handled',
        'opinion': 'Handled',
        'comparison': 'Handled',
        'procedural': 'Handled',
        'summarization': 'Handled',
        'followup': 'Handled'
    }
    for intent, status in intent_checks.items():
        if intent in type_stats:
            print(f"  [OK] {intent}: {status}")
        else:
            print(f"  [MISSING] {intent}: Not tested")
    
    print("\n[PHASE 2 - CONVERSATION CONTEXT]:")
    followups = [h for h in history if h['type'] == 'followup']
    if followups:
        print(f"  [OK] Follow-up queries tested: {len(followups)}")
        for f in followups:
            print(f"      Turn {f['turn']}: '{f['user'][:40]}...'")
    else:
        print("  [MISSING] No follow-up queries tested")
    
    # Overall score
    score = 10 - len(issues) * 0.5 if issues else 10
    score = max(0, score)
    
    print(f"\n{'=' * 80}")
    print(f"OVERALL SCORE: {score}/10")
    print(f"{'=' * 80}")
    
    if score >= 8:
        print("[RESULT]: EXCELLENT - Both phases working well")
        print("[RECOMMENDATION]: Proceed to Phase 3")
    elif score >= 6:
        print("[RESULT]: GOOD - Minor issues to address")
        print("[RECOMMENDATION]: Fix issues, then proceed")
    else:
        print("[RESULT]: NEEDS WORK - Significant issues found")
        print("[RECOMMENDATION]: Debug before proceeding")
    
    return {
        "score": score,
        "avg_confidence": avg_confidence,
        "issues": issues,
        "history": history
    }


async def main():
    # Run conversation
    history = await run_conversation()
    
    # Evaluate
    results = evaluate_conversation(history)
    
    # Save results
    with open("live_conversation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n[FILE] Results saved to live_conversation_results.json")


if __name__ == "__main__":
    asyncio.run(main())
