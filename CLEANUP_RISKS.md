# Cleanup Risk Assessment

This document flags items identified during cleanup that may require human review or action.

---

## 🔴 HIGH RISK: Tracked .env File Contains Secrets

**Status:** Immediate action required

### Issue
The `.env` file is currently tracked in git and contains actual secrets:
- OpenAI API key
- Pinecone API key
- Supabase credentials
- JWT secret
- Neo4j password
- Multiple service API keys

### Risk
- Secrets are in git history (even if removed now, they remain in history)
- Anyone with repo access can see production credentials
- Potential for credential leakage in forks/PRs

### Recommended Actions

1. **Immediately rotate all secrets:**
   ```bash
   # Rotate in respective services:
   # - OpenAI: https://platform.openai.com/api-keys
   # - Pinecone: https://app.pinecone.io/
   # - Supabase: Project Settings > API
   # - Neo4j: Aura Console
   # - etc.
   ```

2. **Add .env to .gitignore** (already in updated .gitignore)

3. **Remove .env from tracking** (without deleting local file):
   ```bash
   git rm --cached .env
   ```

4. **Use .env.example for template** (already created)

5. **For production, prefer secret management:**
   - Render: Environment variables in dashboard
   - Vercel: Environment variables in dashboard
   - Never commit production secrets

### Safe Path Forward
- `.env.example` has been created as a safe template
- `.gitignore` now excludes `.env`
- **Action needed:** Rotate secrets and remove .env from tracking

---

## 🟡 MEDIUM RISK: Frontend Playwright in Dependencies

**Status:** Flagged for future action

### Issue
In `frontend/package.json`:
```json
"dependencies": {
  "@playwright/test": "^1.57.0",
  ...
}
```

Playwright is a testing tool and should be in `devDependencies`.

### Risk
- Slightly larger production bundle (minor)
- Conceptually incorrect separation

### Recommended Action
```bash
cd frontend
npm uninstall @playwright/test
npm install --save-dev @playwright/test
```

**Note:** This is safe to do but verify CI still works after the change.

---

## 🟡 MEDIUM RISK: Hardcoded URLs in .env

**Status:** Review recommended

### Issue
`.env` contains hardcoded deployment URLs:
```
DEPLOYED_FRONTEND_URL=https://digitalbrains.vercel.app/dashboard/simulator
DEPLOYED_BACKEND_URL=https://verified-digital-twin-brains.onrender.com
FRONTEND_URL=https://digitalbrains.vercel.app
```

### Risk
- URLs may change
- Hard to maintain across environments
- Not environment-agnostic

### Recommended Action
- Keep in .env (environment-specific config is correct)
- Document that these need updating for new deployments
- Consider making these dynamic or parameterized

---

## 🟢 LOW RISK: .agent/mcp.json Modified in Git

**Status:** Monitor

### Issue
`.agent/mcp.json` shows as modified in git status. This appears to be generated/local config.

### Recommended Action
- Verify if this file should be tracked
- If it's generated per-environment, add to .gitignore
- If it contains shared config, keep tracked

---

## 🟢 LOW RISK: context/ Directory Contents Unknown

**Status:** Review recommended

### Issue
The `context/` directory exists at root level but contents were not fully classified.

### Recommended Action
- Review `context/` directory contents
- Determine if should be:
  - Kept as-is (if shared context)
  - Moved to docs/
  - Added to .gitignore (if local only)

---

## 🟢 LOW RISK: eval/ Framework Verification

**Status:** Appears safe, verify

### Issue
`eval/` directory exists for evaluation framework. Verified during cleanup but not deeply inspected.

### Recommended Action
- Verify eval results files are not tracked (they are now in .gitignore)
- Ensure evaluation framework itself is properly maintained

---

## 🟢 LOW RISK: tests/ vs backend/tests/ Duplication

**Status:** Verify organization

### Issue
Both `tests/` (root) and `backend/tests/` exist. May have duplication.

### Recommended Action
- Review if tests/ (root) is duplicate of backend/tests/
- If duplicate, consider consolidation
- If distinct (e.g., integration vs unit), document the distinction

---

## 🟢 LOW RISK: package/ Directory Usage

**Status:** Verify before removal

### Issue
`package/` directory exists. Purpose unclear.

### Recommended Action
- Verify if used in deployment
- If unused, consider removal
- If used, document its purpose

---

## Summary Table

| Risk | Item | Action Required | Urgency |
|------|------|-----------------|---------|
| 🔴 High | .env secrets tracked | Rotate secrets, remove from git | Immediate |
| 🟡 Medium | Playwright in deps | Move to devDependencies | Soon |
| 🟡 Medium | Hardcoded URLs | Document/update process | Soon |
| 🟢 Low | .agent/mcp.json | Verify if should be tracked | When convenient |
| 🟢 Low | context/ directory | Review and classify | When convenient |
| 🟢 Low | eval/ framework | Verify no tracked results | When convenient |
| 🟢 Low | tests/ duplication | Review organization | When convenient |
| 🟢 Low | package/ directory | Verify usage | When convenient |

---

## Pre-Deployment Checklist

Before next deployment, verify:

- [ ] All secrets in .env have been rotated
- [ ] .env is no longer tracked in git
- [ ] Production secrets are in Render/Vercel dashboards, not in code
- [ ] CI passes with new .gitignore rules
- [ ] No new secrets have been committed
