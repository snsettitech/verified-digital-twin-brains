#!/usr/bin/env python3
"""Quick test of Cerebras API."""
import os
import sys
sys.path.insert(0, '..')

from dotenv import load_dotenv
load_dotenv(dotenv_path='../.env')

import time

print("Testing Cerebras API...")
print(f"API Key set: {bool(os.getenv('CEREBRAS_API_KEY'))}")

try:
    from modules.inference_cerebras import CerebrasClient
    
    # Reset singleton
    CerebrasClient.reset()
    
    # Create client
    client = CerebrasClient()
    print(f"Model: {client.model}")
    
    # Test generation
    print("\nSending test request...")
    start = time.time()
    response = client.generate([
        {"role": "user", "content": "Say 'Hello from Cerebras!' and nothing else."}
    ], max_tokens=20)
    elapsed = (time.time() - start) * 1000
    
    print(f"\nLatency: {elapsed:.1f}ms")
    print(f"Response: {response.choices[0].message.content}")
    print(f"Tokens: {response.usage.total_tokens}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
