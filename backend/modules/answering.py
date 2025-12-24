from modules.clients import get_openai_client
import os
from dotenv import load_dotenv

load_dotenv()

def generate_answer(query: str, contexts: list):
    client = get_openai_client()
    context_text = "\n\n".join([f"Source {i+1}: {c['text']}" for i, c in enumerate(contexts)])
    
    prompt = f"""
You are a Verified Digital Twin Brain. Your goal is to provide accurate answers based ONLY on the provided context.
If the answer is not in the context, say "I don't have enough information to answer this based on my knowledge base."

Always provide citations in the format [Source N] where N is the number of the source.

Context:
{context_text}

User Query: {query}

Answer:
"""

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a helpful and accurate digital twin."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    
    answer = response.choices[0].message.content
    
    # Simple confidence scoring logic
    avg_score = sum([c['score'] for c in contexts]) / len(contexts) if contexts else 0
    
    return {
        "answer": answer,
        "confidence_score": avg_score,
        "citations": [c['source_id'] for c in contexts]
    }

async def generate_answer_stream(query: str, contexts: list):
    context_text = "\n\n".join([f"Source {i+1}: {c['text']}" for i, c in enumerate(contexts)])
    
    prompt = f"""
You are a Verified Digital Twin Brain. Your goal is to provide accurate answers based ONLY on the provided context.
If the answer is not in the context, say "I don't have enough information to answer this based on my knowledge base."

Always provide citations in the format [Source N] where N is the number of the source.

Context:
{context_text}

User Query: {query}

Answer:
"""

    client = get_openai_client()
    stream = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a helpful and accurate digital twin."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        stream=True
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content
