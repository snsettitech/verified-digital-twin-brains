
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import time

from routers import (
    auth,
    chat,
    ingestion,
    youtube_preflight,
    twins,
    knowledge,
    sources,
    governance,
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
    owner_memory
)
from modules.specializations import get_specialization

app = FastAPI(title="Verified Digital Twin Brain API")

# Add CORS middleware
# Explicitly allow localhost:3000 if ALLOWED_ORIGINS is not set
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_raw:
    allowed_origins = allowed_origins_raw.split(",")
else:
    allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-correlation-id"],
)

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
app.include_router(ingestion.router)
app.include_router(youtube_preflight.router)
app.include_router(twins.router)

app.include_router(knowledge.router)
app.include_router(sources.router)
app.include_router(governance.router)
app.include_router(specializations.router)
app.include_router(observability.router)
app.include_router(cognitive.router)
app.include_router(graph.router)
app.include_router(metrics.router)
app.include_router(jobs.router)
app.include_router(til.router)
app.include_router(feedback.router)
app.include_router(audio.router)
ENHANCED_INGESTION_ENABLED = os.getenv("ENABLE_ENHANCED_INGESTION", "false").lower() == "true"
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



# Conditional VC Routes (only if explicitly enabled)
# VC routes are conditionally loaded to prevent VC files from interfering
# with vanilla flows. This is critical because:
# 1. VC routes should only be available when VC is actively used
# 2. VC imports/dependencies should not be loaded globally
# 3. This prevents VC-related startup errors from breaking vanilla deployments
VC_ROUTES_ENABLED = os.getenv("ENABLE_VC_ROUTES", "false").lower() == "true"
if VC_ROUTES_ENABLED:
    try:
        from api import vc_routes
        app.include_router(vc_routes.router, prefix="/api", tags=["vc"])
        print("[INFO] VC routes enabled (ENABLE_VC_ROUTES=true)")
    except ImportError as e:
        print(f"[WARN] VC routes not available (ImportError): {e}")
        print("   VC routes will be disabled. Set ENABLE_VC_ROUTES=false to suppress this warning.")

# ============================================================================
# P0 Deployment: Health Check Endpoint
# ============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for deployment readiness probes."""
    return {
        "status": "healthy",
        "service": "verified-digital-twin-brain-api",
        "version": "1.0.0"
    }

@app.get("/", tags=["health"])
async def root_health():
    """Fallback health check for platforms checking the root path."""
    return await health_check()

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
        print("  Supabase Dashboard → Settings → API → JWT Secret")
    
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
