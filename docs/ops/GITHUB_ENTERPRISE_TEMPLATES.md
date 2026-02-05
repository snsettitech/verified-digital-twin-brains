# GitHub Enterprise Setup - Quick Template Files

These templates are ready to implement. Just update with your details.

---

## 1. CODEOWNERS (.github/CODEOWNERS)

```
# Code owner assignments for branch protection

# Critical security paths - require lead approval
/backend/modules/auth_guard.py @yourusername
/backend/modules/observability.py @yourusername
/backend/modules/clients.py @yourusername
/backend/modules/_core/ @yourusername

# Database changes - require database team
/backend/database/migrations/ @yourusername
/backend/database/schema/ @yourusername

# Frontend auth - require frontend lead
/frontend/middleware.ts @yourusername
/frontend/lib/supabase/ @yourusername

# Documentation
/docs/architecture/ @yourusername
/.github/ @yourusername

# Everything else - one general reviewer
* @yourusername
```

---

## 2. SECURITY.md (.github/SECURITY.md)

```markdown
# Security Policy

## Reporting a Vulnerability

**Do NOT create public GitHub issues for security vulnerabilities.**

Please email: security@yourdomain.com with:
- Component affected (backend/frontend/database)
- Vulnerability type (auth, injection, secrets, etc.)
- Steps to reproduce
- Potential impact
- Your contact info

We will respond within 24 hours.

## Security Response Timeline
- **24 hours**: Acknowledgment
- **7 days**: Initial assessment
- **30 days**: Patch release or mitigation plan

## Supported Versions
| Version | Support Status |
|---------|----------------|
| 1.x | ✅ Receiving security updates |
| 0.x | ❌ No longer supported |

## Security Measures
- Multi-tenant isolation enforced via `tenant_id` filtering
- Row-level security (RLS) on all database tables
- JWT token validation on every API request
- Secrets stored in environment variables only
- Dependencies scanned by Dependabot weekly
- Commits signed with GPG (recommended)

## Hall of Fame
We credit responsible disclosures. Let us know if you want attribution.
```

---

## 3. dependabot.yml (.github/dependabot.yml)

```yaml
version: 2
updates:
  # Backend Python dependencies
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "03:00"
    open-pull-requests-limit: 5
    reviewers:
      - "yourusername"
    labels:
      - "dependencies"
      - "python"
    version-update-strategy: "increase"
    allow:
      - dependency-type: "production"
      - dependency-type: "development"

  # Frontend JavaScript dependencies
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "04:00"
    open-pull-requests-limit: 5
    reviewers:
      - "yourusername"
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
      time: "05:00"
    labels:
      - "dependencies"
      - "ci-cd"
```

---

## 4. Improved Lint Workflow (.github/workflows/lint.yml) - Security Section

```yaml
# Add this section to existing lint.yml

  security-scanning:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Trivy filesystem scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
      
      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'
      
      - name: Check for hardcoded secrets
        run: |
          # Install detect-secrets
          pip install detect-secrets
          
          # Scan for secrets
          detect-secrets scan \
            --all-files \
            --force-use-all-plugins \
            --baseline .gitignore.secrets || true
```

---

## 5. Staging Deployment (.github/workflows/deploy-staging.yml)

```yaml
name: Deploy to Staging

on:
  workflow_dispatch:
  pull_request:
    types: [labeled]
    branches: [main]

jobs:
  deploy-staging:
    if: |
      github.event_name == 'workflow_dispatch' || 
      contains(github.event.pull_request.labels.*.name, 'deploy-staging')
    
    runs-on: ubuntu-latest
    timeout-minutes: 15
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy Backend to Staging
        env:
          RENDER_DEPLOY_KEY: ${{ secrets.RENDER_DEPLOY_KEY }}
        run: |
          echo "Deploying backend to staging..."
          curl -X POST "https://api.render.com/deploy/srv-REPLACE_WITH_RENDER_ID" \
            -H "Authorization: Bearer $RENDER_DEPLOY_KEY"
      
      - name: Wait for deployment
        run: sleep 15
      
      - name: Health check
        run: |
          for i in {1..30}; do
            if curl -f https://staging.yourapp.com/health > /dev/null 2>&1; then
              echo "✅ Health check passed"
              exit 0
            fi
            echo "Attempt $i/30... waiting for health check"
            sleep 2
          done
          echo "❌ Health check failed after 60s"
          exit 1
      
      - name: Notify on success
        if: success()
        run: echo "✅ Staging deployment successful"
      
      - name: Notify on failure
        if: failure()
        run: echo "❌ Staging deployment failed"
```

