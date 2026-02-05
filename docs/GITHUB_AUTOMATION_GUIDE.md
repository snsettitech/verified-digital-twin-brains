# ⚡ GitHub Settings Automation Guide

> **Question**: Can I automatically apply these rules instead of doing them manually?  
> **Answer**: YES! 3 options provided. Pick the one that fits your workflow.

---

## 🎯 3 AUTOMATION OPTIONS

### Option 1: GitHub CLI (Easiest) ⭐ RECOMMENDED
- **Speed**: 2 minutes
- **Requires**: [GitHub CLI](https://cli.github.com) installed
- **Best for**: Quick setup, anyone on the team
- **Location**: `scripts/github_setup_automation.ps1`

### Option 2: Python Script
- **Speed**: 5 minutes
- **Requires**: Python 3.8+, PyGithub library
- **Best for**: Teams using Python
- **Location**: `scripts/github_setup_automation.py`

### Option 3: Terraform (Infrastructure as Code)
- **Speed**: 10 minutes
- **Requires**: Terraform installed
- **Best for**: Managing multiple repos, CI/CD pipelines
- **Location**: `scripts/github_setup.tf`

---

## ⚙️ OPTION 1: GitHub CLI (EASIEST)

### Prerequisites
```powershell
# Check if GitHub CLI is installed
gh --version

# If not installed, install from: https://cli.github.com
```

### Login to GitHub
```powershell
gh auth login
# Follow prompts to authenticate
```

### Run the Script

#### DRY RUN (Preview changes)
```powershell
cd scripts
.\github_setup_automation.ps1 -Owner "your-org" -Repo "your-repo" -DryRun
```

#### Apply Changes
```powershell
cd scripts
.\github_setup_automation.ps1 -Owner "your-org" -Repo "your-repo"
```

### What It Does
- ✅ Creates branch protection rule for `main`
- ✅ Enables 7 required status checks
- ✅ Requires CODEOWNERS review
- ✅ Enables auto-merge and auto-delete
- ✅ Attempts to enable Dependabot/secret scanning

### Example Output
```
🔧 GitHub Settings Automation
=============================
Owner: my-org
Repo: my-repo
Branch: main

▶️  Create/Update branch protection rule
   ✅ Branch protection rule configured

🔐 Enabling Security Features

▶️  Enable Dependabot Alerts
   ✅ Enabled

▶️  Enable Secret Scanning
   ⚠️  Skipped (may require team plan)

📊 Summary
=========
✓ Branch protection rule for 'main'
✓ Required status checks (7 checks)
✓ Code owner reviews required
✓ Security features (Dependabot, Secret Scanning)
✓ PR auto-merge and auto-delete enabled

✅ GITHUB SETTINGS AUTOMATED SUCCESSFULLY
```

---

## 🐍 OPTION 2: Python Script

### Prerequisites
```bash
# Install Python (if not already installed)
python --version

# Install required library
pip install PyGithub
```

### Login to GitHub
```bash
# Method 1: GitHub CLI (recommended)
gh auth login

# Method 2: Environment variable
$env:GITHUB_TOKEN = "ghp_your_token_here"
```

### Run the Script

#### DRY RUN (Preview changes)
```bash
cd scripts
python github_setup_automation.py my-org my-repo
```

#### Apply Changes
```bash
cd scripts
python github_setup_automation.py my-org my-repo --no-dry-run
```

### What It Does
Same as GitHub CLI option:
- ✅ Branch protection rules
- ✅ Status checks enforcement
- ✅ Code owner reviews
- ✅ PR auto-merge settings

### Example Output
```
============================================================
📌 GitHub Settings Automation
============================================================

Owner:  my-org
Repo:   my-repo
Branch: main

▶️  Configuring Branch Protection Rules
✅ Found branch: main
✅ Branch protection rule configured

📌 Configuring PR Settings
✅ PR settings configured

============================================================
Summary
============================================================
✓ Branch protection rule
✓ Required status checks (7 checks)
✓ Code owner reviews required
✓ PR auto-merge and auto-delete enabled

✅ GITHUB SETTINGS CONFIGURED SUCCESSFULLY

Next steps:
1. Verify settings in GitHub (Settings → Branches)
2. Commit .github/CODEOWNERS to repo
3. Test with a pull request
```

---

## 🏗️ OPTION 3: Terraform (Infrastructure as Code)

### Prerequisites
```bash
# Install Terraform
# Download from: https://www.terraform.io/downloads

# Verify installation
terraform --version
```

### Setup

#### 1. Create `terraform.tfvars`
```hcl
# terraform.tfvars
github_owner = "your-org"
github_repo  = "your-repo"
github_token = "ghp_your_token_here"
main_branch  = "main"
enable_security_features = true
```

**OR use environment variable:**
```bash
$env:TF_VAR_github_token = "ghp_your_token_here"
```

#### 2. Initialize Terraform
```bash
cd scripts
terraform init
```

#### 3. Review Changes (Plan)
```bash
terraform plan
```

Output shows what will be created:
```
Terraform will perform the following actions:

  # github_branch_protection.main will be created
  + resource "github_branch_protection" "main" {
      + pattern           = "main"
      + repository_id     = "R_..."
      + require_conversation_resolution = true
      # ... more settings
    }

Plan: 1 to add, 0 to change, 0 to destroy.
```

#### 4. Apply Changes
```bash
terraform apply
# Type 'yes' to confirm
```

### What It Does
- ✅ Idempotent (safe to run multiple times)
- ✅ Manages complete configuration in code
- ✅ Easy to version control and review
- ✅ Simple to update in the future
- ✅ Works in CI/CD pipelines

### Benefits of Terraform Approach
- **Reproducible**: Same config every time
- **Auditable**: Changes tracked in git
- **Scalable**: Manage 1 repo or 100 repos with same code
- **Destroyable**: Remove all settings with `terraform destroy`

### Update Settings
To change settings later, just edit `github_setup.tf` and run:
```bash
terraform plan   # Review changes
terraform apply  # Apply changes
```

---

## 🔑 Getting Your GitHub Token

### For GitHub CLI
```bash
gh auth login
# CLI will handle token automatically
```

### For Python/Terraform
Generate personal access token:

1. Go to GitHub.com
2. Click your profile → Settings → Developer settings → Personal access tokens
3. Click "Tokens (classic)" → "Generate new token"
4. Select scopes:
   - ✅ `repo` (full control)
   - ✅ `admin:org_hook` (if in organization)
5. Copy token
6. Store securely (don't commit to git!)

---

## 🚀 RECOMMENDED SETUP PATH

### For Individual Contributors
```
1. Install GitHub CLI
2. Run: .\github_setup_automation.ps1 -DryRun
3. Review output
4. Run: .\github_setup_automation.ps1
5. Done! ✅
```

**Time**: ~5 minutes

### For Development Teams
```
1. Use Terraform approach
2. Commit github_setup.tf to .github/terraform/ folder
3. Store token in organization secrets
4. Run in CI/CD on deployment
5. All repos auto-configured
```

**Time**: ~15 minutes setup, automatic thereafter

### For CI/CD Pipelines
Use Terraform in your workflow:

```yaml
# .github/workflows/setup-github-config.yml
name: Setup GitHub Config

on:
  push:
    paths:
      - 'scripts/github_setup.tf'

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - uses: hashicorp/setup-terraform@v2
      
      - name: Terraform Init
        run: cd scripts && terraform init
      
      - name: Terraform Apply
        run: cd scripts && terraform apply -auto-approve
        env:
          TF_VAR_github_token: ${{ secrets.GITHUB_TOKEN }}
          TF_VAR_github_owner: ${{ github.repository_owner }}
          TF_VAR_github_repo: ${{ github.event.repository.name }}
```

---

## ❓ FAQ

### Q: Will this break my existing settings?
**A**: All three options are designed to be idempotent. You can run them multiple times safely. They update existing settings rather than breaking them.

### Q: Can I undo changes?
**A**: 
- **GitHub CLI/Python**: Must undo manually via GitHub UI
- **Terraform**: Run `terraform destroy` to remove all settings

### Q: What if I only want some settings?
**A**: Edit the script/Terraform file to remove sections you don't want before running.

### Q: Can I apply to multiple repos?
**A**: 
- **GitHub CLI**: Run script once per repo
- **Python**: Would need custom loop script
- **Terraform**: Create separate `.tfvars` files for each repo

### Q: Do I need admin access?
**A**: Yes, you need admin or maintain access to the repository.

### Q: Is it safe to run in CI/CD?
**A**: Yes, but store your GitHub token in organization secrets securely.

### Q: What if a setting fails?
**A**: Scripts continue and report which settings failed. You can retry or fix manually in GitHub UI.

---

## ✅ VERIFICATION

After running any automation option, verify:

```
1. Go to GitHub.com → Your Repo → Settings → Branches
2. Confirm 'main' branch has protection rule ✅
3. Check status checks are enabled (7 items) ✅
4. Verify CODEOWNERS review required ✅

5. Go to Settings → Code security & analysis
6. Check Dependabot alerts enabled ✅
7. Check Secret scanning enabled ✅

8. Open a test PR
9. Verify workflow runs automatically ✅
10. Verify merge button is disabled until checks pass ✅
```

---

## 📞 NEXT STEPS

1. **Choose automation option** (GitHub CLI recommended for ease)
2. **Install prerequisites** (gh/python/terraform)
3. **Run with --dry-run** to preview
4. **Apply changes**
5. **Verify in GitHub UI**
6. **Test with a pull request**

---

## 📚 RELATED DOCS

- [GitHub Settings Quick Setup](./GITHUB_SETTINGS_QUICK_SETUP.md) - Manual UI steps
- [GitHub Settings Detailed Guide](./GITHUB_SETTINGS_CONFIGURATION.md) - Why each setting
- [GitHub Configuration Checklist](./GITHUB_SETTINGS_CHECKLIST.md) - Complete reference

