-- ============================================================================
-- Phase 5: Realtime Ingestion (No AssemblyAI) - RLS Hardening
-- Adds Row Level Security policies to prevent cross-tenant leakage via Supabase REST.
-- ============================================================================

ALTER TABLE IF EXISTS ingestion_stream_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ingestion_stream_events ENABLE ROW LEVEL SECURITY;

-- Sessions: allow SELECT only for same-tenant twins.
DROP POLICY IF EXISTS "Tenant Isolation: View Ingestion Stream Sessions" ON ingestion_stream_sessions;
CREATE POLICY "Tenant Isolation: View Ingestion Stream Sessions" ON ingestion_stream_sessions
FOR SELECT
USING (
  EXISTS (
    SELECT 1
    FROM twins
    WHERE twins.id = ingestion_stream_sessions.twin_id
      AND twins.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

-- Events: allow SELECT only when parent session's twin belongs to the same tenant.
DROP POLICY IF EXISTS "Tenant Isolation: View Ingestion Stream Events" ON ingestion_stream_events;
CREATE POLICY "Tenant Isolation: View Ingestion Stream Events" ON ingestion_stream_events
FOR SELECT
USING (
  EXISTS (
    SELECT 1
    FROM ingestion_stream_sessions s
    JOIN twins t ON t.id = s.twin_id
    WHERE s.id = ingestion_stream_events.session_id
      AND t.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

