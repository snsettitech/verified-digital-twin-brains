# scripts/manual_verify_phase3.py
import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

TEST_TWIN_ID = "00000000-0000-0000-0000-000000000000"

async def verify_reasoning_logic():
    print("\nVerifying Reasoning Engine Logic...")
    
    with patch("modules.graph_context._select_seeds") as mock_seeds, \
         patch("modules.graph_context._expand_one_hop") as mock_expand, \
         patch("modules.reasoning_engine.get_openai_client") as mock_client:
        
        # 1. Setup Mock Data
        mock_seeds.return_value = [
            {"id": "node1", "name": "Environmentalism", "type": "Value", "description": "I believe in protecting the planet."},
            {"id": "node2", "name": "Sustainability", "type": "Principle", "description": "Actions should be sustainable long-term."}
        ]
        mock_expand.return_value = ([], [])
        
        # 2. Mock LLM Response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "stance": "positive",
            "confidence": 0.9,
            "logic_chain": [
                "The topic 'Recycling' aligns with my value of 'Environmentalism'.",
                "It specifically supports 'Sustainability'.",
                "Therefore, I support it."
            ],
            "key_factors": ["Environmentalism", "Sustainability"]
        })
        mock_client.return_value.chat.completions.create.return_value = mock_response
        
        # 3. Run Prediction
        from modules.reasoning_engine import ReasoningEngine, StanceType
        engine = ReasoningEngine(TEST_TWIN_ID)
        
        print("   Predicting stance on 'Recycling'...")
        trace = await engine.predict_stance("Recycling")
        
        # 4. output Results
        print("\n   --- Decision Trace ---")
        print(trace.to_readable_trace())
        
        if trace.final_stance == StanceType.POSITIVE:
            print("[OK] Reasoning Logic Verified (Stance: Positive)")
        else:
            print(f"[FAIL] Reasoning Logic Failed (Stance: {trace.final_stance})")

async def verify_chat_routing():
    print("\nVerifying Chat Routing (Simulation)...")
    # This just ensures modules import correctly and class is instantiated
    try:
        from routers.chat import router
        print("[OK] Chat Router loaded.")
    except Exception as e:
        print(f"[FAIL] Chat Router Import Failed: {e}")

async def main():
    print("Starting Phase 3 Manual Verification")
    await verify_reasoning_logic()
    await verify_chat_routing()
    print("\nVerification Complete")

if __name__ == "__main__":
    asyncio.run(main())
