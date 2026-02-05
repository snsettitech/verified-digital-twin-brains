# GitHub Settings - Visual Quick Guide

**Time to Complete**: 15-20 minutes

---

## 🎯 PATH TO SETTINGS

```
Repository Home
    ↓
[Settings] (top right navigation)
    ↓
Left Sidebar:
├─ Branches ← START HERE
├─ Code security & analysis
├─ Collaborators & teams
├─ Pull requests
├─ Notifications
└─ Secrets and variables
```

---

## 1️⃣ BRANCHES PROTECTION (Most Important!)

**Go to**: Settings → **Branches** (left sidebar)

### **Click: "Add rule"**

```
┌─────────────────────────────────────────┐
│ Branch name pattern                      │
│ [main                                   │] ← Type: main
│                                          │
│ ☑ Require a pull request before merging │
│   ├─ Require 1 approval                 │
│   ├─ ☑ Dismiss stale approvals          │
│   └─ ☑ Require CODEOWNERS review        │
│                                          │
│ ☑ Require status checks to pass         │
│   ├─ ☑ Require up to date before merge  │
│   └─ Status checks: [see list below]    │
│                                          │
│ ☑ Require conversation resolution       │
│                                          │
│ ☑ Allow force pushes: ❌                │
│ ☑ Allow deletions: ❌                   │
│                                          │
│ [Create] [Cancel]                       │
└─────────────────────────────────────────┘
```

### **Status Checks to Add** (after first workflow run):
```
☑ CI Linting / lint-backend
☑ CI Linting / lint-frontend
☑ code-review / code-quality
☑ code-review / security-scan
☑ code-review / pr-validation
☑ code-review / architecture-impact
☑ code-review / test-coverage
☑ code-review / migration-check
☑ code-review / config-validation
```

---

## 2️⃣ CODE SECURITY & ANALYSIS

**Go to**: Settings → **Code security & analysis**

### **Enable These**:
```
☑ Dependabot alerts
☑ Dependabot security updates
☑ Secret scanning
☑ Push protection
☑ Code scanning (if available)
```

---

## 3️⃣ COLLABORATORS & TEAMS

**Go to**: Settings → **Collaborators & teams**

### **Add Teams**:
```
Team Name              Role        Permissions
────────────────────────────────────────────
@backend-team          Admin       Full access
@frontend-team         Admin       Full access
@lead-architect        Admin       Full access
@devops-team           Admin       Full access
@qa-team               Write       Review only
```

---

## 4️⃣ PULL REQUESTS SETTINGS

**Go to**: Settings → **Pull requests**

### **Enable These**:
```
☑ Allow auto-merge
  → Select: "Auto-merge pull requests"

☑ Allow squash merging
☑ Allow rebase merging  
☑ Allow merge commits

☑ Automatically delete head branches
  (Clean up merged branches)
```

---

## 5️⃣ NOTIFICATIONS (Optional)

**Go to**: Settings → **Notifications**

### **Configure**:
```
☑ Include your own updates
☑ Include conversations you're part of
☑ Include PR reviews you're requested for
```

---

## 6️⃣ SECRETS & VARIABLES (If Needed)

**Go to**: Settings → **Secrets and variables** → **Actions**

### **Add Secrets** (if not in .env):
```
Name                    Example
─────────────────────────────────────
SUPABASE_URL           https://xxx.supabase.co
OPENAI_API_KEY         sk-...
PINECONE_API_KEY       pinecone-key
JWT_SECRET             your-jwt-secret
```

---

## ✅ VERIFICATION CHECKLIST

After completing all steps, verify:

```
BRANCH PROTECTION
☐ Rule created for 'main'
☐ Require PR before merge: ON
☐ Require 1 approval: ON
☐ Require CODEOWNERS review: ON
☐ Require status checks: ON
☐ Dismiss stale approvals: ON
☐ Conversation resolution: ON

SECURITY
☐ Dependabot alerts: ON
☐ Secret scanning: ON
☐ Push protection: ON
☐ Code scanning: ON (if available)

TEAMS
☐ Teams created in GitHub
☐ Users added to appropriate teams
☐ .github/CODEOWNERS file references correct teams

PULL REQUESTS
☐ Auto-merge enabled
☐ Delete head branches enabled

ACTIONS
☐ Workflows can run (not disabled)
☐ Status checks will appear after first PR
```

---

## 🧪 TEST IT OUT

Once configured, test with a PR:

1. **Create test branch**:
   ```bash
   git checkout -b test/code-review-setup
   echo "test" > test.txt
   git add test.txt
   git commit -m "test: verify code review system"
   git push origin test/code-review-setup
   ```

2. **Open PR on GitHub**
   - Notice: Workflows run automatically
   - Notice: CODEOWNERS automatically requested
   - Notice: Status checks must pass before merge

