# YouTube 403 Error: Actionable Troubleshooting Guide

**Quick Access**: Use this guide to solve YouTube 403 errors step-by-step.

---

## 🚀 Quick Fix (Do This First)

### Step 1: Try a Public Educational Video

```
Copy this URL exactly:
https://www.youtube.com/watch?v=9bZkp7q19f0

Add it to your system
Wait for result (should see "Fetched official YouTube transcript")
```

**Result Options:**
- ✅ Success in < 1 second → System works! Your video has restrictions.
- ❌ Still 403? → Go to **Diagnosis Section** below

---

## 🔍 Diagnosis: What Type of 403 Did You Get?

### Type A: Immediate Failure (Never Even Tried)

**Symptoms:**
```
Error: "Invalid YouTube URL"
```

**Fix:**
- Copy exact YouTube URL from address bar
- Format: `https://www.youtube.com/watch?v=VIDEO_ID`
- Remove any `&t=`, `&list=` parameters

---

### Type B: HTTP 429 Then Success

**Symptoms:**
```
[YouTube] Attempt 1 failed [rate_limit]: HTTP Error 429
[YouTube] Waiting 2s before retry...
[YouTube] Attempt 2: SUCCESS
```

**Status:** ✅ **WORKING NOW** - Rate limit was temporary

**What happened:**
- YouTube detected too many requests from IP
- System automatically retried with backoff
- Retry succeeded

**Next time:**
- Spread requests further apart (wait 5 minutes between videos)

---

### Type C: HTTP 403 After 5 Retries

**Symptoms:**
```
[YouTube] Attempt 1 failed [auth]: HTTP 403
[YouTube] Attempt 2 failed [auth]: HTTP 403
[YouTube] Attempt 3 failed [auth]: HTTP 403
[YouTube] Attempt 4 failed [auth]: HTTP 403
[YouTube] Attempt 5 failed [auth]: HTTP 403
[YouTube] All 5 attempts failed
```

**Root Cause:** One of these:

| Question | Answer | Fix |
|:---------|:-------|-----|
| **Is video playable in YOUR browser?** | NO | Video is unavailable → Try different video |
| **Does video have "CC" badge?** | NO | Will use audio transcription → Wait 60 seconds |
| **Is video 18+ (age-restricted)?** | YES | Need authentication → Use YOUTUBE_PROXY |
| **Is video region-blocked?** | YES | Blocked by country → Use YOUTUBE_PROXY |
| **Is video private/deleted?** | YES | No longer available → Try different video |

**Jump to:** Your matching answer below →

---

## 📋 Solution Guide (Pick Your Scenario)

### Scenario 1: "Video plays fine in MY browser"

**Then why 403?**
```
YouTube detected our server as a bot
(Container IP, no cookies, etc.)

This is NOW FIXED with:
✅ Multiple client emulation
✅ Exponential backoff retry
✅ Smart error handling
```

**What to do:**
1. ✅ Try the test video (see Quick Fix above)
2. ✅ If test works, your video has restrictions (see below)
3. ❌ If test fails, contact ops (system issue)

---

### Scenario 2: "Video is age-restricted (18+)"

**System says:** "This video requires authentication"

**Why it happens:**
```
YouTube requires login verification for adult content
Render server can't log in
System denies access
```

**Solutions (in order):**

#### Solution 2A: Use YOUTUBE_PROXY ⭐ (Recommended)
```
Step 1: Get proxy service
        - Ask infrastructure/ops team
        - Or use commercial service

Step 2: Add to Render Dashboard
        Settings → Environment Variables

        YOUTUBE_PROXY=http://proxy.example.com:8080

        (Or with auth: user:pass@proxy.example.com:8080)

Step 3: Redeploy backend
        Render dashboard → Manual Deploy

Step 4: Try adding video again
        Should work now (different IP = different access)
```

#### Solution 2B: Use Browser Cookies (Advanced)
```
Step 1: Export cookies from your browser
        Chrome: Use "Get cookies.txt" extension
        Firefox: Use "Cookies.txt export" add-on

Step 2: Save file locally
        Name: youtube_cookies.txt

Step 3: Add to Render Dashboard
        YOUTUBE_COOKIES_FILE=https://...path.../youtube_cookies.txt

Step 4: Redeploy and retry
        Should work (using authenticated cookies)
```

