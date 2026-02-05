# Enterprise GitHub Setup Upgrade Guide

**Status**: Current setup is development-ready but lacks enterprise governance  
**Priority**: High (before scaling team/users)  
**Estimated Effort**: 8-12 hours for full implementation

---

## 📊 Current State Analysis

### ✅ What You Have
- **CI/CD Workflows**: 2 workflows (lint.yml, checkpoint.yml)
- **Branch Protection**: Not visible in config (may exist)
- **Code Review Config**: CodeRabbit YAML for AI-assisted reviews
- **PR Template**: Comprehensive checklist (PULL_REQUEST_TEMPLATE.md)
- **Environment Management**: Per-stage setup documented
- **Security**: RLS policies, multi-tenant isolation, JWT validation
- **Testing**: Backend (pytest), Frontend (eslint, typecheck, build)

### ❌ What's Missing (Enterprise Gaps)
1. **Branch Protection Rules** - No enforcement on main branch
2. **Code Owner Approvals** - No CODEOWNERS file for automatic reviewer assignment
3. **Security Policy** - No SECURITY.md for responsible disclosure
4. **Secrets Scanning** - No automated secret detection in commits
5. **Dependency Scanning** - No automated dependency vulnerability scanning
6. **Release Management** - Manual release process
7. **Staging Environment** - Only local dev and production
8. **Monitoring & Alerting** - No failure notifications/alerts
9. **Deployment Approvals** - No manual gate before production
10. **Audit Logging** - No detailed audit trail of deployments

---

## 🎯 Enterprise Upgrade Roadmap

### Phase 1: Branch Protection & Governance (2-3 hours)
**Goal**: Prevent direct pushes to main, enforce code review

#### 1.1 Create CODEOWNERS File
```
# .github/CODEOWNERS
# Define mandatory code reviewers

# Core security
/backend/modules/auth_guard.py @core-team
/backend/modules/observability.py @core-team
/backend/modules/clients.py @core-team
/backend/modules/_core/ @core-team

# Database
/backend/database/migrations/ @database-team
/backend/database/schema/ @database-team

# Frontend auth
/frontend/middleware.ts @core-team
/frontend/lib/supabase/ @core-team

# API contracts
/docs/architecture/api-contracts.md @api-team
```

**Implementation**:
1. Create `.github/CODEOWNERS`
2. Add GitHub teams to your organization
3. In repository settings → Branches → Branch protection rules

#### 1.2 Branch Protection Rules
Configure for `main` branch:
- ✅ Require pull request reviews (minimum 1-2 reviewers)
- ✅ Require code owner reviews (for CODEOWNERS paths)
- ✅ Require status checks to pass:
  - `lint-backend` ✓
  - `lint-frontend` ✓
- ✅ Require branches to be up to date before merge
- ✅ Require conversation resolution before merge
- ✅ Require linear history
- ✅ Lock `main` branch (only admins can push)
- ✅ Auto-delete head branches after merge

**Settings Path**: Repository → Settings → Branches → Add Rule → Branch name pattern: `main`

---

### Phase 2: Security & Secrets Scanning (1-2 hours)
**Goal**: Prevent credential leaks, automated vulnerability detection

#### 2.1 Add SECURITY.md
```markdown
# Security Policy

## Reporting Security Vulnerabilities

**Do NOT open public issues for security vulnerabilities.**

Instead, email security@yourdomain.com with:
- Description of vulnerability
- Affected components/versions
- Steps to reproduce
- Potential impact

We will:
1. Acknowledge receipt within 24 hours
2. Provide fix timeline
3. Credit you (if desired)

## Security Contacts
- @security-team (GitHub team)

## Supported Versions
- Version 1.x: Receiving security updates
- Version 0.x: No longer supported

## Security Best Practices
- Use `.env` files locally (never commit)
- Store secrets in GitHub Secrets/Actions
- Use Supabase RLS policies (mandatory)
- Filter all queries by `tenant_id`
- Validate JWT tokens (auth_guard.py)
```

#### 2.2 Enable Secret Scanning (GitHub Pro+)
**Automatic**: If on GitHub Pro/Enterprise
- Settings → Security → Secret scanning → Enable

**Alternative: Commit Signing**
```bash
# Configure git to sign all commits
git config --global commit.gpgsign true
git config --global user.signingkey <YOUR_GPG_KEY>

# Enforce in branch protection rules:
# ✅ Require signed commits
```

#### 2.3 Dependabot Configuration
```yaml
# .github/dependabot.yml
version: 2
updates:
  # Python backend
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "04:00"
    open-pull-requests-limit: 5
    reviewers:
      - "backend-team"
    labels:
      - "dependencies"
      - "python"
    version-update-strategy: "increase"
    
  # Node.js frontend
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "04:00"
    open-pull-requests-limit: 5
    reviewers:
      - "frontend-team"
    labels:
      - "dependencies"
      - "javascript"
    version-update-strategy: "increase"
    
  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    labels:
      - "dependencies"
      - "ci-cd"
```

---

