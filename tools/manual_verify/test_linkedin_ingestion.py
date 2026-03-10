#!/usr/bin/env python3
"""
Test LinkedIn ingestion and bio generation
"""
import os
import sys
import asyncio
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from supabase import create_client
from modules.observability import supabase as obs_supabase

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

# Use Sainath Setti's twin
TWIN_ID = "88289f30-a068-4350-8c95-4c228f436fee"
LINKEDIN_URL = "https://www.linkedin.com/in/sainathsetti/"

async def test_linkedin_ingestion():
    print("=" * 80)
    print("TESTING LINKEDIN INGESTION")
    print("=" * 80)
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Check current sources for this twin
    print("\n[1] Current sources for twin:")
    sources = supabase.table("sources").select("*").eq("twin_id", TWIN_ID).execute()
    for s in sources.data or []:
        print(f"  - {s.get('filename')} | Status: {s.get('status')} | URL: {s.get('citation_url')}")
    
    # Check if LinkedIn source already exists
    linkedin_exists = any(
        s.get('citation_url') == LINKEDIN_URL or 'linkedin' in (s.get('citation_url') or '').lower()
        for s in sources.data or []
    )
    
    if linkedin_exists:
        print("\n[2] LinkedIn source already exists - checking its status...")
        linkedin_source = next(
            (s for s in sources.data if s.get('citation_url') == LINKEDIN_URL or 'linkedin' in (s.get('citation_url') or '').lower()),
            None
        )
        if linkedin_source:
            print(f"    Status: {linkedin_source.get('status')}")
            print(f"    Content length: {len(linkedin_source.get('content_text') or '')}")
            
            if linkedin_source.get('status') == 'error':
                print("    Source has ERROR status - will re-try ingestion")
                # Delete the old failed source
                supabase.table("sources").delete().eq("id", linkedin_source.get('id')).execute()
                print("    Deleted old failed source")
            elif linkedin_source.get('status') == 'live' and len(linkedin_source.get('content_text') or '') > 100:
                print("    Source is LIVE with content - no need to re-ingest")
                return linkedin_source
    
    # Create new source
    print("\n[2] Creating new LinkedIn source...")
    import uuid
    source_id = str(uuid.uuid4())
    
    new_source = {
        "id": source_id,
        "twin_id": TWIN_ID,
        "filename": "LinkedIn: queued",
        "file_size": 0,
        "content_text": "",
        "status": "pending",
        "staging_status": "staged",
        "citation_url": LINKEDIN_URL,
    }
    
    result = supabase.table("sources").insert(new_source).execute()
    print(f"    Created source: {source_id}")
    
    # Trigger ingestion
    print("\n[3] Triggering ingestion...")
    from modules.ingestion import ingest_url_to_source
    
    try:
        num_chunks = await ingest_url_to_source(
            source_id=source_id,
            twin_id=TWIN_ID,
            url=LINKEDIN_URL,
            correlation_id=f"test_linkedin_{datetime.now().timestamp()}"
        )
        print(f"    SUCCESS! Created {num_chunks} chunks")
        
        # Check the source after ingestion
        updated = supabase.table("sources").select("*").eq("id", source_id).single().execute()
        return updated.data
        
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Check what happened
        updated = supabase.table("sources").select("*").eq("id", source_id).single().execute()
        return updated.data

