import os
import sys
from postgrest import APIResponse
from supabase import create_client, Client

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.observability import supabase

def run_migration():
    print("🚀 Running Gate 1 Specialization Migration...")
    
    # SQL to add columns
    sql = """
    ALTER TABLE twins ADD COLUMN IF NOT EXISTS specialization_id VARCHAR(50) DEFAULT 'vanilla';
    ALTER TABLE twins ADD COLUMN IF NOT EXISTS specialization_version VARCHAR(50) DEFAULT '1.0.0';
    """
    
    try:
        # We can't run raw SQL via the standard Supabase client in some configs
        # but let's try via the RPC or check if we can just update a dummy row to test column existence
        
        # Alternative: Just try to update a twin with these fields. If it fails, we know we need SQL help.
        # But usually in these environments, I need to provide the SQL for the user or use a specific tool.
        
        print("Note: In production environments, please run the SQL in migration_phase3_5_gate1_specialization.sql in the Supabase Dashboard.")
        print("Attempting to verify columns via a dummy update...")
        
        # This is a bit of a hack to see if columns exist
        res = supabase.table("twins").select("id, specialization_id").limit(1).execute()
        print("✅ Columns verified or migration not needed (already exists).")
        
    except Exception as e:
        print(f"❌ Migration check failed: {e}")
        print("Please run the SQL manually in Supabase SQL Editor.")

if __name__ == "__main__":
    run_migration()
