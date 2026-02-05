# GitHub Actions-Based PR Enforcement Rules

This document defines how GitHub Actions enforces PR requirements without needing GitHub Pro branch protection rules.

---

## 🎯 ENFORCEMENT WORKFLOW

### 1. PR Requirements Check (on every PR)
- ✅ PR title must be meaningful (min 10 characters)
- ✅ PR description must be provided (not empty)
- ✅ CODEOWNERS file automatically assigns reviewers based on files changed

### 2. Status Checks (Required)
All of the following must pass before merge:
- Code quality checks
- Security audit
- Architecture validation
- Test coverage
- Build validation

### 3. Code Owner Review
- Automatically assigned based on CODEOWNERS file
- Backend changes → @backend-team + @lead-architect
- Frontend changes → @frontend-team
- Database changes → @devops-team
- Documentation changes → @technical-writers
- Critical files → @lead-architect

### 4. Conversation Resolution
- All discussions must be resolved
- PR comments must be addressed
- No pending changes requested

### 5. Merge Requirements
- All status checks passed
- At least 1 code owner approval
- No unresolved conversations
- All deployments successful

---

## 📋 WORKFLOW FILES

### `.github/workflows/pr-requirements-check.yml`
Validates PR on creation/update:
- Checks PR title length
- Checks PR description exists
- Auto-assigns CODEOWNERS
- Comments with requirements if missing

### `.github/workflows/enforce-pr-requirements.yml`
Enforces requirements throughout PR lifecycle:
- Validates code changes
- Checks for secrets
- Validates file sizes
- Assigns automatic reviews

### `.github/workflows/merge-enforcement.yml`
Prevents merge if requirements not met:
- Checks all status checks passed
- Verifies conversations resolved
- Counts approvals
- Generates merge readiness report

---

## 🔍 ENFORCEMENT RULES BY FILE TYPE

### Backend Python Files
- ✅ Python syntax validation
- ✅ Import validation
- ✅ Code quality checks
- ✅ Security scanning
- ✅ Requires: @backend-team + @lead-architect review

### Frontend TypeScript/TSX Files
- ✅ TypeScript strict mode checks
- ✅ Linting (ESLint)
- ✅ Type safety checks
- ✅ Requires: @frontend-team review

### Database Migrations
- ✅ SQL syntax validation
- ✅ Migration naming convention check
- ✅ Rollback validation
- ✅ Requires: @devops-team + @lead-architect review

### Configuration Files
- ✅ YAML validation
- ✅ JSON validation
- ✅ No hardcoded secrets
- ✅ Requires: @devops-team review

### Documentation
- ✅ Markdown linting
- ✅ Link validation
- ✅ Requires: @technical-writers review

---

## 🚀 HOW TO USE

### Creating a PR
1. Create feature branch
2. Make changes
3. Push to GitHub
4. Open PR
5. GitHub Actions automatically:
   - ✅ Validates PR requirements
   - ✅ Runs all checks
   - ✅ Assigns reviewers via CODEOWNERS
   - ✅ Comments with status

### During Code Review
1. Code owners review automatically assigned
2. Approval required from all assigned reviewers
3. Status checks must all pass
4. Conversations must be resolved
5. Can request changes if needed

### Merging
1. PR must have all statuses green ✅
2. All reviewers must approve
3. No pending changes requested
4. All conversations resolved
5. Can then merge via "Squash and merge" or "Rebase and merge"

---

## ⚙️ CONFIGURABLE RULES

Edit `.github/workflows/` files to customize:

### PR Title Requirements
```yaml
- name: Check PR Title
  run: |
    TITLE="${{ github.event.pull_request.title }}"
    if [ ${#TITLE} -lt 10 ]; then
      echo "valid_title=false" >> $GITHUB_OUTPUT
      exit 1
    fi
```
Change `10` to different minimum length

