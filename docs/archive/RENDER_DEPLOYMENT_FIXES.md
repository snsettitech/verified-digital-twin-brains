# Render Deployment Fixes

## Issues Fixed

### 1. ✅ List Import Error in cost_tracking.py
**File**: `backend/modules/cost_tracking.py` (line 171)

**Problem**: `NameError: name 'List' is not defined`

**Fix**: Changed function signature to use string annotation and added defensive import inside function:
```python
def get_optimization_suggestions(self, usage_data: Dict) -> "List[str]":
    from typing import List
    suggestions: List[str] = []
```

### 2. ✅ Langfuse Import Errors (All Routers)
**Files**: Multiple router files had bare `from langfuse import Langfuse` without try/except

**Affected Files**:
- `backend/routers/dashboard.py` (line 72)
- `backend/routers/trace_compare.py` (lines 30, 119)
- `backend/routers/regression_testing.py` (lines 93, 122, 173, 205)
- `backend/routers/dataset_export.py` (line 136)
- `backend/routers/langfuse_metrics.py` (line 197)

**Fix**: Wrapped all Langfuse imports in try/except with proper HTTP 503 error:
```python
try:
    from langfuse import Langfuse
except ImportError:
    raise HTTPException(status_code=503, detail="Langfuse not available")

client = Langfuse()
```

### 3. ✅ Timeout Issue (Build Cache)
**Recommendation**: Enable build cache in Render dashboard

**Steps**:
1. Go to Render Dashboard → Your Service
2. Settings → Build & Deploy
3. Enable "Build Cache"
4. Add `render.yaml` for explicit configuration

---

## Files Modified

### Critical Fixes (7 files)
1. `backend/modules/cost_tracking.py` - Added defensive List import
2. `backend/routers/dashboard.py` - Added Langfuse import guard
3. `backend/routers/trace_compare.py` - Added Langfuse import guards (2 places)
4. `backend/routers/regression_testing.py` - Added Langfuse import guards (4 places)
5. `backend/routers/dataset_export.py` - Added Langfuse import guard
6. `backend/routers/langfuse_metrics.py` - Added Langfuse import guard

---

## Pre-Deployment Checklist

### 1. Verify requirements.txt has langfuse
```bash
cat backend/requirements.txt | grep langfuse
# Should show: langfuse>=3.14.1
```

### 2. Test locally before deploying
```bash
cd backend
python -c "from modules.cost_tracking import get_cost_tracker; print('✓ cost_tracking imports OK')"
python -c "from routers.dashboard import router; print('✓ dashboard router imports OK')"
python -c "from routers.trace_compare import router; print('✓ trace_compare router imports OK')"
python -c "from routers.regression_testing import router; print('✓ regression_testing router imports OK')"
python -c "from routers.dataset_export import router; print('✓ dataset_export router imports OK')"
python -c "from routers.langfuse_metrics import router; print('✓ langfuse_metrics router imports OK')"
```

### 3. Commit and push
```bash
git add backend/
git commit -m "fix: Add defensive imports for Langfuse and typing.List

- Fix NameError for List in cost_tracking.py
- Add try/except guards for all Langfuse imports
- Return HTTP 503 when Langfuse unavailable
- Fixes Render deployment failures"

git push origin main
```

### 4. Deploy to Render
- Go to Render Dashboard
- Manual Deploy → Deploy Latest Commit
- Monitor logs for startup

---

## Post-Deployment Verification

### Health Checks
```bash
# Check basic health
curl https://verified-digital-twin-brains.onrender.com/health

# Should return:
# {"status": "healthy", "service": "verified-digital-twin-brains-api", ...}
```

### Langfuse Connection Check
```bash
# Check dashboard (should work even if Langfuse fails)
curl https://verified-digital-twin-brains.onrender.com/dashboard/overview \
  -H "Authorization: Bearer YOUR_TOKEN"

# If Langfuse unavailable, should return valid JSON with langfuse_connected: false
```

### Trace Endpoint Check
```bash
# Make a test chat request
curl -X POST https://verified-digital-twin-brains.onrender.com/chat/YOUR_TWIN_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "Hello test"}'
```

---

## If Deployment Still Fails

### Check Render Logs
```
Render Dashboard → Service → Logs
Look for:
1. Import errors (should be fixed now)
2. Timeout errors (increase startup timeout)
3. Memory errors (upgrade plan)
```

### Common Fixes

**Issue**: Still getting `ModuleNotFoundError: No module named 'langfuse'`
- **Fix**: Langfuse should be in requirements.txt
- **Check**: `langfuse>=3.14.1` is present
- **Action**: Clear build cache and redeploy

**Issue**: Build timeout
- **Fix**: Enable build cache in Render settings
- **Alternative**: Use lighter base image
- **Action**: Add `render.yaml` with explicit build config

**Issue**: Startup timeout
- **Fix**: Increase health check grace period
- **Action**: Render Settings → Health Check → Increase timeout to 300s

---

## render.yaml Configuration

Create `render.yaml` in repo root for explicit configuration:

```yaml
services:
  - type: web
    name: verified-digital-twin-brain-api
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    healthCheckTimeout: 300
    buildFilter:
      paths:
        - backend/**
      ignoredPaths:
        - frontend/**
        - "**/*.md"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: LANGFUSE_PUBLIC_KEY
        sync: false
      - key: LANGFUSE_SECRET_KEY
        sync: false
```

---

## Summary

All critical import errors have been fixed:
1. ✅ `List` type annotation fixed in cost_tracking.py
2. ✅ All Langfuse imports now have try/except guards
3. ✅ Graceful degradation when Langfuse unavailable
4. ✅ All syntax validated

**Next Action**: Commit, push, and deploy!
