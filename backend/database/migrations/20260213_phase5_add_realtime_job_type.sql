-- Migration: Add realtime_ingestion job type
-- Purpose: Support async worker processing for Phase 5 realtime ingestion.

ALTER TABLE jobs DROP CONSTRAINT IF EXISTS valid_job_type;

ALTER TABLE jobs ADD CONSTRAINT valid_job_type CHECK (
    job_type IN (
        'ingestion',
        'reindex',
        'health_check',
        'other',
        'graph_extraction',
        'content_extraction',
        'feedback_learning',
        'realtime_ingestion'
    )
);
