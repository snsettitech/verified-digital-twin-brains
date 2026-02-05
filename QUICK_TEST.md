# Quick Testing Guide

**Status:** ✅ Database ready | ✅ Environment variables set | ⏭️ ALLOWED_ORIGINS skipped (using default)

---

## Step 1: Test Backend

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
- Check the error message - it will tell you what's wrong
- Common issues: Missing dependencies (`pip install -r requirements.txt`)

### Test Health Endpoint

**In another terminal:**

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{"status":"healthy","service":"verified-digital-twin-brain-api","version":"1.0.0"}
```

**If health check fails:**
- Check backend terminal for errors
- Verify backend is running on port 8000

---

## Step 2: Test Frontend

### Start Frontend Server

**In a new terminal:**

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

1. Go to: **http://localhost:3000**
2. Open Developer Tools (F12)
3. Check **Console** tab - should see no red errors
4. Check **Network** tab - initial requests should be 200 OK

**If frontend fails:**
- Check browser console for errors
- Verify backend is running (Step 1)
- Check if `npm install` completed successfully

---

## Step 3: Test Login Flow

1. Click **"Login"** or **"Sign in with Google"**
2. Complete OAuth flow
3. **Expected:** Redirected to `/dashboard` or `/onboarding`

### Check Backend Logs

After login, check backend terminal for:
```
[SYNC DEBUG] User created successfully
```

**If login fails:**
- Check backend logs for errors
- Verify JWT_SECRET matches Supabase
- Check OAuth redirect URLs in Supabase Dashboard

---

## Step 4: Test Chat

1. Go to Dashboard → Chat (or after onboarding)
2. Type a message: "Hello, what can you help me with?"
3. **Expected:**
   - Message appears in chat
   - AI responds (may say "I don't know" if no knowledge base - this is normal)

**If chat fails:**
- Check backend logs for errors
- Verify OpenAI API key is valid
- Check Pinecone index exists (if using knowledge base)

---

## Success Criteria

Your app is working when:

- [x] Backend starts without errors
- [x] Frontend starts without errors
- [x] Health endpoint returns 200 OK
- [ ] User can login (OAuth works)
- [ ] User sync creates user record
- [ ] Chat sends/receives messages
- [ ] No console errors in browser
- [ ] No 500 errors in backend logs

---

## Quick Troubleshooting

**Backend won't start?**
- Run: `pip install -r requirements.txt`
- Check environment variables are set
- Look at error message

**Frontend won't start?**
- Run: `npm install`
- Check `NEXT_PUBLIC_BACKEND_URL` is correct
- Check browser console

**401/403 errors?**
- Check JWT_SECRET matches Supabase
- Verify user exists in database
- Check backend logs

**Chat doesn't work?**
- Check OpenAI API key
- Verify Pinecone index exists
- Check backend logs for errors

---

## Next Steps After Testing

Once everything works:

1. **Upload Knowledge:** Add documents to build knowledge base
2. **Test Escalation:** Ask question system doesn't know
3. **Test Verified QnA:** Resolve escalation, verify answer is saved
4. **Deploy to Production:** Follow DEPLOYMENT_RUNBOOK.md (and set ALLOWED_ORIGINS!)

---

## Quick Commands Reference

```bash
# Start backend
cd backend && python main.py

# Test health (in another terminal)
curl http://localhost:8000/health

# Start frontend (in another terminal)
cd frontend && npm run dev

# Check backend logs
# (look at terminal where backend is running)

# Check database (in Supabase SQL Editor)
SELECT id, email, tenant_id FROM users ORDER BY created_at DESC LIMIT 1;
```
