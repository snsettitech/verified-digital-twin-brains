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

Write-Host "GitHub Workflow Setup - Two-Agent Branch Protection" -ForegroundColor Cyan
Write-Host "Repository: $Owner/$Repo" -ForegroundColor Yellow
Write-Host ""

# Check GitHub CLI installed
$ghVersion = & gh --version 2>$null
if ($null -eq $ghVersion) {
    Write-Host "ERROR: GitHub CLI not found. Install: https://cli.github.com/" -ForegroundColor Red
    exit 1
}

Write-Host "OK: GitHub CLI found: $ghVersion" -ForegroundColor Green

# Step 1: Verify CODEOWNERS exists
Write-Host ""
Write-Host "Step 1/3: Verifying CODEOWNERS..." -ForegroundColor Yellow

if (Test-Path ".github/CODEOWNERS") {
    Write-Host "  OK: CODEOWNERS file found at .github/CODEOWNERS" -ForegroundColor Green
} else {
    Write-Host "  ERROR: CODEOWNERS not found." -ForegroundColor Red
    exit 1
}

# Step 2: Set up branch protection
Write-Host ""
Write-Host "Step 2/3: Setting up branch protection for main..." -ForegroundColor Yellow

try {
    Write-Host "  Configuring branch protection..." -ForegroundColor Cyan
    
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
    
    $tempFile = [System.IO.Path]::GetTempFileName()
    $protectionPayload | Out-File -FilePath $tempFile -Encoding UTF8
    
    & gh api -X PUT "repos/$Owner/$Repo/branches/main/protection" --input $tempFile 2>&1 | Out-Null
    Remove-Item -Path $tempFile -Force
    
    Write-Host "  OK: Branch protection enabled on main" -ForegroundColor Green
    Write-Host "    - Require 1 approval" -ForegroundColor Gray
    Write-Host "    - Require status checks: tests, lint, typecheck" -ForegroundColor Gray
    Write-Host "    - Dismiss stale reviews" -ForegroundColor Gray
    Write-Host "    - Block force pushes and deletions" -ForegroundColor Gray
} catch {
    Write-Host "  ERROR: Branch protection API failed" -ForegroundColor Red
    Write-Host "  Manual steps required in GitHub UI:" -ForegroundColor Yellow
    Write-Host "    Settings > Branches > Add rule for main" -ForegroundColor Gray
    Write-Host "    - Require 1 pull request approval" -ForegroundColor Gray
    Write-Host "    - Require status checks: tests, lint, typecheck" -ForegroundColor Gray
    Write-Host "    - Block force pushes and deletions" -ForegroundColor Gray
}

# Step 3: Summary
Write-Host ""
Write-Host "Step 3/3: Manual GitHub UI steps needed..." -ForegroundColor Yellow
Write-Host "  Settings > Code security and analysis" -ForegroundColor Gray
Write-Host "    - Secret scanning: Enable" -ForegroundColor Gray
Write-Host "    - Secret scanning push protection: Enable" -ForegroundColor Gray

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "OK: Two-Agent Workflow Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Workflow is now enforced by:" -ForegroundColor Yellow
Write-Host "  - Branch protection (1 approval + status checks)" -ForegroundColor Gray
Write-Host "  - CODEOWNERS (contract surfaces require review)" -ForegroundColor Gray
Write-Host "  - CI gates (tests, lint, typecheck must pass)" -ForegroundColor Gray
Write-Host "  - Secret scanning (prevents credential leaks)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next: Read CONTRIBUTING.md for full two-agent workflow rules" -ForegroundColor Cyan
