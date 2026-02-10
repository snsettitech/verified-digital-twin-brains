"""
Dynamic CORS Middleware with Pattern Support

Supports:
- Exact origin matches
- Wildcard patterns (*.vercel.app)
- Logging of rejected origins for debugging
"""

import fnmatch
import os
from typing import List
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
import logging

logger = logging.getLogger(__name__)


class DynamicCORSMiddleware(CORSMiddleware):
    """
    Extended CORS middleware that supports wildcard patterns in origins.
    
    Example patterns:
    - "https://digitalbrains.vercel.app" (exact match)
    - "https://*.vercel.app" (matches any Vercel preview domain)
    - "http://localhost:*" (matches any localhost port)
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        allow_credentials: bool = False,
        allow_origin_regex: str = None,
        expose_headers: List[str] = None,
        max_age: int = 600,
        log_rejections: bool = True
    ):
        super().__init__(
            app=app,
            allow_origins=allow_origins or [],
            allow_methods=allow_methods,
            allow_headers=allow_headers,
            allow_credentials=allow_credentials,
            allow_origin_regex=allow_origin_regex,
            expose_headers=expose_headers,
            max_age=max_age
        )
        self.allow_origins_patterns = allow_origins or []
        self.log_rejections = log_rejections
    
    def is_allowed_origin(self, origin: str) -> bool:
        """Check if origin matches any allowed pattern."""
        if not origin:
            return False
            
        # Check exact matches first (fast path)
        if origin in self.allow_origins:
            return True
        
        # Check wildcard patterns
        for pattern in self.allow_origins_patterns:
            if '*' in pattern or '?' in pattern:
                if fnmatch.fnmatch(origin, pattern):
                    return True
        
        return False
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Intercept requests and log CORS rejections."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        origin = request.headers.get("origin", "")
        
        # Check if this is a CORS preflight or actual request with origin
        if origin and not self.is_allowed_origin(origin):
            if self.log_rejections:
                logger.warning(
                    f"CORS rejection: origin='{origin}' "
                    f"method={request.method} "
                    f"path={request.url.path} "
                    f"user_agent='{request.headers.get('user-agent', 'unknown')}'"
                )
        
        # Let parent class handle the actual CORS logic
        await super().__call__(scope, receive, send)


def get_allowed_origins() -> List[str]:
    """
    Parse ALLOWED_ORIGINS environment variable.
    Supports comma-separated list with wildcards.
    """
    origins_raw = os.getenv("ALLOWED_ORIGINS")
    
    if origins_raw:
        origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    else:
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    return origins


def create_cors_middleware(app: ASGIApp) -> ASGIApp:
    """Register dynamic CORS middleware on the app and return the app."""
    origins = get_allowed_origins()
    
    # Log what origins we're allowing
    logger.info(f"CORS allowed origins: {origins}")

    if hasattr(app, "add_middleware"):
        app.add_middleware(
            DynamicCORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["x-correlation-id"],
            log_rejections=os.getenv("CORS_LOG_REJECTIONS", "true").lower() == "true",
        )
        return app

    # Fallback for plain ASGI app instances without add_middleware.
    return DynamicCORSMiddleware(
        app=app,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-correlation-id"],
        log_rejections=os.getenv("CORS_LOG_REJECTIONS", "true").lower() == "true",
    )
