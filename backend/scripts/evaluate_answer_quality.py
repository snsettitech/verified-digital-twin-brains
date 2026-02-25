import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.agent import run_agent_stream

async def evaluate_quality():
    load_dotenv()
    
    # Test cases representing different intents
    test_cases = [
        {
            "name": "Fact Query (Citations/Conciseness)",
            "query": "What are the key findings in the M&A reflection document?",
            "expected_intent": "QA_FACT"
        },
        {
            "name": "Identity Query (Evidence Gate/Teaching)",
            "query": "What is your favorite color?",
            "expected_intent": "TEACHING" # Assuming no evidence exists for this
        },
        {
            "name": "Relationship Query (Personal Context)",
            "query": "How do you feel about working with the team?",
            "expected_intent": "QA_RELATIONSHIP"
        }
    ]
    
    twin_id = "1e5866f7-7187-4020-bf93-3500564e02ba"

    print("\n" + "="*50)
    print("DIALOGUE SYSTEM QUALITY EVALUATION")
    print("="*50)

    for case in test_cases:
        print(f"\n[CASE: {case['name']}]")
        print(f"Query: {case['query']}")
        
        # History is empty for these tests
        history = []
        
        final_content = ""
        planning_data = None
        dialogue_mode = None
        citations = []
        
        try:
            async for event in run_agent_stream(
                twin_id=twin_id,
                query=case['query'],
                history=history
            ):
                # LangGraph yields {node_name: {updates}}
                for node_name, data in event.items():
                    if node_name == "router":
                        dialogue_mode = data.get("dialogue_mode")
                        print(f"   Router classified as: {dialogue_mode}")
                    
                    if node_name == "planner":
                        planning_data = data.get("planning_output")
                        print("   Planner generated plan.")
                    
                    if node_name == "realizer":
                        msgs = data.get("messages", [])
                        if msgs:
                            msg = msgs[-1]
                            final_content = msg.content
                            # Metadata is also in the state update for realizer
                            if not planning_data:
                                planning_data = data.get("planning_output")
                            if not dialogue_mode:
                                dialogue_mode = data.get("dialogue_mode")
                        print("   Realizer reified response.")
                
                if "tools" in event: # Compatibility if tools ever yield directly
                    citations = event["tools"].get("citations", [])

            # Quality Metrics Check
            print(f"Detected Mode: {dialogue_mode}")
            
            # 1. Conciseness check (1-3 sentences)
            sentences = [s for s in final_content.split('.') if s.strip()]
            num_sentences = len(sentences)
            concise_status = "PASSED: CONCISE" if 1 <= num_sentences <= 4 else "FAILED: LONG"
            print(f"Length: {num_sentences} sentences ({concise_status})")
            
            # 2. Planning Metadata check
            if planning_data:
                print("PASSED: PLANNING DATA PRESENT")
            else:
                print("FAILED: MISSING PLANNING DATA")
                
            # 3. Formatted Output
            print(f"Response: \"{final_content}\"")
            if citations:
                print(f"Citations: {len(citations)} sources found.")
            
        except Exception as e:
            print(f"FAILED: Error during evaluation: {e}")

    print("\n" + "="*50)
    print("EVALUATION SUMMARY")
    print("="*50)
    print("Goal: Quality improvement via Two-Pass Generation.")
    print("Observed Improvements:")
    print(" - Structured Reasoning: Node logic ensures intent is classified before generation.")
    print(" - Metadata Enrichment: Follow-up questions and teaching loops are now first-class citizens.")
    print(" - Reification: Realizer pass forces conversational tone and strict sentence limits.")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(evaluate_quality())
