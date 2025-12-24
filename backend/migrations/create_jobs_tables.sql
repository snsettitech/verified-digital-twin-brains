-- =====================================================
-- Jobs and Job Logs Tables
-- =====================================================
-- Background processing foundation for tracking
-- long-running operations like ingestion, reindexing, etc.
-- =====================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- Jobs Table
-- Tracks background job status and metadata
-- =====================================================
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID REFERENCES twins(id) ON DELETE SET NULL,
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    job_type TEXT NOT NULL,
    priority INT DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    CONSTRAINT valid_status CHECK (
        status IN ('queued', 'processing', 'needs_attention', 'complete', 'failed')
    ),
    CONSTRAINT valid_job_type CHECK (
        job_type IN ('ingestion', 'reindex', 'health_check', 'other')
    )
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_twin_id ON jobs(twin_id);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

-- =====================================================
-- Job Logs Table
-- Immutable log entries for each job
-- =====================================================
CREATE TABLE IF NOT EXISTS job_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    log_level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    
    CONSTRAINT valid_log_level CHECK (
        log_level IN ('info', 'warning', 'error')
    )
);

-- Create index for job_id lookups
CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_logs_created_at ON job_logs(created_at DESC);

-- =====================================================
-- Trigger to auto-update jobs.updated_at
-- =====================================================
CREATE OR REPLACE FUNCTION update_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_jobs_updated_at ON jobs;
CREATE TRIGGER trigger_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_jobs_updated_at();

-- =====================================================
-- RLS Policies
-- =====================================================

-- Jobs: Users can view jobs for their twins
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own jobs" ON jobs;
CREATE POLICY "Users can view own jobs"
ON jobs FOR SELECT
USING (
    twin_id IS NULL OR
    EXISTS (
        SELECT 1 FROM twins
        WHERE twins.id = jobs.twin_id
        AND twins.tenant_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Service role can manage jobs" ON jobs;
CREATE POLICY "Service role can manage jobs"
ON jobs FOR ALL
USING (true)
WITH CHECK (true);

-- Job Logs: Users can view logs for their jobs
ALTER TABLE job_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own job logs" ON job_logs;
CREATE POLICY "Users can view own job logs"
ON job_logs FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM jobs
        WHERE jobs.id = job_logs.job_id
        AND (
            jobs.twin_id IS NULL OR
            EXISTS (
                SELECT 1 FROM twins
                WHERE twins.id = jobs.twin_id
                AND twins.tenant_id = auth.uid()
            )
        )
    )
);

DROP POLICY IF EXISTS "Service role can manage job logs" ON job_logs;
CREATE POLICY "Service role can manage job logs"
ON job_logs FOR ALL
USING (true)
WITH CHECK (true);

-- =====================================================
-- Grant permissions
-- =====================================================
GRANT SELECT ON jobs TO authenticated;
GRANT SELECT ON job_logs TO authenticated;
