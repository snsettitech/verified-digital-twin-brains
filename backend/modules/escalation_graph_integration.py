"""
Escalation Graph Memory Integration (Phase 2)

Provides async outbox job enqueueing for escalation resolution.
All operations are non-blocking - jobs are queued for background processing.

Single-Profile Scope Migration:
- All operations use scope_id for isolation
- scope_id: "{tenant_id}__{creator_id}"
"""

import time
from typing import Optional, Dict, Any

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_outbox import GraphOperationType
from modules.graph_memory_config import is_single_profile_enabled


async def enqueue_escalation_graph_jobs(
    tenant_id: str,
    twin_id: str,
    escalation_id: str,
    question: str,
    answer: str,
    owner_id: str,
    correlation_id: Optional[str] = None,
    creator_id: Optional[str] = None,
    scope_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enqueue graph outbox jobs for escalation resolution.
    
    This is a non-blocking operation - jobs are queued and will be
    processed by the background worker. Uses idempotency keys to
    prevent duplicate processing on retries.
    
    Single-Profile Mode:
        Pass creator_id or scope_id for single-profile isolation.
        scope_id format: "{tenant_id}__{creator_id}"
    
    Args:
        tenant_id: Tenant ID for isolation
        twin_id: Twin ID for isolation (legacy, kept for backward compat)
        escalation_id: Unique escalation identifier
        question: Original user question
        answer: Owner's verified answer
        owner_id: ID of owner who resolved
        correlation_id: Optional trace ID
        creator_id: Creator ID for single-profile mode
        scope_id: Pre-computed scope ID (takes precedence if provided)
        
    Returns:
        Dict with job_ids for each enqueued operation
    """
    # Determine scope for single-profile mode
    if scope_id:
        effective_scope_id = scope_id
        effective_creator_id = creator_id
    elif creator_id:
        from modules.graph_memory_config import get_graph_memory_config
        config = get_graph_memory_config()
        effective_scope_id = config.make_scope_id(tenant_id, creator_id)
        effective_creator_id = creator_id
    else:
        effective_scope_id = None
        effective_creator_id = None
    
    client = GraphMemoryCore(
        tenant_id=tenant_id,
        twin_id=twin_id,
        correlation_id=correlation_id or f"escalation-{escalation_id}",
        creator_id=effective_creator_id,
        scope_id=effective_scope_id
    )
    
    results = {
        "escalation_episode_job": None,
        "claim_extraction_job": None,
        "contradiction_eval_job": None,
        "errors": [],
        "scope_id": effective_scope_id
    }
    
    # 1. Create escalation episode job
    try:
        episode_name = f"Escalation Resolution: {question[:50]}..."
        episode_body = f"""
Question: {question}

Owner Answer: {answer}

Resolved by: {owner_id}
Escalation ID: {escalation_id}
""".strip()
        
        # Use idempotency key with scope_id for proper isolation
        content_hash = hash(answer) & 0xFFFFFFFF
        idempotency_key = f"escalation_episode:{escalation_id}:{content_hash}"
        
        job_id = client.outbox.submit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            scope_id=effective_scope_id,
            creator_id=effective_creator_id,
            operation=GraphOperationType.CREATE_EPISODE,
            idempotency_key=idempotency_key,
            payload={
                "name": episode_name,
                "body": episode_body,
                "source_type": "escalation_resolution",
                "source_ref": escalation_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "scope_id": effective_scope_id,
                "metadata": {
                    "question": question,
                    "answer": answer,
                    "owner_id": owner_id,
                    "escalation_id": escalation_id,
                    "scope_id": effective_scope_id
                }
            },
            correlation_id=correlation_id or f"escalation-{escalation_id}"
        )
        results["escalation_episode_job"] = job_id
        
    except Exception as e:
        results["errors"].append(f"episode_job_failed: {e}")
    
    # 2. Enqueue claim extraction (async)
    try:
        # Idempotency key includes content hash to auto-dedupe on retry
        content_hash = hash(answer) & 0xFFFFFFFF
        idempotency_key = f"claim_extract:{escalation_id}:{content_hash}"
        
        job_id = client.outbox.submit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            scope_id=effective_scope_id,
            creator_id=effective_creator_id,
            operation=GraphOperationType.EXTRACT_CLAIMS,
            idempotency_key=idempotency_key,
            payload={
                "source_type": "escalation_resolution",
                "source_ref": escalation_id,
                "content": answer,
                "scope_id": effective_scope_id,
                "context": {
                    "question": question,
                    "owner_id": owner_id,
                    "scope_id": effective_scope_id
                }
            },
            correlation_id=correlation_id or f"escalation-{escalation_id}"
        )
        results["claim_extraction_job"] = job_id
        
    except Exception as e:
        results["errors"].append(f"claim_extraction_job_failed: {e}")
    
    # 3. Enqueue contradiction evaluation (async)
    try:
        # Only evaluate if we have a question-answer pair
        content_hash = hash(question + answer) & 0xFFFFFFFF
        idempotency_key = f"contradiction_eval:{escalation_id}:{content_hash}"
        
        job_id = client.outbox.submit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            scope_id=effective_scope_id,
            creator_id=effective_creator_id,
            operation=GraphOperationType.EVALUATE_CONTRADICTIONS,
            idempotency_key=idempotency_key,
            payload={
                "source_type": "escalation_resolution",
                "source_ref": escalation_id,
                "scope_id": effective_scope_id,
                "claims_context": {
                    "question": question,
                    "answer": answer
                },
                "evaluation_scope": "scope" if effective_scope_id else "twin"
            },
            correlation_id=correlation_id or f"escalation-{escalation_id}"
        )
        results["contradiction_eval_job"] = job_id
        
    except Exception as e:
        results["errors"].append(f"contradiction_eval_job_failed: {e}")
    
    return results


def check_escalation_graph_status(
    tenant_id: str,
    twin_id: str,
    escalation_id: str,
    scope_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check status of graph jobs for an escalation.
    
    Args:
        tenant_id: Tenant ID
        twin_id: Twin ID (legacy)
        escalation_id: Escalation identifier
        scope_id: Scope ID for single-profile mode
        
    Returns:
        Pending/completed status for each job type
    """
    client = GraphMemoryCore(
        tenant_id=tenant_id,
        twin_id=twin_id,
        scope_id=scope_id
    )
    
    # Check outbox for pending jobs matching this escalation
    stats = client.outbox.get_stats(scope_id=scope_id)
    
    return {
        "escalation_id": escalation_id,
        "scope_id": scope_id,
        "outbox_pending": stats.get("pending", 0),
        "outbox_processing": stats.get("processing", 0),
        "outbox_completed": stats.get("completed", 0),
        "outbox_failed": stats.get("failed", 0),
    }


async def escalate_to_graph_memory(
    tenant_id: str,
    twin_id: str,
    question: str,
    answer: str,
    owner_id: str,
    creator_id: Optional[str] = None,
    scope_id: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Optional[str]:
    """
    Direct escalation to graph memory (synchronous episode creation).
    
    This creates an episode immediately in the graph for escalations.
    Use when you want immediate persistence without outbox queuing.
    
    Single-Profile Mode:
        Pass creator_id or scope_id for single-profile isolation.
    
    Args:
        tenant_id: Tenant ID
        twin_id: Twin ID
        question: User question
        answer: Owner's answer
        owner_id: Owner ID
        creator_id: Creator ID for single-profile mode
        scope_id: Pre-computed scope ID
        correlation_id: Trace ID
        
    Returns:
        Episode ID if created, None otherwise
    """
    # Determine scope
    if scope_id:
        effective_scope_id = scope_id
        effective_creator_id = creator_id
    elif creator_id:
        from modules.graph_memory_config import get_graph_memory_config
        config = get_graph_memory_config()
        effective_scope_id = config.make_scope_id(tenant_id, creator_id)
        effective_creator_id = creator_id
    else:
        effective_scope_id = None
        effective_creator_id = None
    
    client = GraphMemoryCore(
        tenant_id=tenant_id,
        twin_id=twin_id,
        correlation_id=correlation_id,
        creator_id=effective_creator_id,
        scope_id=effective_scope_id
    )
    
    episode_name = f"Escalation: {question[:50]}..."
    episode_body = f"""
Question: {question}

Owner Answer: {answer}

Resolved by: {owner_id}
""".strip()
    
    try:
        episode_id = await client.create_episode(
            name=episode_name,
            body=episode_body,
            source_type="escalation",
            source_ref=f"esc_{int(time.time())}",
            async_write=False  # Synchronous for immediate feedback
        )
        return episode_id
    except Exception as e:
        # Log error but don't fail the escalation
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[EscalationGraph] Failed to create episode: {e}")
        return None
