-- =====================================================
-- User Metrics and Events Tracking Schema
-- =====================================================
-- This migration adds tables for tracking user events,
-- analytics, and session data for the Digital Twin platform.
-- =====================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- User Events Table
-- Tracks all significant user actions for analytics
-- =====================================================
CREATE TABLE IF NOT EXISTS user_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    twin_id UUID REFERENCES twins(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_data JSONB DEFAULT '{}',
    session_id TEXT,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Create index for efficient querying
CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON user_events(user_id);
CREATE INDEX IF NOT EXISTS idx_user_events_twin_id ON user_events(twin_id);
CREATE INDEX IF NOT EXISTS idx_user_events_type ON user_events(event_type);
CREATE INDEX IF NOT EXISTS idx_user_events_created_at ON user_events(created_at DESC);

-- Event types:
-- 'signup' - User created account
-- 'login' - User logged in
-- 'logout' - User logged out
-- 'email_verified' - Email verification completed
-- 'onboarding_started' - Started onboarding flow
-- 'onboarding_step_completed' - Completed a step (step number in event_data)
-- 'onboarding_completed' - Finished all onboarding
-- 'twin_created' - Created a new twin
-- 'twin_launched' - Activated/launched a twin
-- 'source_uploaded' - Uploaded a knowledge source
-- 'conversation_started' - New conversation initiated
-- 'message_sent' - Message sent in conversation
-- 'escalation_created' - Question escalated to owner
-- 'escalation_resolved' - Owner answered escalation
-- 'settings_updated' - Changed twin/account settings
-- 'share_link_created' - Generated a share link
-- 'api_key_created' - Created API key

-- =====================================================
-- Session Analytics Table
-- Tracks chat session metrics for insights
-- =====================================================
CREATE TABLE IF NOT EXISTS session_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    visitor_id TEXT,
    visitor_type TEXT DEFAULT 'anonymous', -- 'anonymous', 'authenticated', 'api'
    started_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ,
    messages_count INT DEFAULT 0,
    user_messages_count INT DEFAULT 0,
    twin_messages_count INT DEFAULT 0,
    avg_confidence FLOAT,
    min_confidence FLOAT,
    escalations_count INT DEFAULT 0,
    sources_cited_count INT DEFAULT 0,
    access_group_id UUID REFERENCES access_groups(id) ON DELETE SET NULL,
    referrer TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_session_analytics_twin_id ON session_analytics(twin_id);
CREATE INDEX IF NOT EXISTS idx_session_analytics_started_at ON session_analytics(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_analytics_visitor_id ON session_analytics(visitor_id);

-- =====================================================
-- Page Views Table  
-- Tracks which pages users visit
-- =====================================================
CREATE TABLE IF NOT EXISTS page_views (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    page_path TEXT NOT NULL,
    page_title TEXT,
    referrer TEXT,
    session_id TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_page_views_user_id ON page_views(user_id);
CREATE INDEX IF NOT EXISTS idx_page_views_created_at ON page_views(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_page_views_page_path ON page_views(page_path);

-- =====================================================
-- Daily Metrics Aggregate Table
-- Pre-computed daily stats for dashboard
-- =====================================================
CREATE TABLE IF NOT EXISTS daily_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    conversations_count INT DEFAULT 0,
    messages_count INT DEFAULT 0,
    unique_visitors INT DEFAULT 0,
    avg_confidence FLOAT,
    escalations_count INT DEFAULT 0,
    escalations_resolved INT DEFAULT 0,
    avg_response_time_ms INT,
    sources_uploaded INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(twin_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_twin_date ON daily_metrics(twin_id, date DESC);

-- =====================================================
-- User Profiles Extended
-- Additional user metadata beyond Supabase auth
-- =====================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    email_verified BOOLEAN DEFAULT false,
    onboarding_completed BOOLEAN DEFAULT false,
    onboarding_step INT DEFAULT 0,
    stripe_customer_id TEXT,
    subscription_tier TEXT DEFAULT 'free', -- 'free', 'pro', 'enterprise'
    subscription_status TEXT DEFAULT 'active', -- 'active', 'canceled', 'past_due'
    last_login_at TIMESTAMPTZ,
    login_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- =====================================================
-- RLS Policies
-- =====================================================

-- User Events: Users can only see their own events
ALTER TABLE user_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own events" ON user_events;
CREATE POLICY "Users can view own events"
ON user_events FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role can insert events" ON user_events;
CREATE POLICY "Service role can insert events"
ON user_events FOR INSERT
WITH CHECK (true);

-- Session Analytics: Twin owners can view their analytics
ALTER TABLE session_analytics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Twin owners can view session analytics" ON session_analytics;
CREATE POLICY "Twin owners can view session analytics"
ON session_analytics FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM twins
        WHERE twins.id = session_analytics.twin_id
        AND twins.tenant_id = auth.uid()
    )
);

-- Page Views: Users can only see their own
ALTER TABLE page_views ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own page views" ON page_views;
CREATE POLICY "Users can view own page views"
ON page_views FOR SELECT
USING (auth.uid() = user_id);

-- Daily Metrics: Twin owners can view
ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Twin owners can view daily metrics" ON daily_metrics;
CREATE POLICY "Twin owners can view daily metrics"
ON daily_metrics FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM twins
        WHERE twins.id = daily_metrics.twin_id
        AND twins.tenant_id = auth.uid()
    )
);

-- User Profiles: Users can manage own profile
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
CREATE POLICY "Users can view own profile"
ON user_profiles FOR SELECT
USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
CREATE POLICY "Users can update own profile"
ON user_profiles FOR UPDATE
USING (auth.uid() = id);

-- =====================================================
-- Helper Functions
-- =====================================================

-- Function to log user events (call from backend)
CREATE OR REPLACE FUNCTION log_user_event(
    p_user_id UUID,
    p_event_type TEXT,
    p_twin_id UUID DEFAULT NULL,
    p_event_data JSONB DEFAULT '{}'
) RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
BEGIN
    INSERT INTO user_events (user_id, twin_id, event_type, event_data)
    VALUES (p_user_id, p_twin_id, p_event_type, p_event_data)
    RETURNING id INTO v_event_id;
    
    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update daily metrics (run via cron)
CREATE OR REPLACE FUNCTION update_daily_metrics(p_date DATE DEFAULT CURRENT_DATE) 
RETURNS void AS $$
BEGIN
    INSERT INTO daily_metrics (twin_id, date, conversations_count, messages_count)
    SELECT 
        sa.twin_id,
        p_date,
        COUNT(DISTINCT sa.session_id),
        SUM(sa.messages_count)
    FROM session_analytics sa
    WHERE DATE(sa.started_at) = p_date
    GROUP BY sa.twin_id
    ON CONFLICT (twin_id, date) 
    DO UPDATE SET
        conversations_count = EXCLUDED.conversations_count,
        messages_count = EXCLUDED.messages_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- Trigger for user profile creation
-- =====================================================
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', '')
    );
    
    -- Log signup event
    INSERT INTO user_events (user_id, event_type, event_data)
    VALUES (NEW.id, 'signup', jsonb_build_object('provider', NEW.raw_app_meta_data->>'provider'));
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created'
    ) THEN
        CREATE TRIGGER on_auth_user_created
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION handle_new_user();
    END IF;
END;
$$;

-- =====================================================
-- Grant permissions
-- =====================================================
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT ON user_events TO authenticated;
GRANT SELECT ON session_analytics TO authenticated;
GRANT SELECT ON page_views TO authenticated;
GRANT SELECT ON daily_metrics TO authenticated;
GRANT SELECT, UPDATE ON user_profiles TO authenticated;
