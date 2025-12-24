-- Per-Twin Specialization Migration
-- Adds specialization column to twins table

-- 1. Add specialization column
ALTER TABLE twins ADD COLUMN IF NOT EXISTS specialization TEXT DEFAULT 'vanilla';

-- 2. Add check constraint for valid specializations
-- (Uncomment when more specializations are added)
-- ALTER TABLE twins ADD CONSTRAINT valid_specialization 
--   CHECK (specialization IN ('vanilla', 'vc', 'legal', 'medical'));

-- 3. Create index for efficient filtering
CREATE INDEX IF NOT EXISTS idx_twins_specialization ON twins(specialization);

-- 4. Update existing twins to have default specialization
UPDATE twins SET specialization = 'vanilla' WHERE specialization IS NULL;
