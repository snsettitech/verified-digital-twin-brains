"""
Session Management Module

Handles creation and management of user sessions (anonymous and authenticated).
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from modules.observability import supabase
import uuid


def create_session(
    twin_id: str,
    group_id: Optional[str],
    session_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> str:
    """
    Create a new session.
    session_type: 'anonymous' or 'authenticated'
    Returns session ID
    """
    # Sessions expire after 24 hours of inactivity
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    session_data = {
        "id": str(uuid.uuid4()),
        "twin_id": twin_id,
        "group_id": group_id,
        "session_type": session_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": datetime.utcnow().isoformat(),
        "last_active_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat()
    }
    
    response = supabase.table("sessions").insert(session_data).execute()
    
    if not response.data:
        raise ValueError("Failed to create session")
    
    return response.data[0]["id"]


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a session by ID.
    Returns None if session doesn't exist or is expired.
    """
    try:
        response = supabase.table("sessions").select("*").eq("id", session_id).single().execute()
        
        if not response.data:
            return None
        
        session = response.data
        
        # Check if expired
        expires_at_str = session.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if datetime.now(expires_at.tzinfo) > expires_at:
                return None  # Expired
        
        return session
    except Exception as e:
        print(f"Error retrieving session: {e}")
        return None


def update_session_activity(session_id: str) -> None:
    """
    Update the last_active_at timestamp for a session.
    Also extends expiration if needed.
    """
    try:
        # Extend expiration by 24 hours from now
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        supabase.table("sessions").update({
            "last_active_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat()
        }).eq("id", session_id).execute()
    except Exception as e:
        print(f"Error updating session activity: {e}")
        # Don't fail on activity tracking errors


def cleanup_expired_sessions() -> int:
    """
    Remove expired sessions from the database.
    Returns number of sessions deleted.
    """
    try:
        now = datetime.utcnow().isoformat()
        
        # Get expired sessions
        response = supabase.table("sessions").select("id").lt("expires_at", now).execute()
        
        if not response.data:
            return 0
        
        expired_ids = [s["id"] for s in response.data]
        
        # Delete expired sessions
        for session_id in expired_ids:
            supabase.table("sessions").delete().eq("id", session_id).execute()
        
        return len(expired_ids)
    except Exception as e:
        print(f"Error cleaning up expired sessions: {e}")
        return 0
