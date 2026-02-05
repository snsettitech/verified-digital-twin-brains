# Use centralized Supabase client from observability module
from modules.observability import supabase

async def create_escalation(message_id: str):
    response = supabase.table("escalations").insert({
        "message_id": message_id,
        "status": "open"
    }).execute()
    return response.data

async def resolve_escalation(escalation_id: str, owner_answer: str, owner_id: str):
    """
    Resolve an escalation with owner's answer.
    
    Args:
        escalation_id: ID of the escalation to resolve
        owner_answer: The owner's answer/reply
        owner_id: ID of the owner resolving the escalation
    
    Returns:
        dict: Updated escalation data
    """
    # Add reply
    supabase.table("escalation_replies").insert({
        "escalation_id": escalation_id,
        "owner_id": owner_id,
        "content": owner_answer
    }).execute()
    
    # Mark escalation as resolved
    # Note: Only setting status since resolved_by and resolved_at may not exist in all database schemas
    result = supabase.table("escalations").update({
        "status": "resolved"
    }).eq("id", escalation_id).execute()
    
    # Return the updated escalation data
    if result.data:
        return result.data[0]
    else:
        # Fallback: fetch the escalation
        fetch_result = supabase.table("escalations").select("*").eq("id", escalation_id).single().execute()
        return fetch_result.data if fetch_result.data else {}