---

## 6. Production Deployment (.github/workflows/deploy-production.yml)

```yaml
name: Deploy to Production

on:
  release:
    types: [published]

jobs:
  deploy-production:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    environment: 
      name: production
      url: https://yourapp.com
    
    permissions:
      contents: read
      deployments: write
    
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.release.tag_name }}
      
      - name: Create deployment
        id: deployment
        uses: actions/github-script@v6
        with:
          script: |
            const deployment = await github.rest.repos.createDeployment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: context.ref,
              environment: 'production',
              auto_merge: false,
              required_contexts: []
            });
            core.setOutput('deployment_id', deployment.data.id);
      
      - name: Deploy Backend
        env:
          RENDER_DEPLOY_KEY: ${{ secrets.RENDER_DEPLOY_KEY }}
        run: |
          echo "Deploying backend version ${{ github.event.release.tag_name }}"
          curl -X POST "https://api.render.com/deploy/srv-PROD_RENDER_ID" \
            -H "Authorization: Bearer $RENDER_DEPLOY_KEY"
      
      - name: Deploy Frontend
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        run: |
          echo "Deploying frontend version ${{ github.event.release.tag_name }}"
          npm install -g vercel
          vercel --prod --token=$VERCEL_TOKEN
      
      - name: Wait and verify
        run: sleep 30
      
      - name: Health check
        run: |
          STATUS=$(curl -s https://yourapp.com/health | jq -r '.status')
          if [ "$STATUS" = "ok" ]; then
            echo "✅ Production health check passed"
          else
            echo "❌ Production health check failed"
            exit 1
          fi
      
      - name: Update deployment status
        if: success()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.repos.createDeploymentStatus({
              owner: context.repo.owner,
              repo: context.repo.repo,
              deployment_id: ${{ steps.deployment.outputs.deployment_id }},
              state: 'success',
              environment_url: 'https://yourapp.com'
            });
      
      - name: Update deployment status on failure
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.repos.createDeploymentStatus({
              owner: context.repo.owner,
              repo: context.repo.repo,
              deployment_id: ${{ steps.deployment.outputs.deployment_id }},
              state: 'failure'
            });
```

---

## Setup Instructions

### Step 1: Configure Repository Settings

1. Go to: Repository → Settings → Branches
2. Click "Add rule"
3. Branch name pattern: `main`
4. Configure:
   - ✅ Require pull request reviews (1)
   - ✅ Require code owner reviews
   - ✅ Require status checks:
     - `lint-backend` ✓
     - `lint-frontend` ✓
   - ✅ Require branches to be up to date
   - ✅ Include administrators

### Step 2: Create GitHub Secrets

1. Settings → Secrets and variables → Actions
2. Add these secrets:

```
RENDER_DEPLOY_KEY = (from Render account settings)
VERCEL_TOKEN = (from Vercel account settings)
SLACK_WEBHOOK_URL = (optional, from Slack integration)
```

### Step 3: Replace Placeholder Values

Search and replace in workflow files:
- `REPLACE_WITH_RENDER_ID` → Your Render service ID
- `PROD_RENDER_ID` → Your production Render service ID
- `yourusername` → Your GitHub username
- `yourapp.com` → Your production domain
- `staging.yourapp.com` → Your staging domain

### Step 4: Test

1. Create a test branch
2. Make a small change
3. Create a PR
4. Verify:
   - Tests run automatically ✓
   - Code owner review requested ✓
   - Can't merge without approval ✓

### Step 5: Deploy Staging

1. Add label `deploy-staging` to a PR
2. Workflow triggers automatically
3. Watch deployment progress
4. Verify staging site updates

### Step 6: Release & Deploy Production

1. Create a GitHub Release with tag `v1.0.1`
2. Fill in release notes
3. Publish release
4. Production workflow triggers
5. Requires manual approval (environment feature)
6. Automatically deploys both backend and frontend

---

## Maintenance

### Weekly
- Review Dependabot PRs (security first)
- Check GitHub Security tab for vulnerabilities
- Review failed CI/CD runs

### Monthly
- Audit branch protection rules
- Review CODEOWNERS assignments
- Check for outdated dependencies

### Quarterly
- Review security policy
- Update deployment procedures if needed
- Analyze CI/CD metrics (time, failures, etc.)
