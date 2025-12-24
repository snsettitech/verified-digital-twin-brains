-- ============================================================================
-- ENABLE ROW LEVEL SECURITY (RLS) ON ALL PUBLIC TABLES
-- ============================================================================
-- IMPORTANT: This migration enables RLS and creates policies that allow
-- the service_role (backend) full access while blocking direct anon access.
-- Run this in Supabase SQL Editor.
-- ============================================================================

-- Tables to enable RLS on (26 tables total)
-- Note: After enabling RLS without policies, NO access is allowed by default

-- ============================================================================
-- STEP 1: ENABLE RLS ON ALL TABLES
-- ============================================================================

ALTER TABLE public.access_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.escalation_replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.verified_qna ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.answer_patches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_health_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rate_limit_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.twin_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.governance_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.twin_verification ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- STEP 2: CREATE SERVICE ROLE BYPASS POLICIES
-- ============================================================================
-- These policies allow the backend (using service_role key) full access
-- while the frontend (using anon key) gets no direct access.
-- The backend acts as a trusted intermediary.

-- Access Groups
CREATE POLICY "service_role_access_groups" ON public.access_groups
    FOR ALL USING (auth.role() = 'service_role');

-- Tenants
CREATE POLICY "service_role_tenants" ON public.tenants
    FOR ALL USING (auth.role() = 'service_role');

-- Conversations
CREATE POLICY "service_role_conversations" ON public.conversations
    FOR ALL USING (auth.role() = 'service_role');

-- Chunks
CREATE POLICY "service_role_chunks" ON public.chunks
    FOR ALL USING (auth.role() = 'service_role');

-- Users
CREATE POLICY "service_role_users" ON public.users
    FOR ALL USING (auth.role() = 'service_role');

-- Messages
CREATE POLICY "service_role_messages" ON public.messages
    FOR ALL USING (auth.role() = 'service_role');

-- Escalations
CREATE POLICY "service_role_escalations" ON public.escalations
    FOR ALL USING (auth.role() = 'service_role');

-- Escalation Replies
CREATE POLICY "service_role_escalation_replies" ON public.escalation_replies
    FOR ALL USING (auth.role() = 'service_role');

-- Verified QnA
CREATE POLICY "service_role_verified_qna" ON public.verified_qna
    FOR ALL USING (auth.role() = 'service_role');

-- Answer Patches
CREATE POLICY "service_role_answer_patches" ON public.answer_patches
    FOR ALL USING (auth.role() = 'service_role');

-- Citations
CREATE POLICY "service_role_citations" ON public.citations
    FOR ALL USING (auth.role() = 'service_role');

-- Group Memberships
CREATE POLICY "service_role_group_memberships" ON public.group_memberships
    FOR ALL USING (auth.role() = 'service_role');

-- Content Permissions
CREATE POLICY "service_role_content_permissions" ON public.content_permissions
    FOR ALL USING (auth.role() = 'service_role');

-- Group Limits
CREATE POLICY "service_role_group_limits" ON public.group_limits
    FOR ALL USING (auth.role() = 'service_role');

-- Ingestion Logs
CREATE POLICY "service_role_ingestion_logs" ON public.ingestion_logs
    FOR ALL USING (auth.role() = 'service_role');

-- Group Overrides
CREATE POLICY "service_role_group_overrides" ON public.group_overrides
    FOR ALL USING (auth.role() = 'service_role');

-- Training Jobs
CREATE POLICY "service_role_training_jobs" ON public.training_jobs
    FOR ALL USING (auth.role() = 'service_role');

-- Content Health Checks
CREATE POLICY "service_role_content_health_checks" ON public.content_health_checks
    FOR ALL USING (auth.role() = 'service_role');

-- Sources
CREATE POLICY "service_role_sources" ON public.sources
    FOR ALL USING (auth.role() = 'service_role');

-- Rate Limit Tracking
CREATE POLICY "service_role_rate_limit_tracking" ON public.rate_limit_tracking
    FOR ALL USING (auth.role() = 'service_role');

-- Twin API Keys
CREATE POLICY "service_role_twin_api_keys" ON public.twin_api_keys
    FOR ALL USING (auth.role() = 'service_role');

-- Sessions
CREATE POLICY "service_role_sessions" ON public.sessions
    FOR ALL USING (auth.role() = 'service_role');

-- User Invitations
CREATE POLICY "service_role_user_invitations" ON public.user_invitations
    FOR ALL USING (auth.role() = 'service_role');

-- Audit Logs
CREATE POLICY "service_role_audit_logs" ON public.audit_logs
    FOR ALL USING (auth.role() = 'service_role');

-- Governance Policies
CREATE POLICY "service_role_governance_policies" ON public.governance_policies
    FOR ALL USING (auth.role() = 'service_role');

-- Twin Verification
CREATE POLICY "service_role_twin_verification" ON public.twin_verification
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- VERIFICATION: Check that all tables have RLS enabled
-- ============================================================================
-- Run this query to verify RLS is enabled:
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
