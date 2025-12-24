import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Load .env from backend directory
env_path = os.path.join(os.getcwd(), 'backend', '.env')
load_dotenv(env_path)

def check_phase6_status():
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    anon_key = os.getenv("SUPABASE_KEY")
    
    # Logic matching modules/observability.py
    key = service_key
    if not key or "your_supabase_service_role_key" in key:
        key = anon_key
        key_type = "ANON"
    else:
        key_type = "SERVICE_ROLE"

    if not url or not key or "your_supabase" in key:
        print(f"❌ Error: Missing or placeholder Supabase credentials in {env_path}")
        print(f"URL: {url}")
        print(f"Key Type Detected: {key_type}")
        return False
        
    try:
        supabase: Client = create_client(url, key)
    except Exception as e:
        print(f"❌ Failed to initialize Supabase client: {e}")
        return False
    
    print(f"Checking Phase 6 status using {key_type} key...")
    
    results = {
        "training_jobs": False,
        "ingestion_logs": False,
        "content_health_checks": False,
        "sources_columns": False
    }
    
    # Check tables
    for table in ["training_jobs", "ingestion_logs", "content_health_checks"]:
        try:
            supabase.table(table).select("id").limit(1).execute()
            print(f"✅ Table '{table}' exists")
            results[table] = True
        except Exception as e:
            if "401" in str(e):
                print(f"❌ Auth Error checking '{table}': {e}")
                return False
            print(f"❌ Table '{table}' missing or error: {e}")

    # Check columns in sources
    try:
        supabase.table("sources").select("staging_status").limit(1).execute()
        print("✅ Column 'staging_status' in 'sources' exists")
        results["sources_columns"] = True
    except Exception as e:
        print(f"❌ Column 'staging_status' missing in 'sources' (likely migration not run): {e}")

    return all(results.values())

if __name__ == "__main__":
    if check_phase6_status():
        print("\n✨ Phase 6 Mind Ops Layer is READY and Verified.")
    else:
        print("\n⚠️ Phase 6 Mind Ops Layer is INCOMPLETE.")
        print("Please ensure you have:")
        print("1. Applied the SQL migration from PHASE_6_MIGRATION_GUIDE.md")
        print("2. Verified your SUPABASE_URL and keys in backend/.env match your project.")
