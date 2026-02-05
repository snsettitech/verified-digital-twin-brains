# Start Testing - Quick Commands

**Ready to test!** Follow these steps:

---

## Step 1: Start Backend Server

**Open a terminal and run:**

```powershell
cd backend
python main.py
```

**Expected:** You'll see a banner with the API info and "Application startup complete"

**If you see errors:**
- Install dependencies: `pip install -r requirements.txt`
- Check error message for what's missing

---

## Step 2: Test Backend Health (New Terminal)

**Open a NEW terminal (keep backend running) and run:**

```powershell
curl http://localhost:8000/health
```

**Expected:** `{"status":"healthy","service":"verified-digital-twin-brain-api","version":"1.0.0"}`

---

## Step 3: Start Frontend (New Terminal)

**Open a NEW terminal (keep backend running) and run:**

```powershell
cd frontend
npm run dev
```

**Expected:** Server starts, shows "Local: http://localhost:3000"

---

## Step 4: Open Browser

1. Go to: **http://localhost:3000**
2. Open Developer Tools (F12)
3. Check Console tab (should be clean)
4. Try to login

---

## What to Test

1. **Login** - Sign in with Google
2. **Dashboard** - Should load after login
3. **Chat** - Send a test message
4. **Check Backend Logs** - Look at backend terminal for any errors

---

## Troubleshooting

**Backend won't start?**
- Check if port 8000 is in use
- Check environment variables are set
- Run: `pip install -r requirements.txt`

**Frontend won't start?**
- Run: `npm install`
- Check if port 3000 is in use

**401/403 errors?**
- Check JWT_SECRET in backend/.env
- Verify user exists in database

**Need help?** Check `QUICK_TEST.md` for detailed troubleshooting
