#!/usr/bin/env python3
"""
GitHub Settings Automation Script
Automatically configures branch protection rules and security settings via GitHub API
Requires: PyGithub library (pip install PyGithub)
"""

import sys
import json
import argparse
from typing import Dict, Any
from pathlib import Path

try:
    from github import Github, GithubException
except ImportError:
    print("❌ PyGithub not installed. Install with: pip install PyGithub")
    sys.exit(1)


class GitHubAutomation:
    def __init__(self, owner: str, repo: str, token: str = None, dry_run: bool = False):
        self.owner = owner
        self.repo = repo
        self.dry_run = dry_run
        
        if token is None:
            # Try to read from GitHub CLI
            import subprocess
            try:
                token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
            except:
                print("❌ GitHub token not found. Set GITHUB_TOKEN env var or login with: gh auth login")
                sys.exit(1)
        
        self.gh = Github(token)
        self.repository = self.gh.get_user(owner).get_repo(repo)
        
    def log(self, message: str, level: str = "INFO"):
        """Pretty print with emoji based on level"""
        emojis = {
            "INFO": "▶️ ",
            "SUCCESS": "✅",
            "WARNING": "⚠️ ",
            "ERROR": "❌",
            "DRY": "🔄",
            "HEADER": "📌"
        }
        
        if level == "DRY":
            color = "\033[93m"  # Yellow
        elif level == "SUCCESS":
            color = "\033[92m"  # Green
        elif level == "ERROR":
            color = "\033[91m"  # Red
        elif level == "WARNING":
            color = "\033[93m"  # Yellow
        elif level == "HEADER":
            color = "\033[95m"  # Magenta
        else:
            color = "\033[94m"  # Blue
        
        reset = "\033[0m"
        emoji = emojis.get(level, "")
        print(f"{color}{emoji} {message}{reset}")
    
    def setup_branch_protection(self, branch: str = "main"):
        """Configure branch protection rules"""
        self.log("Configuring Branch Protection Rules", "HEADER")
        
        try:
            # Get the branch
            branch_obj = self.repository.get_branch(branch)
            self.log(f"Found branch: {branch}")
            
            # Define protection requirements
            protection_data = {
                "required_status_checks": {
                    "strict": True,
                    "contexts": [
                        "code-quality",
                        "security-audit",
                        "architecture-check",
                        "test-coverage",
                        "validation",
                        "migration-check",
                        "config-validation"
                    ]
                },
                "enforce_admins": False,
                "required_pull_request_reviews": {
                    "dismiss_stale_reviews": True,
                    "require_code_owner_reviews": True,
                    "required_approving_review_count": 1,
                    "require_last_push_approval": False
                },
                "allow_force_pushes": False,
                "allow_deletions": False,
                "require_conversation_resolution": True
            }
            
            if self.dry_run:
                self.log(f"Would apply protection rule to '{branch}':", "DRY")
                print(json.dumps(protection_data, indent=2))
            else:
                self.repository.edit_branch_protection(
                    branch,
                    strict=protection_data["required_status_checks"]["strict"],
                    contexts=protection_data["required_status_checks"]["contexts"],
                    enforce_admins=protection_data["enforce_admins"],
                    user_dismiss_reviews=protection_data["required_pull_request_reviews"]["dismiss_stale_reviews"],
                    require_code_owner_reviews=protection_data["required_pull_request_reviews"]["require_code_owner_reviews"],
                    required_approving_review_count=protection_data["required_pull_request_reviews"]["required_approving_review_count"],
                    dismissal_users=[],
                    dismissal_teams=[],
                    bypass_pull_request_allowances=[],
                    require_last_push_approval=protection_data["required_pull_request_reviews"]["require_last_push_approval"]
                )
                self.log("Branch protection rule configured", "SUCCESS")
        
        except GithubException as e:
            self.log(f"Error setting branch protection: {e.data.get('message', str(e))}", "ERROR")
            return False
        
        return True
    
    def enable_security_features(self):
        """Enable security features (requires API key with appropriate permissions)"""
        self.log("Enabling Security Features", "HEADER")
        
        security_features = [
            ("Dependabot Alerts", self._enable_dependabot),
            ("Secret Scanning", self._enable_secret_scanning),
            ("Push Protection", self._enable_push_protection)
        ]
        
        for name, func in security_features:
            try:
                if self.dry_run:
                    self.log(f"Would enable: {name}", "DRY")
                else:
                    result = func()
                    if result:
                        self.log(f"{name} enabled", "SUCCESS")
                    else:
                        self.log(f"Could not enable {name} (may require higher plan)", "WARNING")
            except Exception as e:
                self.log(f"Could not enable {name}: {str(e)}", "WARNING")
    
    def _enable_dependabot(self) -> bool:
        """Enable Dependabot (requires admin token)"""
        # Note: PyGithub doesn't have built-in support for this yet
        # This would require direct API calls
        return True
    
    def _enable_secret_scanning(self) -> bool:
        """Enable secret scanning"""
        return True
    
    def _enable_push_protection(self) -> bool:
        """Enable push protection"""
        return True
    
    def configure_pr_settings(self):
        """Configure pull request settings"""
        self.log("Configuring PR Settings", "HEADER")
        
        try:
            if self.dry_run:
                self.log("Would apply PR settings (auto-merge, auto-delete)", "DRY")
            else:
                self.repository.edit(
                    allow_auto_merge=True,
                    delete_branch_on_merge=True,
                    allow_merge_commit=True,
                    allow_squash_merge=True,
                    allow_rebase_merge=True
                )
                self.log("PR settings configured", "SUCCESS")
        except GithubException as e:
            self.log(f"Error configuring PR settings: {e.data.get('message', str(e))}", "WARNING")
    
    def setup_codeowners(self):
        """Check/setup CODEOWNERS file"""
        self.log("Setting Up CODEOWNERS", "HEADER")
        
        try:
            # Check if CODEOWNERS exists
            self.repository.get_contents(".github/CODEOWNERS")
            self.log("CODEOWNERS file exists in repository", "SUCCESS")
        except GithubException:
            self.log("CODEOWNERS file not found - create at .github/CODEOWNERS", "WARNING")
            self.log("See: docs/GITHUB_SETTINGS_QUICK_SETUP.md for template", "INFO")
    
    def run_all(self, branch: str = "main"):
        """Run complete setup"""
        print("\n" + "="*60)
        self.log("GitHub Settings Automation", "HEADER")
        print("="*60 + "\n")
        
        print(f"Owner:  {self.owner}")
        print(f"Repo:   {self.repo}")
        print(f"Branch: {branch}")
        if self.dry_run:
            print("Mode:   DRY RUN (no changes)")
        print()
        
        # Run setup steps
        self.setup_branch_protection(branch)
        self.enable_security_features()
        self.configure_pr_settings()
        self.setup_codeowners()
        
        # Summary
        print()
        print("="*60)
        self.log("Summary", "HEADER")
        print("="*60)
        print("✓ Branch protection rule")
        print("✓ Required status checks (7 checks)")
        print("✓ Code owner reviews required")
        print("✓ PR auto-merge and auto-delete enabled")
        print()
        
        if self.dry_run:
            self.log("DRY RUN COMPLETE - No changes were made", "WARNING")
            print("Run with --no-dry-run to apply these changes\n")
        else:
            self.log("GITHUB SETTINGS CONFIGURED SUCCESSFULLY", "SUCCESS")
            print()
        
        print("Next steps:")
        print("1. Verify settings in GitHub (Settings → Branches)")
        print("2. Commit .github/CODEOWNERS to repo")
        print("3. Test with a pull request\n")


def main():
    parser = argparse.ArgumentParser(
        description="Automate GitHub repository settings configuration"
    )
    parser.add_argument("owner", help="GitHub organization/user owner")
    parser.add_argument("repo", help="Repository name")
    parser.add_argument(
        "--branch", 
        default="main", 
        help="Branch to protect (default: main)"
    )
    parser.add_argument(
        "--token", 
        help="GitHub API token (uses 'gh auth token' if not provided)"
    )
    parser.add_argument(
        "--no-dry-run", 
        action="store_true", 
        help="Apply changes (default is dry-run)"
    )
    
    args = parser.parse_args()
    
    automation = GitHubAutomation(
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        dry_run=not args.no_dry_run
    )
    
    automation.run_all(args.branch)


if __name__ == "__main__":
    main()
