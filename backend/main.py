
from fastapi import FastAPI, Request
import os
import sys
import time

# Import our dynamic CORS middleware
from modules.cors_middleware import create_cors_middleware, get_allowed_origins

from routers import (
    auth,
    chat,
    training_sessions,
    persona_specs,
    decision_capture,
    ingestion,
    ingestion_realtime,
    youtube_preflight,
    twins,
    actions,
    knowledge,
    sources,
    governance,
    escalations,
    specializations,
    observability,
    cognitive,
    graph,
    metrics,
    jobs,
    til,
    feedback,
    audio,
    enhanced_ingestion,

    reasoning,
    interview,
    api_keys,  # Tenant-scoped API keys management
    debug_retrieval, # New debug router
    verify,
    owner_memory,
    retrieval_delphi,
)
from modules.specializations import get_specialization

# ISSUE-003: Feature flag definitions (moved here for proper ordering)
# Realtime ingestion is now enabled by default. Set ENABLE_REALTIME_INGESTION=false to disable.
REALTIME_INGESTION_ENABLED = os.getenv("ENABLE_REALTIME_INGESTION", "true").lower() == "true"
# Enhanced ingestion remains opt-in until further validation
ENHANCED_INGESTION_ENABLED = os.getenv("ENABLE_ENHANCED_INGESTION", "false").lower() == "true"
# Delphi retrieval is now enabled by default. Set ENABLE_DELPHI_RETRIEVAL=false to disable.
DELPHI_RETRIEVAL_ENABLED = os.getenv("ENABLE_DELPHI_RETRIEVAL", "true").lower() == "true"
# VC routes remain opt-in
VC_ROUTES_ENABLED = os.getenv("ENABLE_VC_ROUTES", "false").lower() == "true"

def print_feature_flag_summary():
    """Print enabled/disabled feature summary for observability."""
    print("-" * 60)
    print("Feature Flag Status:")
    print(f"  Realtime Ingestion: {'ENABLED' if REALTIME_INGESTION_ENABLED else 'DISABLED'}")
    print(f"  Enhanced Ingestion: {'ENABLED' if ENHANCED_INGESTION_ENABLED else 'DISABLED'}")
    print(f"  Delphi Retrieval:   {'ENABLED' if DELPHI_RETRIEVAL_ENABLED else 'DISABLED'}")
    print(f"  VC Routes:          {'ENABLED' if VC_ROUTES_ENABLED else 'DISABLED'}")
    print("-" * 60)
    sys.stdout.flush()

app = FastAPI(title="Verified Digital Twin Brain API")

# Add Dynamic CORS middleware with wildcard pattern support
# Supports *.vercel.app for preview deployments
app = create_cors_middleware(app)

# Request tracing middleware for deployment debugging
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    correlation_id = request.headers.get("x-correlation-id") or request.headers.get("x-request-id")
    response = await call_next(request)
    duration = time.time() - start_time
    if correlation_id:
        response.headers["x-correlation-id"] = correlation_id
    # Use standard print for immediate visibility in Render logs
    print(f"DEBUG: {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s) corr={correlation_id or 'none'} UA: {request.headers.get('user-agent')}")
    sys.stdout.flush()
    return response

# Include Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(training_sessions.router)
app.include_router(persona_specs.router)
app.include_router(decision_capture.router)
app.include_router(ingestion.router)
# Use feature flags defined at top of file
if REALTIME_INGESTION_ENABLED:
    app.include_router(ingestion_realtime.router)
    print("[INFO] Realtime ingestion routes enabled (ENABLE_REALTIME_INGESTION=true)")
else:
    print("[INFO] Realtime ingestion routes disabled (ENABLE_REALTIME_INGESTION=false)")
app.include_router(youtube_preflight.router)
app.include_router(twins.router)

app.include_router(actions.router)
app.include_router(knowledge.router)
app.include_router(sources.router)
app.include_router(governance.router)
app.include_router(escalations.router)
app.include_router(specializations.router)
app.include_router(observability.router)
app.include_router(cognitive.router)
app.include_router(graph.router)
app.include_router(metrics.router)
app.include_router(jobs.router)
app.include_router(til.router)
app.include_router(feedback.router)
app.include_router(audio.router)
if ENHANCED_INGESTION_ENABLED:
    app.include_router(enhanced_ingestion.router)
    print("[INFO] Enhanced ingestion routes enabled (ENABLE_ENHANCED_INGESTION=true)")
else:
    print("[INFO] Enhanced ingestion routes disabled (ENABLE_ENHANCED_INGESTION=false)")

app.include_router(reasoning.router)
app.include_router(interview.router)
app.include_router(api_keys.router)
app.include_router(debug_retrieval.router)
app.include_router(verify.router)
app.include_router(owner_memory.router)

if DELPHI_RETRIEVAL_ENABLED:
    app.include_router(retrieval_delphi.router)
    print("[INFO] Delphi retrieval routes enabled (ENABLE_DELPHI_RETRIEVAL=true)")
else:
    print("[INFO] Delphi retrieval routes disabled (ENABLE_DELPHI_RETRIEVAL=false)")



# Conditional VC Routes (only if explicitly enabled)
# VC routes are conditionally loaded to prevent VC files from interfering
# with vanilla flows. This is critical because:
# 1. VC routes should only be available when VC is actively used
# 2. VC imports/dependencies should not be loaded globally
# 3. This prevents VC-related startup errors from breaking vanilla deployments
if VC_ROUTES_ENABLED:
    try:
        from api import vc_routes
        app.include_router(vc_routes.router, prefix="/api", tags=["vc"])
        print("[INFO] VC routes enabled (ENABLE_VC_ROUTES=true)")
    except ImportError as e:
        print(f"[WARN] VC routes not available (ImportError): {e}")
        print("   VC routes will be disabled. Set ENABLE_VC_ROUTES=false to suppress this warning.")

