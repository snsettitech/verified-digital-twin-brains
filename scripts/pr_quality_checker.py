#!/usr/bin/env python3
"""
Automated PR Quality Checker
Validates PR against project standards before review
"""

import os
import re
import sys
import json
import subprocess
from typing import Tuple, List, Dict
from pathlib import Path

class PRQualityChecker:
    """Check PR quality against project standards"""
    
    CRITICAL_FILES = [
        'backend/modules/_core/',
        'backend/modules/auth_guard.py',
        'backend/modules/observability.py',
        'backend/modules/clients.py',
        'backend/main.py',
        'frontend/middleware.ts',
        'frontend/lib/supabase/',
        '.github/workflows/',
    ]
    
    REQUIRED_PR_SECTIONS = [
        'What Changed',
        'How to Test',
        'Risk and Rollback',
        'Checklist'
    ]
    
    SECURITY_KEYWORDS = [
        'OPENAI_API_KEY',
        'PINECONE_API_KEY',
        'SUPABASE_KEY',
        'JWT_SECRET',
        'password =',
        'secret =',
    ]
    
    SECURITY_SAFE_PATTERNS = [
        'os.getenv',
        'process.env',
        '.env',
        'environment variable',
    ]

    def __init__(self):
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []
        self.suggestions: List[Dict] = []

    def add_issue(self, category: str, message: str, severity: str = "ERROR"):
        """Add critical issue"""
        self.issues.append({
            "severity": severity,
            "category": category,
            "message": message
        })

    def add_warning(self, category: str, message: str):
        """Add warning"""
        self.warnings.append({
            "category": category,
            "message": message
        })

    def add_suggestion(self, category: str, message: str):
        """Add suggestion"""
        self.suggestions.append({
            "category": category,
            "message": message
        })

    def check_pr_template(self, pr_body: str) -> None:
        """Verify PR description follows template"""
        if not pr_body:
            self.add_issue("PR Template", "PR description is empty")
            return

        for section in self.REQUIRED_PR_SECTIONS:
            if f"## {section}" not in pr_body and f"# {section}" not in pr_body:
                self.add_issue(
                    "PR Template",
                    f"Missing required section: '{section}'",
                    severity="ERROR"
                )

    def check_conventional_commits(self, commit_msg: str) -> None:
        """Verify commit follows conventional commits"""
        pattern = r'^(feat|fix|docs|style|refactor|perf|test|chore|ci|build)(\(.+\))?!?: '
        if not re.match(pattern, commit_msg):
            self.add_warning(
                "Conventional Commits",
                "Commit message doesn't follow conventional commits format. "
                "Expected: feat|fix|docs|...(...): message"
            )

    def check_hardcoded_secrets(self, file_path: str, content: str) -> None:
        """Check for hardcoded secrets"""
        if any(kw.lower() in file_path.lower() for kw in ['.test', '.mock', '.example']):
            return  # Skip test files

        for keyword in self.SECURITY_KEYWORDS:
            if keyword in content:
                # Check if it's safe usage
                is_safe = any(safe in content for safe in self.SECURITY_SAFE_PATTERNS)
                if not is_safe:
                    self.add_issue(
                        "Security",
                        f"Potential hardcoded secret in {file_path}: '{keyword}'",
                        severity="ERROR"
                    )

    def check_multi_tenant_isolation(self, file_path: str, content: str) -> None:
        """Check for multi-tenant isolation violations"""
        # Skip tests and config files
        if any(x in file_path.lower() for x in ['test', 'mock', 'config', '.env', '.json']):
            return

        if 'backend/routers' in file_path and file_path.endswith('.py'):
            # Check for queries without tenant filters
            query_patterns = [
                r'\.table\(["\'][\w]+["\']\)\.select\(',
                r'\.table\(["\'][\w]+["\']\)\.insert\(',
                r'\.table\(["\'][\w]+["\']\)\.update\(',
                r'\.table\(["\'][\w]+["\']\)\.delete\(',
            ]

            for pattern in query_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Check if next line has .eq("tenant_id"
                    if '.eq("tenant_id' not in content[match.start():match.start()+200]:
                        if '.eq(\'tenant_id' not in content[match.start():match.start()+200]:
                            # Could be a false positive, add as suggestion
                            self.add_warning(
                                "Multi-Tenant",
                                f"Query in {file_path} might be missing tenant_id filter. "
                                "Verify this query is properly scoped."
                            )

    def check_auth_patterns(self, file_path: str, content: str) -> None:
        """Check for proper authentication patterns"""
        if 'routers' not in file_path:
            return

        # Check for unprotected routes
        route_pattern = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)'
        routes = re.finditer(route_pattern, content)

        for route_match in routes:
            method = route_match.group(1).upper()
            path = route_match.group(2)

            # Skip public routes
            if any(x in path for x in ['/health', '/ping', '/auth/sync-user']):
                continue

            # Check if route has Depends(get_current_user)
            start_pos = route_match.start()
            # Look ahead 500 chars for function definition
            func_section = content[start_pos:start_pos+500]
            
            if 'Depends(get_current_user)' not in func_section:
                if 'user:' not in func_section or 'get_current_user' not in func_section:
                    self.add_warning(
                        "Authentication",
                        f"Route {method} {path} might be missing authentication check. "
                        f"Verify it uses Depends(get_current_user)"
                    )

    def check_database_migrations(self, changed_files: List[str]) -> None:
        """Check if schema changes have migrations"""
        schema_changes = [f for f in changed_files if 'database/schema' in f]
        migrations = [f for f in changed_files if 'database/migrations' in f]

        if schema_changes and not migrations:
            self.add_warning(
                "Database",
                "Schema changes detected but no migration files found. "
                "Create migrations in backend/database/migrations/"
            )

        # Check migration quality
        for migration_file in migrations:
            if migration_file.endswith('.sql'):
                try:
                    with open(migration_file, 'r') as f:
                        content = f.read()
                        
                    if 'CREATE TABLE' in content and 'IF NOT EXISTS' not in content:
                        self.add_warning(
                            "Database",
                            f"Migration {migration_file} should use 'CREATE TABLE IF NOT EXISTS' for idempotency"
                        )
                    
                    if ('CREATE TABLE' in content or 'ALTER TABLE' in content) and \
                       'ROW LEVEL SECURITY' not in content and 'RLS' not in content:
                        self.add_suggestion(
                            "Database",
                            f"Migration {migration_file} creates/modifies table. "
                            f"Consider adding RLS policies for security."
                        )
                except Exception as e:
                    print(f"Could not analyze migration file {migration_file}: {e}")

    def check_critical_files(self, changed_files: List[str]) -> None:
        """Check if changes to critical files are present"""
        critical_changes = [f for f in changed_files 
                           if any(cf in f for cf in self.CRITICAL_FILES)]

        if critical_changes:
            self.add_warning(
                "Architecture",
                f"Critical files modified: {', '.join(critical_changes)} - "
                f"Requires lead architect review"
            )

    def check_test_coverage(self, changed_files: List[str]) -> None:
        """Check if tests are added for code changes"""
        code_files = [f for f in changed_files 
                     if f.endswith('.py') and 'test' not in f and 'backend/routers' in f]
        test_files = [f for f in changed_files if 'test' in f]

        if code_files and not test_files:
            self.add_suggestion(
                "Testing",
                f"Code changes detected ({len(code_files)} files) but no test files added. "
                f"Consider adding tests."
            )

    def check_documentation_updates(self, changed_files: List[str]) -> None:
        """Check if documentation is updated with code changes"""
        code_files = [f for f in changed_files 
                     if f.startswith('backend/') or f.startswith('frontend/')
                     or f.startswith('database/')]
        doc_files = [f for f in changed_files 
                    if f.startswith('docs/') or f.endswith('.md')]

        if code_files and not doc_files:
            self.add_suggestion(
                "Documentation",
                f"Code changes detected but no documentation updates. "
                f"Consider updating relevant docs."
            )

    def check_pr_size(self, changed_files: List[str], total_additions: int) -> None:
        """Check if PR is appropriately sized"""
        file_count = len(changed_files)
        
        if file_count > 20 or total_additions > 1000:
            self.add_warning(
                "PR Size",
                f"Large PR detected ({file_count} files, {total_additions} additions). "
                f"Consider splitting into smaller, focused PRs for easier review."
            )

    def generate_report(self) -> Dict:
        """Generate quality report"""
        return {
            "issues": self.issues,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "quality_score": self._calculate_quality_score(),
            "summary": self._generate_summary()
        }

    def _calculate_quality_score(self) -> float:
        """Calculate 0-100 quality score"""
        score = 100.0
        score -= len(self.issues) * 15
        score -= len(self.warnings) * 5
        return max(0, score)

    def _generate_summary(self) -> Dict:
        """Generate summary of findings"""
        total_issues = len(self.issues) + len(self.warnings) + len(self.suggestions)
        
        return {
            "total_findings": total_issues,
            "critical_issues": len(self.issues),
            "warnings": len(self.warnings),
            "suggestions": len(self.suggestions),
            "status": "🔴 BLOCKING" if self.issues else "🟡 WARNING" if self.warnings else "✅ PASS"
        }

    def print_report(self, report: Dict) -> None:
        """Print formatted report"""
        print("\n" + "="*70)
        print("📋 PR QUALITY CHECK REPORT")
        print("="*70)

        summary = report['summary']
        print(f"\n{summary['status']} Quality Score: {report['quality_score']:.0f}/100")
        print(f"   Critical Issues: {summary['critical_issues']}")
        print(f"   Warnings: {summary['warnings']}")
        print(f"   Suggestions: {summary['suggestions']}")

        if report['issues']:
            print("\n🔴 CRITICAL ISSUES (Must Fix):")
            for issue in report['issues']:
                print(f"   [{issue['category']}] {issue['message']}")

        if report['warnings']:
            print("\n🟡 WARNINGS (Should Review):")
            for warning in report['warnings']:
                print(f"   [{warning['category']}] {warning['message']}")

        if report['suggestions']:
            print("\n💡 SUGGESTIONS (Consider):")
            for suggestion in report['suggestions']:
                print(f"   [{suggestion['category']}] {suggestion['message']}")

        print("\n" + "="*70 + "\n")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python pr_quality_checker.py <pr_body_file> [changed_files_json]")
        sys.exit(1)

    checker = PRQualityChecker()

    # Read PR body
    pr_body_file = sys.argv[1]
    try:
        with open(pr_body_file, 'r') as f:
            pr_body = f.read()
    except FileNotFoundError:
        print(f"PR body file not found: {pr_body_file}")
        sys.exit(1)

    # Check PR template
    checker.check_pr_template(pr_body)

    # Check changed files if provided
    if len(sys.argv) > 2:
        changed_files_json = sys.argv[2]
        try:
            with open(changed_files_json, 'r') as f:
                changed_files = json.load(f)
        except FileNotFoundError:
            changed_files = []
    else:
        changed_files = []

    if changed_files:
        checker.check_database_migrations(changed_files)
        checker.check_critical_files(changed_files)
        checker.check_test_coverage(changed_files)
        checker.check_documentation_updates(changed_files)

        # Check file contents for issues
        for file_path in changed_files[:50]:  # Limit to first 50 files
            if file_path.endswith(('.py', '.ts', '.tsx')):
                try:
                    if os.path.exists(file_path) and os.path.getsize(file_path) < 100000:  # Skip huge files
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        checker.check_hardcoded_secrets(file_path, content)
                        checker.check_multi_tenant_isolation(file_path, content)
                        checker.check_auth_patterns(file_path, content)
                except Exception as e:
                    print(f"Warning: Could not analyze {file_path}: {e}")

    # Generate and print report
    report = checker.generate_report()
    checker.print_report(report)

    # Output JSON for CI/CD
    print(json.dumps(report, indent=2))

    # Exit with appropriate code
    sys.exit(1 if checker.issues else 0)


if __name__ == '__main__':
    main()
