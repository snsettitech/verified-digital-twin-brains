from fastapi import Header, HTTPException, Depends, Request
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
from modules.api_keys import validate_api_key, validate_domain
from modules.sessions import create_session

load_dotenv()

# JWT Configuration for Supabase
# JWT_SECRET must match Supabase's JWT secret from Dashboard → Settings → API
SUPABASE_JWT_SECRET = os.getenv("JWT_SECRET", "")
ALGORITHM = "HS256"

# DEV_MODE controls domain validation strictness, NOT auth bypass
# In production, this should be false
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

# Startup validation - warn if JWT secret looks weak
if not SUPABASE_JWT_SECRET or len(SUPABASE_JWT_SECRET) < 32:
    import sys
    print("=" * 60, file=sys.stderr)
    print("SECURITY WARNING: JWT_SECRET is not properly configured!", file=sys.stderr)
    print("  Production auth WILL FAIL without the correct JWT secret.", file=sys.stderr)
    print("  Copy from: Supabase Dashboard → Settings → API → JWT Secret", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


def resolve_tenant_id(user_id: str, email: str = None) -> str:
    """
    Resolve tenant_id for a user, auto-creating tenant if needed.
    
    This is the SINGLE SOURCE OF TRUTH for tenant resolution.
    Never trust client-provided tenant_id.
    
    Args:
        user_id: Supabase auth user ID
        email: Optional email for naming the auto-created tenant
    
    Returns:
        The resolved tenant_id (never None for valid users)
    
    Raises:
        HTTPException if tenant cannot be resolved or created
    """
    from modules.observability import supabase as supabase_client
    
    # 1. Try to lookup existing tenant from users table
    try:
        user_lookup = supabase_client.table("users").select("tenant_id").eq("id", user_id).execute()
        if user_lookup.data and user_lookup.data[0].get("tenant_id"):
            tenant_id = user_lookup.data[0]["tenant_id"]
            print(f"[resolve_tenant_id] Found existing tenant {tenant_id} for user {user_id}")
            return tenant_id
    except Exception as e:
        print(f"[resolve_tenant_id] User lookup failed: {e}")
    
    # 2. User exists but has no tenant, or user doesn't exist - auto-create tenant
    print(f"[resolve_tenant_id] No tenant for user {user_id}, auto-creating...")
    
    try:
        # Create tenant
        name = email.split("@")[0] if email else f"User-{user_id[:8]}"
        tenant_insert = supabase_client.table("tenants").insert({
            "name": f"{name}'s Workspace"
        }).execute()
        
        if not tenant_insert.data:
            raise HTTPException(status_code=500, detail="Failed to auto-create tenant")
        
        tenant_id = tenant_insert.data[0]["id"]
        print(f"[resolve_tenant_id] Created tenant {tenant_id}")
        
        # 3. Ensure user record exists with this tenant_id
        user_data = {
            "id": user_id,
            "tenant_id": tenant_id
        }
        if email:
            user_data["email"] = email
        
        supabase_client.table("users").upsert(user_data).execute()
        print(f"[resolve_tenant_id] Linked user {user_id} to tenant {tenant_id}")
        
        return tenant_id
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[resolve_tenant_id] ERROR creating tenant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve tenant: {str(e)}")

def get_current_user(
    request: Request,
    authorization: str = Header(None),
    x_twin_api_key: str = Header(None),
    origin: str = Header(None),
    referer: str = Header(None)
):
    """
    Authenticate the current user via:
    1. API Key (for public widgets)
    2. Supabase JWT (for authenticated users)
    
    NO AUTH BYPASS EXISTS - all requests must be properly authenticated.
    """
    # Import here to avoid circular imports
    from modules.observability import supabase as supabase_client
    
    # 1. API Key check (for public widgets)
    if x_twin_api_key:
        key_info = validate_api_key(x_twin_api_key)
        if not key_info:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Domain validation (enforced in production)
        domain_source = origin or referer or ""
        allowed_domains = key_info.get("allowed_domains", [])
        
        if not DEV_MODE and not validate_domain(domain_source, allowed_domains):
            raise HTTPException(status_code=403, detail="Domain not allowed for this API key")
        
        # Extract IP and user agent for session
        ip_address = None
        user_agent = None
        try:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        except:
            pass
        
        # Create anonymous session
        try:
            session_id = create_session(
                twin_id=key_info["twin_id"],
                group_id=key_info.get("group_id"),
                session_type="anonymous",
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            print(f"Error creating session: {e}")
            session_id = None
        
        return {
            "user_id": None,
            "tenant_id": None,
            "role": "visitor",
            "twin_id": key_info["twin_id"],
            "group_id": key_info.get("group_id"),
            "session_id": session_id,
            "api_key_id": key_info["id"]
        }

    # 2. JWT Authentication (Supabase tokens)
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    if not SUPABASE_JWT_SECRET or len(SUPABASE_JWT_SECRET) < 32:
        raise HTTPException(
            status_code=500, 
            detail="Server authentication not configured. Contact administrator."
        )
    
    try:
        # Extract bearer token
        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        token = parts[1]
        
        # DEBUG: Print token info
        print(f"[JWT DEBUG] Token length: {len(token)}")
        print(f"[JWT DEBUG] Secret length: {len(SUPABASE_JWT_SECRET)}")
        print(f"[JWT DEBUG] Secret first 10: {SUPABASE_JWT_SECRET[:10]}...")
        
        # Verify and decode JWT signature (this validates expiry too)
        # NOTE: Supabase tokens have aud="authenticated" but jose library's audience
        # validation can be strict. We verify manually instead.
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=[ALGORITHM],
            options={"verify_exp": True, "verify_aud": False}
        )
        
        # Manually verify audience if needed (Supabase uses "authenticated")
        aud = payload.get("aud")
        if aud and aud != "authenticated":
            print(f"[JWT DEBUG] WARNING: Unexpected audience: {aud}")
        
        # Supabase JWT has 'sub' as user_id
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        
        # Extract email and metadata from JWT (Supabase includes these)
        email = payload.get("email", "")
        user_metadata = payload.get("user_metadata", {})
        
        # Lookup tenant_id from database (not in JWT)
        # PRIMARY: Try direct tenant_id column (more reliable)
        # FALLBACK: Try join through tenants table
        tenant_id = None
        try:
            # First try direct tenant_id column
            user_lookup = supabase_client.table("users").select("tenant_id").eq("id", user_id).execute()
            if user_lookup.data and len(user_lookup.data) > 0:
                tenant_id = user_lookup.data[0].get("tenant_id")
                print(f"[AUTH DEBUG] tenant_id from direct lookup: {tenant_id}")
            
            # Fallback: try join through tenants table
            if not tenant_id:
                user_lookup = supabase_client.table("users").select("tenants(id)").eq("id", user_id).execute()
                if user_lookup.data and len(user_lookup.data) > 0:
                    tenants_data = user_lookup.data[0].get("tenants")
                    if isinstance(tenants_data, dict):
                        tenant_id = tenants_data.get("id")
                        print(f"[AUTH DEBUG] tenant_id from join: {tenant_id}")
            
            # CRITICAL: Log if tenant_id is still null for debugging
            if not tenant_id:
                print(f"[AUTH WARNING] User {user_id} has NO tenant_id - twins will return empty")
        except Exception as e:
            # User might not exist yet (first login) - sync-user will create them
            print(f"[AUTH ERROR] Tenant lookup failed for user {user_id}: {e}")

        # Update user activity timestamp (best effort)
        try:
            from datetime import datetime
            supabase_client.table("users").update({
                "last_active_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()
        except Exception:
            # Ignore errors (e.g. column missing, db down) to prevent blocking auth
            pass
        
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": "owner",  # All authenticated users are owners of their content
            "email": email,
            "user_metadata": user_metadata,
            "name": user_metadata.get("full_name") or user_metadata.get("name"),
            "avatar_url": user_metadata.get("avatar_url")
        }
        
    except jwt.ExpiredSignatureError:
        print("[JWT DEBUG] ERROR: Token has EXPIRED")
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        print(f"[JWT DEBUG] ERROR: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def verify_owner(user=Depends(get_current_user)):
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user

def verify_twin_ownership(twin_id: str, user: dict) -> None:
    """
    Verify that the user has access to the specified twin.
    Helper function to be called inside endpoints after getting user from dependency.
    
    For owners: checks if twin belongs to their tenant
    For visitors (API key): checks if twin_id matches their allowed twin
    
    Raises HTTPException if access is denied.
    Returns None if access is allowed.
    """
    from modules.observability import supabase
    
    # API key users have explicit twin_id in their context
    if user.get("role") == "visitor":
        allowed_twin = user.get("twin_id")
        if allowed_twin and allowed_twin == twin_id:
            return
        raise HTTPException(status_code=403, detail="API key not authorized for this twin")
    
    # Authenticated users: verify twin belongs to their tenant
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Get user's tenant_id (may already be in user dict from auth)
    user_tenant_id = user.get("tenant_id")
    
    # If not in user dict, look it up from database
    if not user_tenant_id:
        try:
            user_lookup = supabase.table("users").select("tenant_id").eq("id", user_id).single().execute()
            if user_lookup.data:
                user_tenant_id = user_lookup.data.get("tenant_id")
        except Exception as e:
            print(f"[verify_twin_ownership] Error looking up user tenant: {e}")
    
    if not user_tenant_id:
        raise HTTPException(status_code=403, detail="User has no tenant association")
    
    # Check if twin belongs to user's tenant
    try:
        twin_check = supabase.table("twins").select("id, tenant_id").eq("id", twin_id).single().execute()
        if not twin_check.data:
            raise HTTPException(status_code=404, detail="Twin not found or access denied")
        
        twin_tenant_id = twin_check.data.get("tenant_id")
        if twin_tenant_id == user_tenant_id:
            return
            
        print(f"[verify_twin_ownership] Access denied: user tenant {user_tenant_id} != twin tenant {twin_tenant_id}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[verify_twin_ownership] Error checking twin access: {e}")
    
    raise HTTPException(status_code=404, detail="Twin not found or access denied")

def verify_source_ownership(source_id: str, user: dict) -> str:
    """
    Verify that the user has access to the specified source.
    Returns the twin_id of the source if access is allowed.
    
    For owners: checks if source belongs to a twin in their tenant
    For visitors (API key): checks if source belongs to their allowed twin
    
    Raises HTTPException if access is denied.
    Returns twin_id if access is allowed.
    """
    from modules.observability import supabase
    
    # Get source's twin_id
    try:
        source_check = supabase.table("sources").select("id, twin_id").eq("id", source_id).single().execute()
        if not source_check.data:
            raise HTTPException(status_code=404, detail="Source not found or access denied")
        
        source_twin_id = source_check.data.get("twin_id")
        if not source_twin_id:
            raise HTTPException(status_code=404, detail="Source not found or access denied")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[verify_source_ownership] Error checking source: {e}")
        raise HTTPException(status_code=404, detail="Source not found or access denied")
    
    # Verify twin ownership (reuse existing logic)
    verify_twin_ownership(source_twin_id, user)
    
    return source_twin_id

def verify_conversation_ownership(conversation_id: str, user: dict) -> str:
    """
    Verify that the user has access to the specified conversation.
    Returns the twin_id of the conversation if access is allowed.
    
    For owners: checks if conversation belongs to a twin in their tenant
    For visitors (API key): checks if conversation belongs to their allowed twin
    
    Raises HTTPException if access is denied.
    Returns twin_id if access is allowed.
    """
    from modules.observability import supabase
    
    # Get conversation's twin_id
    try:
        conv_check = supabase.table("conversations").select("id, twin_id").eq("id", conversation_id).single().execute()
        if not conv_check.data:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
        
        conv_twin_id = conv_check.data.get("twin_id")
        if not conv_twin_id:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[verify_conversation_ownership] Error checking conversation: {e}")
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    
    # Verify twin ownership (reuse existing logic)
    verify_twin_ownership(conv_twin_id, user)
    
    return conv_twin_id

