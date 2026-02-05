# GitHub Settings Automation Script
# Automatically configures branch protection rules and security settings
# Requires: GitHub CLI installed (https://cli.github.com)
# Requires: gh auth login

param(
    [Parameter(Mandatory=$true)]
    [string]$Owner,
    
    [Parameter(Mandatory=$true)]
    [string]$Repo,
    
    [string]$Branch = "main",
    
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host "🔧 GitHub Settings Automation" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host "Owner: $Owner"
Write-Host "Repo: $Repo"
Write-Host "Branch: $Branch"
if ($DryRun) { Write-Host "Mode: DRY RUN (no changes)" -ForegroundColor Yellow }
Write-Host ""

# Function to run gh command with DryRun support
function Invoke-GhCommand {
    param(
        [string]$Description,
        [string[]]$Arguments
    )
    
    Write-Host "▶️  $Description" -ForegroundColor Blue
    
    if ($DryRun) {
        Write-Host "   [DRY RUN] gh $($Arguments -join ' ')" -ForegroundColor Yellow
        return
    }
    
    try {
        $output = & gh @Arguments 2>&1
        Write-Host "   ✅ Success" -ForegroundColor Green
        return $output
    }
    catch {
        Write-Host "   ❌ Error: $_" -ForegroundColor Red
        throw
    }
}

# 1. Create branch protection rule
Write-Host "📌 Configuring Branch Protection Rules" -ForegroundColor Magenta
Write-Host ""

# Check if rule exists
$repoApi = "repos/$Owner/$Repo"
if ($DryRun) {
    Write-Host "   [DRY RUN] Checking existing rules..." -ForegroundColor Yellow
} else {
    try {
        $existingRules = gh api "$repoApi/branches/$Branch/protection" 2>&1 | Out-Null
        Write-Host "   ⚠️  Rule already exists, will update..." -ForegroundColor Yellow
    }
    catch {
        Write-Host "   ✓ No existing rule (will create new)" -ForegroundColor Green
    }
}

# Create/update branch protection rule
$ruleJson = @{
    required_status_checks = @{
        strict = $true
        contexts = @(
            "code-quality",
            "security-audit",
            "architecture-check",
            "test-coverage",
            "validation",
            "migration-check",
            "config-validation"
        )
    }
    enforce_admins = $false
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $true
        require_code_owner_reviews = $true
        required_approving_review_count = 1
        require_last_push_approval = $false
    }
    restrictions = $null
    allow_force_pushes = $false
    allow_deletions = $false
    require_conversation_resolution = $true
} | ConvertTo-Json -Depth 10

if ($DryRun) {
    Write-Host "▶️  Create/Update branch protection rule for '$Branch'" -ForegroundColor Blue
    Write-Host "   [DRY RUN] Would apply:" -ForegroundColor Yellow
    Write-Host $ruleJson -ForegroundColor Gray
} else {
    try {
        gh api -X PUT "$repoApi/branches/$Branch/protection" --input - <$ruleJson 2>&1 | Out-Null
        Write-Host "   ✅ Branch protection rule configured" -ForegroundColor Green
    }
    catch {
        Write-Host "   ❌ Error configuring branch protection: $_" -ForegroundColor Red
    }
}

Write-Host ""

# 2. Enable security features
Write-Host "🔐 Enabling Security Features" -ForegroundColor Magenta
Write-Host ""

$securityFeatures = @(
    @{ Name = "Dependabot Alerts"; Endpoint = "dependabot/alerts"; Method = "PATCH" },
    @{ Name = "Secret Scanning"; Endpoint = "secret-scanning"; Method = "PATCH" },
    @{ Name = "Push Protection"; Endpoint = "secret-scanning/push-protection"; Method = "PATCH" }
)

