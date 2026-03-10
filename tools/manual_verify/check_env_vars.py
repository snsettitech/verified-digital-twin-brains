#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Environment Variables Checker
Checks if all required environment variables are set
"""
import os
from pathlib import Path

def check_backend_env():
    """Check backend environment variables"""
    backend_env = Path("backend/.env")
    
    print("=" * 60)
    print("BACKEND ENVIRONMENT VARIABLES CHECK")
    print("=" * 60)
    
    if not backend_env.exists():
        print("[X] backend/.env file NOT FOUND")
        print("   Create it from backend/.env.example (if exists)")
        return False
    
    print("[OK] backend/.env file exists")
    
    # Read .env file
    env_vars = {}
    with open(backend_env, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    # Required variables
    required = {
        "SUPABASE_URL": "Supabase project URL",
        "SUPABASE_KEY": "Supabase anon key",
        "SUPABASE_SERVICE_KEY": "Supabase service_role key",
        "JWT_SECRET": "JWT secret from Supabase Dashboard",
        "OPENAI_API_KEY": "OpenAI API key",
        "PINECONE_API_KEY": "Pinecone API key",
        "PINECONE_INDEX_NAME": "Pinecone index name",
        "ALLOWED_ORIGINS": "CORS allowed origins",
    }
    
    # Optional but recommended
    recommended = {
        "DEV_MODE": "Should be 'false' in production",
    }
    
    all_good = True
    
    print("\nRequired Variables:")
    for var, desc in required.items():
        value = env_vars.get(var, "")
        if value:
            # Mask sensitive values
            if "KEY" in var or "SECRET" in var:
                display = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display = value
            print(f"  [OK] {var}: {display}")
        else:
            print(f"  [X] {var}: MISSING - {desc}")
            all_good = False
    
    print("\nRecommended Variables:")
    for var, desc in recommended.items():
        value = env_vars.get(var, "")
        if value:
            print(f"  [OK] {var}: {value}")
        else:
            print(f"  [!] {var}: NOT SET - {desc}")
    
    return all_good

def check_frontend_env():
    """Check frontend environment variables"""
    frontend_env = Path("frontend/.env.local")
    
    print("\n" + "=" * 60)
    print("FRONTEND ENVIRONMENT VARIABLES CHECK")
    print("=" * 60)
    
    if not frontend_env.exists():
        print("[X] frontend/.env.local file NOT FOUND")
        print("   Create it from frontend/.env.local.example (if exists)")
        return False
    
    print("[OK] frontend/.env.local file exists")
    
    # Read .env.local file
    env_vars = {}
    with open(frontend_env, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    # Required variables
    required = {
        "NEXT_PUBLIC_SUPABASE_URL": "Supabase project URL",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": "Supabase anon key",
        "NEXT_PUBLIC_BACKEND_URL": "Backend API URL",
    }
    
    all_good = True
    
    print("\nRequired Variables:")
    for var, desc in required.items():
        value = env_vars.get(var, "")
        if value:
            # Mask sensitive values
            if "KEY" in var:
                display = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display = value
            print(f"  [OK] {var}: {display}")
        else:
            print(f"  [X] {var}: MISSING - {desc}")
            all_good = False
    
    return all_good

def main():
    print("\nChecking Environment Variables...\n")
    
    backend_ok = check_backend_env()
    frontend_ok = check_frontend_env()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if backend_ok and frontend_ok:
        print("[OK] All required environment variables are set!")
        print("\nNext steps:")
        print("  1. Test backend: cd backend && python main.py")
        print("  2. Test frontend: cd frontend && npm run dev")
        print("  3. Check health: curl http://localhost:8000/health")
    else:
        print("[X] Some environment variables are missing")
        print("\nAction required:")
        if not backend_ok:
            print("  - Fix backend/.env file")
        if not frontend_ok:
            print("  - Fix frontend/.env.local file")
        print("\nSee DEPLOYMENT_READINESS.md for required values")
    
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
