"""
Rate Limiting Module

Implements sliding window rate limiting for API keys and sessions.
"""
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timedelta
from modules.observability import supabase


def get_window_start(timestamp: datetime, limit_type: str) -> datetime:
    """
    Calculate the window start time for a given limit type.
    For requests_per_hour: rounds down to the hour
    For requests_per_day: rounds down to midnight UTC
    """
    if limit_type == "requests_per_hour":
        # Round down to the hour
        return timestamp.replace(minute=0, second=0, microsecond=0)
    elif limit_type == "requests_per_day":
        # Round down to midnight UTC
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Unknown limit_type: {limit_type}")


def check_rate_limit(
    tracking_key: str,
    tracking_type: str,
    limit_type: str,
    limit_value: int
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if a request should be allowed based on rate limits.
    Returns: (allowed: bool, status_dict)
    status_dict contains: remaining, reset_at, limit_value
    """
    now = datetime.utcnow()
    window_start = get_window_start(now, limit_type)
    
    try:
        # Get current count for this window
        response = supabase.table("rate_limit_tracking").select("*").eq(
            "tracking_key", tracking_key
        ).eq("tracking_type", tracking_type).eq("limit_type", limit_type).eq(
            "window_start", window_start.isoformat()
        ).execute()
        
        current_count = 0
        if response.data and len(response.data) > 0:
            current_count = response.data[0].get("request_count", 0)
        
        # Check if limit exceeded
        allowed = current_count < limit_value
        remaining = max(0, limit_value - current_count)
        
        # Calculate reset time (next window start)
        if limit_type == "requests_per_hour":
            reset_at = window_start + timedelta(hours=1)
        elif limit_type == "requests_per_day":
            reset_at = window_start + timedelta(days=1)
        else:
            reset_at = None
        
        return allowed, {
            "remaining": remaining,
            "reset_at": reset_at.isoformat() if reset_at else None,
            "limit_value": limit_value,
            "current_count": current_count
        }
    except Exception as e:
        print(f"Error checking rate limit: {e}")
        # On error, allow the request (fail open for availability)
        return True, {
            "remaining": limit_value,
            "reset_at": None,
            "limit_value": limit_value,
            "current_count": 0
        }


def record_request(
    tracking_key: str,
    tracking_type: str,
    limit_type: str
) -> None:
    """
    Record a request in the rate limit tracking table.
    """
    try:
        now = datetime.utcnow()
        window_start = get_window_start(now, limit_type)
        window_start_str = window_start.isoformat()
        
        # Try to get existing record
        response = supabase.table("rate_limit_tracking").select("*").eq(
            "tracking_key", tracking_key
        ).eq("tracking_type", tracking_type).eq("limit_type", limit_type).eq(
            "window_start", window_start_str
        ).execute()
        
        if response.data and len(response.data) > 0:
            # Update existing record
            current_count = response.data[0].get("request_count", 0)
            supabase.table("rate_limit_tracking").update({
                "request_count": current_count + 1
            }).eq("id", response.data[0]["id"]).execute()
        else:
            # Create new record
            supabase.table("rate_limit_tracking").insert({
                "tracking_key": tracking_key,
                "tracking_type": tracking_type,
                "limit_type": limit_type,
                "window_start": window_start_str,
                "request_count": 1
            }).execute()
    except Exception as e:
        print(f"Error recording request: {e}")
        # Don't fail on rate limit tracking errors


def get_rate_limit_status(
    tracking_key: str,
    tracking_type: str
) -> Dict[str, Any]:
    """
    Get current rate limit status for a tracking key.
    Returns usage stats for all limit types.
    """
    try:
        # Get all tracking records for this key
        response = supabase.table("rate_limit_tracking").select("*").eq(
            "tracking_key", tracking_key
        ).eq("tracking_type", tracking_type).execute()
        
        status = {}
        now = datetime.utcnow()
        
        for record in (response.data or []):
            limit_type = record["limit_type"]
            window_start_str = record["window_start"]
            window_start = datetime.fromisoformat(window_start_str.replace('Z', '+00:00'))
            
            # Only include current window
            current_window_start = get_window_start(now, limit_type)
            if window_start == current_window_start:
                status[limit_type] = {
                    "current_count": record.get("request_count", 0),
                    "window_start": window_start_str
                }
        
        return status
    except Exception as e:
        print(f"Error getting rate limit status: {e}")
        return {}


def cleanup_old_windows() -> int:
    """
    Remove rate limit tracking records older than 2 days.
    Returns number of records deleted.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=2)
        cutoff_str = cutoff.isoformat()
        
        # Delete old windows
        response = supabase.table("rate_limit_tracking").select("id").lt("window_start", cutoff_str).execute()
        
        if not response.data:
            return 0
        
        deleted_count = 0
        for record in response.data:
            supabase.table("rate_limit_tracking").delete().eq("id", record["id"]).execute()
            deleted_count += 1
        
        return deleted_count
    except Exception as e:
        print(f"Error cleaning up old rate limit windows: {e}")
        return 0
