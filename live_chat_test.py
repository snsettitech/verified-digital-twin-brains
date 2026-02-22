#!/usr/bin/env python3
"""
LIVE CHAT TEST with Twin
Shows actual conversation and evaluates quality
"""
import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('backend/.env')

import httpx

# Configuration
TWIN_ID = "88289f30-a068-4350-8c95-4c228f436fee"
BASE_URL = "https://verified-digital-twin-brains.onrender.com"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiaWF0IjoxNzcxNzgxNjEyLCJleHAiOjE3NzE4NjgwMTIsImF1ZCI6ImF1dGhlbnRpY2F0ZWQiLCJyb2xlIjoiYXV0aGVudGljYXRlZCJ9.-ykq9a8mo3UHby7AW7YoPoCguLnSo1jfUlrP-fRKp2c"

# Test conversation flow
CONVERSATION_FLOW = [
    # 1. Greeting
    {"type": "greeting", "message": "Hi there!"},
    
    # 2. Knowledge base question (should retrieve from sources)
    {"type": "knowledge", "message": "Tell me about yourself and your background"},
    
    # 3. Follow-up (context test)
    {"type": "followup", "message": "What about your work experience?"},
    
    # 4. Opinion question
    {"type": "opinion", "message": "What do you think is the most important skill in your field?"},
    
    # 5. Out-of-scope question (should handle gracefully)
    {"type": "out_of_scope", "message": "What do you think about the current political situation?"},
    
    # 6. Another follow-up with pronoun
    {"type": "followup", "message": "Can you tell me more about that?"},
    
    # 7. General knowledge question
    {"type": "knowledge", "message": "What projects have you worked on?"},
    
    # 8. Closing
    {"type": "closing", "message": "Thanks for the chat!"},
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
                print(f"    [ERROR {resp.status_code}] {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"    [EXCEPTION] {e}")
            return None


async def run_live_chat():
    """Run live chat test."""
    
    print("=" * 80)
    print("LIVE CHAT TEST WITH TWIN")
    print("=" * 80)
    print(f"Twin ID: {TWIN_ID}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    conversation_id = None
    chat_history = []
    
    for i, turn in enumerate(CONVERSATION_FLOW, 1):
        print(f"\n{'-' * 80}")
        print(f"TURN {i}/{len(CONVERSATION_FLOW)} [{turn['type'].upper()}]")
        print(f"{'-' * 80}")
        
        # User message
        print(f"\n[USER] USER: {turn['message']}")
        
        # Get twin response
        response = await chat_with_twin(turn['message'], conversation_id)
        
        if not response:
            print("[FAIL] No response from twin")
            continue
        
        # Extract response info
        twin_response = response.get('response', 'No response')
        citations = response.get('citations', [])
        conversation_id = response.get('conversation_id', conversation_id)
        confidence = response.get('confidence_score', 0)
        
        # Twin response
        print(f"\n[TWIN] TWIN: {twin_response}")
        print(f"\n[META] Metadata:")
        print(f"   - Citations: {len(citations)} documents")
        print(f"   - Confidence: {confidence:.2f}")
        print(f"   - Conversation ID: {conversation_id[:8]}...")
        
        # Store for evaluation
        chat_history.append({
            "turn": i,
            "type": turn['type'],
            "user": turn['message'],
            "twin": twin_response,
            "citations_count": len(citations),
            "confidence": confidence
        })
        
        # Brief pause between messages
        await asyncio.sleep(1)
    
    print(f"\n{'=' * 80}")
    print("CHAT COMPLETE")
    print(f"{'=' * 80}")
    
    return chat_history


def evaluate_with_moonshot(chat_history: list) -> dict:
    """Use Moonshot AI to evaluate the conversation."""
    
    # Format conversation
    convo_text = "\n\n".join([
        f"Turn {h['turn']} [{h['type']}]\nUser: {h['user']}\nTwin: {h['twin'][:500]}"
        for h in chat_history
    ])
    
    evaluation_prompt = f"""You are an expert evaluator of AI Digital Twin conversations.

Evaluate this conversation between a user and a Digital Twin:

{convo_text}

Evaluate these aspects (score 1-10, provide detailed reasoning):

1. **Intent Handling** 
   - Did the twin handle greetings naturally?
   - Did it retrieve knowledge when appropriate?
   - Did it skip retrieval for greetings/closing?
   - How well did it handle follow-ups with context?

2. **Knowledge Base Usage**
   - Did it use retrieved information effectively?
   - Were citations appropriate?
   - Did it stay grounded in the provided knowledge?

3. **Out-of-Scope Handling**
   - How did it handle questions outside its knowledge base?
   - Did it gracefully acknowledge limitations without being repetitive?
   - Did it try to be helpful even when lacking specific info?

4. **Conversational Flow**
   - Was the conversation natural?
   - Did context carry over between turns?
   - Were transitions smooth?

5. **Persona & Friendliness**
   - Was the twin warm and engaging?
   - Did it maintain a consistent personality?
   - Was it helpful and approachable?

6. **Overall Quality**
   - Compare to a basic RAG chatbot
   - Is this production-ready?

Return JSON:
{{
  "intent_handling": {{"score": 8, "reasoning": "..."}},
  "knowledge_usage": {{"score": 8, "reasoning": "..."}},
  "out_of_scope_handling": {{"score": 7, "reasoning": "..."}},
  "conversational_flow": {{"score": 8, "reasoning": "..."}},
  "persona_friendliness": {{"score": 8, "reasoning": "..."}},
  "overall_quality": {{"score": 8, "reasoning": "..."}},
  "overall_score": 7.8,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "recommendations": ["..."],
  "production_ready": true,
  "proceed_to_next_phase": true
}}"""

    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=os.getenv("MOONSHOT_API_KEY"),
            base_url="https://api.moonshot.cn/v1"
        )
        
        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[{"role": "user", "content": evaluation_prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        text = response.choices[0].message.content
        return json.loads(text)
        
    except Exception as e:
        print(f"Moonshot evaluation error: {e}")
        return {"error": str(e)}


async def main():
    """Main test flow."""
    
    # Run live chat
    chat_history = await run_live_chat()
    
    # Save chat history
    with open("live_chat_history.json", "w") as f:
        json.dump(chat_history, f, indent=2)
    
    print("\n[SAVE] Chat history saved to live_chat_history.json")
    
    # Evaluate with Moonshot
    print("\n" + "=" * 80)
    print("MOONSHOT AI EVALUATION")
    print("=" * 80)
    
    evaluation = evaluate_with_moonshot(chat_history)
    
    if "error" in evaluation:
        print(f"[FAIL] Evaluation failed: {evaluation['error']}")
        return
    
    # Display results
    print("\n[META] EVALUATION RESULTS:\n")
    
    for category in ["intent_handling", "knowledge_usage", "out_of_scope_handling", 
                     "conversational_flow", "persona_friendliness", "overall_quality"]:
        if category in evaluation:
            score = evaluation[category].get("score", 0)
            reasoning = evaluation[category].get("reasoning", "")
            print(f"{category.replace('_', ' ').title()}:")
            print(f"  Score: {score}/10")
            print(f"  Reasoning: {reasoning[:200]}...")
            print()
    
    # Summary
    overall = evaluation.get("overall_score", 0)
    print(f"{'=' * 80}")
    print(f"[SCORE] OVERALL SCORE: {overall}/10")
    print(f"{'=' * 80}")
    
    # Strengths/Weaknesses
    print("\n[OK] Strengths:")
    for s in evaluation.get("strengths", []):
        print(f"   + {s}")
    
    print("\n[WARN] Weaknesses:")
    for w in evaluation.get("weaknesses", []):
        print(f"   - {w}")
    
    print("\n[TIP] Recommendations:")
    for r in evaluation.get("recommendations", []):
        print(f"   > {r}")
    
    # Final verdict
    print("\n" + "=" * 80)
    if evaluation.get("production_ready"):
        print("[OK] PRODUCTION READY: Yes")
    else:
        print("[WARN] PRODUCTION READY: No")
    
    if evaluation.get("proceed_to_next_phase"):
        print("[OK] RECOMMENDATION: Proceed to Phase 2")
    else:
        print("[WARN] RECOMMENDATION: Refine before Phase 2")
    print("=" * 80)
    
    # Save evaluation
    with open("live_chat_evaluation.json", "w") as f:
        json.dump(evaluation, f, indent=2)
    
    print("\n[SAVE] Evaluation saved to live_chat_evaluation.json")


if __name__ == "__main__":
    asyncio.run(main())
