-- Migration: Add feedback_learning job type
-- Purpose: Support async persona feedback-learning jobs in the jobs table

-- Drop old constraint so we can extend the enum-like check.
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS valid_job_type;

-- Recreate constraint with feedback_learning included.
ALTER TABLE jobs ADD CONSTRAINT valid_job_type CHECK (
    job_type IN (
        'ingestion',
        'reindex',
        'health_check',
        'other',
        'graph_extraction',
        'content_extraction',
        'feedback_learning'
    )
);
