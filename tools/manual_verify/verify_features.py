#!/usr/bin/env python3
"""
Automated Daily Feature Verification Script
Runs continuous checks on all features
Purpose: Identify what's working and what needs fixing
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

@dataclass
class FeatureStatus:
    name: str
    status: str  # WORKING, PARTIAL, NOT_WORKING, PENDING
    latency_ms: float = None
    error_rate: float = None
    last_tested: str = None
    issue: str = None
    solution: str = None

class FeatureVerifier:
    def __init__(self):
        self.results: List[FeatureStatus] = []
        self.timestamp = datetime.now().isoformat()
        
    def test_backend_health(self) -> FeatureStatus:
        """Test: GET /health endpoint"""
        try:
            import requests
            start = time.time()
            response = requests.get("http://localhost:8000/health", timeout=5)
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return FeatureStatus(
                    name="Backend Health",
                    status="WORKING",
                    latency_ms=latency,
                    error_rate=0.0,
                    last_tested=self.timestamp
                )
            else:
                return FeatureStatus(
                    name="Backend Health",
                    status="NOT_WORKING",
                    latency_ms=latency,
                    issue=f"HTTP {response.status_code}",
                    solution="Backend service not running"
                )
        except Exception as e:
            return FeatureStatus(
                name="Backend Health",
                status="NOT_WORKING",
                issue=str(e),
                solution="Start backend: python main.py"
            )
    
    def test_database_connection(self) -> FeatureStatus:
        """Test: Can connect to Supabase"""
        try:
            from modules.observability import supabase
            
            result = supabase.table("users").select("count", count="exact").execute()
            return FeatureStatus(
                name="Database Connection",
                status="WORKING",
                error_rate=0.0,
                last_tested=self.timestamp
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "avatar_url" in error_msg:
                return FeatureStatus(
                    name="Database Connection",
                    status="NOT_WORKING",
                    issue="avatar_url column missing",
                    solution="ALTER TABLE users ADD COLUMN avatar_url TEXT;"
                )
            else:
                return FeatureStatus(
                    name="Database Connection",
                    status="NOT_WORKING",
                    issue=str(e)[:100],
                    solution="Check Supabase connection string"
                )
    
    def test_avatar_url_column(self) -> FeatureStatus:
        """Test: avatar_url column exists"""
        try:
            from modules.observability import supabase
            
            # Try to query the column
            result = supabase.table("users").select("avatar_url").limit(1).execute()
            return FeatureStatus(
                name="avatar_url Column",
                status="WORKING",
                last_tested=self.timestamp
            )
        except Exception as e:
            if "column" in str(e).lower():
                return FeatureStatus(
                    name="avatar_url Column",
                    status="NOT_WORKING",
                    issue="Column missing",
                    solution="ALTER TABLE users ADD COLUMN avatar_url TEXT;",
                    error_rate=100.0
                )
            else:
                return FeatureStatus(
                    name="avatar_url Column",
                    status="PARTIAL",
                    issue=str(e)[:50]
                )
    
    def test_interview_sessions_table(self) -> FeatureStatus:
        """Test: interview_sessions table exists"""
        try:
            from modules.observability import supabase
            
            result = supabase.table("interview_sessions").select("*").limit(1).execute()
            return FeatureStatus(
                name="interview_sessions Table",
                status="WORKING",
                last_tested=self.timestamp
            )
        except Exception as e:
            if "relation" in str(e).lower() or "table" in str(e).lower():
                return FeatureStatus(
                    name="interview_sessions Table",
                    status="NOT_WORKING",
                    issue="Table missing",
                    solution="Apply migration: migration_interview_sessions.sql",
                    error_rate=100.0
                )
            else:
                return FeatureStatus(
                    name="interview_sessions Table",
                    status="PARTIAL"
                )
    
    def test_rpc_functions(self) -> FeatureStatus:
        """Test: RPC functions exist"""
        try:
            from modules.observability import supabase
            
            # Probe with a real twin when available to validate end-to-end execution.
            twin_rows = supabase.table("twins").select("id").limit(1).execute().data or []
            if not twin_rows:
                return FeatureStatus(
                    name="RPC Functions",
                    status="PARTIAL",
                    issue="RPC not validated: no twins available in this environment",
                )

            result = supabase.rpc("get_or_create_interview_session", {
                "t_id": twin_rows[0]["id"],
                "conv_id": None,
            }).execute()
            
            return FeatureStatus(
                name="RPC Functions",
                status="WORKING",
                last_tested=self.timestamp
            )
        except Exception as e:
            error_text = str(e).lower()
            if (
                "could not find the function" in error_text
                or "does not exist" in error_text
            ):
                return FeatureStatus(
                    name="RPC Functions",
                    status="NOT_WORKING",
                    issue="RPC functions missing",
                    solution="Apply migration: migration_interview_sessions.sql",
                    error_rate=100.0
                )
            if (
                "foreign key" in error_text
                or "violates row-level security" in error_text
                or "permission denied" in error_text
                or "invalid input syntax for type uuid" in error_text
            ):
                return FeatureStatus(
                    name="RPC Functions",
                    status="PARTIAL",
                    issue="RPC exists but probe data is not executable in current env",
                )
            else:
                # May exist but fail with test data
                return FeatureStatus(
                    name="RPC Functions",
                    status="PARTIAL",
                    issue="Exists but test failed"
                )
    
    def test_pinecone_connection(self) -> FeatureStatus:
        """Test: Pinecone connection works"""
        try:
            from modules.clients import get_pinecone_client
            from modules.embeddings import _resolve_target_dimension
            
            client = get_pinecone_client()
            index_name = os.getenv("PINECONE_INDEX_NAME", "unknown")
            index = client.Index(index_name)
            
            start = time.time()
            stats = index.describe_index_stats()
            latency = (time.time() - start) * 1000
            target_dim = _resolve_target_dimension() or 3072
            
            if stats.dimension == target_dim:
                return FeatureStatus(
                    name="Pinecone Connection",
                    status="WORKING",
                    latency_ms=latency,
                    error_rate=0.0,
                    last_tested=self.timestamp
                )
            else:
                return FeatureStatus(
                    name="Pinecone Connection",
                    status="NOT_WORKING",
                    issue=f"Dimension {stats.dimension}, expected {target_dim}",
                    solution="Align EMBEDDING_TARGET_DIMENSION / index dimension with active embedding provider"
                )
        except Exception as e:
            return FeatureStatus(
                name="Pinecone Connection",
                status="NOT_WORKING",
                issue=str(e)[:50],
                solution="Check Pinecone API key and index name"
            )
    
    def test_openai_connection(self) -> FeatureStatus:
        """Test: OpenAI API connection"""
        try:
            from modules.clients import get_openai_client
            
            client = get_openai_client()
            
            start = time.time()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            latency = (time.time() - start) * 1000
            
            if response.choices[0].message.content:
                return FeatureStatus(
                    name="OpenAI Connection",
                    status="WORKING",
                    latency_ms=latency,
                    error_rate=0.0,
                    last_tested=self.timestamp
                )
            else:
                return FeatureStatus(
                    name="OpenAI Connection",
                    status="NOT_WORKING",
                    issue="No response from OpenAI"
                )
        except Exception as e:
            return FeatureStatus(
                name="OpenAI Connection",
                status="NOT_WORKING",
                issue=str(e)[:50],
                solution="Check OpenAI API key"
            )
    
    def test_job_queue(self) -> FeatureStatus:
        """Test: Job queue is accessible"""
        try:
            from modules.observability import supabase
            
            result = supabase.table("jobs").select("*").limit(1).execute()
            return FeatureStatus(
                name="Job Queue",
                status="WORKING",
                last_tested=self.timestamp
            )
        except Exception as e:
            return FeatureStatus(
                name="Job Queue",
                status="NOT_WORKING",
                issue=str(e)[:50],
                solution="Check jobs table exists"
            )
    
    def test_auth_endpoint(self) -> FeatureStatus:
        """Test: /auth/sync-user endpoint"""
        try:
            import requests
            
            start = time.time()
            response = requests.post(
                "http://localhost:8000/auth/sync-user",
                headers={
                    "Authorization": "Bearer test-token",
                    "Content-Type": "application/json"
                },
                timeout=5
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return FeatureStatus(
                    name="Auth Endpoint",
                    status="WORKING",
                    latency_ms=latency,
                    error_rate=0.0,
                    last_tested=self.timestamp
                )
            elif response.status_code == 401:
                # Token issue is OK - endpoint exists
                return FeatureStatus(
                    name="Auth Endpoint",
                    status="WORKING",
                    latency_ms=latency,
                    error_rate=0.0,
                    last_tested=self.timestamp,
                    issue="Endpoint exists (got 401, expected with invalid token)"
                )
            elif "avatar_url" in response.text.lower():
                return FeatureStatus(
                    name="Auth Endpoint",
                    status="NOT_WORKING",
                    latency_ms=latency,
                    issue="avatar_url column missing",
                    solution="ALTER TABLE users ADD COLUMN avatar_url TEXT;",
                    error_rate=100.0
                )
            else:
                return FeatureStatus(
                    name="Auth Endpoint",
                    status="PARTIAL",
                    latency_ms=latency,
                    issue=response.text[:50]
                )
        except Exception as e:
            return FeatureStatus(
                name="Auth Endpoint",
                status="NOT_WORKING",
                issue=str(e)[:50],
                solution="Backend may not be running"
            )
    
    def run_all_tests(self) -> List[FeatureStatus]:
        """Run all verification tests"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}FEATURE VERIFICATION REPORT{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        print(f"Timestamp: {self.timestamp}\n")
        
        tests = [
            ("Backend Health", self.test_backend_health),
            ("Database Connection", self.test_database_connection),
            ("avatar_url Column", self.test_avatar_url_column),
            ("interview_sessions Table", self.test_interview_sessions_table),
            ("RPC Functions", self.test_rpc_functions),
            ("Pinecone", self.test_pinecone_connection),
            ("OpenAI", self.test_openai_connection),
            ("Job Queue", self.test_job_queue),
            ("Auth Endpoint", self.test_auth_endpoint),
        ]
        
        for name, test_func in tests:
            print(f"Testing {name}...", end=" ", flush=True)
            try:
                result = test_func()
                self.results.append(result)
                
                # Print status with color
                if result.status == "WORKING":
                    print(f"{GREEN}[OK] {result.status}{RESET}")
                elif result.status == "PARTIAL":
                    print(f"{YELLOW}[WARN] {result.status}{RESET}")
                else:
                    print(f"{RED}[FAIL] {result.status}{RESET}")
                
                # Print details if available
                if result.latency_ms:
                    print(f"   Latency: {result.latency_ms:.1f}ms")
                if result.issue:
                    print(f"   Issue: {result.issue}")
                if result.solution:
                    print(f"   Solution: {result.solution}")
            
            except Exception as e:
                print(f"{RED}[ERR] ERROR: {str(e)[:50]}{RESET}")
                self.results.append(FeatureStatus(
                    name=name,
                    status="ERROR",
                    issue=str(e)[:100]
                ))
        
        return self.results
    
    def print_summary(self):
        """Print summary report"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}SUMMARY{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        working = sum(1 for r in self.results if r.status == "WORKING")
        partial = sum(1 for r in self.results if r.status == "PARTIAL")
        not_working = sum(1 for r in self.results if r.status == "NOT_WORKING")
        errors = sum(1 for r in self.results if r.status == "ERROR")
        
        print(f"[OK] Working: {working}")
        print(f"[WARN] Partial: {partial}")
        print(f"[FAIL] Not Working: {not_working}")
        print(f"[ERR] Errors: {errors}")
        
        print(f"\n{BLUE}BLOCKERS DETECTED:{RESET}")
        blockers = [r for r in self.results if r.status == "NOT_WORKING"]
        if blockers:
            for i, blocker in enumerate(blockers, 1):
                print(f"\n{RED}{i}. {blocker.name}{RESET}")
                print(f"   Issue: {blocker.issue}")
                if blocker.solution:
                    print(f"   Solution: {blocker.solution}")
        else:
            print(f"{GREEN}No critical blockers!{RESET}")
    
    def save_report(self, filename: str = "feature_verification_report.json"):
        """Save report to file"""
        report = {
            "timestamp": self.timestamp,
            "features": [asdict(r) for r in self.results],
            "summary": {
                "working": sum(1 for r in self.results if r.status == "WORKING"),
                "partial": sum(1 for r in self.results if r.status == "PARTIAL"),
                "not_working": sum(1 for r in self.results if r.status == "NOT_WORKING"),
                "errors": sum(1 for r in self.results if r.status == "ERROR"),
            }
        }
        
        path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "eval",
            filename
        )
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[OK] Report saved to {path}")

def main():
    verifier = FeatureVerifier()
    verifier.run_all_tests()
    verifier.print_summary()
    verifier.save_report()

if __name__ == "__main__":
    main()
