-- Migration: Interview Sessions for Intent-First Controller
-- Creates table to track interview state machine per session

CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    
    -- State machine
    stage TEXT NOT NULL DEFAULT 'opening',
    -- 'opening' | 'intent_capture' | 'confirm_intent' | 'deep_interview' | 'complete'
    
    -- Intent tracking
    intent_confirmed BOOLEAN DEFAULT FALSE,
    intent_summary TEXT,  -- Host's summary for confirmation
    
    -- Interview blueprint (generated after intent confirmation)
    blueprint_json JSONB DEFAULT '{}',
    -- Stores: { selected_packs: [], slot_order: [], intent_tags: [] }
    
    -- Progress tracking
    asked_template_ids TEXT[] DEFAULT '{}',
    turn_count INTEGER DEFAULT 0,
    slots_filled INTEGER DEFAULT 0,
    total_required_slots INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Index for fast lookup by twin
CREATE INDEX IF NOT EXISTS idx_interview_sessions_twin_id ON interview_sessions(twin_id);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_conversation_id ON interview_sessions(conversation_id);

-- Enable RLS
ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can manage sessions for their twins
CREATE POLICY "interview_sessions_tenant_isolation" ON interview_sessions
    FOR ALL USING (
        twin_id IN (
            SELECT id FROM twins WHERE tenant_id = auth.uid()
        )
    );

-- System RPC: Create or get session (bypasses RLS for service operations)
CREATE OR REPLACE FUNCTION get_or_create_interview_session(
    t_id UUID,
    conv_id UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    session_record interview_sessions%ROWTYPE;
BEGIN
    -- First, check if there's a completed session from the last 24 hours
    -- Return it so the interview can continue conversationally
    SELECT * INTO session_record
    FROM interview_sessions
    WHERE twin_id = t_id
      AND (conv_id IS NULL OR conversation_id = conv_id)
    ORDER BY 
        CASE WHEN stage = 'complete' THEN 0 ELSE 1 END,  -- Prefer complete sessions
        created_at DESC
    LIMIT 1;
    
    -- If found any session (complete or not), return it
    IF FOUND THEN
        RETURN to_jsonb(session_record);
    END IF;
    
    -- If no session exists at all, create a new one
    INSERT INTO interview_sessions (twin_id, conversation_id, stage)
    VALUES (t_id, conv_id, 'opening')
    RETURNING * INTO session_record;
    
    RETURN to_jsonb(session_record);
END;
$$;

-- System RPC: Update session state
CREATE OR REPLACE FUNCTION update_interview_session(
    session_id UUID,
    new_stage TEXT DEFAULT NULL,
    new_intent_confirmed BOOLEAN DEFAULT NULL,
    new_intent_summary TEXT DEFAULT NULL,
    new_blueprint JSONB DEFAULT NULL,
    add_template_id TEXT DEFAULT NULL,
    increment_turn BOOLEAN DEFAULT FALSE,
    new_slots_filled INTEGER DEFAULT NULL,
    new_total_slots INTEGER DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    session_record interview_sessions%ROWTYPE;
BEGIN
    UPDATE interview_sessions
    SET
        stage = COALESCE(new_stage, stage),
        intent_confirmed = COALESCE(new_intent_confirmed, intent_confirmed),
        intent_summary = COALESCE(new_intent_summary, intent_summary),
        blueprint_json = COALESCE(new_blueprint, blueprint_json),
        asked_template_ids = CASE 
            WHEN add_template_id IS NOT NULL 
            THEN array_append(asked_template_ids, add_template_id)
            ELSE asked_template_ids
        END,
        turn_count = CASE WHEN increment_turn THEN turn_count + 1 ELSE turn_count END,
        slots_filled = COALESCE(new_slots_filled, slots_filled),
        total_required_slots = COALESCE(new_total_slots, total_required_slots),
        updated_at = NOW(),
        completed_at = CASE WHEN new_stage = 'complete' THEN NOW() ELSE completed_at END
    WHERE id = session_id
    RETURNING * INTO session_record;
    
    RETURN to_jsonb(session_record);
END;
$$;

-- Grant execute to service role
GRANT EXECUTE ON FUNCTION get_or_create_interview_session TO service_role;
GRANT EXECUTE ON FUNCTION update_interview_session TO service_role;
