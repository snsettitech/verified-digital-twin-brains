# 🚀 QUICK COMMAND REFERENCE - GitHub Automation

> Print this page as a sticky note! 📌

---

## GITHUB CLI METHOD (⭐ Easiest)

### Command 1: Test First (Preview Changes)
```powershell
cd scripts
.\github_setup_automation.ps1 -Owner "your-org" -Repo "your-repo" -DryRun
```

### Command 2: Apply Changes
```powershell
cd scripts
.\github_setup_automation.ps1 -Owner "your-org" -Repo "your-repo"
```

**Replace:**
- `your-org` = GitHub organization or username
- `your-repo` = Repository name

**Time:** 2-3 minutes

---

## PYTHON METHOD

### Install (First Time Only)
```bash
pip install PyGithub
gh auth login
```

### Test First
```bash
cd scripts
python github_setup_automation.py your-org your-repo
```

### Apply
```bash
cd scripts
python github_setup_automation.py your-org your-repo --no-dry-run
```

**Time:** 5 minutes

---

## TERRAFORM METHOD

### Setup (First Time Only)
```bash
terraform --version  # Check installed
cd scripts
```

### Create Config
Create `terraform.tfvars`:
```hcl
github_owner = "your-org"
github_repo  = "your-repo"
github_token = "ghp_your_token_here"
```

### Test First
```bash
terraform init
terraform plan
```

### Apply
```bash
terraform apply
# Type: yes
```

**Time:** 10 minutes

---

## ✅ WHAT GETS CONFIGURED

```
✓ Branch protection for 'main'
✓ Require 1 approval
✓ Require CODEOWNERS review  
✓ Require status checks (7)
✓ Auto-merge on PRs
✓ Auto-delete branches
✓ Dependabot alerts
✓ Secret scanning (if available)
```

---

## 🔑 GET YOUR GITHUB TOKEN

1. GitHub.com → Profile → Settings
2. Developer settings → Personal tokens (classic)
3. Generate new token
4. Scopes: `repo`, `admin:org_hook`
5. Copy & store safely

---

## VERIFICATION CHECKLIST

After running automation:

```
☐ Go to GitHub → Repo → Settings → Branches
☐ Verify 'main' branch protected
☐ Check 7 status checks required
☐ Verify CODEOWNERS review enabled
☐ Check "Require conversation resolution"

☐ Go to Settings → Code security
☐ Verify Dependabot alerts enabled
☐ Verify Secret scanning enabled

☐ Open test PR
☐ Verify CI runs automatically
☐ Verify merge blocked until checks pass
```

---

## WHICH METHOD TO CHOOSE

| Your Situation | Use |
|---|---|
| "I just want it done NOW" | GitHub CLI |
| "I use Python already" | Python |
| "We manage many repos" | Terraform |
| "We have CI/CD pipeline" | Terraform |
| "I'm not sure" | GitHub CLI ⭐ |

---

## TROUBLESHOOTING

| Problem | Solution |
|---------|----------|
| "gh command not found" | Install GitHub CLI: https://cli.github.com |
| "401 Unauthorized" | Run `gh auth login` or check token |
| "Rate limit exceeded" | Wait 1 hour (GitHub limit) |
| "Could not find branch" | Check branch name (default: main) |
| "Permission denied" | Need repo admin access |

---

## FILES CREATED

```
scripts/
  ├─ github_setup_automation.ps1  (PowerShell)
  ├─ github_setup_automation.py   (Python)
  └─ github_setup.tf              (Terraform)

docs/
  ├─ GITHUB_AUTOMATION_GUIDE.md   (Detailed)
  ├─ GITHUB_CONFIGURATION_GUIDE.md (Master)
  ├─ GITHUB_SETTINGS_QUICK_SETUP.md (Manual)
  ├─ GITHUB_SETTINGS_CONFIGURATION.md (Deep dive)
  └─ GITHUB_SETTINGS_CHECKLIST.md (Reference)
```

---

## NEXT STEPS

1. **Choose method** (GitHub CLI recommended)
2. **Install prerequisites** (if needed)
3. **Run with DRY-RUN** to preview
4. **Review output**
5. **Apply changes**
6. **Verify in GitHub UI**

---

## MORE HELP

- Full guide: `docs/GITHUB_AUTOMATION_GUIDE.md`
- Manual steps: `docs/GITHUB_SETTINGS_QUICK_SETUP.md`
- All settings: `docs/GITHUB_SETTINGS_CONFIGURATION.md`

---

**Ready? Pick method above and run command!** 🎯
