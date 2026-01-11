"""
Migration script to backfill verified QnA entries from existing verified vectors in Pinecone.
This script queries Pinecone for all vectors with is_verified=True and creates corresponding
verified_qna entries in Postgres.
"""
import os
import sys
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.clients import get_pinecone_index, get_openai_client
from modules.observability import supabase
from modules.verified_qna import create_verified_qna

load_dotenv()


async def fetch_all_verified_vectors(twin_id: str = None) -> List[Dict[str, Any]]:
    """
    Fetches all verified vectors from Pinecone.
    Since Pinecone doesn't support listing all vectors directly, we use a dummy query
    with high top_k to get as many as possible, or query by namespace if twin_id provided.
    """
    index = get_pinecone_index()
    verified_vectors = []
    
    # Get list of all namespaces (twins) if twin_id not provided
    namespaces = []
    if twin_id:
        namespaces = [twin_id]
    else:
        # Fetch all twins from database to get namespaces
        twins_res = supabase.table("twins").select("id").execute()
        if twins_res.data:
            namespaces = [t["id"] for t in twins_res.data]
        else:
            # Fallback: try to query stats to get namespaces
            try:
                stats = index.describe_index_stats()
                namespaces = list(stats.get("namespaces", {}).keys())
            except:
                print("Warning: Could not fetch namespaces. Using empty list.")
    
    # Query each namespace for verified vectors
    # Use a dummy embedding (zeros) with high top_k and filter
    dummy_embedding = [0.0] * 3072
    
    for namespace in namespaces:
        try:
            print(f"Querying namespace: {namespace}")
            # Query with high top_k to get many results
            results = index.query(
                vector=dummy_embedding,
                top_k=10000,  # High number to get many results
                include_metadata=True,
                namespace=namespace,
                filter={"is_verified": {"$eq": True}}
            )
            
            for match in results.get("matches", []):
                verified_vectors.append({
                    "vector_id": match["id"],
                    "namespace": namespace,
                    "metadata": match["metadata"],
                    "score": match.get("score", 0.0)
                })
            
            print(f"Found {len(results.get('matches', []))} verified vectors in namespace {namespace}")
        except Exception as e:
            print(f"Error querying namespace {namespace}: {e}")
    
    return verified_vectors


async def migrate_verified_vector(vector_data: Dict[str, Any]) -> bool:
    """
    Migrates a single verified vector to a verified_qna entry.
    """
    try:
        vector_id = vector_data["vector_id"]
        namespace = vector_data["namespace"]  # This is the twin_id
        metadata = vector_data["metadata"]
        
        # Extract data from metadata
        answer = metadata.get("text", "")
        source_id = metadata.get("source_id", "")
        
        if not answer:
            print(f"Skipping vector {vector_id}: No answer text in metadata")
            return False
        
        # Try to find escalation from source_id (format: verified_{escalation_id})
        escalation_id = None
        if source_id.startswith("verified_"):
            escalation_id = source_id.replace("verified_", "")
            
            # Verify escalation exists
            esc_res = supabase.table("escalations").select("*, messages(content)").eq("id", escalation_id).single().execute()
            if not esc_res.data:
                print(f"Warning: Escalation {escalation_id} not found for vector {vector_id}")
                escalation_id = None
        
        # If no escalation found, try to get question from escalation_replies
        question = ""
        owner_id = None
        
        if escalation_id:
            esc_res = supabase.table("escalations").select(
                "*, messages(content, conversations(twin_id)), escalation_replies(owner_id)"
            ).eq("id", escalation_id).single().execute()
            
            if esc_res.data:
                question = esc_res.data["messages"]["content"]
                # Get owner_id from escalation_replies
                if esc_res.data.get("escalation_replies"):
                    owner_id = esc_res.data["escalation_replies"][0].get("owner_id")
        else:
            # No escalation found - we'll need to create a placeholder question
            # Use first part of answer or a generic question
            question = f"Question for verified answer: {answer[:100]}..."
            print(f"Warning: Using placeholder question for vector {vector_id}")
        
        # Check if verified_qna already exists (to avoid duplicates)
        existing = supabase.table("verified_qna").select("id").eq(
            "twin_id", namespace
        ).eq("question", question).eq("answer", answer).execute()
        
        if existing.data:
            print(f"Skipping: Verified QnA already exists for vector {vector_id}")
            return False
        
        # Create verified_qna entry
        # We need to handle the case where escalation_id might not exist
        # For now, create directly in database
        question_embedding_json = None
        try:
            from modules.embeddings import get_embedding
            question_embedding = get_embedding(question)
            import json
            question_embedding_json = json.dumps(question_embedding)
        except Exception as e:
            print(f"Warning: Could not generate embedding for question: {e}")
        
        qna_response = supabase.table("verified_qna").insert({
            "twin_id": namespace,
            "question": question,
            "answer": answer,
            "question_embedding": question_embedding_json,
            "visibility": "private",
            "created_by": owner_id,
            "is_active": True
        }).execute()
        
        if qna_response.data:
            print(f"✓ Migrated vector {vector_id} to verified_qna {qna_response.data[0]['id']}")
            return True
        else:
            print(f"✗ Failed to create verified_qna for vector {vector_id}")
            return False
            
    except Exception as e:
        print(f"Error migrating vector {vector_data.get('vector_id', 'unknown')}: {e}")
        return False


