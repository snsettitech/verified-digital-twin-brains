# GitHub Repository Settings Configuration

> **Date**: February 4, 2026  
> **Purpose**: Configure GitHub to enforce code review standards  
> **Time Required**: 15-20 minutes

---

## 🎯 Step-by-Step GitHub Configuration

### **STEP 1: Access Repository Settings**

1. Go to your repository on GitHub
2. Click **Settings** (top navigation)
3. In left sidebar, click **Branches**

---

## 📋 STEP 2: Create Branch Protection Rule for `main`

### **2.1 Add Rule**
```
1. Click "Add rule" button
2. Enter branch name pattern: main
3. Click "Create"
```

### **2.2 Configure Basic Settings**

Enable these checkboxes:

✅ **Require a pull request before merging**
- Require approvals: **1** (or 2 for strict teams)
- Dismiss stale pull request approvals when new commits are pushed: **✅**
- Require review from Code Owners: **✅**
- Require approval of the most recent reviewable push: **✅**

✅ **Require status checks to pass before merging**
- Require branches to be up to date before merging: **✅**
- Status checks that must pass:
  - `CI Linting / lint-backend` ✅
  - `CI Linting / lint-frontend` ✅
  - Any other status checks from `.github/workflows/`

✅ **Require code reviews**
- Require at least 1 approval
- (Or 2 for critical repos)

✅ **Require conversation resolution**
- Conversations must be resolved before merging: **✅**

---

## 🔒 STEP 3: Additional Security Settings

### **3.1 Go to: Settings → Code Security & Analysis**

Enable:
```
☑ Dependabot alerts
☑ Dependabot security updates
☑ Secret scanning
☑ Push protection
```

### **3.2 Go to: Settings → Security & Analysis → GitHub Advanced Security**

Enable (if available):
```
☑ Code scanning
☑ Secret scanning (push protection)
☑ Dependency graph
```

---

## 👥 STEP 4: Collaborators & Teams

### **4.1 Go to: Settings → Collaborators & Teams**

Add teams with appropriate permissions:
```
@backend-team         → Admin
@frontend-team        → Admin
@lead-architect       → Admin
@devops-team          → Admin
@qa-team              → Write (review-only)
```

### **4.2 Verify CODEOWNERS** (Already created!)
- Location: `.github/CODEOWNERS`
- This automatically requests reviews from specified teams
- GitHub will request approval from these reviewers

---

## 🔧 STEP 5: Status Checks Configuration

### **5.1 Under "Status checks that must pass":**

These should appear automatically once workflows run. Add:
```
✅ CI Linting / lint-backend
✅ CI Linting / lint-frontend
✅ code-review / code-quality
✅ code-review / security-scan
✅ code-review / pr-validation
✅ code-review / architecture-impact
✅ code-review / test-coverage
✅ code-review / migration-check
✅ code-review / config-validation
```

**Note**: Status checks appear after first workflow run

---

## 📝 STEP 6: Pull Request Settings

### **Go to: Settings → Pull Requests**

Enable:
```
☑ Allow auto-merge
  → Select: Auto-merge pull requests (GitHub will automatically merge when all requirements are met)
  
☑ Allow squash merging
☑ Allow rebase merging
☑ Allow merge commits

Delete head branches:
☑ Automatically delete head branches (clean up after merge)
```

---

## 📧 STEP 7: Notifications

### **Go to: Settings → Notifications**

Configure for team:
```
Default notification settings:
→ Watching: Include your own updates
→ Participating: Include conversations you're part of
→ Pull request reviews: Include when you're requested
```

---

## 🔑 STEP 8: Repository Secrets

### **Go to: Settings → Secrets and Variables → Actions**

Add any needed secrets:
```
SUPABASE_URL
SUPABASE_KEY
OPENAI_API_KEY
PINECONE_API_KEY
JWT_SECRET
```

**Note**: Most should come from environment, not secrets

---

## 🚀 STEP 9: Environments (Optional)

### **Go to: Settings → Environments**

Create environments:
```
1. production
   - Require reviewers: Yes
   - Required reviewers: @lead-architect, 1 other
   - Deployment branches: main

2. staging
   - Require reviewers: No
   - Deployment branches: develop
```

---

## ✅ FINAL CHECKLIST

Run through this to verify everything is set up:

### **Branch Protection**
- [ ] Branch protection rule created for `main`
- [ ] Require PR before merging: ✅
- [ ] Require code reviews: ✅
- [ ] Require CODEOWNERS review: ✅
- [ ] Require status checks: ✅
- [ ] Dismiss stale approvals: ✅
- [ ] Require conversation resolution: ✅

### **Security**
- [ ] Dependabot enabled
- [ ] Secret scanning enabled
- [ ] Code scanning enabled (if available)
- [ ] Push protection enabled

### **Access Control**
- [ ] Teams created and assigned roles
- [ ] CODEOWNERS file configured (.github/CODEOWNERS)
- [ ] Required status checks configured

