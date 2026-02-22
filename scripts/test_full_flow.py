#!/usr/bin/env python3
"""
Full flow test: Add LinkedIn URL -> Add manual content -> Generate Bio -> Test Chat
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
from modules.clients import get_openai_client, get_pinecone_index, get_async_openai_client
from modules.retrieval import retrieve_context_for_twin
from modules.embeddings import get_embedding

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

# Test twin (Sainath Setti)
TWIN_ID = "88289f30-a068-4350-8c95-4c228f436fee"
LINKEDIN_URL = "https://www.linkedin.com/in/sainathsetti/"

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

async def add_linkedin_source():
    """Step 1: Add LinkedIn URL as a source"""
    print("=" * 80)
    print("STEP 1: ADDING LINKEDIN SOURCE")
    print("=" * 80)
    
    supabase = get_supabase()
    
    # Clean up old test sources
    old_sources = supabase.table("sources").select("id").eq("twin_id", TWIN_ID).ilike("citation_url", "%linkedin%").execute()
    for s in old_sources.data or []:
        print(f"  Deleting old source: {s['id']}")
        supabase.table("sources").delete().eq("id", s['id']).execute()
    
    # Create new source
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
    print(f"  Created source: {source_id}")
    
    return source_id

async def trigger_ingestion(source_id):
    """Step 2: Trigger LinkedIn ingestion"""
    print("\n" + "=" * 80)
    print("STEP 2: TRIGGERING LINKEDIN INGESTION")
    print("=" * 80)
    
    from modules.ingestion import ingest_url_to_source
    
    try:
        num_chunks = await ingest_url_to_source(
            source_id=source_id,
            twin_id=TWIN_ID,
            url=LINKEDIN_URL,
            correlation_id=f"test_linkedin_{datetime.now().timestamp()}"
        )
        print(f"  SUCCESS! Created {num_chunks} chunks")
        return num_chunks
    except Exception as e:
        print(f"  Expected error (LinkedIn blocked): {e}")
        return None

def add_manual_content(source_id):
    """Step 3: Add manual LinkedIn content"""
    print("\n" + "=" * 80)
    print("STEP 3: ADDING MANUAL LINKEDIN CONTENT")
    print("=" * 80)
    
    supabase = get_supabase()
    
    # Sample LinkedIn profile content
    linkedin_content = """# LinkedIn Profile: Sainath Setti
URL: https://www.linkedin.com/in/sainathsetti/

## About
Results-driven Software Engineer with 5+ years of experience in full-stack development, cloud architecture, and AI/ML integration. Passionate about building scalable systems and mentoring junior developers. Proven track record of delivering high-impact projects in fast-paced startup environments.

## Experience

### Senior Software Engineer | TechCorp Inc.
*January 2022 - Present*
- Architected and deployed microservices handling 10M+ daily requests
- Led migration from monolith to Kubernetes, reducing deployment time by 70%
- Mentored team of 5 engineers, improving code quality by 40%
- Implemented CI/CD pipelines using GitHub Actions and ArgoCD

### Software Engineer | StartupXYZ
*June 2019 - December 2021*
- Built full-stack applications using React, Node.js, and PostgreSQL
- Developed RESTful APIs serving 500K+ active users
- Integrated third-party services including Stripe, Twilio, and AWS
- Optimized database queries, reducing latency by 60%

### Junior Developer | Digital Solutions
*August 2017 - May 2019*
- Developed responsive web applications using JavaScript and Python
- Collaborated with cross-functional teams to deliver client projects
- Implemented automated testing, achieving 90% code coverage

## Education

### Master of Science in Computer Science
*Stanford University | 2017*
- GPA: 3.9/4.0
- Specialization: Artificial Intelligence and Distributed Systems

### Bachelor of Technology in Computer Science
*Indian Institute of Technology | 2015*
- GPA: 3.8/4.0
- Relevant Coursework: Algorithms, Database Systems, Software Engineering

## Skills
- Languages: Python, JavaScript, TypeScript, Go, SQL
- Frontend: React, Next.js, Vue.js, Tailwind CSS
- Backend: Node.js, FastAPI, Django, GraphQL
- Cloud: AWS, GCP, Kubernetes, Docker, Terraform
- Databases: PostgreSQL, MongoDB, Redis, Elasticsearch
- AI/ML: TensorFlow, PyTorch, OpenAI API, LangChain
- Tools: Git, GitHub Actions, Jenkins, Datadog, Grafana

## Certifications
- AWS Solutions Architect Professional
- Google Cloud Professional Data Engineer
- Kubernetes Administrator (CKA)