### Status Checks Required
Edit `enforce-pr-requirements.yml`:
```yaml
contexts:
  - "code-quality"
  - "security-audit"
  - "architecture-check"
  - "test-coverage"
  - "validation"
```
Add/remove required checks here

### Code Owner Assignments
Edit `.github/CODEOWNERS`:
```
/backend/ @backend-team @lead-architect
/frontend/ @frontend-team
/database/ @devops-team
```
Add new patterns or modify team assignments

---

## ✅ VERIFICATION

### Check Enforcement is Active
1. Create test PR
2. Leave title < 10 characters
3. Leave description empty
4. GitHub Actions will:
   - ✅ Comment with requirements
   - ✅ Block merge until fixed
   - ✅ Assign reviewers

### Monitor Enforcement
- Go to PR → Checks tab
- See all running status checks
- See enforcement comments
- Review assignment status

---

## 📊 ENFORCEMENT MATRIX

| Requirement | Who | When | Enforcement |
|-------------|-----|------|------------|
| PR Title | Submitter | On PR open | GH Actions comment |
| PR Description | Submitter | On PR open | GH Actions comment |
| Code Quality | Automation | On push | Status check |
| Security Scan | Automation | On push | Status check |
| Approvals | Reviewers | On review | GH Actions check |
| Conversations | All | Before merge | GH Actions block |
| All Checks Pass | Automation | Before merge | GH Actions block |

---

## 🎓 EXAMPLES

### Example 1: Backend PR (Approved & Ready)
```
PR Title: Add authentication token validation to API routes
Description: Implements JWT validation checking...

Status Checks:
  ✅ Code Quality
  ✅ Security Audit  
  ✅ Architecture Check
  ✅ Tests (85% coverage)
  ✅ Build

Assigned Reviewers:
  ✅ @backend-team (approved by 2)
  ✅ @lead-architect (approved)

Conversations: All resolved

Result: ✅ READY TO MERGE
```

### Example 2: Frontend PR (Waiting for Review)
```
PR Title: Refactor dashboard component layout

Status Checks:
  ✅ Code Quality
  ✅ Security Audit
  ✅ Lint (TypeScript)
  ✅ Build
  ⏳ E2E Tests (running)

Assigned Reviewers:
  ⏳ @frontend-team (no response yet)

Result: ⏳ WAITING FOR APPROVAL
```

### Example 3: Database PR (Changes Requested)
```
PR Title: Migrate users table to new schema

Status Checks:
  ✅ Code Quality
  ✅ Security Audit
  ❌ Migration Validation (missing rollback)

Assigned Reviewers:
  ❌ @devops-team (changes requested)

Result: ❌ REQUIRES CHANGES
```

---

## 🔧 TROUBLESHOOTING

### PR Checks Stuck
- Go to PR → Checks tab
- Click "Re-run" on failed checks
- Wait for re-run to complete

### CODEOWNERS Not Assigning
- Check `.github/CODEOWNERS` syntax
- Verify team exists in org
- Try force-pushing commit

### Status Checks Failing
- Click on check for details
- Fix issue locally
- Push new commit
- Check will re-run automatically

### Need to Override
- Only repo admins can override enforcement
- Go to PR → Merge anyway
- Not recommended for production

---

## 📞 SUPPORT

- **PR Requirements:** Check `.github/workflows/pr-requirements-check.yml`
- **Enforcement Rules:** Check `.github/workflows/enforce-pr-requirements.yml`
- **Reviewer Assignment:** Check `.github/CODEOWNERS`
- **Merge Rules:** Check `.github/workflows/merge-enforcement.yml`

---

## ✨ BENEFITS

✅ **No Pro Plan Required** - Free, built-in to GitHub  
✅ **Fully Customizable** - Edit workflows to match your needs  
✅ **Clear Feedback** - Detailed comments explain what's needed  
✅ **Automatic Reviewers** - CODEOWNERS assigns based on changes  
✅ **Transparent** - All rules visible in workflows  
✅ **Flexible** - Can add custom checks as needed  

