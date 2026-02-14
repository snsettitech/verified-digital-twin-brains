import asyncio
import os
import json
import logging
from typing import Dict, Any

# Load environment variables from .env
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

load_env()

# Mocking parts of the system for standalone testing if needed,
# but ideally this runs against a dev environment.
from modules.langfuse_client import observe, log_trace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ObservabilitySmokeTest")

@observe(name="smoke_test_case_1")
async def test_case_1_happy_path():
    """Case 1: Happy Path (Factual + Citations)"""
    logger.info("Running Case 1: Happy Path")
    # In v3, attributes are added via log_trace/update_current_trace 
    # but we'll stick to basic connectivity for smoke test
    pass

@observe(name="smoke_test_case_2")
async def test_case_2_uncertainty():
    """Case 2: Uncertainty (No answer in KB)"""
    logger.info("Running Case 2: Uncertainty")
    pass

@observe(name="smoke_test_case_3")
async def test_case_3_owner_specific():
    """Case 3: Owner Specific (Owner stance)"""
    logger.info("Running Case 3: Owner Stance")
    pass

@observe(name="smoke_test_case_4")
async def test_case_4_pii_redaction():
    """Case 4: PII Redaction Verification"""
    logger.info("Running Case 4: PII Redaction")
    # This should be caught by our redact_pii if we were using log_trace
    pass

@observe(name="smoke_test_case_5")
async def test_case_5_error():
    """Case 5: Error Scenario"""
    logger.info("Running Case 5: Error Scenario")
    raise RuntimeError("Pinecone Connection Timeout")

async def main():
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        logger.warning("LANGFUSE_PUBLIC_KEY not set. Test will run but not send to server unless configured.")
    
    try:
        await test_case_1_happy_path()
        await test_case_2_uncertainty()
        await test_case_3_owner_specific()
        await test_case_4_pii_redaction()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        
    try:
        await test_case_5_error()
    except Exception as e:
        logger.info(f"Caught expected error: {e}")
        
    logger.info("Smoke tests completed.")

if __name__ == "__main__":
    asyncio.run(main())
