from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from routers import (
    auth,
    chat,
    ingestion,
    twins,
    actions,
    knowledge,
    governance,
    escalations,
    specializations,
    observability,
    cognitive,
    graph
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
app.include_router(twins.router)
app.include_router(actions.router)
app.include_router(knowledge.router)
app.include_router(governance.router)
app.include_router(escalations.router)
app.include_router(specializations.router)
app.include_router(observability.router)
app.include_router(cognitive.router)
app.include_router(graph.router)

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
        
        # Show feature flags
        features = spec.get_feature_flags()
        vc_features = [k for k, v in features.items() if v and k not in ['actions_engine', 'verified_qna', 'access_groups', 'governance', 'escalations', 'share_links', 'analytics']]
        if vc_features:
            print(f"   VC Features Enabled: {', '.join(vc_features)}\n")
        
        uvicorn.run(app, host=host, port=port)
