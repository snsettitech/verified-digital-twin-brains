# ⚙️ GitHub Configuration - Complete Checklist

> **Quick Reference**: Everything you need to configure in GitHub repo settings

---

## 🎯 5-MINUTE SUMMARY

### **Go to**: Repository Settings → Branches

```
Create Rule for 'main':
✅ Require pull requests: Yes (1 approval)
✅ Require CODEOWNERS review: Yes
✅ Require status checks: Yes (add after first PR)
✅ Dismiss stale approvals: Yes
✅ Require conversation resolution: Yes
```

### **Go to**: Repository Settings → Code security & analysis

```
✅ Enable Dependabot alerts
✅ Enable Secret scanning
✅ Enable Push protection
```

### **Add Teams** (as needed):
- @backend-team, @frontend-team, @lead-architect, etc.

---

## 📋 COMPLETE CONFIGURATION CHECKLIST

### **SECTION 1: BRANCH PROTECTION (Critical)**

**Location**: Settings → Branches → Add rule for `main`

- [ ] **Require a pull request before merging**
  - [ ] Require at least 1 approval (or 2 for strict)
  - [ ] Dismiss stale pull request approvals: **✅**
  - [ ] Require review from Code Owners: **✅**
  - [ ] Require approval of most recent push: **✅**

- [ ] **Require status checks to pass before merging**
  - [ ] Require branches to be up to date: **✅**
  - [ ] Add status checks (after first workflow run):
    - [ ] CI Linting / lint-backend
    - [ ] CI Linting / lint-frontend
    - [ ] code-review / code-quality
    - [ ] code-review / security-scan
    - [ ] code-review / pr-validation
    - [ ] code-review / architecture-impact
    - [ ] code-review / test-coverage
    - [ ] code-review / migration-check
    - [ ] code-review / config-validation

- [ ] **Require conversation resolution**
  - [ ] Conversations must be resolved: **✅**

- [ ] **Restrict who can push**
  - [ ] Allow force pushes: **❌ Disable**
  - [ ] Allow deletions: **❌ Disable**

---

### **SECTION 2: SECURITY SETTINGS**

**Location**: Settings → Code security & analysis

- [ ] **Dependabot**
  - [ ] Dependabot alerts: **✅ Enable**
  - [ ] Dependabot security updates: **✅ Enable**

- [ ] **Secret scanning**
  - [ ] Secret scanning: **✅ Enable**
  - [ ] Push protection: **✅ Enable**

- [ ] **Code scanning** (if available)
  - [ ] Code scanning: **✅ Enable**

---

### **SECTION 3: ACCESS CONTROL**

**Location**: Settings → Collaborators & teams

- [ ] **Add Teams with Roles**:
  - [ ] @backend-team → **Admin**
  - [ ] @frontend-team → **Admin**
  - [ ] @lead-architect → **Admin**
  - [ ] @devops-team → **Admin**
  - [ ] @qa-team → **Write** (read-only for approvals)

- [ ] **Verify CODEOWNERS**
  - [ ] File exists: `.github/CODEOWNERS` ✅
  - [ ] Teams referenced exist in GitHub ✅
  - [ ] Users are members of those teams ✅

---

### **SECTION 4: PULL REQUEST SETTINGS**

**Location**: Settings → Pull requests

- [ ] **Merge settings**
  - [ ] Allow squash merging: **✅**
  - [ ] Allow rebase merging: **✅**
  - [ ] Allow merge commits: **✅**
  - [ ] Default merge type: **Squash and merge** (recommended)

- [ ] **Automation**
  - [ ] Allow auto-merge: **✅**
  - [ ] Auto-merge type: **Auto-merge pull requests**
  - [ ] Automatically delete head branches: **✅**

---

### **SECTION 5: NOTIFICATIONS (Optional)**

**Location**: Settings → Notifications

- [ ] **Default notification settings**
  - [ ] Include your own updates: **✅**
  - [ ] Participating and mentions: **✅**
  - [ ] Pull request reviews requested: **✅**

---

### **SECTION 6: SECRETS & VARIABLES (If Needed)**

**Location**: Settings → Secrets and variables → Actions

- [ ] **Add Secrets** (if not using .env):
  - [ ] SUPABASE_URL
  - [ ] OPENAI_API_KEY
  - [ ] PINECONE_API_KEY
  - [ ] JWT_SECRET
  - [ ] (Other required env vars)

---

### **SECTION 7: GITHUB ACTIONS (Verify)**

**Location**: Settings → Actions → General

- [ ] **Actions permissions**
  - [ ] Allow all actions and reusable workflows: **✅**

- [ ] **Verify workflows exist**:
  - [ ] `.github/workflows/lint.yml` ✅
  - [ ] `.github/workflows/code-review.yml` ✅

---

### **SECTION 8: ENVIRONMENTS (Optional - Advanced)**

**Location**: Settings → Environments

- [ ] **Create "production" environment**
  - [ ] Require reviewers: **✅**
  - [ ] Required reviewers: @lead-architect
  - [ ] Deployment branches: main only

- [ ] **Create "staging" environment** (if needed)
  - [ ] Require reviewers: No
  - [ ] Deployment branches: develop

---

## ✅ VERIFICATION STEPS

After completing all configurations:

### **1. Verify Branch Protection**
```
Settings → Branches → main
Look for:
✅ All checkboxes enabled as configured
✅ Status checks listed (after first PR)
```

