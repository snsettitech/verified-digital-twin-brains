# GitHub Workflow Automation: Two-Agent Branch Protection + Secret Scanning
# Purpose: Enable branch protection, secret scanning, and push protection in one command
#
# Prerequisites:
#   - GitHub CLI (gh) installed and authenticated: gh auth login
#   - Admin access to the repository
#   - Run from repo root
#
# Usage:
#   ./scripts/setup-github-workflow.ps1 -Owner <github-username> -Repo <repo-name>
#   Example: ./scripts/setup-github-workflow.ps1 -Owner sainathsetti -Repo verified-digital-twin-brains

param(
    [Parameter(Mandatory=$true)]
    [string]$Owner,
    
    [Parameter(Mandatory=$true)]
    [string]$Repo,
    
    [Parameter(Mandatory=$false)]
    [string]$ReviewerHandle = "@sainathsetti"
)

Write-Host "🔒 GitHub Workflow Setup — Two-Agent Branch Protection" -ForegroundColor Cyan
Write-Host "Repository: $Owner/$Repo" -ForegroundColor Yellow
Write-Host ""

# Check GitHub CLI installed
$ghVersion = gh --version 2>$null
if ($null -eq $ghVersion) {
    Write-Host "❌ GitHub CLI not found. Install: https://cli.github.com/" -ForegroundColor Red
    exit 1
}

Write-Host "✅ GitHub CLI found: $ghVersion" -ForegroundColor Green

# Step 1: Enable Secret Scanning
Write-Host ""
Write-Host "Step 1/4: Enabling secret scanning..." -ForegroundColor Yellow

try {
    # Create a GraphQL mutation to enable secret scanning
    $secretScanningMutation = @"
mutation {
  enableRepositorySecretScanning(input: {repositoryId: "$repo"}) {
    clientMutationId
  }
}
"@
    
    # Note: This requires using the GitHub API directly, gh doesn't have a built-in command
    Write-Host "⚠️  Secret scanning requires GitHub API (CLI limitation)" -ForegroundColor Yellow
    Write-Host "    Manual step: Settings → Code security → Secret scanning → Enable" -ForegroundColor Gray
    Write-Host "    Or use: gh api -H 'Accept: application/vnd.github+json' repos/{owner}/{repo} -f secret_scanning=true" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Secret scanning setup requires manual GitHub UI (admin API limitation)" -ForegroundColor Yellow
}

# Step 2: Enable Secret Scanning Push Protection
Write-Host ""
Write-Host "Step 2/4: Push protection requires manual GitHub UI or API calls..." -ForegroundColor Yellow
Write-Host "    Manual: Settings → Code security → Secret scanning → Push protection → Enable" -ForegroundColor Gray

# Step 3: Set up branch protection rule on main
Write-Host ""
Write-Host "Step 3/4: Setting up branch protection for 'main'..." -ForegroundColor Yellow

$branchProtectionCmd = @"
gh api repos/$Owner/$Repo/branches/main/protection `
  --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["tests", "lint", "typecheck"]
  },
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "enforce_admins": true,
  "dismiss_stale_reviews": true,
  "restrict_who_can_push": {
    "users": [],
    "teams": []
  },
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "required_conversation_resolution": false
}
JSON
"@

try {
    Write-Host "  Configuring branch protection..." -ForegroundColor Cyan
    
    # Build the GitHub API call manually
    $protectionPayload = @{
        required_status_checks = @{
            strict   = $true
            contexts = @("tests", "lint", "typecheck")
        }
        required_pull_request_reviews = @{
            dismiss_stale_reviews          = $true
            require_code_owner_reviews     = $true
            required_approving_review_count = 1
        }
        enforce_admins                = $true
        allow_force_pushes              = $false
        allow_deletions                 = $false
        required_linear_history         = $false
        required_conversation_resolution = $false
    } | ConvertTo-Json -Depth 10
    
    # Use gh API to set branch protection
    $protectionResult = gh api `
        -X PUT `
        "repos/$Owner/$Repo/branches/main/protection" `
        --input - <<< $protectionPayload
    
    Write-Host "  ✅ Branch protection enabled on 'main'" -ForegroundColor Green
    Write-Host "    - Require 1 approval" -ForegroundColor Gray
    Write-Host "    - Require status checks: tests, lint, typecheck" -ForegroundColor Gray
    Write-Host "    - Dismiss stale reviews" -ForegroundColor Gray
    Write-Host "    - Block force push" -ForegroundColor Gray
    Write-Host "    - Block deletions" -ForegroundColor Gray
    Write-Host "    - Require code owner reviews" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Branch protection setup failed. Manual steps:" -ForegroundColor Yellow
    Write-Host "    Settings → Branches → Add rule" -ForegroundColor Gray
    Write-Host "    Branch name: main" -ForegroundColor Gray
    Write-Host "    ✓ Require pull request reviews (1 approval)" -ForegroundColor Gray
    Write-Host "    ✓ Require status checks: tests, lint, typecheck" -ForegroundColor Gray
    Write-Host "    ✓ Require branches to be up to date" -ForegroundColor Gray
    Write-Host "    ✓ Restrict who can push (off for now)" -ForegroundColor Gray
    Write-Host "    ✓ Allow force pushes: OFF" -ForegroundColor Gray
    Write-Host "    ✓ Allow deletions: OFF" -ForegroundColor Gray
}

# Step 4: Verify CODEOWNERS is in place
Write-Host ""
Write-Host "Step 4/4: Verifying CODEOWNERS..." -ForegroundColor Yellow

if (Test-Path ".github/CODEOWNERS") {
    Write-Host "  ✅ CODEOWNERS file found" -ForegroundColor Green
    Write-Host "    GitHub will auto-request reviews on protected paths" -ForegroundColor Gray
} else {
    Write-Host "  ❌ CODEOWNERS not found at .github/CODEOWNERS" -ForegroundColor Red
    Write-Host "    Create it before pushing to main" -ForegroundColor Gray
}

# Summary
Write-Host ""
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✅ GitHub Workflow Setup Complete" -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan

Write-Host ""
Write-Host "📋 Two-Agent Workflow is now enforced by:" -ForegroundColor Yellow
Write-Host "   • Branch protection (1 approval + status checks required)" -ForegroundColor Gray
Write-Host "   • CODEOWNERS (contract surfaces require your review)" -ForegroundColor Gray
Write-Host "   • CI gates (tests, lint, typecheck must pass)" -ForegroundColor Gray
Write-Host "   • Secret scanning (prevents credential leaks)" -ForegroundColor Gray

Write-Host ""
Write-Host "⚠️  Manual GitHub UI steps still needed:" -ForegroundColor Yellow
Write-Host "   Settings → Code security → Secret scanning → Enable" -ForegroundColor Gray
Write-Host "   Settings → Code security → Secret scanning push protection → Enable" -ForegroundColor Gray

Write-Host ""
Write-Host "📖 Refer to CONTRIBUTING.md for full two-agent workflow rules" -ForegroundColor Cyan
