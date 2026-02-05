"""
Direct Pinecone query to verify vectors exist
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.clients import get_pinecone_index
from modules.embeddings import get_embedding

TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
QUERY = "XYLOPHONE-REPRO-SUCCESS-3"

print(f"\n{'='*70}")
print(f" PROOF ARTIFACT 4: PINECONE VECTOR VERIFICATION")
print(f"{'='*70}")
print(f"Twin ID (namespace): {TWIN_ID}")
print(f"Query: {QUERY}")

try:
    index = get_pinecone_index()
    
    # Get stats for namespace
    print(f"\n--- Index Stats ---")
    stats = index.describe_index_stats()
    print(f"Total vectors: {stats.get('total_vector_count', 'N/A')}")
    
    namespaces = stats.get('namespaces', {})
    if TWIN_ID in namespaces:
        ns_stats = namespaces[TWIN_ID]
        print(f"Namespace {TWIN_ID}: {ns_stats.get('vector_count', 0)} vectors")
    else:
        print(f"⚠️ Namespace {TWIN_ID} not found in index")
        print(f"Available namespaces: {list(namespaces.keys())[:5]}...")
    
    # Query for vectors
    print(f"\n--- Querying for test phrase ---")
    query_embedding = get_embedding(QUERY)
    results = index.query(
        vector=query_embedding,
        top_k=3,
        include_metadata=True,
        namespace=TWIN_ID
    )
    
    output_data = {
        "index_stats": stats,
        "matches": []
    }
    
    if results.get('matches'):
        print(f"\n✅ VECTORS FOUND")
        for match in results['matches']:
            match_data = {
                "id": match['id'],
                "score": match['score'],
                "metadata": match.get('metadata', {})
            }
            output_data["matches"].append(match_data)
            
            print(f"\n  ID: {match['id'][:20]}...")
            print(f"  Score: {match['score']:.4f}")
            metadata = match.get('metadata', {})
            text_preview = metadata.get('text', '')[:100]
            print(f"  Text: {text_preview}...")
            if 'XYLOPHONE' in metadata.get('text', '').upper():
                print(f"  ✅ UNIQUE PHRASE FOUND IN VECTOR!")
    else:
        print(f"\n❌ NO VECTORS RETURNED FROM QUERY")
    
    with open("pinecone_results.json", "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"\nResults saved to pinecone_results.json")
        
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print(f"{'='*70}")
