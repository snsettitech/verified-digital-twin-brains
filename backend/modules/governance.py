"""
Governance Module
Manages audit logging, twin verification, and governance policies.
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from modules.observability import supabase

class AuditLogger:
    """Centralized logger for immutable system events."""
    
    @staticmethod
    def log(twin_id: str, event_type: str, action: str,
            actor_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Records an audit event in the database.
        
        Args:
            twin_id: Twin UUID
            event_type: Category (AUTHENTICATION, CONFIGURATION_CHANGE, KNOWLEDGE_UPDATE, etc.)
            action: Specific action taken (API_KEY_CREATED, SOURCE_DELETED, etc.)
            actor_id: Optional User UUID who performed the action
            metadata: Optional additional context
        """
        try:
            supabase.table("audit_logs").insert({
                "twin_id": twin_id,
                "actor_id": actor_id,
                "event_type": event_type,
                "action": action,
                "metadata": metadata or {}
            }).execute()
        except Exception as e:
            # Fallback to stdout if DB logging fails to ensure audit trail isn't lost
            print(f"CRITICAL: Audit logging failed: {e}")
            print(f"Audit Event: {twin_id} | {event_type} | {action} | {actor_id} | {metadata}")

def get_audit_logs(twin_id: str, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetches audit logs for a twin."""
    query = supabase.table("audit_logs").select("*").eq("twin_id", twin_id)
    if event_type:
        query = query.eq("event_type", event_type)
    
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data if response.data else []

def request_verification(twin_id: str, method: str = "MANUAL_REVIEW", metadata: Optional[Dict[str, Any]] = None) -> str:
    """Initiates a verification request for a twin."""
    # Check if already verified or pending
    existing = supabase.table("twin_verification").select("status").eq("twin_id", twin_id).execute()
    if existing.data and existing.data[0]["status"] in ("pending", "verified"):
        return existing.data[0]["status"]
    
    # Upsert verification record
    supabase.table("twin_verification").upsert({
        "twin_id": twin_id,
        "status": "pending",
        "verification_method": method,
        "metadata": metadata or {},
        "requested_at": datetime.utcnow().isoformat()
    }).execute()
    
    # Update twin record status
    supabase.table("twins").update({
        "verification_status": "pending"
    }).eq("id", twin_id).execute()
    
    # Log the action
    AuditLogger.log(twin_id, "CONFIGURATION_CHANGE", "VERIFICATION_REQUESTED", metadata={"method": method})
    
    return "pending"

def approve_verification(twin_id: str, verifier_id: str):
    """Approves a twin's verification request (Admin only logic)."""
    now = datetime.utcnow().isoformat()
    
    supabase.table("twin_verification").update({
        "status": "verified",
        "verified_at": now,
        "verified_by": verifier_id
    }).eq("twin_id", twin_id).execute()
    
    supabase.table("twins").update({
        "is_verified": True,
        "verification_status": "verified"
    }).eq("id", twin_id).execute()
    
    AuditLogger.log(twin_id, "CONFIGURATION_CHANGE", "VERIFICATION_APPROVED", actor_id=verifier_id)

def get_governance_policies(twin_id: str) -> List[Dict[str, Any]]:
    """Fetches active policies for a twin."""
    response = supabase.table("governance_policies").select("*").eq("twin_id", twin_id).eq("is_active", True).execute()
    return response.data if response.data else []

def create_governance_policy(twin_id: str, policy_type: str, name: str, content: str) -> Dict[str, Any]:
    """Creates a new governance policy."""
    response = supabase.table("governance_policies").insert({
        "twin_id": twin_id,
        "policy_type": policy_type,
        "name": name,
        "content": content
    }).execute()
    
    AuditLogger.log(twin_id, "CONFIGURATION_CHANGE", "POLICY_CREATED", metadata={"name": name, "type": policy_type})
    return response.data[0] if response.data else {}

async def deep_scrub_source(source_id: str, reason: Optional[str] = None):
    """
    Permanently purges a source and its derived vectors.
    """
    # 1. Get source metadata
    source_res = supabase.table("sources").select("twin_id, filename").eq("id", source_id).single().execute()
    if not source_res.data:
        raise ValueError("Source not found")
    
    twin_id = source_res.data["twin_id"]
    filename = source_res.data["filename"]
    
    # 2. Delete from Pinecone
    from modules.clients import get_pinecone_index
    index = get_pinecone_index()
    try:
        # Delete all vectors with this source_id in the twin's namespace
        index.delete(filter={"source_id": {"$eq": source_id}}, namespace=twin_id)
    except Exception as e:
        print(f"Error purging Pinecone vectors: {e}")
        # Continue to ensure DB is scrubbed even if Pinecone fails
    
    # 3. Delete from Database (CASCADE will handle chunks and health checks)
    supabase.table("sources").delete().eq("id", source_id).execute()
    
    # 4. Log the scrub
    AuditLogger.log(
        twin_id,
        "KNOWLEDGE_UPDATE",
        "DEEP_SCRUB_PERFORMED",
        metadata={"source_id": source_id, "filename": filename, "reason": reason}
    )
    
    return True