### **2. Verify CODEOWNERS Works**
```
Create a test PR
Look for:
✅ Workflows start automatically
✅ CODEOWNERS notification appears
✅ Teams are automatically requested as reviewers
```

### **3. Verify Status Checks**
```
Look at PR:
✅ CI Linting checks running
✅ Code review checks running
✅ All workflows complete (after first PR)
✅ Merge button disabled until all pass
```

### **4. Test Merge Prevention**
```
1. Create PR with failing test
2. Try to merge
Look for:
❌ Merge button disabled (GOOD!)
✅ Error message about failing checks
```

### **5. Test Stale Approval Dismissal**
```
1. Get approval on PR
2. Push new commit
3. Look for:
❌ Approval dismissed (GOOD!)
✅ New approval required
```

---

## 🎯 CONFIGURATION BY TEAM

### **Minimal Setup (Solo Dev)**
- [ ] Branch protection for main
- [ ] Require 1 approval
- [ ] Require status checks
- [ ] Auto-delete branches

### **Small Team (2-5 people)**
- All minimal setup, plus:
- [ ] Add teams
- [ ] CODEOWNERS file
- [ ] Code security enabled
- [ ] Conversation resolution

### **Medium Team (5-10 people)**
- All small team setup, plus:
- [ ] Require CODEOWNERS review
- [ ] Require 2 approvals for critical files
- [ ] Secret scanning
- [ ] Code scanning (if available)

### **Large Team (10+ people)**
- All medium team setup, plus:
- [ ] Environments (production, staging)
- [ ] Environment approvals
- [ ] Advanced security features
- [ ] Additional branch protections

---

## 🚨 COMMON MISTAKES TO AVOID

❌ **Don't**: Forget to enable "Require CODEOWNERS review"
✅ **Do**: Enable it after verifying `.github/CODEOWNERS` is committed

❌ **Don't**: Skip status checks
✅ **Do**: Add them after first workflow run

❌ **Don't**: Allow force pushes to main
✅ **Do**: Keep them disabled for safety

❌ **Don't**: Forget to add users to GitHub teams
✅ **Do**: Make sure users are team members for CODEOWNERS to work

❌ **Don't**: Configure rules without testing
✅ **Do**: Test with a PR to verify everything works

---

## 📊 CONFIGURATION SUMMARY TABLE

| Setting | Location | Value | Why |
|---------|----------|-------|-----|
| Branch rule | Settings → Branches | main | Protect main branch |
| Require PR | Branch rule | On | Enforce code review |
| Require approval | Branch rule | 1 (or 2) | Prevent self-merge |
| Require CODEOWNERS | Branch rule | On | Right people review |
| Require status checks | Branch rule | On | Tests must pass |
| Dismiss stale approvals | Branch rule | On | Re-test after changes |
| Conversation resolution | Branch rule | On | Address comments |
| Dependabot | Security → analysis | On | Track dependencies |
| Secret scanning | Security → analysis | On | Prevent secret commits |
| Push protection | Security → analysis | On | Catch secrets before push |
| Auto-merge | Pull requests | On | Merge when ready |
| Delete branches | Pull requests | On | Clean up after merge |

---

## 🎬 STEP-BY-STEP WALKTHROUGH

### **Step 1: Login to GitHub** (1 min)
- Go to repository
- Click Settings (top right)

### **Step 2: Create Branch Protection** (5 min)
- Click "Branches" in left menu
- Click "Add rule"
- Enter: `main`
- Enable all recommended options
- Create rule

### **Step 3: Enable Security** (2 min)
- Click "Code security & analysis"
- Enable Dependabot and secrets
- Wait for options to load

### **Step 4: Add Teams** (3 min)
- Click "Collaborators & teams"
- Add your teams with roles
- Ensure `.github/CODEOWNERS` references them

### **Step 5: Configure Pull Requests** (2 min)
- Click "Pull requests"
- Enable auto-merge and auto-delete branches

### **Step 6: Verify** (2 min)
- Go back to Branches
- Confirm all settings saved
- Rule shows ✅ enabled

### **Step 7: Test** (Variable)
- Create test PR
- Watch workflows run
- Watch CODEOWNERS request review
- Try to merge (should be blocked)

**Total Time**: 15-20 minutes

---

## 📞 QUICK HELP

| Problem | Solution |
|---------|----------|
| "Merge button disabled" | Check PR status - all checks must pass |
| "CODEOWNERS not requesting" | Verify teams exist, users are members |
| "Status checks not showing" | Run first PR - checks appear after |
| "Can't find setting" | Use search in Settings page |
| "Need to modify rule" | Click "Edit" next to rule in Branches |
| "Want to delete rule" | Click "Delete" next to rule in Branches |

---

## ✅ FINAL VERIFICATION

Once complete, your GitHub will:

✅ Enforce code reviews (no direct pushes to main)  
✅ Require CODEOWNERS approval  
✅ Run automated checks  
✅ Block merge if tests fail  
✅ Dismiss stale approvals  
✅ Require conversation resolution  
✅ Track security issues  
✅ Clean up branches after merge  

---

## 🎉 YOU'RE DONE!

Your repository is now professionally configured.

**What happens next**:
1. Open a PR
2. Watch workflows run
3. Watch CODEOWNERS request review
4. Fix any issues
5. Get approval
6. Merge when ready

**Enjoy better code quality! 🚀**

---

**Reference**: 
- Detailed guide: `docs/GITHUB_SETTINGS_CONFIGURATION.md`
- Quick visual guide: `docs/GITHUB_SETTINGS_QUICK_SETUP.md`
