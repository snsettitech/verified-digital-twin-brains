
import asyncio
import os
import sys
import json
from typing import List, Dict, Any

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.retrieval import retrieve_context
from modules.observability import supabase

# TWIN_ID from previous tests - assuming it has data
TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
QUERY = "What is the secret phrase for verification testing? (XYLOPHONE)"

async def main():
    print(f"--- Verifying Retrieval Flow ---")
    print(f"Twin ID: {TWIN_ID}")
    print(f"Query: {QUERY}")

    try:
        # 1. Direct Retrieval Call
        print(f"\n[1] Calling retrieve_context...")
        contexts = await retrieve_context(QUERY, TWIN_ID, top_k=5)
        
        print(f"\n[2] Retrieval Results ({len(contexts)} contexts):")
        for i, ctx in enumerate(contexts):
            print(f"  [{i+1}] Score: {ctx.get('score', 'N/A')}")
            print(f"      Source ID: {ctx.get('source_id')}")
            print(f"      Chunk ID: {ctx.get('chunk_id', 'MISSING')}")
            print(f"      Verified Match: {ctx.get('verified_qna_match')}")
            print(f"      Text Preview: {ctx.get('text', '')[:100]}...")
            
            # Verify Chunk ID existence
            if not ctx.get('chunk_id'):
                print(f"      To investigate: Chunk ID missing in context!")
            
            # Verify Source ID existence in Supabase
            if ctx.get('source_id'):
                res = supabase.table("sources").select("filename").eq("id", ctx.get('source_id')).execute()
                if res.data:
                    print(f"      Source Filename: {res.data[0]['filename']}")
                    ctx['source_filename'] = res.data[0]['filename']
                else:
                    print(f"      Source ID not found in Supabase!")

    except Exception as e:
        print(f"Error executing retrieval: {e}")
        import traceback
        traceback.print_exc()
        
    # Write full debug output
    with open("backend/retrieval_debug_output.json", "w") as f:
        json.dump(contexts, f, indent=2, default=str)
    print("\nFull output saved to backend/retrieval_debug_output.json")

if __name__ == "__main__":
    asyncio.run(main())