#### Solution 2C: Use Different Video (Quickest)
```
Try a non-age-restricted alternative instead
```

---

### Scenario 3: "Video is region-blocked"

**System says:** "This video is not available in your region"

**Why it happens:**
```
YouTube restricts video by country
Render server is in US
If content not available in US → 403 Forbidden
```

**Solutions:**

#### Solution 3A: Use YOUTUBE_PROXY ⭐ (Recommended)
```
Step 1: Get proxy routed through allowed country
        Ask ops team for proxy in correct region

Step 2: Add to Render Dashboard
        YOUTUBE_PROXY=http://proxy-in-allowed-country:8080

Step 3: Redeploy and retry
        Should work (server appears to be in that region)
```

#### Solution 3B: Use Different Video (Quickest)
```
Find video available globally instead
```

---

### Scenario 4: "Video is private or deleted"

**System says:** "This video is unavailable"

**Why:**
```
Video owner made it private
OR
Video owner deleted it
```

**Solution:**
```
❌ CANNOT FIX - Video no longer publicly accessible
✅ Use different public video instead
```

**How to find replacement:**
```
1. Search original topic on YouTube
2. Look for videos with "CC" badge (captions)
3. Click into that video
4. Copy URL from address bar
5. Try adding that instead
```

---

### Scenario 5: "Video has no captions but plays fine"

**System says:** "No captions found. Starting robust audio download..."

**Why:**
```
Video has no closed captions (CC badge)
System will download audio and transcribe it
(Using Whisper speech-to-text)
```

**Expected behavior:**
```
Time: 30-60 seconds
Result: Full transcript from audio
This is NORMAL and working correctly ✅
```

**What to do:**
```
Just wait 60 seconds for transcription to complete
System is working (slower but thorough)
```

---

### Scenario 6: "Got same video to work before, now 403"

**Possible causes:**

#### Cause A: Rate Limiting (YouTube Mad About Traffic)
```
YouTube thinks: "Too many requests from this IP!"

Solution:
1. Wait 10 minutes
2. Try again
3. (System now has backoff, so this is handled)
```

#### Cause B: Video Status Changed
```
Video was public, now private
OR
Video was available globally, now region-blocked

Solution: Try different video
```

#### Cause C: System Not Deployed
```
Fixes haven't deployed to production yet

Solution:
1. Check Render dashboard
2. Verify deployment shows the fix
3. Trigger manual deploy if needed
```

---

## 🧪 Verification Checklist

### Is System Working? (Test This)

```
Step 1: Try official test video
URL: https://www.youtube.com/watch?v=9bZkp7q19f0

Expected:
✅ [YouTube] Fetched official YouTube transcript (3000+ chars)
✅ Completes in < 1 second

Result:
  YES ✅ → System works
  NO ❌  → System problem, check logs
```

### Is Your Video Specific?

```
Step 1: Check your video in your browser
URL: Your video URL
Click play

Expected:
✅ Video plays and you can watch it
✅ Look for "CC" badge (closed captions)

Result:
  YES ✅ → Video playable
  NO ❌  → Video doesn't work for you either
```

### Is It Rate Limiting?

```
Step 1: Check log messages
Look for: "HTTP 429" or "Rate Limited"

Expected after 5-10 minutes:
✅ Video should work on retry

Result:
  YES ✅ → It was rate limiting (normal)
  NO ❌  → Different issue (see scenarios above)
```

---

## 🔧 Configuration Changes (Advanced)

### Current Configuration (render.yaml)

```yaml
YOUTUBE_MAX_RETRIES: "5"              # Try up to 5 times
YOUTUBE_ASR_PROVIDER: "openai"        # Use OpenAI for transcription
YOUTUBE_ASR_MODEL: "whisper-large-v3" # Best quality
YOUTUBE_LANGUAGE_DETECTION: "true"    # Auto-detect language
YOUTUBE_PII_SCRUB: "true"            # Flag private info
YOUTUBE_VERBOSE_LOGGING: "false"      # Extra debug logs
```

