# Quick Start Guide

This guide provides the essential steps and references to get the Digital Brain platform running and verified.

## 🚀 The Path to Production (1 Hour)

### Step 1: Fix Critical Blockers (30 min)
| Blocker | Symptom | Action |
| :--- | :--- | :--- |
| **Missing Column** | `POST /twins` or User Sync 500 | `ALTER TABLE users ADD COLUMN avatar_url TEXT;` |
| **Missing RPC** | Interviews fail with 500 | Apply `migration_interview_sessions.sql` in Supabase. |
| **Worker Process** | Jobs stuck in `pending` | Deploy `worker.py` as a separate service on Render/Railway. |
| **Vector Dimension** | Vector search fails | Recreate Pinecone index with **3072** dimensions. |

### Step 2: Configure Environment (15 min)
Ensure these 8 critical variables are set in your backend `.env`:
- `OPENAI_API_KEY`
- `SUPABASE_URL` & `SUPABASE_SERVICE_ROLE_KEY`
- `PINECONE_API_KEY` & `PINECONE_INDEX_NAME`
- `JWT_SECRET` (Must match Supabase exactly)
- `ALLOWED_ORIGINS`
- `ELEVENLABS_API_KEY` (for Voice)

### Step 3: Deployment (15 min)
- **Frontend**: Vercel (Auto-deploys on push to `main`)
- **Backend API**: Render/Railway (`uvicorn main:app`)
- **Worker**: Render/Railway (`python worker.py`)

---

## 🔍 Daily health Verification
Run this command every morning to catch regressions early:

```bash
# Backend
python scripts/verify_features.py

# Frontend
npm run lint
```

### Success Metrics
- ✅ 8+ features WORKING
- ✅ <1 feature NOT_WORKING
- ✅ Response time <1s
- ✅ Error rate <1%

---

## 🎯 Golden Rules for AI Agents
1. **Context First**: Always check `COMPLETE_ARCHITECTURE_ANALYSIS.md` before significant changes.
2. **Filters**: Every query MUST filter by `tenant_id` or `twin_id`.
3. **Auth**: Use `Depends(get_current_user)` and `verify_owner()`.
4. **Singleton**: Import `supabase` from `modules.observability`.
5. **No Placeholders**: Never use placeholder URLs or keys in PRs.

---

## Support & Documentation
- **Architecture**: [architecture/system-overview.md](architecture/system-overview.md)
- **API Contracts**: [architecture/api_contracts.md](architecture/api_contracts.md)
- **AI Operating Manual**: [ai/agent-manual.md](ai/agent-manual.md)
- **Known Failures**: [KNOWN_FAILURES.md](KNOWN_FAILURES.md)
- **Known Limitations**: [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)