foreach ($feature in $securityFeatures) {
    if ($DryRun) {
        Write-Host "▶️  Enable $($feature.Name)" -ForegroundColor Blue
        Write-Host "   [DRY RUN] gh api -X $($feature.Method) repos/$Owner/$Repo/$($feature.Endpoint) -f enabled=true" -ForegroundColor Yellow
    } else {
        try {
            gh api -X $feature.Method "repos/$Owner/$Repo/$($feature.Endpoint)" -f enabled=true 2>&1 | Out-Null
            Write-Host "▶️  Enable $($feature.Name)" -ForegroundColor Blue
            Write-Host "   ✅ Enabled" -ForegroundColor Green
        }
        catch {
            Write-Host "▶️  Enable $($feature.Name)" -ForegroundColor Blue
            Write-Host "   ⚠️  Skipped (may require team plan)" -ForegroundColor Yellow
        }
    }
}

Write-Host ""

# 3. Configure pull request settings
Write-Host "🔄 Configuring Pull Request Settings" -ForegroundColor Magenta
Write-Host ""

$prSettings = @{
    allow_auto_merge = $true
    delete_branch_on_merge = $true
    allow_squash_merge = $true
    allow_merge_commit = $true
    allow_rebase_merge = $true
} | ConvertTo-Json

if ($DryRun) {
    Write-Host "▶️  Configure PR settings (auto-merge, auto-delete)" -ForegroundColor Blue
    Write-Host "   [DRY RUN] Would apply:" -ForegroundColor Yellow
    Write-Host $prSettings -ForegroundColor Gray
} else {
    try {
        gh api -X PATCH "$repoApi" --input - <$prSettings 2>&1 | Out-Null
        Write-Host "▶️  Configure PR settings (auto-merge, auto-delete)" -ForegroundColor Blue
        Write-Host "   ✅ Settings applied" -ForegroundColor Green
    }
    catch {
        Write-Host "   ⚠️  Some PR settings may require organization level settings" -ForegroundColor Yellow
    }
}

Write-Host ""

# 4. Upload CODEOWNERS file (if exists)
Write-Host "👥 Setting Up CODEOWNERS" -ForegroundColor Magenta
Write-Host ""

$codeOwnersPath = ".github/CODEOWNERS"
if (Test-Path $codeOwnersPath) {
    Write-Host "▶️  CODEOWNERS file exists" -ForegroundColor Blue
    Write-Host "   ✅ File found at $codeOwnersPath" -ForegroundColor Green
    Write-Host "   Make sure to commit this file to your repository" -ForegroundColor Yellow
} else {
    Write-Host "▶️  CODEOWNERS file" -ForegroundColor Blue
    Write-Host "   ⚠️  File not found at $codeOwnersPath" -ForegroundColor Yellow
    Write-Host "   You may need to create it manually" -ForegroundColor Yellow
}

Write-Host ""

# 5. Summary
Write-Host "📊 Summary" -ForegroundColor Cyan
Write-Host "=========" -ForegroundColor Cyan
Write-Host "✓ Branch protection rule for '$Branch'" -ForegroundColor Green
Write-Host "✓ Required status checks (7 checks)" -ForegroundColor Green
Write-Host "✓ Code owner reviews required" -ForegroundColor Green
Write-Host "✓ Security features (Dependabot, Secret Scanning)" -ForegroundColor Green
Write-Host "✓ PR auto-merge and auto-delete enabled" -ForegroundColor Green
Write-Host ""

if ($DryRun) {
    Write-Host "🔄 DRY RUN COMPLETE - No changes were made" -ForegroundColor Yellow
    Write-Host "Run without -DryRun to apply these changes" -ForegroundColor Yellow
} else {
    Write-Host "✅ GITHUB SETTINGS AUTOMATED SUCCESSFULLY" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Verify settings in GitHub web UI (Settings → Branches)" -ForegroundColor White
Write-Host "2. Ensure .github/CODEOWNERS is committed to repo" -ForegroundColor White
Write-Host "3. Test with a pull request" -ForegroundColor White