### To Enable Debug Logging

```
In Render Dashboard:
  Settings → Environment Variables

Change:
  YOUTUBE_VERBOSE_LOGGING=true

Redeploy

Now you'll see detailed logs in Render dashboard
```

### To Increase Retry Attempts

```
In Render Dashboard:
  Settings → Environment Variables

Change:
  YOUTUBE_MAX_RETRIES=10

Redeploy

System will try up to 10 times instead of 5
(Each retry waits exponentially longer)
```

### To Add Proxy Support

```
In Render Dashboard:
  Settings → Environment Variables

Add:
  YOUTUBE_PROXY=http://your-proxy-url:8080

  (Or with auth)
  YOUTUBE_PROXY=http://user:password@proxy-url:8080

Redeploy

All YouTube requests will route through proxy
```

---

## 📊 Decision Tree (Pick Your Path)

```
Got YouTube 403 error?
         │
         ↓
Is test video working?
(https://www.youtube.com/watch?v=9bZkp7q19f0)
    │           │
   YES          NO
    │           │
    ↓           ↓
Your video  System not
has issues  working yet
    │       (Contact ops)
    ↓
Does it play in
YOUR browser?
    │           │
   YES          NO
    │           │
    ↓           ↓
Has "CC"    Video unavailable
badge?      (Try different video)
    │    │
   YES   NO
    │    │
    ↓    ↓
Age/Region  Will auto-
restricted?  transcribe
    │    │     (Wait 60s)
   YES   NO
    │    │
    ↓    ↓
Use proxy  Try after
or diff    60 seconds
video      (Should work)
```

---

## 📞 When to Contact Support

### Contact Ops If:

```
❌ Test video (9bZkp7q19f0) still gets 403
❌ You set YOUTUBE_PROXY but still failing
❌ Same error across ALL videos
❌ Error pattern repeats hourly
```

### Tell Them:

```
1. Which video URL you tried
2. Full error message from logs
3. When you first saw the error
4. Whether it worked before
5. Steps you already tried
```

### Example Report:

```
"Trying to add https://www.youtube.com/watch?v=VIDEO_ID
Getting: HTTP 403 error after 5 retries
Even public videos fail
Started today after deployment
Already tried: restart, wait 10 min, diff video"
```

---

## 📚 More Information

For deeper understanding, see:

- **[YOUTUBE_403_ROOT_CAUSE_ANALYSIS.md](YOUTUBE_403_ROOT_CAUSE_ANALYSIS.md)**
  - Technical details
  - Why the fix works
  - Configuration reference

- **[YOUTUBE_403_VISUAL_REFERENCE.md](YOUTUBE_403_VISUAL_REFERENCE.md)**
  - Diagrams and flowcharts
  - Quick reference tables
  - Testing cases

- **[YOUTUBE_403_BEFORE_AFTER.md](YOUTUBE_403_BEFORE_AFTER.md)**
  - Code changes made
  - Performance impact
  - Testing scripts

---

## ✅ Success Indicators

### These Mean It's Working

```
✅ "Fetched official YouTube transcript"
   → Video has captions, using official API (fastest)

✅ "Audio transcribed via Whisper"
   → Downloaded audio and transcribed (slower but works)

✅ "Attempt 3: SUCCESS"
   → Rate limited but recovered with exponential backoff

✅ Completes in < 1 second
   → Using official captions (very good)

✅ Completes in 30-60 seconds
   → Using audio transcription (still good)
```

### These Mean There's an Issue

```
❌ "All 5 attempts failed"
   → Video requires authentication or is blocked

❌ "HTTP 403" after 5 retries
   → Age-restricted, region-blocked, or private

❌ "This video is unavailable"
   → Video deleted or made private

❌ "This video requires authentication"
   → Age-restricted content
```

---

## 🎯 One-Minute Fix

If you only have 1 minute:

```
1. Open: https://www.youtube.com/watch?v=9bZkp7q19f0
2. Try adding it to your system
3. If works ✅ → Your video has restrictions, try different one
4. If fails ❌ → System issue, contact ops
```

That's it.