## Publications
- "Scaling Microservices at TechCorp" - Medium, 2023
- "AI-Powered Chatbots: Best Practices" - Dev.to, 2022
"""
    
    # Update source with manual content
    result = supabase.table("sources").update({
        "filename": "LinkedIn: Sainath Setti",
        "file_size": len(linkedin_content),
        "content_text": linkedin_content,
        "status": "processing",
        "staging_status": "staged",
        "extracted_text_length": len(linkedin_content),
    }).eq("id", source_id).execute()
    
    print(f"  Updated source with {len(linkedin_content)} characters")
    return linkedin_content

async def index_content(source_id, content):
    """Step 4: Index the content into Pinecone"""
    print("\n" + "=" * 80)
    print("STEP 4: INDEXING CONTENT INTO PINECONE")
    print("=" * 80)
    
    from modules.ingestion import process_and_index_text
    
    num_chunks = await process_and_index_text(
        source_id=source_id,
        twin_id=TWIN_ID,
        text=content,
        metadata_override={
            "filename": "LinkedIn: Sainath Setti",
            "type": "linkedin_profile",
            "url": LINKEDIN_URL,
            "profile_name": "Sainath Setti",
        },
        provider="linkedin",
    )
    
    # Update source to live
    supabase = get_supabase()
    supabase.table("sources").update({
        "status": "live",
        "staging_status": "live",
        "chunk_count": num_chunks,
    }).eq("id", source_id).execute()
    
    print(f"  Indexed {num_chunks} chunks")
    return num_chunks

def generate_bio():
    """Step 5: Generate bio from indexed content"""
    print("\n" + "=" * 80)
    print("STEP 5: GENERATING BIO FROM INDEXED CONTENT")
    print("=" * 80)
    
    supabase = get_supabase()
    openai_client = get_openai_client()
    
    # Query Pinecone for bio-relevant chunks
    from modules.delphi_namespace import get_namespace_candidates_for_twin
    
    bio_queries = [
        "professional background experience summary",
        "skills expertise technologies",
        "education qualifications",
        "achievements accomplishments"
    ]
    
    all_chunks = []
    index = get_pinecone_index()
    namespaces = get_namespace_candidates_for_twin(twin_id=TWIN_ID, include_legacy=True)
    
    print(f"  Querying namespaces: {namespaces}")
    
    for query in bio_queries:
        query_embedding = get_embedding(query)
        
        for ns in namespaces:
            try:
                results = index.query(
                    vector=query_embedding,
                    top_k=3,
                    include_metadata=True,
                    namespace=ns
                )
                all_chunks.extend(results.get('matches', []))
            except Exception as e:
                print(f"  Error querying {ns}: {e}")
    
    # Deduplicate and sort by score
    seen_texts = set()
    unique_chunks = []
    for chunk in sorted(all_chunks, key=lambda x: x.get('score', 0), reverse=True):
        text = chunk.get('metadata', {}).get('chunk_text', '') or chunk.get('metadata', {}).get('text', '')
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_chunks.append(text)
    
    print(f"  Retrieved {len(unique_chunks)} unique chunks")
    
    if not unique_chunks:
        print("  No chunks found - cannot generate bio")
        return None
    
    # Combine context
    context = "\n\n".join(unique_chunks[:10])  # Top 10 chunks
    print(f"  Context length: {len(context)} characters")
    
    # Generate bio
    bio_prompt = f"""Based on the following LinkedIn profile information, create a compelling professional bio (3-4 paragraphs) that highlights:
1. Professional background and current role
2. Key skills and areas of expertise
3. Notable achievements and experience
4. Educational background
5. Professional interests and passion

Write in first person (as if the person is writing about themselves). Make it engaging and authentic.

LinkedIn Profile Information:
{context}

Generate a professional bio:"""
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional bio writer. Create compelling, authentic-sounding professional bios that sound natural and engaging."},
            {"role": "user", "content": bio_prompt}
        ],
        temperature=0.7,
        max_tokens=600
    )
    
    bio = response.choices[0].message.content
    
    print(f"\n{'='*80}")
    print("GENERATED BIO:")
    print('='*80)
    print(bio)
    print('='*80)
    
    return bio

async def test_chat():
    """Step 6: Test chat with the ingested content"""
    print("\n" + "=" * 80)
    print("STEP 6: TESTING CHAT WITH INGESTED CONTENT")
    print("=" * 80)
    
    test_questions = [
        "What is my professional background?",
        "What are my key skills?",
        "What experience do I have?",
        "What is my educational background?",
    ]
    
    for question in test_questions:
        print(f"\n  Q: {question}")
        try:
            context = await retrieve_context_for_twin(
                twin_id=TWIN_ID,
                query=question,
                top_k=3
            )
            
            if context and context.get('chunks'):
                print(f"    Retrieved {len(context['chunks'])} chunks:")
                for i, chunk in enumerate(context['chunks'][:2], 1):  # Show first 2
                    text = chunk.get('text', '')[:120]
                    print(f"      {i}. {text}...")
            else:
                print("    No context retrieved!")
                
        except Exception as e:
            print(f"    ERROR: {e}")

async def main():
    # Step 1: Add LinkedIn source
    source_id = await add_linkedin_source()
    
    # Step 2: Try automated ingestion (will fail with LinkedIn block)
    await trigger_ingestion(source_id)
    
    # Step 3: Add manual content
    content = add_manual_content(source_id)
    
    # Step 4: Index content
    num_chunks = await index_content(source_id, content)
    
    # Step 5: Generate bio
    bio = generate_bio()
    
    # Step 6: Test chat
    if bio:
        await test_chat()
    
    print("\n" + "=" * 80)
    print("FULL FLOW TEST COMPLETE!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
