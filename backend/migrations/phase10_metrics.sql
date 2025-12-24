-- Phase 10: Enterprise Scale & Reliability
-- Migration: Create metrics and usage quotas tables

-- ============================================================================
-- Metrics Table - Time-series metrics storage
-- ============================================================================

CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    user_id UUID,
    metric_type TEXT NOT NULL,
    -- Types: 'retrieval_latency_ms', 'llm_latency_ms', 'total_latency_ms', 
    --        'tokens_prompt', 'tokens_completion', 'tokens_total',
    --        'error_count', 'request_count'
    value FLOAT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_metrics_twin_id ON metrics(twin_id);
CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_twin_type_time ON metrics(twin_id, metric_type, created_at DESC);

-- ============================================================================
-- Usage Quotas Table - Tenant quotas and limits
-- ============================================================================

CREATE TABLE IF NOT EXISTS usage_quotas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    quota_type TEXT NOT NULL,
    -- Types: 'daily_tokens', 'daily_requests', 'monthly_tokens', 'monthly_requests'
    limit_value INTEGER NOT NULL DEFAULT 100000,
    current_usage INTEGER DEFAULT 0,
    reset_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, quota_type)
);

-- Index for quota lookups
CREATE INDEX IF NOT EXISTS idx_usage_quotas_tenant ON usage_quotas(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usage_quotas_reset ON usage_quotas(reset_at);

-- ============================================================================
-- Service Health Logs - For health check history
-- ============================================================================

CREATE TABLE IF NOT EXISTS service_health_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name TEXT NOT NULL,
    -- Services: 'supabase', 'pinecone', 'openai', 'backend'
    status TEXT NOT NULL,
    -- Status: 'healthy', 'degraded', 'unhealthy'
    response_time_ms FLOAT,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for health history
CREATE INDEX IF NOT EXISTS idx_health_logs_service ON service_health_logs(service_name);
CREATE INDEX IF NOT EXISTS idx_health_logs_created ON service_health_logs(created_at DESC);

-- ============================================================================
-- Daily Aggregates View - For dashboard performance
-- ============================================================================

CREATE OR REPLACE VIEW metrics_daily_summary AS
SELECT 
    twin_id,
    metric_type,
    DATE(created_at) as date,
    COUNT(*) as count,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    SUM(value) as sum_value
FROM metrics
GROUP BY twin_id, metric_type, DATE(created_at);

-- ============================================================================
-- Enable RLS
-- ============================================================================

ALTER TABLE metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_health_logs ENABLE ROW LEVEL SECURITY;

-- Service role bypass for backend
CREATE POLICY "service_role_bypass_metrics" ON metrics
    FOR ALL TO service_role USING (true) WITH CHECK (true);
    
CREATE POLICY "service_role_bypass_quotas" ON usage_quotas
    FOR ALL TO service_role USING (true) WITH CHECK (true);
    
CREATE POLICY "service_role_bypass_health" ON service_health_logs
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- Function to reset daily quotas
-- ============================================================================

CREATE OR REPLACE FUNCTION reset_daily_quotas()
RETURNS void AS $$
BEGIN
    UPDATE usage_quotas 
    SET current_usage = 0, 
        reset_at = NOW() + INTERVAL '1 day',
        updated_at = NOW()
    WHERE quota_type LIKE 'daily_%' 
    AND reset_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function to increment quota usage (atomic)
-- ============================================================================

CREATE OR REPLACE FUNCTION increment_quota_usage(
    p_tenant_id UUID,
    p_quota_type TEXT,
    p_increment INTEGER DEFAULT 1
)
RETURNS TABLE (
    allowed BOOLEAN,
    current_usage INTEGER,
    limit_value INTEGER
) AS $$
DECLARE
    v_quota RECORD;
BEGIN
    -- Get or create quota record
    SELECT * INTO v_quota 
    FROM usage_quotas 
    WHERE tenant_id = p_tenant_id AND quota_type = p_quota_type
    FOR UPDATE;
    
    IF NOT FOUND THEN
        -- Create default quota (100k daily tokens)
        INSERT INTO usage_quotas (tenant_id, quota_type, limit_value, reset_at)
        VALUES (p_tenant_id, p_quota_type, 100000, NOW() + INTERVAL '1 day')
        RETURNING * INTO v_quota;
    END IF;
    
    -- Check if quota would be exceeded
    IF v_quota.current_usage + p_increment > v_quota.limit_value THEN
        RETURN QUERY SELECT 
            false::BOOLEAN, 
            v_quota.current_usage, 
            v_quota.limit_value;
        RETURN;
    END IF;
    
    -- Increment usage
    UPDATE usage_quotas 
    SET current_usage = current_usage + p_increment,
        updated_at = NOW()
    WHERE id = v_quota.id
    RETURNING current_usage INTO v_quota.current_usage;
    
    RETURN QUERY SELECT 
        true::BOOLEAN, 
        v_quota.current_usage, 
        v_quota.limit_value;
END;
$$ LANGUAGE plpgsql;