# Print feature flag summary after all routers loaded
print_feature_flag_summary()

# ============================================================================
# P0 Deployment: Health Check Endpoint
# ============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for deployment readiness probes."""
    # Include ingestion diagnostics schema availability for fast debug in production.
    try:
        from modules.ingestion_diagnostics import diagnostics_schema_status

        diag_ok, _diag_err = diagnostics_schema_status()
    except Exception:
        diag_ok = False

    return {
        "status": "healthy",
        "service": "verified-digital-twin-brain-api",
        "version": "1.0.0",
        "ingestion_diagnostics_schema": {
            "available": bool(diag_ok),
        },
    }

@app.get("/", tags=["health"])
async def root_health():
    """Fallback health check for platforms checking the root path."""
    return await health_check()

# ============================================================================
# P0 Deployment: Version Endpoint for Deployment Verification
# ============================================================================

import subprocess

@app.get("/version", tags=["health"])
async def version():
    """
    Return build version info for deployment verification.
    
    This endpoint helps verify which git commit is running in production,
    preventing the "changes not reflecting" debugging nightmare.
    """
    git_sha = os.getenv("GIT_SHA", "unknown")
    
    # Try to get git SHA from filesystem if not in env (development)
    if git_sha == "unknown":
        try:
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            pass
    
    build_time = os.getenv("BUILD_TIME", "unknown")
    environment = "production" if os.getenv("DEV_MODE", "true").lower() == "false" else "development"
    
    return {
        "git_sha": git_sha,
        "build_time": build_time,
        "environment": environment,
        "service": "verified-digital-twin-brain-api",
        "version": "1.0.0"
    }


@app.get("/cors-test", tags=["health"])
async def cors_test(request: Request):
    """
    CORS test endpoint for debugging cross-origin issues.
    
    Returns information about the request origin and whether it's allowed.
    """
    # Never echo sensitive request headers in production.
    dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
    origin = request.headers.get("origin", "no-origin")
    allowed_origins = get_allowed_origins()
    
    # Check if origin matches any pattern
    is_allowed = False
    matched_pattern = None
    
    for pattern in allowed_origins:
        if '*' in pattern or '?' in pattern:
            import fnmatch
            if fnmatch.fnmatch(origin, pattern):
                is_allowed = True
                matched_pattern = pattern
                break
        elif origin == pattern:
            is_allowed = True
            matched_pattern = pattern
            break
    
    payload = {
        "origin": origin,
        "is_allowed": is_allowed,
        "matched_pattern": matched_pattern,
        "allowed_origins": allowed_origins,
        "timestamp": time.time()
    }

    if dev_mode:
        safe_allowlist = {
            "origin",
            "referer",
            "user-agent",
            "x-forwarded-for",
            "x-forwarded-proto",
            "x-real-ip",
            "sec-fetch-site",
            "sec-fetch-mode",
            "sec-fetch-dest",
            "sec-fetch-user",
        }
        payload["headers"] = {
            k: v for k, v in dict(request.headers).items() if k.lower() in safe_allowlist
        }

    return payload


# ============================================================================
# P0 Deployment: Startup Validation
# ============================================================================

def validate_required_env_vars():
    """Validate required environment variables at startup."""
    required_vars = [
        "SUPABASE_URL",
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "PINECONE_INDEX_NAME"
    ]
    
    # At least one Supabase key is required
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if not supabase_key:
        missing.append("SUPABASE_KEY or SUPABASE_SERVICE_KEY")
    
    # JWT_SECRET should be set in production
    jwt_secret = os.getenv("JWT_SECRET", "")
    dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
    if not dev_mode and (not jwt_secret or jwt_secret == "your_jwt_secret" or "secret" in jwt_secret.lower()):
        print("WARNING: JWT_SECRET is not properly configured for production!")
        print("  Set JWT_SECRET to your Supabase project's JWT secret from:")
        print("  Supabase Dashboard -> Settings -> API -> JWT Secret")
    
    if missing:
        print("=" * 60)
        print("FATAL: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("=" * 60)
        sys.stdout.flush()
        exit(1)

def print_startup_banner():
    """Print the startup banner with environment info."""
    port = os.getenv("PORT", "8000")
    spec = get_specialization()
    print("Starting Verified Digital Twin Brain...")
    print(f"Specialization: {spec.display_name}")
    print(f"Mode:           {spec.name}")
    print(f"Port:           {port}")
    print("Status:         INITIALIZING...")
    sys.stdout.flush()

# Run validation on import (when app starts)
print_startup_banner()
validate_required_env_vars()
print(f"FastAPI initialization complete. Bound to PORT: {os.getenv('PORT', '8000')}")
sys.stdout.flush()

@app.on_event("startup")
async def startup_event():
    print("READY: Event loop running, accepting traffic.")
    print(f"DEBUG: Listening for Probes on: http://0.0.0.0:{os.getenv('PORT', '8000')}")
    sys.stdout.flush()


# Startup Logic
import socket

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Get active specialization
    spec = get_specialization()
    
    if is_port_in_use(port):
        print(f"ERROR: Port {port} is already in use.")
        print(f"Please kill the process using this port or set a different port via the PORT environment variable.")
    else:
        # Startup banner with specialization info
        print("-" * 60)
        print("Verified Digital Twin Brain API")
        print(f"Specialization: {spec.display_name}")
        print(f"Mode:           {spec.name}")
        print(f"Port:           {port}")
        print(f"API Docs:       http://localhost:{port}/docs")
        print("-" * 60)
        
        uvicorn.run(app, host=host, port=port)
