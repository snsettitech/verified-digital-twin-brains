from fastapi import Header, HTTPException, Depends, Request
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
from modules.api_keys import validate_api_key, validate_domain
from modules.sessions import create_session

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET", "secret")
ALGORITHM = "HS256"
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"  # Default to true for local development

# Multi-tenant dev tokens for testing tenant isolation
DEV_TOKENS = {
    "development_token": {
        "user_id": "b415a7a9-c8f8-43b3-8738-a0062a90c016",
        "tenant_id": "986f270e-2d5c-4f88-ad88-7d2a15ea8ab1",
        "role": "owner",
        "allowed_twins": ["eeeed554-9180-4229-a9af-0f8dd2c69e9b"]
    },
    "tenant_b_dev_token": {
        "user_id": "user-b-id-0000-0000-0000",
        "tenant_id": "tenant-b-id-0000-0000-0000",
        "role": "owner",
        "allowed_twins": []  # Tenant B has no twins - for testing isolation
    }
}

def get_current_user(
    request: Request,
    authorization: str = Header(None),
    x_twin_api_key: str = Header(None),
    origin: str = Header(None),
    referer: str = Header(None)
):
    # 1. API Key check (for public widgets)
    if x_twin_api_key:
        # Validate API key
        key_info = validate_api_key(x_twin_api_key)
        if not key_info:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Domain validation
        domain_source = origin or referer or ""
        allowed_domains = key_info.get("allowed_domains", [])
        
        # Skip domain validation in dev mode for backward compatibility
        if not DEV_MODE and not validate_domain(domain_source, allowed_domains):
            raise HTTPException(status_code=403, detail="Domain not allowed for this API key")
        
        # Extract IP address and user agent for session
        ip_address = None
        user_agent = None
        try:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        except:
            pass  # Request might not have client info
        
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
            "user_id": None,  # Anonymous user
            "tenant_id": None,  # No tenant for anonymous
            "role": "visitor",
            "twin_id": key_info["twin_id"],
            "group_id": key_info.get("group_id"),
            "session_id": session_id,
            "api_key_id": key_info["id"]
        }

    # 2. Development bypass with multi-tenant support
    if DEV_MODE and authorization:
        token = authorization.replace("Bearer ", "")
        if token in DEV_TOKENS:
            token_info = DEV_TOKENS[token]
            return {
                "user_id": token_info["user_id"],
                "tenant_id": token_info["tenant_id"],
                "role": token_info["role"],
                "allowed_twins": token_info.get("allowed_twins", [])
            }

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        if user_id is None or tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"user_id": user_id, "tenant_id": tenant_id, "role": payload.get("role")}
    except (JWTError, IndexError):
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def verify_owner(user=Depends(get_current_user)):
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user
