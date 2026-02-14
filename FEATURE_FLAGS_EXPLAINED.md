# Feature Flags Comparison & Analysis

**Date**: 2026-02-12  
**Context**: ISSUE-003 Implementation  

---

## Quick Comparison Table

| Flag | What It Controls | Current Default | Status After ISSUE-003 | Risk Level |
|------|------------------|-----------------|------------------------|------------|
| **ENABLE_REALTIME_INGESTION** | Real-time audio/streaming ingestion | `true` (was `false`) | ✅ **ENABLED** | Low |
| **ENABLE_ENHANCED_INGESTION** | Web crawling, RSS, social media | `false` | ❌ **DISABLED** | Medium |
| **ENABLE_DELPHI_RETRIEVAL** | Creator-scoped namespace retrieval | `true` (was `false`) | ✅ **ENABLED** | Low |
| **ENABLE_VC_ROUTES** | VC (Venture Capital) specialization | `false` | ❌ **DISABLED** | High |

---

## Detailed Breakdown

### 1. ENABLE_REALTIME_INGESTION

**What it does:**
- Enables real-time audio/streaming ingestion endpoints
- Allows live interview sessions with continuous transcription
- Supports streaming content ingestion (e.g., live audio feeds)

**Router:** `ingestion_realtime` (loaded dynamically, may not exist in all deployments)

**Code in main.py:**
```python
if REALTIME_INGESTION_ENABLED:
    if ingestion_realtime is not None:
        app.include_router(ingestion_realtime.router)
```

**Pros:**
- ✅ Enables live interview functionality (core product feature)
- ✅ Real-time content capture for dynamic knowledge updates
- ✅ Well-tested and stable

**Cons:**
- ⬇️ Requires additional infrastructure for streaming
- ⬇️ May increase resource usage during active sessions

**Why changed to `true` in ISSUE-003:**
- This is a **core product feature** - the interview functionality depends on it
- Was confusing for users who couldn't access live interviews
- Low risk - well-tested and stable

---

### 2. ENABLE_ENHANCED_INGESTION

**What it does:**
- Enables advanced ingestion capabilities:
  - **Website deep crawling** (Firecrawl integration)
  - **RSS feed subscriptions** (auto-updating content)
  - **Social media ingestion** (Twitter, LinkedIn profiles)
  - **Pipeline management** (scheduled/auto ingestion)

**Router:** `enhanced_ingestion`

**Endpoints include:**
```
POST /enhanced-ingestion/website/crawl
POST /enhanced-ingestion/rss/subscribe
POST /enhanced-ingestion/twitter
POST /enhanced-ingestion/linkedin
```

**Pros:**
- ✅ Powerful content discovery capabilities
- ✅ Automated content updates via RSS
- ✅ Social media presence capture

**Cons:**
- ⬇️ **External dependencies** (Firecrawl API, Twitter API, etc.)
- ⬇️ **Higher cost** - API calls to external services
- ⬇️ **Complexity** - more failure points
- ⬇️ **Not fully validated** - marked as "until further validation"

**Why remains `false`:**
- Requires external API keys and configurations
- Higher operational costs
- Not core to the basic twin functionality
- Needs additional testing and validation

---

### 3. ENABLE_DELPHI_RETRIEVAL

**What it does:**
- Enables **creator-scoped namespace retrieval** system
- Uses "Delphi" namespace strategy for tenant isolation
- Provides retrieval endpoints with strict tenant boundaries

**Router:** `retrieval_delphi`

**Key concept:** "Delphi" refers to a namespace strategy where vectors are stored in Pinecone namespaces based on `creator_id` rather than `twin_id`, enabling cross-twin retrieval while maintaining isolation.

**Endpoints include:**
```
POST /retrieval/query           # Query vectors by creator
POST /retrieval/query-across    # Query across multiple twins
POST /retrieval/delete          # GDPR-compliant deletion
```

**Pros:**
- ✅ **Better tenant isolation** - creator-scoped namespaces
- ✅ **Cross-twin search** - can query across a creator's twins
- ✅ **GDPR compliance** - easy deletion by creator
- ✅ More scalable namespace strategy

**Cons:**
- ⬇️ **Migration complexity** - different from legacy twin-scoped namespaces
- ⬇️ Requires understanding of namespace strategy

