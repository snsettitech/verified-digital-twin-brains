#!/usr/bin/env python3
"""
Quick diagnostic script to check worker and job queue status.
Run this to verify your setup before deploying the worker.
"""
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

load_dotenv()

def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_SERVICE_KEY',
        'OPENAI_API_KEY',
        'PINECONE_API_KEY',
        'PINECONE_INDEX_NAME'
    ]
    
    print("[CHECK] Checking Environment Variables...")
    missing = []
    for var in required_vars:
        if os.getenv(var):
            print(f"  [OK] {var}")
        else:
            print(f"  [MISSING] {var}")
            missing.append(var)
    
    worker_vars = {
        'WORKER_ENABLED': os.getenv('WORKER_ENABLED', 'false'),
        'WORKER_POLL_INTERVAL': os.getenv('WORKER_POLL_INTERVAL', '5')
    }
    
    print("\n[CHECK] Worker Configuration:")
    for var, value in worker_vars.items():
        print(f"  {var}: {value}")
    
    return len(missing) == 0

def check_job_queue():
    """Check job queue status."""
    try:
        from modules.job_queue import get_queue_length
        from modules.observability import supabase
        
        print("\n[CHECK] Checking Job Queue...")
        
        # Check queue length
        queue_length = get_queue_length()
        print(f"  Queue length: {queue_length}")
        
        # Check jobs in database
        try:
            jobs_result = supabase.table("jobs").select("id, status, job_type, created_at").eq("status", "queued").limit(10).execute()
            queued_jobs = jobs_result.data if jobs_result.data else []
            
            print(f"  Queued jobs in database: {len(queued_jobs)}")
            if queued_jobs:
                print("\n  Recent queued jobs:")
                for job in queued_jobs[:5]:
                    print(f"    - {job['id'][:8]}... ({job['job_type']}) created at {job['created_at']}")
        except Exception as e:
            print(f"  [WARN] Could not check database jobs: {e}")
        
        # Check training_jobs table (legacy)
        try:
            training_jobs_result = supabase.table("training_jobs").select("id, status, job_type, created_at").eq("status", "queued").limit(10).execute()
            training_jobs = training_jobs_result.data if training_jobs_result.data else []
            
            if training_jobs:
                print(f"\n  Queued training_jobs: {len(training_jobs)}")
                print("  ⚠️  Note: training_jobs table is legacy, jobs should be in 'jobs' table")
        except Exception as e:
            print(f"  ⚠️  Could not check training_jobs table: {e}")
        
        return True
    except Exception as e:
        print(f"  [ERROR] Error checking job queue: {e}")
        return False

def check_sources():
    """Check sources that need processing."""
    try:
        from modules.observability import supabase
        
        print("\n[CHECK] Checking Sources Status...")
        
        # Check approved sources
        approved_result = supabase.table("sources").select("id, filename, staging_status, status, chunk_count").eq("staging_status", "approved").limit(10).execute()
        approved_sources = approved_result.data if approved_result.data else []
        
        print(f"  Approved sources (waiting for indexing): {len(approved_sources)}")
        if approved_sources:
            print("\n  Sources needing processing:")
            for source in approved_sources[:5]:
                chunk_info = f"{source.get('chunk_count', 0)} chunks" if source.get('chunk_count') else "not indexed"
                print(f"    - {source.get('filename', 'unknown')[:50]}... ({chunk_info})")
        
        # Check live sources
        live_result = supabase.table("sources").select("id, filename, chunk_count").eq("staging_status", "live").limit(5).execute()
        live_sources = live_result.data if live_result.data else []
        
        print(f"\n  Live sources (indexed): {len(live_sources)}")
        if live_sources:
                print("  [OK] These sources are indexed and searchable")
        
        return True
    except Exception as e:
        print(f"  [ERROR] Error checking sources: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("Worker Status Diagnostic Tool")
    print("=" * 60)
    
    env_ok = check_environment()
    queue_ok = check_job_queue()
    sources_ok = check_sources()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if env_ok:
        print("[OK] Environment variables configured")
    else:
        print("[ERROR] Missing environment variables - check .env file")
    
    if queue_ok:
        print("[OK] Job queue accessible")
    else:
        print("[ERROR] Job queue check failed")
    
    if sources_ok:
        print("[OK] Sources check completed")
    else:
        print("[ERROR] Sources check failed")
    
    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("1. If environment variables are missing, add them to .env")
    print("2. If you have approved sources, deploy the worker to process them")
    print("3. Check Render dashboard for worker service status")
    print("4. View worker logs to see job processing")
    print("\nFor detailed setup instructions, see:")
    print("  docs/ops/WORKER_SETUP_GUIDE.md")

if __name__ == "__main__":
    main()

