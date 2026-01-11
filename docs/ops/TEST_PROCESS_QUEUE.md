# Testing Process Queue Functionality

This guide helps you test the Process Queue button and verify it's working correctly.

## Current Status

Based on diagnostics:
- ✅ **1 Approved Source** waiting for indexing (X Thread)
- ✅ **1 Queued Training Job** in database
- ✅ **Endpoint configured** at `/training-jobs/process-queue`

## Test Methods

### Method 1: Frontend Button (Recommended)

1. **Deploy Frontend** (if not already deployed)
   - The Process Queue button should appear on the staging page
   - Vercel should auto-deploy from `main` branch

2. **Navigate to Staging Page**
   - Go to: `https://your-frontend-url/dashboard/knowledge/staging`
   - Or locally: `http://localhost:3000/dashboard/knowledge/staging`

3. **Look for the Button**
   - Should see: **"Process Queue (1 approved)"** button in green
   - Located in the top right area

4. **Click the Button**
   - Button will show spinner: "Processing..."
   - Wait for processing to complete (usually 10-30 seconds)

5. **Check Results**
   - Success message appears showing:
     - Processed: X job(s)
     - Failed: X job(s) (if any)
     - Remaining: X job(s)
   - Source status changes from "Approved" → "Live"
   - Source should now have `chunk_count > 0`

6. **Verify in Simulator**
   - Go to simulator
   - Ask a question about your X Thread content
   - Should now retrieve relevant information

### Method 2: API Direct Test

If frontend isn't deployed yet, test the API directly:

**Using curl:**
```bash
curl -X POST "https://your-backend-url/training-jobs/process-queue?twin_id=YOUR_TWIN_ID" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json"
```

**Using Python script:**
```bash
cd backend
python ../scripts/test_process_queue.py
```

**Using Postman/Insomnia:**
- Method: POST
- URL: `https://your-backend-url/training-jobs/process-queue?twin_id=YOUR_TWIN_ID`
- Headers:
  - `Authorization: Bearer YOUR_AUTH_TOKEN`
  - `Content-Type: application/json`

### Method 3: Browser DevTools

1. Open your frontend in browser
2. Open DevTools (F12) → Network tab
3. Navigate to staging page
4. Click "Process Queue" button
5. Watch for POST request to `/training-jobs/process-queue`
6. Check response:
   ```json
   {
     "status": "success",
     "processed": 1,
     "failed": 0,
     "remaining": 0,
     "message": "Processed 1 job(s), 0 failed, 0 remaining in queue"
   }
   ```

## Expected Behavior

### Success Case

**Before Processing:**
- Source status: `approved`
- Source `chunk_count`: `null` or `0`
- Training job status: `queued`

**After Processing:**
- Source status: `live`
- Source `chunk_count`: `> 0` (e.g., 15, 23, etc.)
- Training job status: `complete`
- Success message displayed

**API Response:**
```json
{
  "status": "success",
  "processed": 1,
  "failed": 0,
  "remaining": 0,
  "message": "Processed 1 job(s), 0 failed, 0 remaining in queue"
}
```

### Error Cases

**Authentication Error (401):**
```json
{
  "detail": "Not authenticated"
}
```
**Fix:** Check your auth token is valid

**Access Denied (403):**
```json
{
  "detail": "Not authorized to perform this action"
}
```
**Fix:** Make sure you own the twin

**No Jobs Found:**
```json
{
  "status": "success",
  "processed": 0,
  "failed": 0,
  "remaining": 0,
  "message": "Processed 0 job(s), 0 failed, 0 remaining in queue"
}
```
**Meaning:** No queued jobs to process (this is OK if all jobs are already processed)

## Troubleshooting

### Button Not Appearing

**Check:**
1. Are there approved sources? Button only shows if `staging_status === 'approved'`
2. Is frontend deployed? Check Vercel deployment status
3. Hard refresh browser (Ctrl+F5 / Cmd+Shift+R)

### Processing Fails

**Check Backend Logs:**
- Render Dashboard → Your backend service → Logs
- Look for errors during job processing
- Common issues:
  - Missing OpenAI API key
  - Missing Pinecone API key
  - Source text extraction failed
  - Network timeout

**Check Job Status:**
```bash
GET /training-jobs?twin_id=YOUR_TWIN_ID&status=failed
```

### Source Stays "Approved"

**Possible Causes:**
1. Job processing failed silently
2. Database update didn't complete
3. Frontend cache showing old data

**Fix:**
1. Refresh the page
2. Check backend logs for errors
3. Manually check source status in database:
   ```sql
   SELECT id, filename, staging_status, chunk_count 
   FROM sources 
   WHERE twin_id = 'YOUR_TWIN_ID' 
   AND staging_status = 'approved';
   ```

### No Results in Simulator

**Check:**
1. Source is actually "Live" (not just "Approved")
2. `chunk_count > 0` in database
3. Vectors exist in Pinecone (check Pinecone dashboard)
4. Query matches content (try more specific questions)

## Verification Checklist

After clicking Process Queue, verify:

- [ ] Success message appears
- [ ] Source status changed to "Live"
- [ ] Source has `chunk_count > 0`
- [ ] Training job status is "Complete"
- [ ] Can retrieve content in simulator
- [ ] No errors in backend logs

## Next Steps After Testing

1. **If successful:**
   - Your X Thread should now be searchable
   - Test retrieval in simulator
   - Consider setting up the worker service for automatic processing

2. **If failed:**
   - Check backend logs for specific error
   - Verify environment variables are set
   - Check source has extractable text content
   - Retry processing

3. **For production:**
   - Set up worker service (see `WORKER_SETUP_GUIDE.md`)
   - Jobs will process automatically when sources are approved
   - No need to manually click Process Queue

## Quick Test Commands

**Check current status:**
```bash
cd backend
python ../scripts/check_worker_status.py
```

**Test API endpoint:**
```bash
cd backend
python ../scripts/test_process_queue.py
```

**Check sources:**
```bash
# Via API
GET /sources/YOUR_TWIN_ID

# Look for sources with staging_status='approved'
```

**Check jobs:**
```bash
# Via API
GET /training-jobs?twin_id=YOUR_TWIN_ID&status=queued
```