### Phase 3: Enhanced CI/CD Workflows (2-3 hours)
**Goal**: Comprehensive testing, staged deployments, automatic alerts

#### 3.1 Add Staging Deployment Workflow
```yaml
# .github/workflows/deploy-staging.yml
name: Deploy to Staging

on:
  workflow_dispatch:  # Manual trigger
  pull_request:
    types: [labeled]
    branches: [main]

jobs:
  deploy-staging:
    if: contains(github.event.pull_request.labels.*.name, 'deploy-staging')
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy Backend to Staging
        env:
          RENDER_DEPLOY_KEY: ${{ secrets.RENDER_DEPLOY_KEY }}
        run: |
          curl -X POST https://api.render.com/deploy/srv-staging \
            -H "Authorization: Bearer $RENDER_DEPLOY_KEY"
      
      - name: Deploy Frontend to Staging
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        run: |
          npx vercel --prod \
            --token=$VERCEL_TOKEN \
            --scope=your-org

      - name: Health Check
        run: |
          sleep 10
          curl -f https://staging.yourapp.com/health || exit 1
      
      - name: Notify Slack
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {"text": "❌ Staging deployment failed"}
```

#### 3.2 Add Production Deployment Workflow
```yaml
# .github/workflows/deploy-production.yml
name: Deploy to Production

on:
  release:
    types: [published]

jobs:
  deploy-production:
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.release.tag_name }}
      
      - name: Deploy Backend
        env:
          RENDER_DEPLOY_KEY: ${{ secrets.RENDER_DEPLOY_KEY }}
        run: |
          curl -X POST https://api.render.com/deploy/srv-prod \
            -H "Authorization: Bearer $RENDER_DEPLOY_KEY"
      
      - name: Deploy Frontend
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        run: |
          npx vercel --prod --token=$VERCEL_TOKEN
      
      - name: Run Smoke Tests
        run: |
          npm install -g playwright
          playwright install
          npx playwright test tests/smoke.spec.ts

      - name: Slack Notification
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "✅ Production deployment: ${{ github.event.release.tag_name }}",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "Release: ${{ github.event.release.html_url }}"
                  }
                }
              ]
            }
```

#### 3.3 Enhanced Linting Workflow
```yaml
# .github/workflows/lint.yml (Updated)
name: CI Linting & Testing

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint-backend:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version-file: 'backend/.python-version'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install flake8 pytest pytest-cov
      
      - name: Lint
        run: |
          cd backend
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
      
      - name: Run tests with coverage
        run: |
          cd backend
          pytest -v --cov=modules --cov-report=xml -m "not network"
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml
          flags: backend
  
  lint-frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version-file: 'frontend/.nvmrc'
          cache: 'npm'
      
      - name: Install dependencies
        run: cd frontend && npm ci
      
      - name: Lint
        run: cd frontend && npm run lint
      
      - name: Type check
        run: cd frontend && npm run typecheck
      
      - name: Build
        run: cd frontend && npm run build
        env:
          NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.STAGING_SUPABASE_URL }}
          NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.STAGING_SUPABASE_ANON_KEY }}
          NEXT_PUBLIC_BACKEND_URL: ${{ secrets.STAGING_BACKEND_URL }}
      
      - name: Unit tests
        run: cd frontend && npm run test || true
  
  security-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      - name: Upload results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

---

### Phase 4: Release & Versioning Management (1-2 hours)
**Goal**: Automated semantic versioning, changelog generation

#### 4.1 Add Release Workflow
```yaml
# .github/workflows/release.yml
name: Release

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version bump (major/minor/patch)'
        required: true
        default: 'patch'

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Determine version
        id: version
        run: |
          # Implement semantic versioning logic
          # Current version from VERSION file or git tags
          CURRENT=$(cat VERSION)
          # Bump based on input
          NEW=$(python scripts/bump_version.py ${{ github.event.inputs.version }} $CURRENT)
          echo "version=$NEW" >> $GITHUB_OUTPUT
      
      - name: Generate changelog
        uses: orhun/git-cliff-action@v2
        with:
          config: cliff.toml
          args: --latest --tag ${{ steps.version.outputs.version }}
      
      - name: Create release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: v${{ steps.version.outputs.version }}
          body_path: CHANGELOG.md
          draft: false
          prerelease: false
```

#### 4.2 Add VERSION File
```
# VERSION file at root
1.0.0
```

---

### Phase 5: Monitoring & Observability (1-2 hours)
**Goal**: Track deployments, monitor health, alert on failures

#### 5.1 Add Deployment Tracking
```yaml
# .github/workflows/track-deployment.yml
name: Track Deployment

on:
  workflow_run:
    workflows:
      - Deploy to Production
    types:
      - completed