async def main():
    """
    Main migration function.
    """
    print("=" * 60)
    print("Verified QnA Migration Script")
    print("=" * 60)
    print()
    
    # Check if twin_id provided as argument
    twin_id = None
    if len(sys.argv) > 1:
        twin_id = sys.argv[1]
        print(f"Migrating verified vectors for twin: {twin_id}")
    else:
        print("Migrating verified vectors for all twins")
    
    print()
    
    # Step 1: Fetch all verified vectors
    print("Step 1: Fetching verified vectors from Pinecone...")
    verified_vectors = await fetch_all_verified_vectors(twin_id)
    print(f"Found {len(verified_vectors)} verified vectors")
    print()
    
    if len(verified_vectors) == 0:
        print("No verified vectors found. Nothing to migrate.")
        return
    
    # Step 2: Check existing verified_qna entries
    print("Step 2: Checking existing verified_qna entries...")
    if twin_id:
        existing_qna = supabase.table("verified_qna").select("id").eq("twin_id", twin_id).execute()
    else:
        existing_qna = supabase.table("verified_qna").select("id").execute()
    
    existing_count = len(existing_qna.data) if existing_qna.data else 0
    print(f"Found {existing_count} existing verified_qna entries")
    print()
    
    # Step 3: Migrate each vector
    print("Step 3: Migrating vectors to verified_qna...")
    migrated_count = 0
    failed_count = 0
    
    for i, vector_data in enumerate(verified_vectors, 1):
        print(f"[{i}/{len(verified_vectors)}] Processing vector {vector_data['vector_id']}...")
        success = await migrate_verified_vector(vector_data)
        if success:
            migrated_count += 1
        else:
            failed_count += 1
    
    print()
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Total verified vectors found: {len(verified_vectors)}")
    print(f"Successfully migrated: {migrated_count}")
    print(f"Failed/Skipped: {failed_count}")
    print(f"Existing verified_qna entries: {existing_count}")
    
    # Step 4: Verify migration
    print()
    print("Step 4: Verifying migration...")
    if twin_id:
        final_qna = supabase.table("verified_qna").select("id").eq("twin_id", twin_id).execute()
    else:
        final_qna = supabase.table("verified_qna").select("id").execute()
    
    final_count = len(final_qna.data) if final_qna.data else 0
    print(f"Final verified_qna count: {final_count}")
    print(f"New entries created: {final_count - existing_count}")
    print()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(main())