### **Workflow Settings**
- [ ] Auto-merge enabled (optional)
- [ ] Delete head branches enabled
- [ ] Notifications configured

### **GitHub Actions**
- [ ] Workflows can run (Settings → Actions → Allow all actions)
- [ ] Status checks appear (after first PR)

---

## 🎯 QUICK REFERENCE: Before/After

### **BEFORE** (Without Configuration)
```
❌ Anyone can push to main
❌ No code review required
❌ No security checks
❌ PRs can merge with failing tests
❌ No status check validation
```

### **AFTER** (With Configuration)
```
✅ PRs required before merging to main
✅ CODEOWNERS must approve
✅ Security checks pass
✅ All status checks pass
✅ Conversations resolved
✅ Up-to-date with main
```

---

## 📊 Expected GitHub UI After Setup

### **Branch Protection Rule for `main`**
```
✓ Require pull requests: 1 approval
✓ Dismiss stale approvals: Enabled
✓ Require CODEOWNERS review: Enabled
✓ Require status checks:
  ├─ CI Linting / lint-backend
  ├─ CI Linting / lint-frontend
  ├─ code-review / code-quality
  ├─ code-review / security-scan
  ├─ code-review / pr-validation
  ├─ code-review / architecture-impact
  ├─ code-review / test-coverage
  ├─ code-review / migration-check
  └─ code-review / config-validation
✓ Require conversation resolution: Enabled
✓ Require branches up to date: Enabled
```

---

## 🚨 COMMON ISSUES & SOLUTIONS

### **Issue: "Status check not available"**
**Solution**: Run a PR first to trigger workflow, then add to required checks

### **Issue: "CODEOWNERS not requesting review"**
**Solution**: 
1. Verify `.github/CODEOWNERS` file exists
2. Verify team names in CODEOWNERS match GitHub teams
3. Users must be in those GitHub teams

### **Issue: "Merge button disabled but rules look correct"**
**Solution**: Check:
- CI/workflow status (green checkmarks)
- PR approvals (at least 1 review)
- Conversations resolved
- Branch is up to date with main

### **Issue: "Can't dismiss approvals when new commits pushed"**
**Solution**: 
- This option only works if "Require status checks" is also enabled
- Make sure `.github/workflows/lint.yml` is active

---

## 📖 Configuration by Team Size

### **Small Team (1-3 reviewers)**
```
Require approvals: 1
Require CODEOWNERS: ✅
Status checks: All
Conversation resolution: ✅
```

### **Medium Team (4-10 reviewers)**
```
Require approvals: 1 (or 2 for main)
Require CODEOWNERS: ✅
Status checks: All
Conversation resolution: ✅
Code scanning: ✅
```

### **Large Team (10+ reviewers)**
```
Require approvals: 2
Require CODEOWNERS: ✅
Status checks: All
Conversation resolution: ✅
Code scanning: ✅
Environments: production + staging
Deployments: Require approval
```

---

## 🎓 Settings Explanation

### **Why Require CODEOWNERS Review?**
- Ensures right people review right code
- Security-sensitive files get architect review
- Prevents knowledge silos
- Enforces team standards

### **Why Dismiss Stale Approvals?**
- New code needs new approval
- Prevents approving untested changes
- Catches regressions

### **Why Require Status Checks?**
- Prevents broken code merges
- Ensures tests pass
- Catches security issues
- Validates PR quality

### **Why Require Conversation Resolution?**
- Ensures review comments addressed
- Prevents "LGTM but..." situations
- Creates paper trail of decisions

---

## 🔐 Security Best Practices

### **Minimum Recommended Settings**
```
For all repositories:
✅ Require 1 approval
✅ Require CODEOWNERS
✅ Require status checks (all)
✅ Dismiss stale approvals
✅ Secret scanning enabled
✅ Dependabot enabled
```

### **For Production-Critical Repos**
```
Additional:
✅ Require 2 approvals
✅ Require conversation resolution
✅ Require up-to-date branch
✅ Code scanning enabled
✅ Environment approvals
✅ Protected environment secrets
```

---

## 📞 Quick Links

**GitHub Documentation:**
- [Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
- [CODEOWNERS File](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/requiring-status-checks-before-merging)

---

## ✅ AFTER CONFIGURATION

Once complete, your GitHub will:
1. ✅ Enforce code reviews via CODEOWNERS
2. ✅ Run automated checks on every PR
3. ✅ Block merge if any checks fail
4. ✅ Require status checks to pass
5. ✅ Clean up branches after merge
6. ✅ Track all code changes with audit trail

---

## 🎉 YOU'RE DONE!

Your repository is now configured for professional code reviews with:
- ✅ Branch protection
- ✅ Code review enforcement
- ✅ Automated status checks
- ✅ Security scanning
- ✅ Team-based access control

**Next**: Run your first PR through the new system and watch it work! 🚀
