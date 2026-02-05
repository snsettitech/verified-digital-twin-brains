# Testing Guide - After Database Setup Complete

**Status:** ✅ Database is ready (all tables, RPC functions, RLS enabled)

Now let's verify the application works end-to-end.

---

## Step 1: Check Environment Variables

Run the environment checker:

```bash
python scripts/check_env_vars.py
```

This will show you:
- ✅ Which environment variables are set
- ❌ Which ones are missing
- ⚠️ Which ones need attention

**Fix any missing variables before proceeding.**

---

## Step 2: Test Backend

### Start Backend Server

```bash
cd backend
python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**If you see errors:**
- Check error messages - they usually tell you what's missing
- Common issues:
  - Missing environment variables
  - Database connection failed (check SUPABASE_URL/KEY)
  - Pinecone connection failed (check PINECONE_API_KEY)
  - OpenAI connection failed (check OPENAI_API_KEY)

### Test Health Endpoint

In another terminal:

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "service": "verified-digital-twin-brain-api",
  "version": "1.0.0"
}
```

### Test Enhanced Health (if Phase 10 migration applied)

```bash
curl http://localhost:8000/metrics/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "services": {
    "supabase": "healthy",
    "pinecone": "healthy",
    "openai": "healthy"
  }
}
```

**If health check fails:**
- Check backend logs for specific error
- Verify environment variables are correct
- Check external service connections (Supabase, Pinecone, OpenAI)

---

## Step 3: Test Frontend

### Start Frontend Server

In a new terminal:

```bash
cd frontend
npm run dev
```

**Expected output:**
```
  ▲ Next.js 14.x.x
  - Local:        http://localhost:3000
  - Ready in X.Xs
```

### Open Browser

1. Go to: http://localhost:3000
2. Open Developer Tools (F12)
3. Check Console tab - should see no red errors
4. Check Network tab - initial requests should be 200 OK

**If frontend fails:**
- Check browser console for errors
- Verify `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_BACKEND_URL` are correct
- Check if backend is running (Step 2)

---

## Step 4: Test User Authentication Flow

### Login Test

1. Go to http://localhost:3000/auth/login
2. Click "Sign in with Google" (or your auth method)
3. Complete OAuth flow
4. **Expected:** Redirected to `/dashboard` or `/onboarding`

### Check Backend Logs

After login, check backend terminal for:
```
[SYNC DEBUG] User created successfully
```

Or verify in Supabase:
```sql
SELECT id, email, tenant_id, created_at
FROM users
ORDER BY created_at DESC
LIMIT 1;
```

**If login fails:**
- Check backend logs for errors
- Verify JWT_SECRET matches Supabase Dashboard
- Check OAuth redirect URLs in Supabase Dashboard → Authentication → URL Configuration

---

## Step 5: Test Twin Creation

### If Onboarding Appears

1. Complete onboarding flow
2. Create a twin
3. **Expected:** Twin appears in dashboard

### Verify Twin Created

Check backend logs or database:
```sql
SELECT id, name, tenant_id, created_at
FROM twins
ORDER BY created_at DESC
LIMIT 1;
```

---

## Step 6: Test Chat Functionality

### Send a Test Message

1. Go to Dashboard → Chat
2. Type a message (e.g., "Hello, what can you help me with?")
3. **Expected:**
   - Message appears in chat
   - AI responds (may say "I don't know" if no knowledge base)

### Check Backend Logs

Look for:
- Chat request received
- Retrieval process (if knowledge base exists)
- LLM response generated
- Message saved to database

**If chat fails:**
- Check backend logs for errors
- Verify OpenAI API key is valid
- Check Pinecone index exists (if using knowledge base)
- Verify conversation/messages tables exist

---

## Step 7: Verify Knowledge Base (Optional)

### Upload a Document

1. Go to Dashboard → Knowledge
2. Upload a PDF or add a URL
3. Wait for processing

### Verify Document Processed

Check database:
```sql
SELECT id, filename, status, created_at
FROM sources
ORDER BY created_at DESC
LIMIT 1;
```

**Expected:** Status should be `processed` (or `pending` if still processing)

---

## Common Issues & Solutions

### Issue: Backend won't start

**Symptoms:** Errors on startup

**Solutions:**
- Check environment variables are set correctly
- Verify database connection (Supabase URL/key)
- Check Python dependencies: `pip install -r requirements.txt`
- Look at error message - it usually tells you what's wrong

### Issue: 401 Unauthorized errors

**Symptoms:** All API calls return 401

**Solutions:**
- Verify JWT_SECRET matches Supabase Dashboard → Settings → API → JWT Secret
- Check token is being sent in Authorization header
- Verify user exists in database (run user sync)

### Issue: 500 Internal Server Error

**Symptoms:** Server errors on API calls

**Solutions:**
- Check backend logs for specific error
- Verify database tables exist (you've already checked this ✅)
- Check RPC functions exist (you've already checked this ✅)
- Verify external services (Pinecone, OpenAI) are accessible

### Issue: CORS errors

**Symptoms:** Browser console shows CORS policy errors

**Solutions:**
- Update `ALLOWED_ORIGINS` in backend `.env` to include `http://localhost:3000`
- Restart backend server
- Verify CORS middleware is enabled in `backend/main.py`

### Issue: Chat returns "I don't know" always

**Symptoms:** AI always says it doesn't have information

**Solutions:**
- This is NORMAL if no documents are uploaded
- Upload documents to build knowledge base
- Verify Pinecone index exists and is configured correctly
- Check documents are processed (status = 'processed' in sources table)

---

## Success Criteria

Your application is ready when:

- [ ] Backend starts without errors
- [ ] Frontend starts without errors
- [ ] Health endpoint returns 200 OK
- [ ] User can login (OAuth works)
- [ ] User sync creates user record
- [ ] Twin creation works (if applicable)
- [ ] Chat sends/receives messages
- [ ] No console errors in browser
- [ ] No 500 errors in backend logs

---

## Next Steps After Testing

Once everything works:

1. **Upload Knowledge:** Add documents to build knowledge base
2. **Test Escalation:** Ask question system doesn't know
3. **Test Verified QnA:** Resolve escalation, verify answer is saved
4. **Test Cognitive Features:** Interview flow, graph memory (if applicable)
5. **Deploy to Production:** Follow DEPLOYMENT_RUNBOOK.md

---

## Quick Reference Commands

```bash
# Check environment variables
python scripts/check_env_vars.py

# Start backend
cd backend && python main.py

# Start frontend (new terminal)
cd frontend && npm run dev

# Test backend health
curl http://localhost:8000/health

# Test enhanced health
curl http://localhost:8000/metrics/health

# Check database (in Supabase SQL Editor)
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';
```
