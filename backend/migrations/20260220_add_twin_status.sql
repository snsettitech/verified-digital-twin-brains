-- Migration: Add Twin Status Field for Link-First Architecture
-- Date: 2026-02-20
-- Description: Adds state machine fields to twins table

-- =============================================================================
-- Add status field for state machine
-- =============================================================================

ALTER TABLE twins 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) 
DEFAULT 'active' 
CHECK (status IN ('draft', 'ingesting', 'claims_ready', 'clarification_pending', 'persona_built', 'active', 'archived'));

-- =============================================================================
-- Add creation_mode field to distinguish paths
-- =============================================================================

ALTER TABLE twins 
ADD COLUMN IF NOT EXISTS creation_mode VARCHAR(20) 
DEFAULT 'manual' 
CHECK (creation_mode IN ('manual', 'link_first'));

-- =============================================================================
-- Add comments for documentation
-- =============================================================================

COMMENT ON COLUMN twins.status IS 
'Twin lifecycle state: draft -> ingesting -> claims_ready -> clarification_pending -> persona_built -> active';

COMMENT ON COLUMN twins.creation_mode IS 
'Creation path: manual (onboarding_v2 questionnaire) or link_first (content ingestion)';

-- =============================================================================
-- Create indexes for common queries
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_twins_status ON twins(status);
CREATE INDEX IF NOT EXISTS idx_twins_creation_mode ON twins(creation_mode);
CREATE INDEX IF NOT EXISTS idx_twins_status_creation ON twins(status, creation_mode);

-- =============================================================================
-- Backfill existing twins
-- =============================================================================

UPDATE twins 
SET status = 'active', 
    creation_mode = 'manual' 
WHERE status IS NULL;

-- =============================================================================
-- Verify migration
-- =============================================================================

-- Count by status
SELECT status, creation_mode, COUNT(*) 
FROM twins 
GROUP BY status, creation_mode;

-- Migration complete
