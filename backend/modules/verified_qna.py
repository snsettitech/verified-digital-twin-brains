"""
Verified QnA Module: Canonical storage and retrieval of owner-verified answers.
"""
import uuid
import json
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher
from modules.observability import supabase
from modules.ingestion import get_embedding
from modules.clients import get_pinecone_index
from modules.memory import inject_verified_memory


async def create_verified_qna(
    escalation_id: str,
    question: str,
    answer: str,
    owner_id: str,
    citations: Optional[List[str]] = None,
    twin_id: Optional[str] = None
) -> str:
    """
    Creates a verified QnA entry in Postgres and optionally stores in Pinecone.
    
    Args:
        escalation_id: ID of the escalation being resolved
        question: Original question that triggered escalation
        answer: Owner's verified answer
        owner_id: ID of the user creating this QnA
        citations: Optional list of source/chunk IDs
        twin_id: Optional twin_id (will be fetched from escalation if not provided)
    
    Returns:
        verified_qna_id: UUID of the created verified QnA entry
    """
    # Fetch escalation to get twin_id if not provided
    if not twin_id:
        response = supabase.table("escalations").select(
            "*, messages(conversation_id, conversations(twin_id))"
        ).eq("id", escalation_id).single().execute()
        if not response.data:
            raise ValueError(f"Escalation {escalation_id} not found")
        twin_id = response.data["messages"]["conversations"]["twin_id"]
    
    # Generate embedding for question (for semantic matching)
    try:
        question_embedding = get_embedding(question)
        question_embedding_json = json.dumps(question_embedding)
    except Exception as e:
        import traceback
        error_msg = f"Error generating embedding: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Create verified_qna entry
    try:
        qna_response = supabase.table("verified_qna").insert({
            "twin_id": twin_id,
            "question": question,
            "answer": answer,
            "question_embedding": question_embedding_json,
            "visibility": "private",
            "created_by": owner_id,
            "is_active": True
        }).execute()
        
        if not qna_response.data:
            raise ValueError("Failed to create verified QnA entry - no data returned")
        
        verified_qna_id = qna_response.data[0]["id"]
    except Exception as e:
        import traceback
        error_msg = f"Error creating verified_qna entry: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Create citation entries if provided
    if citations:
        citation_entries = [
            {
                "verified_qna_id": verified_qna_id,
                "source_id": citation,
                "chunk_id": None,
                "citation_url": None
            }
            for citation in citations
        ]
        supabase.table("citations").insert(citation_entries).execute()
    
    # Maintain backward compatibility: Also inject into Pinecone
    # This ensures existing retrieval still works during migration
    try:
        await inject_verified_memory(escalation_id, answer)
    except Exception as e:
        # Log error but don't fail the whole operation if Pinecone injection fails
        print(f"Warning: Failed to inject verified memory to Pinecone: {e}")
        # Continue - the Postgres entry is more important
    
    return verified_qna_id


async def match_verified_qna(
    query: str,
    twin_id: str,
    group_id: Optional[str] = None,
    use_exact: bool = True,
    use_semantic: bool = True,
    exact_threshold: float = 0.7,  # Lowered from 0.8 to 0.7 for better matching
    semantic_threshold: float = 0.7
) -> Optional[Dict[str, Any]]:
    """
    Matches a query against verified QnA entries using exact and/or semantic matching.
    If group_id is provided, only matches QnA entries accessible to that group.
    
    Args:
        query: User's query string
        twin_id: Twin ID to filter by
        group_id: Optional group ID to filter by permissions
        use_exact: Whether to use exact/fuzzy text matching
        use_semantic: Whether to use semantic (embedding) matching
        exact_threshold: Similarity threshold for exact matching (0-1)
        semantic_threshold: Similarity threshold for semantic matching (0-1)
    
    Returns:
        Best matching QnA entry with similarity score, or None if no match above threshold
    """
    # Fetch verified QnA entries, filtered by group if provided
    if group_id:
        # Get allowed content_ids from content_permissions
        permissions_response = supabase.table("content_permissions").select("content_id").eq(
            "group_id", group_id
        ).eq("content_type", "verified_qna").execute()
        
        allowed_content_ids = [perm["content_id"] for perm in (permissions_response.data or [])]
        
        if not allowed_content_ids:
            # No permissions for this group, return None
            return None
        
        # Fetch verified QnA entries that match the allowed content_ids
        response = supabase.table("verified_qna").select("*").eq(
            "twin_id", twin_id
        ).eq("is_active", True).in_("id", allowed_content_ids).execute()
    else:
        # No group filter - fetch all active verified QnA entries for this twin
        response = supabase.table("verified_qna").select("*").eq(
            "twin_id", twin_id
        ).eq("is_active", True).execute()
    
    if not response.data:
        return None
    
    best_match = None
    best_score = 0.0
    
    # Exact matching: Compare query with question using fuzzy matching
    if use_exact:
        query_normalized = query.lower().strip()
        for qna in response.data:
            question_normalized = qna["question"].lower().strip()
            
            # Check for exact match first (case-insensitive)
            if query_normalized == question_normalized:
                # Perfect match - return immediately
                best_score = 1.0
                best_match = qna
                break
            
            # Otherwise use fuzzy matching
            similarity = SequenceMatcher(None, query_normalized, question_normalized).ratio()
            if similarity > best_score and similarity >= exact_threshold:
                best_score = similarity
                best_match = qna
    
    # Semantic matching: Use Pinecone to search verified vectors
    if use_semantic:
        try:
            query_embedding = get_embedding(query)
            index = get_pinecone_index()
            
            # Search in Pinecone for verified vectors matching this twin
            results = index.query(
                vector=query_embedding,
                top_k=5,
                include_metadata=True,
                namespace=twin_id,
                filter={"is_verified": {"$eq": True}}
            )
            
            # For each Pinecone match, try to find corresponding Postgres entry
            # by matching on question or answer text
            for match in results.get("matches", []):
                if match["score"] >= semantic_threshold and match["score"] > best_score:
                    # Try to match Pinecone metadata with Postgres entries
                    match_text = match["metadata"].get("text", "")
                    for qna in response.data:
                        # Match if answer text matches or if source_id links to escalation
                        if qna["answer"] == match_text or match["metadata"].get("source_id", "").startswith("verified_"):
                            if match["score"] > best_score:
                                best_score = match["score"]
                                best_match = qna
                                break
        except Exception as e:
            print(f"Error during semantic matching: {e}")
    
    if best_match and best_score >= exact_threshold:
        # Fetch citations for this QnA
        citations_res = supabase.table("citations").select("*").eq(
            "verified_qna_id", best_match["id"]
        ).execute()
        citations = citations_res.data if citations_res.data else []
        
        return {
            "id": best_match["id"],
            "question": best_match["question"],
            "answer": best_match["answer"],
            "similarity_score": best_score,
            "is_verified": True,
            "citations": [c["source_id"] for c in citations if c.get("source_id")]
        }
    
    return None


