
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import random
import asyncio
from datetime import datetime

from modules.auth_guard import get_current_user, verify_twin_ownership, ensure_twin_active
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
        ensure_twin_active(twin_id)
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


# ============================================================================
# ISSUE-002: Quality Verification Suite
# Comprehensive pre-publish verification with 3 test prompts
# ============================================================================

class QualityTestResult(BaseModel):
    test_name: str
    query: str
    passed: bool
    has_answer: bool
    has_citations: bool
    confidence_score: float
    answer_preview: str
    issues: List[str]


class QualityVerificationResponse(BaseModel):
    status: str  # PASS, FAIL
    twin_id: str
    overall_score: float  # 0.0 to 1.0
    tests_run: int
    tests_passed: int
    test_results: List[QualityTestResult]
    issues: List[str]
    verified_at: str


@router.post("/twins/{twin_id}/quality-suite", response_model=QualityVerificationResponse)
async def run_quality_verification_suite(
    twin_id: str, 
    user=Depends(get_current_user)
):
    """
    Run comprehensive quality verification suite before publish.
    
    Executes 3 deterministic test prompts and validates:
    - Response contains actual content (not empty/fallback)
    - Citations are returned
    - Confidence score is above threshold (0.7)
    
    Requires all 3 tests to pass for overall PASS status.
    Records result in twin_verifications table.
    """
    # 1. Verify Ownership
    try:
        verify_twin_ownership(twin_id, user)
        ensure_twin_active(twin_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        return QualityVerificationResponse(
            status="FAIL",
            twin_id=twin_id,
            overall_score=0.0,
            tests_run=0,
            tests_passed=0,
            test_results=[],
            issues=[f"Auth Check Failed: {str(e)}"],
            verified_at=datetime.now().isoformat()
        )

    # 2. Define 3 deterministic test prompts
    # These are designed to test different aspects of retrieval
    test_prompts = [
        {
            "name": "Basic Knowledge Retrieval",
            "query": "What topics can you help me with?"
        },
        {
            "name": "Source-Grounded Response", 
            "query": "Based on my uploaded documents, what are my main areas of expertise?"
        },
        {
            "name": "Confidence Check",
            "query": "Tell me something about my work."
        }
    ]
    
    test_results: List[QualityTestResult] = []
    issues: List[str] = []
    
    try:
        # 3. Run each test
        for test_def in test_prompts:
            result = await _run_single_quality_test(
                twin_id=twin_id,
                test_name=test_def["name"],
                query=test_def["query"],
                user=user
            )
            test_results.append(result)
            
            if not result.passed:
                issues.extend(result.issues)
        
        # 4. Calculate overall results
        tests_passed = sum(1 for r in test_results if r.passed)
        tests_run = len(test_results)
        overall_score = tests_passed / tests_run if tests_run > 0 else 0.0
        
        # Require all tests to pass for overall PASS
        status = "PASS" if tests_passed == tests_run else "FAIL"
        
        # Additional check: must have vectors
        from modules.delphi_namespace import get_namespace_candidates_for_twin
        from modules.clients import get_pinecone_index
        
        try:
            index = get_pinecone_index()
            p_stats = index.describe_index_stats()
            namespaces = p_stats.get("namespaces", {})
            vector_count = 0
            for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
                if namespace in namespaces:
                    vector_count += namespaces[namespace]["vector_count"]
            
            if vector_count == 0:
                status = "FAIL"
                issues.append("No knowledge vectors found. Upload documents first.")
        except Exception as e:
            print(f"[QualityVerify] Warning: Could not check vector count: {e}")
        
        response = QualityVerificationResponse(
            status=status,
            twin_id=twin_id,
            overall_score=overall_score,
            tests_run=tests_run,
            tests_passed=tests_passed,
            test_results=test_results,
            issues=issues,
            verified_at=datetime.now().isoformat()
        )
        
        # 5. Record result
        await _record_quality_verification(twin_id, response)
        
        return response
        
    except Exception as e:
        print(f"[QualityVerify] Error running suite: {e}")
        import traceback
        traceback.print_exc()
        return QualityVerificationResponse(
            status="FAIL",
            twin_id=twin_id,
            overall_score=0.0,
            tests_run=0,
            tests_passed=0,
            test_results=[],
            issues=[f"Suite execution error: {str(e)}"],
            verified_at=datetime.now().isoformat()
        )


# Quality verification constants
QUALITY_CONFIDENCE_THRESHOLD = 0.7
QUALITY_ANSWER_MIN_LENGTH = 20
AGENT_STREAM_TIMEOUT_SECONDS = 30

# Defensive imports for optional modules
try:
    from modules.agent import run_agent_stream
    from modules.retrieval import retrieve_context
    AGENT_AVAILABLE = True
except ImportError as e:
    print(f"[QualityVerify] Warning: Agent module not available: {e}")
    AGENT_AVAILABLE = False
    run_agent_stream = None
    retrieve_context = None


async def _run_single_quality_test(
    twin_id: str,
    test_name: str,
    query: str,
    user: Dict[str, Any]
) -> QualityTestResult:
    """Run a single quality test by calling the chat endpoint internally."""
    
    issues = []
    has_answer = False
    has_citations = False
    confidence_score = 0.0
    answer_preview = ""
    
    try:
        # Check if agent is available
        if not AGENT_AVAILABLE:
            issues.append(f"Test '{test_name}': Agent module not available")
            return QualityTestResult(
                test_name=test_name,
                query=query,
                passed=False,
                has_answer=False,
                has_citations=False,
                confidence_score=0.0,
                answer_preview="",
                issues=issues
            )
        
        from langchain_core.messages import HumanMessage
        
        # Run retrieval to get context (similar to chat)
        contexts = await retrieve_context(query, twin_id, top_k=5)
        
        if not contexts:
            issues.append(f"Test '{test_name}': No retrieval contexts found")
            return QualityTestResult(
                test_name=test_name,
                query=query,
                passed=False,
                has_answer=False,
                has_citations=False,
                confidence_score=0.0,
                answer_preview="",
                issues=issues
            )
        
        # Check if citations are present
        has_citations = len(contexts) > 0
        
        # Get confidence from top context
        if contexts:
            confidence_score = float(contexts[0].get("score", 0.0))
        
        # Run a simplified agent stream to get answer
        # We'll collect the response
        langchain_history = [HumanMessage(content=query)]
        
        full_response = ""
        try:
            # Add timeout to prevent hanging
            import asyncio
            start_time = asyncio.get_event_loop().time()
            
            async for chunk in run_agent_stream(
                twin_id=twin_id,
                query=query,
                history=langchain_history,
                conversation_id=None
            ):
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > AGENT_STREAM_TIMEOUT_SECONDS:
                    raise asyncio.TimeoutError(f"Agent stream exceeded {AGENT_STREAM_TIMEOUT_SECONDS}s")
                
                if isinstance(chunk, dict):
                    # Extract from agent output
                    agent_payload = chunk.get("agent", {})
                    if agent_payload:
                        msgs = agent_payload.get("messages", [])
                        if msgs:
                            last_msg = msgs[-1]
                            if hasattr(last_msg, "content"):
                                full_response = last_msg.content
                    
                    # Also check for tools metadata
                    tools_payload = chunk.get("tools", {})
                    if tools_payload:
                        citations = tools_payload.get("citations", [])
                        if citations:
                            has_citations = True
                        conf = tools_payload.get("confidence_score")
                        if conf is not None:
                            confidence_score = float(conf)
        except asyncio.TimeoutError:
            print(f"[QualityTest] Agent stream timeout for test '{test_name}'")
            issues.append(f"Test '{test_name}': Agent response timeout (>{AGENT_STREAM_TIMEOUT_SECONDS}s)")
        except Exception as e:
            print(f"[QualityTest] Error in agent stream: {e}")
            issues.append(f"Agent error: {str(e)}")
        
        # Evaluate result
        has_answer = bool(full_response) and len(full_response.strip()) > QUALITY_ANSWER_MIN_LENGTH
        answer_preview = full_response[:100] + "..." if len(full_response) > 100 else full_response
        
        # Check for fallback message
        fallback_phrases = [
            "I don't have this specific information",
            "I don't know",
            "I don't have information about"
        ]
        is_fallback = any(phrase in full_response for phrase in fallback_phrases)
        
        if is_fallback:
            has_answer = False
            issues.append(f"Test '{test_name}': Response was a fallback - the twin doesn't have relevant knowledge")
        
        # Determine pass/fail
        # Must have: answer, citations, confidence >= threshold
        passed = has_answer and has_citations and confidence_score >= QUALITY_CONFIDENCE_THRESHOLD
        
        if not has_answer:
            issues.append(f"Test '{test_name}': No meaningful answer generated. Try uploading relevant documents.")
        if not has_citations:
            issues.append(f"Test '{test_name}': No source citations found. Content may not be properly indexed.")
        if confidence_score < QUALITY_CONFIDENCE_THRESHOLD:
            issues.append(f"Test '{test_name}': Answer confidence too low ({confidence_score:.0%} < {QUALITY_CONFIDENCE_THRESHOLD:.0%}). Content may need review.")
        
        return QualityTestResult(
            test_name=test_name,
            query=query,
            passed=passed,
            has_answer=has_answer,
            has_citations=has_citations,
            confidence_score=confidence_score,
            answer_preview=answer_preview,
            issues=issues
        )
        
    except Exception as e:
        print(f"[QualityTest] Error in test '{test_name}': {e}")
        import traceback
        traceback.print_exc()
        issues.append(f"Test '{test_name}' error: {str(e)}")
        return QualityTestResult(
            test_name=test_name,
            query=query,
            passed=False,
            has_answer=False,
            has_citations=False,
            confidence_score=0.0,
            answer_preview="",
            issues=issues
        )


async def _record_quality_verification(twin_id: str, result: QualityVerificationResponse):
    """Record quality verification result to database."""
    try:
        data = {
            "twin_id": twin_id,
            "status": result.status,
            "score": result.overall_score,
            "details": result.model_dump(),
            "created_at": datetime.now().isoformat()
        }
        supabase.table("twin_verifications").insert(data).execute()
        print(f"[QualityVerify] Recorded {result.status} for twin {twin_id} "
              f"({result.tests_passed}/{result.tests_run} tests passed)")
    except Exception as e:
        print(f"[QualityVerify] Failed to record verification: {e}")

