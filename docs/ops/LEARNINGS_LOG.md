> Compounding ledger of lessons learned. Add new entries at the top.

---

## 2024-12-24: Twins Table Uses tenant_id, Not owner_id

### Issue
Jobs migration failed with: `ERROR: 42703: column twins.owner_id does not exist`

### Root Cause
The twins table uses `tenant_id` to identify the owner, not `owner_id`. Different naming convention than expected.

### Fix
Changed RLS policies and backend router to use `twins.tenant_id = auth.uid()` instead of `twins.owner_id = auth.uid()`.

### Preventative Guardrail
- **Always check existing migrations** for column naming patterns before writing new ones
- Look at `create_metrics_tables.sql` as a reference for RLS policy patterns

### Reusable Snippet
```sql
-- Correct pattern for twins ownership check
EXISTS (
    SELECT 1 FROM twins
    WHERE twins.id = <table>.twin_id
    AND twins.tenant_id = auth.uid()
)
```

---

## 2024-12-24: Vercel Build Failures

### Issue
Vercel builds failed with "Module not found" errors for `@/lib/context/TwinContext`, `@/lib/supabase/client`, and `@/lib/features/FeatureFlags`.

### Root Cause
The root `.gitignore` had a broad pattern `lib/` which ignored ALL folders named `lib` anywhere in the repo, including `frontend/lib/`. These files existed locally but were never pushed to GitHub.

### Fix
1. Changed `.gitignore` from `lib/` to `backend/lib/` (specific path)
2. Force-added the files: `git add -f frontend/lib/`
3. Committed and pushed

### Preventative Guardrail
- **Pre-commit check**: Always run `git ls-files <path>` to verify new files are tracked
- **Added to AGENT_BRIEF.md**: DON'T add broad patterns to `.gitignore`
- **Created preflight script**: Runs full build locally before push

### Reusable Snippet
```powershell
# Check if files are tracked
git ls-files frontend/lib

# Force-add ignored files
git add -f frontend/lib/

# Check what's ignoring a file
git check-ignore -v frontend/lib/supabase/client.ts
```

---

## 2024-12-24: Missing React Hook Imports

### Issue
TypeScript build failed with "Cannot find name 'useCallback'" errors in multiple files.

### Root Cause
Files used `useCallback` but only imported `useState` and `useEffect`. This worked locally in dev mode (hot reload) but failed in production build.

### Fix
Added `useCallback` to React imports in affected files:
```typescript
import React, { useState, useEffect, useCallback } from 'react';
```

### Preventative Guardrail
- **ALWAYS run `npm run build` locally** before pushing
- **Add ALL hooks upfront** when creating new components
- **Fix ALL errors in one commit**, not one at a time

### Reusable Snippet
```typescript
// Standard React import with all common hooks
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
```

---

## 2024-12-24: Hoisting Errors in Dashboard Pages

### Issue
ESLint errors: "Cannot access variable before it is declared" for functions like `formatTimeAgo` and `loadShareLinks`.

### Root Cause
Functions were defined AFTER the `useEffect` that called them. JavaScript hoisting doesn't work for `const` declarations.

### Fix
Moved helper functions ABOVE their usage in `useEffect`.

### Preventative Guardrail
- Define functions before using them
- Or use `useCallback` and include in dependencies

---

## Template for New Entries

```markdown
## YYYY-MM-DD: Brief Title

### Issue
What went wrong?

### Root Cause
Why did it happen?

### Fix
What was the solution?

### Preventative Guardrail
How do we prevent this in the future?

### Reusable Snippet
```code
Any helpful code or commands
```
```
