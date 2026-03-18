-- ============================================================================
-- ADK Migration: Conversation State Table
-- ============================================================================
-- Replaces LangGraph's PostgresSaver checkpointer with a simple
-- key-value state store for conversation threads.
--
-- Run via Supabase SQL Editor or migration tool.
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversation_state (
    conversation_id TEXT PRIMARY KEY,
    twin_id TEXT NOT NULL,
    state JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast lookup by twin
CREATE INDEX IF NOT EXISTS idx_conversation_state_twin_id
    ON conversation_state (twin_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_conversation_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversation_state_updated ON conversation_state;
CREATE TRIGGER trg_conversation_state_updated
    BEFORE UPDATE ON conversation_state
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_state_timestamp();

-- RLS: Enable row-level security
ALTER TABLE conversation_state ENABLE ROW LEVEL SECURITY;

-- Policy: Service role can do everything
CREATE POLICY "service_role_all" ON conversation_state
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Auto-cleanup: conversations older than 30 days
-- (Run as a cron job or scheduled function)
-- DELETE FROM conversation_state WHERE updated_at < now() - interval '30 days';
