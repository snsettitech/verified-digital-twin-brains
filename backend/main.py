from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from routers import (
    auth,
    chat,
    ingestion,
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
    reasoning
)
from modules.specializations import get_specialization

app = FastAPI(title="Verified Digital Twin Brain API")

# Add CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(ingestion.router)
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
app.include_router(enhanced_ingestion.router)
app.include_router(reasoning.router)

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
        print("✅ VC routes enabled (ENABLE_VC_ROUTES=true)")
    except ImportError as e:
        print(f"⚠️  VC routes not available (ImportError): {e}")
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
        exit(1)

# Run validation on import (when app starts)
validate_required_env_vars()

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
        banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🧠  VERIFIED DIGITAL TWIN BRAIN                            ║
║                                                              ║
║   Specialization: {spec.display_name:<40} ║
║   Mode:           {spec.name:<40} ║
║   Port:           {port:<40} ║
║                                                              ║
║   API:      http://localhost:{port:<27} ║
║   Docs:     http://localhost:{port}/docs{' ' * 22} ║
║   Config:   http://localhost:{port}/config/specialization{' ' * 5} ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        print(banner)
        
        uvicorn.run(app, host=host, port=port)
