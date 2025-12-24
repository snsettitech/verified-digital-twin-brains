import os
import sys
import json
import time
from dotenv import load_dotenv

# #region agent log
def log_debug(message, data=None, hypothesis_id="A"):
    log_entry = {
        "sessionId": "debug-session",
        "timestamp": int(time.time() * 1000),
        "location": "verify_setup.py",
        "message": message,
        "data": data or {},
        "hypothesisId": hypothesis_id
    }
    with open(r'c:\Users\saina\verified-digital-twin-brain\.cursor\debug.log', 'a') as f:
        f.write(json.dumps(log_entry) + "\n")
# #endregion

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.clients import get_openai_client, get_pinecone_index
from modules.observability import supabase

def verify_env():
    log_debug("Checking environment variables", {"cwd": os.getcwd()}, "A")
    print("--- Environment Verification ---")
    required_vars = [
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "PINECONE_INDEX_NAME",
        "SUPABASE_URL",
        "SUPABASE_KEY"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            print(f"❌ {var} is missing")
        else:
            print(f"✅ {var} is set")
            
    if missing:
        print("\nERR: Missing environment variables. Please check your .env file.")
        return False
    return True

def verify_openai():
    log_debug("Verifying OpenAI connectivity", hypothesis_id="C")
    print("\n--- OpenAI Connectivity ---")
    try:
        client = get_openai_client()
        client.models.list()
        log_debug("OpenAI success")
        print("✅ OpenAI client connected successfully")
        return True
    except Exception as e:
        log_debug("OpenAI failure", {"error": str(e)})
        print(f"❌ OpenAI connection failed: {str(e)}")
        return False

def verify_pinecone():
    print("\n--- Pinecone Connectivity ---")
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        print(f"✅ Pinecone index connected. Stats: {stats}")
        return True
    except Exception as e:
        print(f"❌ Pinecone connection failed: {str(e)}")
        return False

def verify_supabase():
    log_debug("Verifying Supabase connectivity", hypothesis_id="C")
    print("\n--- Supabase Connectivity ---")
    try:
        # Try to fetch one row from twins table
        res = supabase.table("twins").select("id").limit(1).execute()
        log_debug("Supabase success", {"data_count": len(res.data)})
        print("✅ Supabase connection successful")
        return True
    except Exception as e:
        log_debug("Supabase failure", {"error": str(e)})
        print(f"❌ Supabase connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    load_dotenv()
    
    success = True
    success &= verify_env()
    success &= verify_openai()
    success &= verify_pinecone()
    success &= verify_supabase()
    
    print("\n" + "="*30)
    if success:
        print("🎉 ALL SYSTEMS READY")
    else:
        print("⚠️ SOME SYSTEMS FAILED")
    print("="*30)
    
    sys.exit(0 if success else 1)
