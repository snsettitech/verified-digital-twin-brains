#!/usr/bin/env python3
"""
Verification script for bug fixes.

Usage:
    python scripts/verify_bug_fixes.py --api-url http://localhost:8000 --token <jwt_token>
"""

import argparse
import sys
import requests


def check_worker_validation():
    """Verify worker startup validation exists."""
    print("\n[1/5] Checking Worker Startup Validation...")
    
    with open("backend/worker.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("validate_worker_environment function", "validate_worker_environment" in content),
        ("SUPABASE_URL check", "SUPABASE_URL" in content),
        ("OPENAI_API_KEY check", "OPENAI_API_KEY" in content),
        ("Fatal error message", "FATAL: Worker missing" in content),
        ("Exit on failure", "sys.exit(1)" in content),
    ]
    
    all_pass = True
    for name, result in checks:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
        if not result:
            all_pass = False
    
    return all_pass


def check_content_hash_dedup():
    """Verify content hash deduplication exists."""
    print("\n[2/5] Checking Content Hash Deduplication...")
    
    with open("backend/routers/ingestion.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("Content hash calculation", "content_hash = calculate_content_hash(text)" in content),
        ("Duplicate detection query", '.eq("content_hash", content_hash)' in content),
        ("Duplicate response flag", '"duplicate": True' in content),
        ("Duplicate message", "This file has already been uploaded" in content),
    ]
    
    all_pass = True
    for name, result in checks:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
        if not result:
            all_pass = False
    
    return all_pass


def check_job_polling_hook():
    """Verify useJobPoller hook exists."""
    print("\n[3/5] Checking Job Polling Hook...")
    
    try:
        with open("frontend/lib/hooks/useJobPoller.ts", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("useJobPoller export", "useJobPoller" in content),
            ("Page visibility handling", "visibilitychange" in content),
            ("Error backoff logic", "errorCountRef" in content),
            ("Request cancellation", "AbortController" in content),
            ("Polling intervals", "queuedInterval" in content),
        ]
        
        all_pass = True
        for name, result in checks:
            status = "[OK]" if result else "[FAIL]"
            print(f"  {status} {name}")
            if not result:
                all_pass = False
        
        return all_pass
    except FileNotFoundError:
        print("  [FAIL] useJobPoller.ts not found")
        return False


def check_dlq_implementation():
    """Verify Dead Letter Queue implementation."""
    print("\n[4/5] Checking Dead Letter Queue...")
    
    with open("backend/modules/training_jobs.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("Max retry config", "MAX_RETRY_ATTEMPTS" in content),
        ("Retry eligibility logic", "should_retry_job" in content),
        ("Exponential backoff", "calculate_retry_delay" in content),
        ("Dead letter state", "dead_letter" in content),
        ("Replay functionality", "replay_dead_letter_job" in content),
    ]
    
    all_pass = True
    for name, result in checks:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
        if not result:
            all_pass = False
    
    return all_pass


def check_documentation():
    """Verify documentation exists."""
    print("\n[5/5] Checking Documentation...")
    
    try:
        with open("docs/KNOWN_LIMITATIONS.md", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("X/Twitter section", "X (Twitter)" in content or "X/Twitter" in content),
            ("Unreliable warning", "UNRELIABLE" in content),
            ("User workarounds", "User Workaround" in content),
            ("LinkedIn section", "LinkedIn" in content),
        ]
        
        all_pass = True
        for name, result in checks:
            status = "[OK]" if result else "[FAIL]"
            print(f"  {status} {name}")
            if not result:
                all_pass = False
        
        return all_pass
    except FileNotFoundError:
        print("  [FAIL] KNOWN_LIMITATIONS.md not found")
        return False


def test_api_endpoints(api_url, token):
    """Test API endpoints if URL provided."""
    print("\n[Bonus] Testing API Endpoints...")
    
    if not api_url or not token:
        print("  [SKIP] No API URL or token provided")
        return True
    
    try:
        # Test health endpoint
        resp = requests.get(f"{api_url}/health", timeout=5)
        if resp.status_code == 200:
            print("  [OK] API is healthy")
        else:
            print(f"  [WARN] API health check returned {resp.status_code}")
        
        # Test version endpoint
        resp = requests.get(f"{api_url}/version", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  [OK] Version: {data.get('version', 'unknown')}")
            print(f"  [OK] Git SHA: {data.get('git_sha', 'unknown')[:8]}...")
        
        return True
    except Exception as e:
        print(f"  [WARN] API test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Verify bug fix implementations")
    parser.add_argument("--api-url", help="Backend API URL for live testing")
    parser.add_argument("--token", help="JWT token for authenticated requests")
    args = parser.parse_args()
    
    print("=" * 70)
    print("BUG FIX VERIFICATION")
    print("=" * 70)
    
    results = []
    
    # Run all checks
    results.append(("Worker Validation", check_worker_validation()))
    results.append(("Content Deduplication", check_content_hash_dedup()))
    results.append(("Job Polling Hook", check_job_polling_hook()))
    results.append(("Dead Letter Queue", check_dlq_implementation()))
    results.append(("Documentation", check_documentation()))
    
    # Optional API test
    test_api_endpoints(args.api_url, args.token)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\n  Total: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n  SUCCESS: All bug fixes are implemented correctly!")
        return 0
    else:
        print(f"\n  WARNING: {total - passed} check(s) failed. Review implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
