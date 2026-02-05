# Quick Reference Card: Feature Verification Loop

**Print This & Keep at Desk**

---

## 🎯 What to Do Every Day

```
9:00 AM   └─ Run: python scripts/verify_features.py
          └─ Time: 2-5 minutes

Review:   ✅ = Working (no action)
          🟡 = Partial (monitor)
          ❌ = Broken (apply fix)

Check:    Any ❌ items?
          └─ Find solution in output
          └─ Apply fix
          └─ Re-run verification

Report:   Send status to team Slack
```

---

## 🔴 Critical Blockers (Fix FIRST)

### #1: avatar_url Column
```
Symptom:   User sync returns 500 error
Solution:  ALTER TABLE users ADD COLUMN avatar_url TEXT;
Time:      15 minutes
```

### #2: interview_sessions Table
```
Symptom:   POST /cognitive/interview returns 500
Solution:  Apply migration_interview_sessions.sql
Time:      5 minutes
```

### #3: Worker Not Running
```
Symptom:   Jobs stay in pending status
Solution:  Configure worker service on Render/Railway
Time:      30 minutes
```

### #4: Pinecone Dimension
```
Symptom:   Vector upsert fails or dimension mismatch
Solution:  Verify index is 3072-dimensional
Time:      15-60 minutes
```

---

## 📊 Current Status at a Glance

```
✅ WORKING (4 features)       🟡 PARTIAL (1 feature)    ❌ BROKEN (4 features)
├─ Backend health            ├─ Pinecone              ├─ User auth
├─ OpenAI integration         └─ (dimension check)     ├─ Interviews
├─ Job queue                                          ├─ Graph extraction
└─ Database                                           └─ Chat (blocked by auth)

Fix blockers:  ALTER TABLE + migrations + deploy
Time needed:   1 hour
Gain:          70% → 95% features working
```

---

## 🚀 7-Day Quick Plan

```
Day 1: Fix blockers (1h)           → Auth works
Day 2: Configure worker (1.5h)     → Jobs process
Day 3: Run tests (2h)              → Validate all
Day 4: Measure baseline (1.5h)     → Capture metrics
Day 5: Add caching (4h)            → 5x faster
Day 6: Add logging (3h)            → Better debugging
Day 7: Documentation (2h)          → Team ready

Total: 15 hours → Production ready
```

---

## 💻 Commands You'll Use

```bash
# Check feature status
python scripts/verify_features.py

# Measure performance
python scripts/track_improvements.py

# View report
cat eval/feature_verification_report.json

# View metrics
cat eval/improvement_metrics.json

# Deploy fixes
git add -A && git commit -m "fixes" && git push origin main
```

---

## ✅ Verification Checklist

```
□ Run verify_features.py daily
□ Fix any ❌ items within 24h
□ Track improvements weekly
□ Review with team on Monday
□ Update roadmap monthly
□ Keep this card handy
□ Know the 4 critical blockers
□ Know the solutions off-hand
```

---

## 🎯 Success = When...

```
✅ 8+ features WORKING
✅ <1 feature NOT_WORKING
✅ Auth working end-to-end
✅ Chat working end-to-end
✅ Interviews working end-to-end
✅ Test coverage 70%+
✅ Response time <1s
✅ Error rate <1%
```

---

## 🚨 If Something Breaks

```
1. Run: python scripts/verify_features.py
2. Find: The ❌ feature
3. Read: The "Issue" line
4. Apply: The "Solution" line
5. Verify: Run script again
6. If still broken: Check FEATURE_VERIFICATION_LOOP.md
```

---

## 📞 Emergency Numbers

**If features suddenly break:**
1. Check health endpoint: `curl http://localhost:8000/health`
2. Check database: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"`
3. Check logs on Render/Railway
4. Run blocker check: `python scripts/verify_features.py`
5. Apply fix from error message
6. Re-test and verify

**If you can't figure it out:**
- Check FEATURE_VERIFICATION_LOOP.md "Solution Library"
- Check FEATURE_STATUS_REPORT.md "Support" section
- Check COMPLETE_ARCHITECTURE_ANALYSIS.md for context

---

## 🎓 What Each Script Does

```
verify_features.py        = Daily health check (2-5 min)
                           = Shows ✅ 🟡 ❌ status
                           = Saves report to JSON

track_improvements.py     = Weekly performance check (5 min)
                           = Compares baseline vs current
                           = Shows % improvement
                           = Saves metrics to JSON
```

---

## 🔧 The 4 Critical Fixes (Copy-Paste Ready)

### Fix #1 (Avatar Column)
```sql
ALTER TABLE users ADD COLUMN avatar_url TEXT;
```

### Fix #2 (Interview Sessions)
```
Location: Supabase SQL Editor
Command: \i backend/database/migrations/migration_interview_sessions.sql
```

### Fix #3 (Worker Setup)
```
Location: Render/Railway dashboard
Add: Worker service with `python worker.py`
Copy: Same environment variables as API service
```

### Fix #4 (Pinecone Dimension)
```
Verify: In Pinecone console
Check: Index dimension = 3072
If wrong: Recreate index with 3072 dimensions
```

---

## 📈 Performance Targets

```
Metric                  Current    Target    Status
────────────────────────────────────────────────
Auth Latency           150ms      <100ms    🟡
Chat Latency           2500ms     <1000ms   🟡
Vector Search          400ms      <200ms    🟡
Error Rate             5%         <1%       🟡
Test Coverage          40%        70%       🟡
Uptime                 95%        99.9%     🟡
```

---

## ✨ Pro Tips

```
1. Run verification every morning
   └─ Catch issues early

2. Keep a log of all fixes applied
   └─ Faster debugging next time

3. Measure before and after optimizations
   └─ Proves impact

4. Alert team on ❌ items
   └─ Prevents surprises

5. Review improvements weekly
   └─ Celebrate progress
```

---

## 🎯 One-Minute Summary

```
We have 9 critical features.
Currently: 4 working, 1 partial, 4 broken.
Blockers: 4 items (all have exact fixes).
Time to fix: 1 hour.
Time to optimize: 15 hours.
Time to enterprise-grade: 30 days.

Daily task: Run verify_features.py, fix any ❌.
Weekly task: Review metrics with team.
Monthly task: Plan next sprint based on data.

Start now: python scripts/verify_features.py
```

---

**Last Updated:** January 20, 2026
**Framework Status:** ✅ ACTIVE
**Next Action:** Run the script, apply fixes, celebrate wins!