def check_vectors_and_generate_bio(source_data):
    print("\n[4] Checking vectors in Pinecone...")
    
    from modules.clients import get_pinecone_index
    from modules.delphi_namespace import get_namespace_candidates_for_twin
    
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        namespaces = get_namespace_candidates_for_twin(twin_id=TWIN_ID, include_legacy=True)
        print(f"    Namespaces: {namespaces}")
        
        total_vectors = 0
        for ns in namespaces:
            ns_stats = stats.namespaces.get(ns, {})
            count = ns_stats.get('vector_count', 0)
            total_vectors += count
            print(f"    - {ns}: {count} vectors")
        
        print(f"    TOTAL: {total_vectors} vectors")
        
        # Generate bio if we have vectors
        if total_vectors > 0:
            print("\n[5] Generating bio from LinkedIn content...")
            
            # Query Pinecone for bio-related content
            from openai import OpenAI
            import os
            
            openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            # Get embedding for bio query
            query = "professional bio summary expertise experience"
            embed_response = openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=query
            )
            query_embedding = embed_response.data[0].embedding
            
            # Query each namespace
            all_matches = []
            for ns in namespaces:
                try:
                    results = index.query(
                        vector=query_embedding,
                        top_k=5,
                        include_metadata=True,
                        namespace=ns
                    )
                    all_matches.extend(results.get('matches', []))
                except Exception as e:
                    print(f"    Error querying {ns}: {e}")
            
            if all_matches:
                # Sort by score and take top 5
                all_matches.sort(key=lambda x: x.get('score', 0), reverse=True)
                top_matches = all_matches[:5]
                
                print(f"    Found {len(top_matches)} relevant chunks")
                
                # Combine text for bio generation
                context = "\n\n".join([
                    m.get('metadata', {}).get('chunk_text', '') or m.get('metadata', {}).get('text', '')
                    for m in top_matches
                ])
                
                print(f"    Context length: {len(context)} chars")
                
                # Generate bio using GPT
                bio_prompt = f"""Based on this LinkedIn profile information, create a compelling professional bio (2-3 paragraphs) highlighting:
- Professional background and expertise
- Key skills and achievements
- Career highlights
- Professional interests

LinkedIn Profile Content:
{context}

Generate a professional bio:"""
                
                bio_response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a professional bio writer. Create compelling, authentic-sounding professional bios."},
                        {"role": "user", "content": bio_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                bio = bio_response.choices[0].message.content
                print(f"\n{'='*80}")
                print("GENERATED BIO:")
                print('='*80)
                print(bio)
                print('='*80)
                
                return bio
            else:
                print("    No matching chunks found!")
                return None
        else:
            print("    No vectors found - cannot generate bio")
            return None
            
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_chat_with_linkedin():
    print("\n[6] Testing chat functionality...")
    
    # Simulate a chat query about the LinkedIn profile
    test_questions = [
        "What is my professional background?",
        "What are my key skills?",
        "Tell me about my experience",
    ]
    
    from modules.retrieval import retrieve_context_for_twin
    
    for question in test_questions:
        print(f"\n    Q: {question}")
        try:
            context = await retrieve_context_for_twin(
                twin_id=TWIN_ID,
                query=question,
                top_k=3
            )
            
            if context and context.get('chunks'):
                print(f"    Retrieved {len(context['chunks'])} chunks:")
                for i, chunk in enumerate(context['chunks'], 1):
                    text = chunk.get('text', '')[:150]
                    print(f"      {i}. {text}...")
            else:
                print("    No context retrieved!")
                
        except Exception as e:
            print(f"    ERROR: {e}")

async def main():
    # Step 1: Ingest LinkedIn
    source_data = await test_linkedin_ingestion()
    
    if source_data:
        print(f"\nSource Status: {source_data.get('status')}")
        print(f"Content Preview: {(source_data.get('content_text') or '')[:300]}...")
        
        # Step 2: Check vectors and generate bio
        if source_data.get('status') == 'live':
            bio = check_vectors_and_generate_bio(source_data)
            
            # Step 3: Test chat
            if bio:
                await test_chat_with_linkedin()
        else:
            print("\nSource not live yet - waiting for ingestion to complete...")
            print("Will check again in 30 seconds...")
            await asyncio.sleep(30)
            
            # Re-check
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            updated = supabase.table("sources").select("*").eq("id", source_data.get('id')).single().execute()
            if updated.data:
                print(f"Updated status: {updated.data.get('status')}")
                if updated.data.get('status') == 'live':
                    bio = check_vectors_and_generate_bio(updated.data)
                    if bio:
                        await test_chat_with_linkedin()

if __name__ == "__main__":
    asyncio.run(main())
