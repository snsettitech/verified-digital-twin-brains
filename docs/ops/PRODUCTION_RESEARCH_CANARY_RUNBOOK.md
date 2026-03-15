# Production Research Canary Runbook

## Purpose

Run a repeatable production smoke test against the onboarding and deep-research path using a dedicated QA account. This catches the class of failures you hit recently:

- crawl completes but post-confirmation ingestion fails
- UI shows a generic failure state instead of the real backend error
- claims enrichment or post-research steps fail after the main research run appears complete

This runbook is for controlled QA use only. Do not run it against a customer tenant.

## Preconditions

- Use a dedicated QA account in production
- That account should belong to an isolated tenant
- The account should have permission to create and reset its own profile
- The identity you test should be stable and public
- Prefer a canary identity with:
  - full name
  - role/headline
  - location
  - one known LinkedIn or profile URL

## Required environment variables

PowerShell:

```powershell
$env:E2E_BASE_URL = "https://your-frontend.example.com"
$env:E2E_CANARY_EMAIL = "qa+prod@yourdomain.com"
$env:E2E_CANARY_PASSWORD = "your-password"
$env:E2E_CANARY_FULL_NAME = "Your Canary Identity"
$env:E2E_CANARY_HEADLINE = "Founder at Example Co"
$env:E2E_CANARY_LOCATION = "Toronto, Canada"
$env:E2E_CANARY_LINKEDIN_URL = "https://www.linkedin.com/in/example"
$env:E2E_CANARY_RESEARCH_TIMEOUT_MS = "180000"
$env:E2E_CANARY_CLAIMS_TIMEOUT_MS = "60000"
$env:E2E_CANARY_RESET_PROFILE = "1"
```

Bash:

```bash
export E2E_BASE_URL="https://your-frontend.example.com"
export E2E_CANARY_EMAIL="qa+prod@yourdomain.com"
export E2E_CANARY_PASSWORD="your-password"
export E2E_CANARY_FULL_NAME="Your Canary Identity"
export E2E_CANARY_HEADLINE="Founder at Example Co"
export E2E_CANARY_LOCATION="Toronto, Canada"
export E2E_CANARY_LINKEDIN_URL="https://www.linkedin.com/in/example"
export E2E_CANARY_RESEARCH_TIMEOUT_MS="180000"
export E2E_CANARY_CLAIMS_TIMEOUT_MS="60000"
export E2E_CANARY_RESET_PROFILE="1"
```

## What the automated canary does

The Playwright canary:

1. logs into production with the QA account
2. resets the QA profile from `Settings -> Danger Zone`
3. starts onboarding from `/onboarding`
4. fills:
   - full name
   - headline
   - location
   - optional LinkedIn URL
5. starts the research run
6. waits up to 3 minutes for:
   - confirmation state, or
   - direct completion
7. if confirmations appear:
   - confirms all displayed sources
   - continues ingestion
8. waits for the research run to reach `completed`
9. waits for claims review
10. fails immediately if:
   - `Research Failed` appears
   - `Claims Extraction Failed` appears
   - the research run returns `failed` or `timed_out`
11. exits through the claims review screen and verifies redirect to `/dashboard/profile`

## Run the automated canary

From `frontend/`:

```powershell
npm run test:e2e:prod-canary
```

Headed mode:

```powershell
npm run test:e2e:prod-canary:headed
```

Artifacts:

- Playwright HTML report: `frontend/playwright-report/`
- Raw output: `frontend/playwright-test-results/`
- Failure screenshots are captured automatically

## Manual production canary checklist

Use this when you want me to drive the run interactively or when you want a human spot-check after deploy.

1. Sign in with the QA account
2. Go to `Dashboard -> Settings -> Danger Zone`
3. Reset the profile
4. Open `/onboarding`
5. Fill the canary identity
6. Start research
7. Confirm the discovered sources
8. Verify statuses progress through:
   - `Crawling`
   - `Awaiting Confirmation`
   - `Ingesting`
   - `Generating Bio`
   - `Finalizing`
   - `Completed`
9. Verify claims review loads
10. Skip or complete claims review
11. Verify redirect to `/dashboard/profile`

## Failure handling

If the canary fails:

1. keep the Playwright report
2. capture the last visible UI state
3. inspect the latest backend status warning shown in the failed card
4. correlate the failure timestamp with Render logs
5. do not redeploy again until the same canary passes

## Suggested release gate

Use this order:

1. local targeted tests
2. preview/staging smoke test
3. production canary with the QA account
4. only then mark the release healthy

## How to ask Codex to run it

Use a prompt like:

```text
Run the production research canary.

Frontend URL: https://your-frontend.example.com
QA email: qa+prod@yourdomain.com
QA password: ...
Full name: Your Canary Identity
Headline: Founder at Example Co
Location: Toronto, Canada
LinkedIn URL: https://www.linkedin.com/in/example

Use only the QA tenant. Reset the profile first. If it fails, find the root cause and tell me exactly where.
```