jobs:
  track:
    runs-on: ubuntu-latest
    if: github.event.workflow_run.conclusion == 'success'
    
    steps:
      - name: Log deployment
        env:
          DEPLOYMENT_API: ${{ secrets.DEPLOYMENT_API_URL }}
        run: |
          curl -X POST $DEPLOYMENT_API \
            -H "Authorization: Bearer ${{ secrets.DEPLOYMENT_TOKEN }}" \
            -d '{
              "status": "success",
              "version": "${{ github.event.workflow_run.head_commit.message }}",
              "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
            }'
      
      - name: Health check alert
        run: |
          sleep 30
          STATUS=$(curl -s https://yourapp.com/health | jq -r '.status')
          if [ "$STATUS" != "ok" ]; then
            echo "Health check failed!"
            exit 1
          fi
```

#### 5.2 Add GitHub Status Checks
In `backend/main.py` and `backend/routers/observability.py`:
```python
# Ensure /health endpoint returns:
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-02-03T10:00:00Z",
  "services": {
    "supabase": "ok",
    "openai": "ok",
    "pinecone": "ok"
  }
}
```

---

## 📋 Implementation Checklist

### Before You Start
- [ ] Team members have GitHub accounts
- [ ] You have at least 2 people to handle reviews
- [ ] Slack workspace integrated (optional but recommended)
- [ ] Rendering/Railway accounts connected

### Phase 1: Branch Protection
- [ ] Create `.github/CODEOWNERS`
- [ ] Create GitHub teams (core-team, backend-team, frontend-team)
- [ ] Configure branch protection rules for `main`
- [ ] Test: Try pushing directly to main (should be blocked)

### Phase 2: Security
- [ ] Create `.github/SECURITY.md`
- [ ] Create `.github/dependabot.yml`
- [ ] Enable secret scanning (if available)
- [ ] Configure commit signing (optional)

### Phase 3: CI/CD
- [ ] Update `.github/workflows/lint.yml` with coverage
- [ ] Add `.github/workflows/deploy-staging.yml`
- [ ] Add `.github/workflows/deploy-production.yml`
- [ ] Create environment secrets (staging vs production)
- [ ] Test staging deployment manually

### Phase 4: Releases
- [ ] Add VERSION file
- [ ] Add `.github/workflows/release.yml`
- [ ] Configure git-cliff (cliff.toml)
- [ ] Test: Create a release manually

### Phase 5: Monitoring
- [ ] Add `.github/workflows/track-deployment.yml`
- [ ] Verify `/health` endpoint working
- [ ] Set up Slack notifications (optional)
- [ ] Test: Deploy and watch notifications

---

## 🔐 GitHub Secrets to Configure

Create in Repository → Settings → Secrets and Variables → Actions:

**Production Secrets**:
- `RENDER_DEPLOY_KEY` - Render API key
- `VERCEL_TOKEN` - Vercel API token
- `PROD_SUPABASE_URL` - Production Supabase URL
- `PROD_SUPABASE_SERVICE_KEY` - Service role key
- `PROD_OPENAI_API_KEY` - OpenAI API key
- `PROD_PINECONE_API_KEY` - Pinecone API key

**Staging Secrets**:
- `STAGING_SUPABASE_URL`
- `STAGING_SUPABASE_ANON_KEY`
- `STAGING_BACKEND_URL`

**Notifications**:
- `SLACK_WEBHOOK_URL` - For Slack notifications
- `DEPLOYMENT_TOKEN` - For tracking API

---

## 🎯 Success Criteria

After implementing all phases, you should have:

✅ **Governance**
- [ ] No direct pushes to main
- [ ] All merges require code review
- [ ] Core team auto-assigned for security paths
- [ ] Linear history on main branch

✅ **Security**
- [ ] No credentials in git history
- [ ] Dependency vulnerabilities tracked
- [ ] Security policy documented
- [ ] Signed commits optional/enforced

✅ **Reliability**
- [ ] All tests pass before merge
- [ ] Staging environment before production
- [ ] Automated rollback capability
- [ ] Health checks on deployment

✅ **Observability**
- [ ] Deployment tracking
- [ ] Release notes auto-generated
- [ ] Slack notifications
- [ ] Version history clear

---

## 📚 Additional Resources

- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
- [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub Environments](https://docs.github.com/en/actions/deployment/targeting-different-environments)
- [Dependabot](https://docs.github.com/en/code-security/dependabot)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

## 🚀 Quick Start (Minimum Viable Enterprise Setup)

If you only have 2-3 hours, do this:

1. **Branch Protection** (30 min)
   - Create `.github/CODEOWNERS`
   - Enable branch protection on main
   - Require 1 approver

2. **Security Policy** (15 min)
   - Create `.github/SECURITY.md`
   - Add `.github/dependabot.yml`

3. **Enhanced CI** (1 hour)
   - Update lint.yml with coverage
   - Add basic staging deploy workflow

**Result**: Core governance + security basics = 1.5 hours to enterprise baseline

---

## 📈 Maturity Progression

| Level | Features | Timeline |
|-------|----------|----------|
| **Development** | CI/CD, PR template | Current |
| **Staging** | + Branch protection, staging deploy | +2h |
| **Early Enterprise** | + Secrets scanning, codeowners | +2h |
| **Enterprise** | + Releases, monitoring, environments | +6h |
| **SOC2/Enterprise Plus** | + Audit logs, signed commits, RBAC | +8h |

You're currently at **Staging** level. With all phases, you'll be at **Enterprise**.