**Why changed to `true` in ISSUE-003:**
- This is the **preferred retrieval strategy** going forward
- Better security and isolation
- Enables advanced features like cross-twin search
- Was confusing when disabled (retrieval didn't work properly)

---

### 4. ENABLE_VC_ROUTES

**What it does:**
- Enables **Venture Capital specialization** routes
- VC-specific workflows, templates, and data models
- Separate from "vanilla" (standard) twin flows

**Router:** `vc_routes` (loaded from `api.vc_routes`)

**Special behavior:**
```python
if VC_ROUTES_ENABLED:
    try:
        from api import vc_routes  # Dynamic import!
        app.include_router(vc_routes.router, prefix="/api", tags=["vc"])
```

**Pros:**
- ✅ Specialized workflows for VC use case
- ✅ Custom data models for portfolio companies
- ✅ VC-specific analytics and reporting

**Cons:**
- ⬇️ **HIGH RISK** - can interfere with vanilla flows
- ⬇️ **Dynamic import** - may cause startup errors
- ⬇️ **Complex dependencies** - VC module may not exist
- ⬇️ Only relevant for VC customers

**Why remains `false`:**
- **Critical comment in code:**
  ```python
  # VC routes are conditionally loaded to prevent VC files from interfering
  # with vanilla flows. This is critical because:
  # 1. VC routes should only be available when VC is actively used
  # 2. VC imports/dependencies should not be loaded globally
  # 3. This prevents VC-related startup errors from breaking vanilla deployments
  ```
- Could break standard deployments if enabled
- Only needed for VC-specialized deployments

---

## Implementation Pattern

All flags follow the same pattern:

```python
# 1. Read from environment with default
FLAG_ENABLED = os.getenv("ENABLE_FLAG_NAME", "default").lower() == "true"

# 2. Conditional router inclusion
if FLAG_ENABLED:
    app.include_router(router)
    print("[INFO] Feature enabled")
else:
    print("[INFO] Feature disabled")
```

### Key Implementation Details:

1. **Environment variable names** match the flag names: `ENABLE_REALTIME_INGESTION`
2. **Case-insensitive** parsing (`.lower() == "true"`)
3. **Startup logging** - each flag prints status on boot
4. **Observability** - `print_feature_flag_summary()` shows all flags

---

## Current vs Previous State (ISSUE-003 Changes)

### Before ISSUE-003:
```
Realtime Ingestion:  DISABLED (default: false)
Enhanced Ingestion:  DISABLED (default: false)
Delphi Retrieval:    DISABLED (default: false)  ← Problem!
VC Routes:           DISABLED (default: false)
```

### After ISSUE-003:
```
Realtime Ingestion:  ENABLED  (default: true)   ← Fixed
Enhanced Ingestion:  DISABLED (default: false)
Delphi Retrieval:    ENABLED  (default: true)   ← Fixed
VC Routes:           DISABLED (default: false)
```

### Why These Changes Matter:

| Feature | Impact of Being Disabled |
|---------|------------------------|
| Realtime Ingestion | Users can't do live interviews |
| Delphi Retrieval | Retrieval fails or uses legacy (worse) strategy |
| Enhanced Ingestion | No web crawling/social media (acceptable) |
| VC Routes | No VC specialization (acceptable for non-VC) |

---

## Recommendations

### For Development:
```bash
# .env file for development
ENABLE_REALTIME_INGESTION=true      # Always enable for dev
ENABLE_DELPHI_RETRIEVAL=true        # Always enable for dev
ENABLE_ENHANCED_INGESTION=false     # Only enable if testing
ENABLE_VC_ROUTES=false              # Only enable for VC testing
```

### For Production:
```bash
# Stable production settings
ENABLE_REALTIME_INGESTION=true      # Core feature
ENABLE_DELPHI_RETRIEVAL=true        # Preferred retrieval
ENABLE_ENHANCED_INGESTION=false     # Until fully validated
ENABLE_VC_ROUTES=false              # Only for VC deployments
```

### For Debugging:
Check the startup logs:
```
------------------------------------------------------------
Feature Flag Status:
  Realtime Ingestion: ENABLED
  Enhanced Ingestion: DISABLED
  Delphi Retrieval:   ENABLED
  VC Routes:          DISABLED
------------------------------------------------------------
```

---

## Troubleshooting

### Issue: "Interview sessions not working"
**Check:** `ENABLE_REALTIME_INGESTION=true`

### Issue: "Retrieval returning empty results"
**Check:** `ENABLE_DELPHI_RETRIEVAL=true`

### Issue: "Can't crawl websites or connect social media"
**Check:** `ENABLE_ENHANCED_INGESTION=true` (and verify API keys)

### Issue: "VC-specific features missing"
**Check:** `ENABLE_VC_ROUTES=true` (only for VC deployments)

---

## Summary

| Flag | Should Enable If... | Keep Disabled If... |
|------|---------------------|---------------------|
| REALTIME | You need live interviews | Never (core feature) |
| ENHANCED | You need web crawling/social | You want stability |
| DELPHI | You want proper retrieval | Never (preferred strategy) |
| VC | You're a VC customer | You're not VC |
