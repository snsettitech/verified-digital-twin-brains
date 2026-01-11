# Worker Setup Guide for Render

This guide will help you set up the background worker service on Render to automatically process ingestion jobs.

## Why You Need a Worker

When you approve a source (like your X thread), it creates a training job that needs to be processed to:
1. Generate embeddings from the text
2. Store vectors in Pinecone
3. Update source status to "Live"

Without a worker, jobs sit in the queue and sources never get indexed.

## Step-by-Step Setup on Render

### Option A: Using Render Dashboard (Recommended)

1. **Go to Render Dashboard**
   - Navigate to https://dashboard.render.com
   - Select your account/organization

2. **Create New Background Worker**
   - Click **"New +"** button (top right)
   - Select **"Background Worker"**

3. **Connect Repository**
   - If not already connected, connect your GitHub repository:
     - Repository: `snsettitech/verified-digital-twin-brains`
     - Branch: `main`

4. **Configure Worker Settings**
   ```
   Name: verified-digital-twin-worker
   Root Directory: backend
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python worker.py
   ```

5. **Set Environment Variables**
   Copy ALL environment variables from your web service:
   - `SUPABASE_URL` (same as web service)
   - `SUPABASE_KEY` (same as web service)
   - `SUPABASE_SERVICE_KEY` (same as web service)
   - `JWT_SECRET` (same as web service)
   - `OPENAI_API_KEY` (same as web service)
   - `PINECONE_API_KEY` (same as web service)
   - `PINECONE_INDEX_NAME` (same as web service)
   - `DATABASE_URL` (if you have one, same as web service)
   
   **Worker-Specific Variables:**
   - `WORKER_ENABLED`: `true`
   - `WORKER_POLL_INTERVAL`: `5` (seconds between job checks)

6. **Deploy**
   - Click **"Create Background Worker"**
   - Wait for build to complete
   - Check logs to ensure worker starts successfully

### Option B: Using Render Blueprint (If Supported)

If Render supports blueprints from `render.yaml`:
1. Go to Render Dashboard
2. Click **"New +"** → **"Blueprint"**
3. Connect your repository
4. Render should auto-detect both web and worker services
5. Review and deploy both services

## Verification Steps

### 1. Check Worker is Running

**In Render Dashboard:**
- Go to your worker service
- Check **"Logs"** tab
- You should see:
  ```
  Training worker started (poll interval: 5s)
  ```

**If you see errors:**
- Check environment variables are set correctly
- Verify `WORKER_ENABLED=true`
- Check database connection (if using DATABASE_URL)

### 2. Test Job Processing

**Method 1: Check Existing Jobs**
1. Go to your backend API (or use Postman/curl)
2. Check if there are pending jobs:
   ```bash
   GET /training-jobs?twin_id=YOUR_TWIN_ID&status=queued
   ```
3. If jobs exist, the worker should process them automatically

**Method 2: Create Test Job**
1. Approve a source (if you have one in "Staged" status)
2. This creates a training job
3. Watch worker logs - you should see:
   ```
   Processing job <job_id> (type: ingestion, priority: 0)
   Job <job_id> completed successfully
   ```

### 3. Verify Source Indexing

After a job completes:
1. Check source status in database/API:
   ```bash
   GET /sources/YOUR_TWIN_ID
   ```
2. Find your source - it should show:
   - `staging_status`: `"live"` (not "approved")
   - `status`: `"live"`
   - `chunk_count`: Should be > 0

3. Test retrieval in simulator:
   - Ask a question about content from your X thread
   - Should now retrieve relevant chunks

## Troubleshooting

### Worker Not Processing Jobs

**Check 1: Worker is Running**
- Go to Render Dashboard → Worker service
- Check status is "Live" (green)
- Check logs for errors

**Check 2: Jobs Exist**
```bash
# Check if jobs are queued
GET /training-jobs?twin_id=YOUR_TWIN_ID&status=queued
```

**Check 3: Database Connection**
- Worker needs access to `jobs` table
- Verify `SUPABASE_SERVICE_KEY` is set (not just `SUPABASE_KEY`)
- Check database logs for connection errors

**Check 4: Manual Processing Test**
If worker isn't working, manually trigger processing:
```bash
POST /training-jobs/process-queue?twin_id=YOUR_TWIN_ID
Authorization: Bearer YOUR_TOKEN
```

### Common Errors

**Error: "Worker is disabled"**
- Set `WORKER_ENABLED=true` in environment variables

**Error: "No module named 'modules'"**
- Verify `Root Directory` is set to `backend`
- Check build logs for Python path issues

**Error: "Database connection failed"**
- Verify `SUPABASE_SERVICE_KEY` is set
- Check Supabase dashboard for connection limits

**Error: "Job processing failed"**
- Check worker logs for specific error
- Common causes:
  - Missing OpenAI API key
  - Missing Pinecone API key
  - Source text extraction failed
  - Network timeout

## Monitoring

### Worker Health Check

The worker logs will show:
- `Processing job <id>` - Job started
- `Job <id> completed successfully` - Job finished
- `Queue has X jobs` - Jobs waiting
- Any errors with stack traces

### Job Status Tracking

Check job status via API:
```bash
GET /training-jobs/{job_id}
```

Status values:
- `queued` - Waiting to be processed
- `processing` - Currently being processed
- `complete` - Successfully completed
- `failed` - Processing failed

## Cost Considerations

**Worker Pricing:**
- Render free tier: Limited hours/month
- Paid tier: ~$7/month for always-on worker
- Alternative: Use scheduled cron job to process queue periodically

**Optimization:**
- Increase `WORKER_POLL_INTERVAL` to reduce CPU usage (default: 5s)
- Worker only uses resources when processing jobs
- Idle worker uses minimal resources

## Alternative: Scheduled Processing

If you don't want an always-on worker, you can use Render's Cron Jobs:

1. Create a Cron Job service
2. Set schedule: `*/5 * * * *` (every 5 minutes)
3. Command: `python -c "import requests; requests.post('https://your-api-url/training-jobs/process-queue?twin_id=YOUR_TWIN_ID', headers={'Authorization': 'Bearer YOUR_TOKEN'})"`

This processes the queue every 5 minutes instead of continuously.

## Next Steps

After worker is running:
1. ✅ Verify worker logs show "Training worker started"
2. ✅ Check if pending jobs get processed
3. ✅ Verify sources change from "Approved" to "Live"
4. ✅ Test retrieval in simulator

If you encounter any issues, check the troubleshooting section above or review worker logs for specific error messages.

