-- ============================================================================
-- Phase 5: Realtime Ingestion (No AssemblyAI)
-- Adds stream session + stream event primitives for near-realtime ingest flows.
-- ============================================================================

-- Session lifecycle for a realtime ingest stream (audio/text chunk append model)
CREATE TABLE IF NOT EXISTS ingestion_stream_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    tenant_id UUID,
    creator_id TEXT,
    owner_id UUID,
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active',
    source_type TEXT NOT NULL DEFAULT 'realtime_stream',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_sequence_no INTEGER NOT NULL DEFAULT 0,
    appended_chars INTEGER NOT NULL DEFAULT 0,
    indexed_chars INTEGER NOT NULL DEFAULT 0,
    last_indexed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    committed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('active', 'committed', 'failed', 'cancelled'))
);

-- Ordered event log for each stream session. Used for replay + idempotency.
CREATE TABLE IF NOT EXISTS ingestion_stream_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES ingestion_stream_sessions(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'transcript_partial',
    text_chunk TEXT NOT NULL DEFAULT '',
    chars_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (sequence_no >= 0),
    CHECK (event_type IN ('transcript_partial', 'transcript_final', 'text', 'marker'))
);

-- Idempotency key: same session + same sequence number should never duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ingestion_stream_events_session_sequence
ON ingestion_stream_events(session_id, sequence_no);

CREATE INDEX IF NOT EXISTS idx_ingestion_stream_sessions_twin_status
ON ingestion_stream_sessions(twin_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_stream_sessions_creator
ON ingestion_stream_sessions(creator_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_stream_events_session_created
ON ingestion_stream_events(session_id, created_at);

-- Keep sessions' updated_at fresh during writes/updates.
CREATE OR REPLACE FUNCTION set_ingestion_stream_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ingestion_stream_sessions_updated_at ON ingestion_stream_sessions;
CREATE TRIGGER trg_ingestion_stream_sessions_updated_at
BEFORE UPDATE ON ingestion_stream_sessions
FOR EACH ROW
EXECUTE FUNCTION set_ingestion_stream_sessions_updated_at();
