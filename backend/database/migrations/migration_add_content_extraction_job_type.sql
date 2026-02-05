-- Migration: Add content_extraction job type
-- Purpose: Support async content extraction jobs in the jobs table

-- Drop the old constraint
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS valid_job_type;

-- Add new constraint with content_extraction
ALTER TABLE jobs ADD CONSTRAINT valid_job_type CHECK (
    job_type IN ('ingestion', 'reindex', 'health_check', 'other', 'graph_extraction', 'content_extraction')
);
