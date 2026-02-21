"""
Comprehensive System Audit

Checks all backend-frontend connections, database integrations, and identifies issues.

Usage:
    cd backend
    python scripts/comprehensive_system_audit.py
"""

import os
import sys
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class CheckResult:
    name: str
    status: str  # 'pass', 'fail', 'warning', 'skip'
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None


class SystemAuditor:
    """Comprehensive system auditor for backend-frontend connections"""
    
    def __init__(self):
        self.results: List[CheckResult] = []
        self.start_time = datetime.now()
    
    def add_result(self, result: CheckResult):
        self.results.append(result)
    
    async def check_environment_variables(self) -> CheckResult:
        """Check critical environment variables"""
        name = "Environment Variables"
        required_vars = [
            'SUPABASE_URL',
            'SUPABASE_SERVICE_KEY',
            'PINECONE_API_KEY',
            'OPENAI_API_KEY',
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            return CheckResult(
                name=name,
                status='fail',
                message=f"Missing required environment variables: {', '.join(missing)}",
                details={'missing': missing}
            )
        
        # Check optional but recommended vars
        optional_vars = [
            'LANGFUSE_SECRET_KEY',
            'LANGFUSE_PUBLIC_KEY',
            'SENTRY_DSN',
        ]
        missing_optional = [v for v in optional_vars if not os.getenv(v)]
        
        return CheckResult(
            name=name,
            status='pass',
            message=f"All required environment variables set. Optional missing: {len(missing_optional)}",
            details={'optional_missing': missing_optional}
        )
    
    async def check_supabase_connection(self) -> CheckResult:
        """Check Supabase database connection"""
        name = "Supabase Connection"
        try:
            from modules.observability import supabase
            
            # Try a simple query
            result = supabase.table("twins").select("count", count="exact").limit(1).execute()
            
            return CheckResult(
                name=name,
                status='pass',
                message="Supabase connection successful",
                details={'count_result': result.count if hasattr(result, 'count') else 'N/A'}
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"Supabase connection failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_pinecone_connection(self) -> CheckResult:
        """Check Pinecone vector database connection"""
        name = "Pinecone Connection"
        try:
            from modules.clients import get_pinecone_client, get_pinecone_index
            
            pc = get_pinecone_client()
            index = get_pinecone_index()
            
            # Get index stats
            stats = index.describe_index_stats()
            
            return CheckResult(
                name=name,
                status='pass',
                message=f"Pinecone connection successful",
                details={
                    'total_vectors': stats.total_vector_count if hasattr(stats, 'total_vector_count') else 'N/A',
                    'dimension': stats.dimension if hasattr(stats, 'dimension') else 'N/A',
                }
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"Pinecone connection failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_openai_connection(self) -> CheckResult:
        """Check OpenAI API connection"""
        name = "OpenAI Connection"
        try:
            from modules.clients import get_openai_client
            
            client = get_openai_client()
            
            # Try a simple embedding request
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input="test"
            )
            
            return CheckResult(
                name=name,
                status='pass',
                message="OpenAI API connection successful",
                details={'embedding_dimensions': len(response.data[0].embedding)}
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"OpenAI connection failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_langfuse_connection(self) -> CheckResult:
        """Check Langfuse observability connection"""
        name = "Langfuse Connection"
        try:
            from modules.langfuse_client import get_langfuse_client
            
            client = get_langfuse_client()
            if client:
                return CheckResult(
                    name=name,
                    status='pass',
                    message="Langfuse client initialized",
                    details={'host': os.getenv('LANGFUSE_HOST', 'not_set')}
                )
            else:
                return CheckResult(
                    name=name,
                    status='warning',
                    message="Langfuse client not initialized (may be disabled)",
                )
        except Exception as e:
            return CheckResult(
                name=name,
                status='warning',
                message=f"Langfuse check failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_5layer_persona_integration(self) -> CheckResult:
        """Check 5-Layer Persona Model integration"""
        name = "5-Layer Persona Integration"
        try:
            from modules.persona_spec_v2 import PersonaSpecV2
            from modules.persona_decision_engine import PersonaDecisionEngine
            from modules.persona_agent_integration import PersonaAgentIntegration
            
            # Create a test spec
            spec = PersonaSpecV2(
                version="2.0.0",
                name="Test Spec"
            )
            
            engine = PersonaDecisionEngine(spec)
            
            # Check feature flag
            from modules.persona_spec_store_v2 import PERSONA_5LAYER_ENABLED
            
            return CheckResult(
                name=name,
                status='pass',
                message=f"5-Layer Persona Model loaded. Feature flag: {PERSONA_5LAYER_ENABLED}",
                details={
                    'feature_flag': PERSONA_5LAYER_ENABLED,
                    'spec_version': spec.version,
                    'engine_initialized': True
                }
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"5-Layer Persona integration failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_database_tables(self) -> CheckResult:
        """Check critical database tables exist"""
        name = "Database Tables"
        try:
            from modules.observability import supabase
            
            required_tables = [
                'twins',
                'sources',
                'chunks',
                'conversations',
                'messages',
                'persona_specs',
            ]
            
            missing_tables = []
            for table in required_tables:
                try:
                    result = supabase.table(table).select("count", count="exact").limit(1).execute()
                except Exception:
                    missing_tables.append(table)
            
            if missing_tables:
                return CheckResult(
                    name=name,
                    status='fail',
                    message=f"Missing tables: {', '.join(missing_tables)}",
                    details={'missing': missing_tables}
                )
            
            return CheckResult(
                name=name,
                status='pass',
                message=f"All {len(required_tables)} required tables exist",
                details={'tables': required_tables}
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"Database table check failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_retrieval_pipeline(self) -> CheckResult:
        """Check retrieval pipeline components"""
        name = "Retrieval Pipeline"
        try:
            from modules.retrieval import retrieve_context, retrieve_context_vectors
            from modules.embeddings import get_embedding, get_embeddings_async
            
            return CheckResult(
                name=name,
                status='pass',
                message="Retrieval pipeline components loaded",
                details={
                    'retrievers': ['retrieve_context', 'retrieve_context_vectors'],
                    'embedding_functions': ['get_embedding', 'get_embeddings_async'],
                    'embedding_provider': os.getenv('EMBEDDING_PROVIDER', 'openai')
                }
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"Retrieval pipeline check failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_agent_components(self) -> CheckResult:
        """Check LangGraph agent components"""
        name = "Agent Components"
        try:
            from modules.agent import router_node, planner_node, realizer_node, TwinState
            
            return CheckResult(
                name=name,
                status='pass',
                message="LangGraph agent components loaded",
                details={
                    'nodes': ['router_node', 'planner_node', 'realizer_node'],
                    'state_type': 'TwinState'
                }
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"Agent component check failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def check_memory_system(self) -> CheckResult:
        """Check memory system components"""
        name = "Memory System"
        try:
            from modules.owner_memory_store import list_owner_memories
            from modules.mem0_client import get_memory_provider
            
            return CheckResult(
                name=name,
                status='pass',
                message="Memory system components loaded",
                details={
                    'owner_memory': 'list_owner_memories',
                    'memory_provider': 'get_memory_provider'
                }
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status='fail',
                message=f"Memory system check failed: {str(e)}",
                details={'error': str(e)}
            )
    
    async def run_all_checks(self):
        """Run all system checks"""
        import time
        
        checks = [
            self.check_environment_variables,
            self.check_supabase_connection,
            self.check_pinecone_connection,
            self.check_openai_connection,
            self.check_langfuse_connection,
            self.check_5layer_persona_integration,
            self.check_database_tables,
            self.check_retrieval_pipeline,
            self.check_agent_components,
            self.check_memory_system,
        ]
        
        for check_func in checks:
            start = time.time()
            try:
                result = await check_func()
                result.duration_ms = (time.time() - start) * 1000
            except Exception as e:
                result = CheckResult(
                    name=check_func.__name__,
                    status='fail',
                    message=f"Check crashed: {str(e)}",
                    duration_ms=(time.time() - start) * 1000
                )
            self.add_result(result)
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate audit report"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == 'pass')
        failed = sum(1 for r in self.results if r.status == 'fail')
        warnings = sum(1 for r in self.results if r.status == 'warning')
        
        duration = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'timestamp': self.start_time.isoformat(),
            'duration_seconds': duration,
            'summary': {
                'total_checks': total,
                'passed': passed,
                'failed': failed,
                'warnings': warnings,
                'success_rate': f"{(passed/total*100):.1f}%" if total > 0 else "N/A"
            },
            'results': [asdict(r) for r in self.results],
            'critical_issues': [
                asdict(r) for r in self.results 
                if r.status == 'fail'
            ],
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on findings"""
        recommendations = []
        
        # Check which specific checks failed
        failed_checks = {r.name: r for r in self.results if r.status == 'fail'}
        
        # Environment variables
        if "Environment Variables" in failed_checks:
            # Check if connections still work (using fallbacks)
            if "Supabase Connection" not in failed_checks and \
               "Pinecone Connection" not in failed_checks and \
               "OpenAI Connection" not in failed_checks:
                recommendations.append("INFO: Environment variables not set but connections working via fallbacks. Set explicit vars for production.")
            else:
                recommendations.append("CRITICAL: Set missing environment variables in .env file - connections failing")
        
        # Connection failures
        if "Supabase Connection" in failed_checks:
            recommendations.append("CRITICAL: Fix Supabase connection - database is required for all operations")
        if "Pinecone Connection" in failed_checks:
            recommendations.append("HIGH: Fix Pinecone connection - vector search will not work")
        if "OpenAI Connection" in failed_checks:
            recommendations.append("HIGH: Fix OpenAI connection - embeddings and LLM calls will fail")
        
        # Component failures
        if "Retrieval Pipeline" in failed_checks:
            recommendations.append("HIGH: Fix retrieval pipeline - document search will not work")
        if "Memory System" in failed_checks:
            recommendations.append("MEDIUM: Fix memory system - owner memory features unavailable")
        if "5-Layer Persona Integration" in failed_checks:
            recommendations.append("MEDIUM: Fix 5-Layer Persona integration - new persona system unavailable")
        if "Agent Components" in failed_checks:
            recommendations.append("CRITICAL: Fix agent components - chat functionality broken")
        
        if not recommendations:
            recommendations.append("All checks passed! System is healthy.")
        
        return recommendations


def print_report(report: Dict[str, Any]):
    """Print formatted report to console"""
    print("\n" + "="*80)
    print("COMPREHENSIVE SYSTEM AUDIT REPORT")
    print("="*80)
    print(f"\nTimestamp: {report['timestamp']}")
    print(f"Duration: {report['duration_seconds']:.2f}s")
    
    print("\n" + "-"*80)
    print("SUMMARY")
    print("-"*80)
    summary = report['summary']
    print(f"Total Checks: {summary['total_checks']}")
    print(f"Passed: {summary['passed']} [OK]")
    print(f"Failed: {summary['failed']} [FAIL]")
    print(f"Warnings: {summary['warnings']} [WARN]")
    print(f"Success Rate: {summary['success_rate']}")
    
    print("\n" + "-"*80)
    print("DETAILED RESULTS")
    print("-"*80)
    
    for result in report['results']:
        status_icon = {
            'pass': '[OK]',
            'fail': '[FAIL]',
            'warning': '[WARN]',
            'skip': '[SKIP]'
        }.get(result['status'], '[?]')
        
        print(f"\n{status_icon} {result['name']}")
        print(f"   Status: {result['status'].upper()}")
        print(f"   Message: {result['message']}")
        if result.get('duration_ms'):
            print(f"   Duration: {result['duration_ms']:.2f}ms")
        if result.get('details'):
            print(f"   Details: {json.dumps(result['details'], indent=2)[:200]}")
    
    print("\n" + "-"*80)
    print("RECOMMENDATIONS")
    print("-"*80)
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"{i}. {rec}")
    
    print("\n" + "="*80)


async def main():
    """Main entry point"""
    print("Starting Comprehensive System Audit...")
    print("This may take 10-30 seconds depending on network latency.\n")
    
    auditor = SystemAuditor()
    await auditor.run_all_checks()
    
    report = auditor.generate_report()
    print_report(report)
    
    # Save report to file
    report_file = f"system_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to: {report_file}")
    
    # Exit with error code if critical failures
    if report['summary']['failed'] > 0:
        print("\n[!] AUDIT COMPLETED WITH FAILURES")
        return 1
    else:
        print("\n[OK] AUDIT COMPLETED SUCCESSFULLY")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
