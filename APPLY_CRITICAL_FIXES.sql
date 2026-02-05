-- ============================================================================
-- CRITICAL FIXES: Apply Database Blockers (#1 and #2)
-- ============================================================================
-- This script fixes the database blockers in the correct order.
-- Run this in Supabase SQL Editor to unblock the system.
-- Expected time: 5-10 minutes
-- ============================================================================

-- BLOCKER #1: Add avatar_url column to users table
-- This allows user authentication to work
-- ============================================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
CREATE INDEX IF NOT EXISTS idx_users_avatar_url ON users(avatar_url) WHERE avatar_url IS NOT NULL;
COMMENT ON COLUMN users.avatar_url IS 'User avatar URL from OAuth provider';

-- Verification
SELECT
    'BLOCKER #1: avatar_url' as check_name,
    COUNT(column_name) > 0 as is_fixed
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'avatar_url';

-- ============================================================================
-- BLOCKER #2: Create interview_sessions table
-- This allows cognitive interviews to persist state
-- ============================================================================
CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,

    -- State machine
    stage TEXT NOT NULL DEFAULT 'opening',

    -- Intent tracking
    intent_confirmed BOOLEAN DEFAULT FALSE,
    intent_summary TEXT,

    -- Interview blueprint
    blueprint_json JSONB DEFAULT '{}',

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

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_interview_sessions_twin_id ON interview_sessions(twin_id);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_conversation_id ON interview_sessions(conversation_id);

-- Enable RLS
ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;

-- RLS Policy
CREATE POLICY IF NOT EXISTS "interview_sessions_tenant_isolation" ON interview_sessions
    FOR ALL USING (
        twin_id IN (SELECT id FROM twins WHERE tenant_id = auth.uid())
    );

-- Verification
SELECT
    'BLOCKER #2: interview_sessions' as check_name,
    EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'interview_sessions') as is_fixed;

-- ============================================================================
-- SUMMARY: Database blockers should now be fixed
-- ============================================================================
-- Next steps:
-- 1. Reload PostgREST schema (Supabase Dashboard → Settings → API → Reload)
-- 2. Restart backend service (Render/Railway)
-- 3. Run verification script: python scripts/verify_features.py
-- 4. Verify auth + interviews, then configure worker and Pinecone as needed
-- ============================================================================

-- Final verification - show all fixed tables
SELECT
    table_name,
    EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = t.table_name) as exists
FROM (VALUES ('users'), ('interview_sessions')) as t(table_name);