async def get_verified_qna(qna_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches a verified QnA entry with its citations and patch history.
    
    Args:
        qna_id: UUID of the verified QnA entry
    
    Returns:
        QnA entry with citations and patches, or None if not found
    """
    qna_res = supabase.table("verified_qna").select("*").eq("id", qna_id).single().execute()
    if not qna_res.data:
        return None
    
    qna = qna_res.data
    
    # Fetch citations
    citations_res = supabase.table("citations").select("*").eq(
        "verified_qna_id", qna_id
    ).execute()
    citations = citations_res.data if citations_res.data else []
    
    # Fetch patch history
    patches_res = supabase.table("answer_patches").select("*").eq(
        "verified_qna_id", qna_id
    ).order("patched_at", desc=True).execute()
    patches = patches_res.data if patches_res.data else []
    
    return {
        **qna,
        "citations": citations,
        "patches": patches
    }


async def edit_verified_qna(
    qna_id: str,
    new_answer: str,
    reason: str,
    owner_id: str
) -> bool:
    """
    Edits a verified QnA entry, creating a patch entry for version history.
    
    Args:
        qna_id: UUID of the verified QnA entry
        new_answer: New answer text
        reason: Reason for the edit
        owner_id: ID of the user making the edit
    
    Returns:
        True if successful
    """
    # Fetch current answer
    qna_res = supabase.table("verified_qna").select("*").eq("id", qna_id).single().execute()
    if not qna_res.data:
        raise ValueError(f"Verified QnA {qna_id} not found")
    
    previous_answer = qna_res.data["answer"]
    
    # Create patch entry
    supabase.table("answer_patches").insert({
        "verified_qna_id": qna_id,
        "previous_answer": previous_answer,
        "new_answer": new_answer,
        "reason": reason,
        "patched_by": owner_id
    }).execute()
    
    # Update verified_qna entry
    from datetime import datetime
    supabase.table("verified_qna").update({
        "answer": new_answer,
        "updated_at": datetime.now().isoformat()
    }).eq("id", qna_id).execute()
    
    # TODO: Update Pinecone vector if dual storage enabled
    # This would require storing the vector_id in verified_qna or searching Pinecone
    
    return True


async def list_verified_qna(
    twin_id: str,
    visibility: Optional[str] = None,
    group_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Lists all verified QnA entries for a twin.
    
    Args:
        twin_id: Twin ID to filter by
        visibility: Optional visibility filter ('private', 'shared', 'public')
        group_id: Optional group ID to filter by permissions
    
    Returns:
        List of verified QnA entries
    """
    # If group_id provided, filter by permissions
    if group_id:
        permissions_response = supabase.table("content_permissions").select("content_id").eq(
            "group_id", group_id
        ).eq("content_type", "verified_qna").execute()
        
        allowed_content_ids = [perm["content_id"] for perm in (permissions_response.data or [])]
        
        if not allowed_content_ids:
            return []
        
        query = supabase.table("verified_qna").select("*").eq("twin_id", twin_id).eq("is_active", True).in_("id", allowed_content_ids)
    else:
        query = supabase.table("verified_qna").select("*").eq("twin_id", twin_id).eq("is_active", True)
    
    if visibility:
        query = query.eq("visibility", visibility)
    
    response = query.order("created_at", desc=True).execute()
    return response.data if response.data else []
