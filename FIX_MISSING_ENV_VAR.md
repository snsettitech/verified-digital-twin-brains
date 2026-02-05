# Fix Missing Environment Variable

**Status:** Database ✅ | Environment Variables: 1 missing

---

## Missing Variable

**Backend:** `ALLOWED_ORIGINS` is missing from `backend/.env`

---

## Fix

Add this line to `backend/.env`:

```bash
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

**For production:** Use your actual domain:
```bash
ALLOWED_ORIGINS=https://yourapp.com,https://www.yourapp.com
```

**For local development:** Use:
```bash
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

---

## After Adding

1. Save the file
2. Restart backend server (if running)
3. Run check again: `python scripts/check_env_vars.py`

---

## Why This Matters

`ALLOWED_ORIGINS` controls CORS (Cross-Origin Resource Sharing). Without it:
- Frontend (localhost:3000) can't call backend API
- Browser blocks requests with CORS errors
- Application won't work

---

## Next Steps

After fixing:
1. ✅ Verify env vars: `python scripts/check_env_vars.py`
2. ✅ Test backend: `cd backend && python main.py`
3. ✅ Test frontend: `cd frontend && npm run dev`
4. ✅ Test login flow
