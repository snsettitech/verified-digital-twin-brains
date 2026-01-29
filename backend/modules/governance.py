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
    def log(tenant_id: str, event_type: str, action: str, 
            twin_id: Optional[str] = None, 
            actor_id: Optional[str] = None, 
            metadata: Optional[Dict[str, Any]] = None):
        """
        Records an audit event in the database.
        """
        import os
        import inspect
        
        # HARDENED: Fail Loudly on missing tenant_id
        if not tenant_id:
            msg = f"AuditLogger.log called without tenant_id. Action: {action}"
            # Use same DEV_MODE check as auth_guard
            is_dev = os.getenv("DEV_MODE", "true").lower() == "true"
            
            if is_dev:
                raise ValueError(f"[DEV_MODE] {msg}")
            else:
                # Production: Structured error log with callsite info
                frame = inspect.currentframe().f_back
                callsite = f"{frame.f_code.co_filename}:{frame.f_lineno}"
                print(f"ERROR: AUDIT_FAILURE | {msg} | Callsite: {callsite}")
                # We don't crash prod to preserve availability, but we log loudly.
                return

        try:
            log_entry = {
                "tenant_id": tenant_id,
                "event_type": event_type,
                "action": action,
                "metadata": metadata or {}
            }
            
            if twin_id:
                log_entry["twin_id"] = twin_id
            
            if actor_id:
                log_entry["actor_id"] = actor_id
            
            supabase.table("audit_logs").insert(log_entry).execute()
        except Exception as e:
            print(f"CRITICAL: Audit logging DB failure: {e}")
            print(f"Audit Event Sync: tenant={tenant_id} twin={twin_id} | {event_type} | {action}")



def get_audit_logs(tenant_id: str, twin_id: Optional[str] = None, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetches audit logs filtered by tenant_id (REQUIRED) and optional twin_id."""
    query = supabase.table("audit_logs").select("*").eq("tenant_id", tenant_id)
    
    if twin_id:
        query = query.eq("twin_id", twin_id)
    if event_type:
        query = query.eq("event_type", event_type)
    
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data if response.data else []


def request_verification(twin_id: str, tenant_id: str, method: str = "MANUAL_REVIEW", metadata: Optional[Dict[str, Any]] = None) -> str:
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
    AuditLogger.log(
        tenant_id=tenant_id,
        twin_id=twin_id,
        event_type="CONFIGURATION_CHANGE",
        action="VERIFICATION_REQUESTED",
        metadata={"method": method}
    )
    
    return "pending"


def approve_verification(twin_id: str, tenant_id: str, verifier_id: str):
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
    
    AuditLogger.log(
        tenant_id=tenant_id,
        twin_id=twin_id,
        event_type="CONFIGURATION_CHANGE",
        action="VERIFICATION_APPROVED",
        actor_id=verifier_id
    )


def get_governance_policies(twin_id: str) -> List[Dict[str, Any]]:
    """Fetches active policies for a twin."""
    response = supabase.table("governance_policies").select("*").eq("twin_id", twin_id).eq("is_active", True).execute()
    return response.data if response.data else []

def create_governance_policy(tenant_id: str, twin_id: Optional[str], policy_type: str, name: str, content: str) -> Dict[str, Any]:
    """Creates a new governance policy scoped to tenant (and optionally twin)."""
    policy_data = {
        "tenant_id": tenant_id,
        "policy_type": policy_type,
        "name": name,
        "content": content
    }
    if twin_id:
        policy_data["twin_id"] = twin_id
        
    response = supabase.table("governance_policies").insert(policy_data).execute()
    
    AuditLogger.log(
        tenant_id=tenant_id,
        twin_id=twin_id,
        event_type="CONFIGURATION_CHANGE",
        action="POLICY_CREATED",
        metadata={"name": name, "type": policy_type}
    )
    return response.data[0] if response.data else {}


async def deep_scrub_source(source_id: str, tenant_id: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    """
    Permanently purges a source and its derived vectors.
    """
    # 1. Get source metadata and verify tenant association
    source_res = supabase.table("sources").select("twin_id, filename, twins(tenant_id)").eq("id", source_id).single().execute()
    if not source_res.data:
        raise ValueError("Source not found")
    
    twin_id = source_res.data["twin_id"]
    filename = source_res.data["filename"]
    twin_tenant_id = source_res.data.get("twins", {}).get("tenant_id")
    
    if twin_tenant_id != tenant_id:
        print(f"[SECURITY] Deep scrub attempt on cross-tenant source: {source_id}")
        raise ValueError("Source does not belong to your tenant")
    
    # 2. Delete from Pinecone
    from modules.clients import get_pinecone_index
    index = get_pinecone_index()
    try:
        index.delete(filter={"source_id": {"$eq": source_id}}, namespace=twin_id)
    except Exception as e:
        print(f"Error purging Pinecone vectors: {e}")
    
    # 3. Delete from Database
    supabase.table("sources").delete().eq("id", source_id).execute()
    
    # 4. Log the scrub (Scoping to both tenant and twin)
    AuditLogger.log(
        tenant_id=tenant_id,
        twin_id=twin_id,
        event_type="KNOWLEDGE_UPDATE", 
        action="DEEP_SCRUB_PERFORMED", 
        actor_id=actor_id,
        metadata={"source_id": source_id, "filename": filename, "reason": reason}
    )
    
    return True

