#!/usr/bin/env python3
"""Test intent classification"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')

import sys
sys.path.insert(0, 'backend')
from modules.retrieval_intent import classify_retrieval_intent, RetrievalIntentType


async def test_intents():
    """Test various query types."""
    
    test_queries = [
        # Entity lookup
        "What is machine learning?",
        "Tell me about your experience at Google",
        
        # Opinion
        "What do you think about remote work?",
        "What's your view on AI regulation?",
        
        # Comparison
        "Compare Python and JavaScript",
        "What's the difference between REST and GraphQL?",
        
        # Procedural
        "How do you build a startup?",
        "What are the steps to learn data science?",
        
        # Summarization
        "Summarize your career",
        "Give me an overview of your expertise",
        
        # Greeting
        "Hello!",
        "Hi there",
        
        # Followup (with history)
        "What about that?",
        "Tell me more",
    ]
    
    print("=== Intent Classification Tests ===\n")
    
    for query in test_queries:
        print(f"Query: \"{query}\"")
        intent = await classify_retrieval_intent(query)
        print(f"  Intent: {intent.intent_type.value}")
        print(f"  Confidence: {intent.confidence:.2f}")
        print(f"  Entities: {intent.key_entities}")
        print(f"  Is Followup: {intent.is_followup}")
        print(f"  Strategy: {intent.retrieval_strategy}")
        print()


if __name__ == "__main__":
    asyncio.run(test_intents())
