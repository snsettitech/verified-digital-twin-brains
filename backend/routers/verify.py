
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import random
import asyncio

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.observability import supabase
from modules.retrieval import retrieve_context

router = APIRouter(
    prefix="/verify",
    tags=["verify"]
)

class VerifyResponse(BaseModel):
    status: str # PASS, FAIL
    tested_source_id: Optional[str] = None
    tested_chunk_id: Optional[str] = None
    query_used: Optional[str] = None
    match_found: bool = False
    rank_of_match: Optional[int] = None
    top_score: float = 0.0
    issues: List[str] = []

@router.post("/twins/{twin_id}/run")
async def run_verification(twin_id: str, user=Depends(get_current_user)):
    """
    Run a 'Verify Retrieval' test for the twin.
    Picks a random chunk from the twin's knowledge and checks if it can be retrieved.
    Records the result in twin_verifications table.
    """
    # 1. Verify Ownership
    try:
        verify_twin_ownership(twin_id, user)
    except HTTPException as e:
        raise e
    except Exception as e:
        return VerifyResponse(status="FAIL", issues=[f"Auth Check Failed: {str(e)}"])

    response = VerifyResponse(status="FAIL")
    
    try:
        # 2. Fetch a probe chunk (latest 20 chunks to ensure we test recent knowledge)
        # We need to find sources for this twin first
        sources_res = supabase.table("sources").select("id").eq("twin_id", twin_id).execute()
        source_ids = [s["id"] for s in sources_res.data]
        
        if not source_ids:
            response.issues.append("No uploaded sources found.")
            await _record_verification(twin_id, "FAIL", response)
            return response
            
        # Get chunks for these sources
        chunks_res = supabase.table("chunks") \
            .select("id, content, source_id") \
            .in_("source_id", source_ids) \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute()
            
        chunks = chunks_res.data
        if not chunks:
            response.issues.append("No chunks found in database.")
            await _record_verification(twin_id, "FAIL", response)
            return response
            
        target = random.choice(chunks)
        # print(f"DEBUG: Selected chunk {target['id']}") # Optional logging
        response.tested_chunk_id = target["id"]
        response.tested_source_id = target["source_id"]
        
        # 3. Construct Query (use a snippet of the text)
        content = target["content"]
        # Take a distinct snippet (e.g., first 20 words or 100 chars)
        if len(content) < 50:
            query = content
        else:
            # Take a slice from the middle to avoid header weirdness
            start = 0
            query = content[start:start+200]
            
        response.query_used = query
        
        # 4. Execute Retrieval (Restored)
        # Request top_k=10 to be generous for verification
        contexts = await retrieve_context(query, twin_id, top_k=10)
        
        if not contexts:
            response.issues.append("Retrieval returned 0 results (I don't know triggered).")
            # We fail if we can't retrieve known content
            # status implies "Can we retrieve our own knowledge?"
            response.status = "FAIL" 
            
        else:
            # Force conversion from numpy types to standard Python float
            response.top_score = float(contexts[0].get("score", 0.0))
            
            # 5. Evaluate
            found = False
            for i, ctx in enumerate(contexts):
                # Check for chunk_id match (strongest)
                ctx_chunk_id = ctx.get("chunk_id")
                # Or check source_id match (acceptable)
                ctx_source_id = ctx.get("source_id")
                
                if ctx_chunk_id == target["id"] or ctx_source_id == target["source_id"]:
                    found = True
                    response.rank_of_match = i + 1
                    break
            
            response.match_found = found
            
            if found:
                # Check if top score is reasonably high
                if response.top_score > 0.001:
                    response.status = "PASS"
                else:
                    response.issues.append(f"Match found but score too low ({response.top_score})")
            else:
                response.issues.append("Target source/chunk not found in top 10 results.")

        
    except Exception as e:
        response.issues.append(f"System error: {str(e)}")
        print(f"[Verify] Error: {e}")
        
    # 6. Record Result
    await _record_verification(twin_id, response.status, response)
    
    return response

async def _record_verification(twin_id: str, status: str, details: VerifyResponse):
    try:
        data = {
            "twin_id": twin_id,
            "status": status,
            "score": float(details.top_score),
            "source_id": details.tested_source_id,
            "chunk_id": details.tested_chunk_id,
            "details": details.model_dump()
        }
        supabase.table("twin_verifications").insert(data).execute()
        print(f"[Verify] Recorded {status} for twin {twin_id}")
    except Exception as e:
        print(f"[Verify] Failed to record verification: {e}")