3. **Verify**:
   - ✅ Workflows run?
   - ✅ CODEOWNERS requested?
   - ✅ Status checks appear?
   - ✅ Can't merge without approval?

4. **Cleanup**:
   ```bash
   git branch -D test/code-review-setup
   ```

---

## 🚨 TROUBLESHOOTING

### Problem: "Merge button disabled but everything looks right"

**Check**:
- [ ] Is CI workflow passing? (green checkmark)
- [ ] Has CODEOWNERS approved? (check review status)
- [ ] Is branch up to date? (compare with main)
- [ ] Are conversations resolved? (check comments)

### Problem: "Status checks not appearing"

**Solution**: 
- Run first PR to trigger workflows
- Workflows will create status checks
- Then add them to required checks

### Problem: "CODEOWNERS not requesting review"

**Check**:
- [ ] `.github/CODEOWNERS` file exists?
- [ ] Team names match GitHub teams?
- [ ] Users are in those teams?
- [ ] File is committed to main?

### Problem: "Can't enforce CODEOWNERS"

**Solution**:
- `Require status checks` must also be ON
- Then enable `Require CODEOWNERS review`

---

## 📊 WHAT HAPPENS AFTER SETUP

### When Someone Opens a PR:

```
1. GitHub triggers workflows
   ↓
2. All checks run in parallel
   ├─ Code quality (linting, types)
   ├─ Security scanning
   ├─ Architecture analysis
   ├─ Test coverage
   └─ PR validation
   ↓
3. CODEOWNERS automatically requested
   ├─ backend-team if backend/ changed
   ├─ frontend-team if frontend/ changed
   └─ lead-architect if critical files changed
   ↓
4. PR shows status:
   ├─ ⏳ Waiting for status checks
   ├─ 🔴 Some checks failing
   ├─ ✅ All checks passing
   └─ 👥 Waiting for reviewers
   ↓
5. When all requirements met:
   → [Merge Pull Request] button enabled
   ↓
6. After merge:
   → Branch automatically deleted (if configured)
   → Workflows run on main (CI/CD)
```

---

## 💡 KEY SETTINGS EXPLAINED

| Setting | Purpose | Recommended |
|---------|---------|-------------|
| Require PR | Ensures code review | ✅ Always |
| Require approvals | Someone must approve | ✅ 1-2 |
| Require CODEOWNERS | Right people review | ✅ Always |
| Require status checks | Tests must pass | ✅ Always |
| Dismiss stale approvals | Re-test after changes | ✅ Always |
| Conversation resolution | Address comments | ✅ Always |
| Require up to date | Merge conflicts resolved | ✅ Always |
| Push protection | Secrets caught before push | ✅ Always |
| Auto-merge | Merge when ready | 🟡 Optional |
| Delete head branches | Clean up | ✅ Recommended |

---

## 🎯 MINIMUM VIABLE SETUP

If you only have 5 minutes, configure:

1. **Branch Protection** (Settings → Branches)
   - Rule for: `main`
   - ✅ Require PR
   - ✅ Require 1 approval
   - ✅ Require status checks (add after first PR)

2. **Code Security** (Settings → Code security)
   - ✅ Dependabot alerts
   - ✅ Secret scanning

3. **Teams** (Settings → Collaborators & teams)
   - Add teams with appropriate roles

---

## ✨ FULL SETUP

If you have 20 minutes, also configure:

Everything above, plus:

4. **Require CODEOWNERS** (in Branch Protection)
   - Requires `.github/CODEOWNERS` configured
   - Automatic request to right reviewers

5. **Conversation Resolution** (in Branch Protection)
   - Comments must be resolved

6. **Auto-merge** (in Pull Requests)
   - Auto-merge when all checks pass

7. **Delete Head Branches** (in Pull Requests)
   - Clean up after merge

8. **Code Scanning** (if available)
   - GitHub Advanced Security

---

## 📞 QUICK REFERENCE

| Need | Go To |
|------|-------|
| Require PR/approvals | Settings → Branches → Edit rule |
| Require CODEOWNERS | Settings → Branches → Edit rule → Check "Require CODEOWNERS" |
| Add status checks | Settings → Branches → Edit rule → Add checks (after first PR) |
| Enable security | Settings → Code security & analysis |
| Manage teams | Settings → Collaborators & teams |
| View GitHub docs | github.com/docs/repositories |

---

## 🎉 YOU'RE ALL SET!

Your repository is now protected and configured for professional code reviews.

**Next Steps**:
1. Open your first PR
2. Watch the system work
3. Share CODE_REVIEW_QUICK_REFERENCE with reviewers
4. Enjoy better code quality!

---

**Questions?** See `docs/GITHUB_SETTINGS_CONFIGURATION.md` for detailed explanations
