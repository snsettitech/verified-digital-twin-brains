-- ============================================================================
-- Migration: Ingestion Diagnostics
-- Date: 2026-02-07
-- Purpose: Add structured error tracking and step-event logging to ingestion
--
-- Adds to sources table:
--   last_error      JSONB   - structured error object (code, message, http_status, provider_error_code, retryable, raw, step, provider)
--   last_error_at   TIMESTAMPTZ - when the last error occurred
--   last_provider   TEXT    - provider that last processed this source (youtube, linkedin, web, file, x, rss)
--   last_step       TEXT    - last ingestion step reached (fetch, parse, transcript, chunk, embed, index)
--   last_event_at   TIMESTAMPTZ - timestamp of most recent step event
--
-- Creates source_events table:
--   Append-only log of every step transition during ingestion.
--   Used by the UI diagnostics drawer to show a step timeline.
-- ============================================================================

-- 1. Extend sources table with diagnostics columns
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_error JSONB;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMPTZ;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_provider TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_step TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ;

-- 2. Create source_events table (append-only step log)
CREATE TABLE IF NOT EXISTS source_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  step TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
  error JSONB,
  metadata JSONB DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  ended_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_source_events_source_id ON source_events(source_id);
CREATE INDEX IF NOT EXISTS idx_source_events_twin_id ON source_events(twin_id);
CREATE INDEX IF NOT EXISTS idx_source_events_created_at ON source_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sources_last_error_at ON sources(last_error_at DESC) WHERE last_error IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sources_last_provider ON sources(last_provider) WHERE last_provider IS NOT NULL;

-- 4. RLS policies for source_events (match sources table pattern)
ALTER TABLE source_events ENABLE ROW LEVEL SECURITY;

-- Service role can do everything
CREATE POLICY source_events_service_all ON source_events
  FOR ALL
  USING (true)
  WITH CHECK (true);

-- Authenticated users can read events for twins they own (through the twins -> tenant join)
-- This mirrors the sources RLS pattern used elsewhere in the schema
CREATE POLICY source_events_select_own ON source_events
  FOR SELECT
  USING (
    twin_id IN (
      SELECT t.id FROM twins t
      JOIN users u ON u.tenant_id = t.tenant_id
      WHERE u.id = auth.uid()
    )
  );

-- 5. Update sources status CHECK constraint to include 'fetching' status
--    This allows the status progression: pending -> fetching -> processing -> live | error
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_status_check;
ALTER TABLE sources ADD CONSTRAINT sources_status_check CHECK (
  status IN (
    'pending', 'fetching', 'processing', 'processed',
    'error', 'staged', 'approved', 'rejected',
    'training', 'live', 'needs_attention'
  )
);

-- 6. Comment documentation
COMMENT ON COLUMN sources.last_error IS 'Structured JSONB error: {code, message, http_status, provider_error_code, retryable, raw, step, provider}';
COMMENT ON COLUMN sources.last_error_at IS 'Timestamp of the most recent ingestion error';
COMMENT ON COLUMN sources.last_provider IS 'Ingestion provider: youtube, linkedin, web, file, x, rss';
COMMENT ON COLUMN sources.last_step IS 'Last ingestion step reached: fetch, parse, transcript, chunk, embed, index';
COMMENT ON COLUMN sources.last_event_at IS 'Timestamp of the most recent source_events entry';
COMMENT ON TABLE source_events IS 'Append-only log of ingestion step transitions. Each row = one step attempt.';
