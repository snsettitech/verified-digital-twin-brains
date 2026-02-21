-- Migration: Link-First Persona Claims
-- Date: 2026-02-20
-- Description: Minimal schema for claim-level citations

-- =============================================================================
-- Table: persona_claims
-- Stores atomic claims extracted from source chunks
-- =============================================================================

CREATE TABLE IF NOT EXISTS persona_claims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    -- Claim content
    claim_text TEXT NOT NULL,
    claim_type VARCHAR(50) NOT NULL CHECK (claim_type IN (
        'preference', 'belief', 'heuristic', 'value', 
        'experience', 'boundary', 'uncertain'
    )),
    
    -- Source attribution (stable citations)
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    chunk_id UUID,  -- Optional: references chunks table
    
    -- Span information for verification
    span_start INTEGER,  -- Character offset in original content
    span_end INTEGER,    -- Character offset end
    quote TEXT,          -- Exact quoted text from source
    content_hash VARCHAR(64),  -- SHA-256 hash of source content
    
    -- Authority and confidence
    authority VARCHAR(20) NOT NULL DEFAULT 'extracted' CHECK (authority IN (
        'extracted',      -- AI extracted from source
        'owner_direct',   -- Owner clarified directly
        'inferred',       -- Inferred from multiple sources
        'uncertain'       -- Low confidence
    )),
    confidence FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    
    -- Temporal scope
    time_scope_start TIMESTAMP,
    time_scope_end TIMESTAMP,
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Extraction metadata
    extracted_at TIMESTAMP DEFAULT NOW(),
    extraction_version VARCHAR(10) DEFAULT '1.0.0',
    extractor_model VARCHAR(50),
    
    -- Verification status
    verification_status VARCHAR(20) DEFAULT 'unverified' CHECK (verification_status IN (
        'unverified', 'confirmed', 'disputed', 'deprecated'
    )),
    verified_at TIMESTAMP,
    verified_by UUID REFERENCES auth.users(id),
    
    -- Soft delete
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Tenant isolation
    tenant_id UUID REFERENCES tenants(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_persona_claims_twin_id ON persona_claims(twin_id);
CREATE INDEX IF NOT EXISTS idx_persona_claims_source_id ON persona_claims(source_id);
CREATE INDEX IF NOT EXISTS idx_persona_claims_type ON persona_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_persona_claims_authority ON persona_claims(authority);
CREATE INDEX IF NOT EXISTS idx_persona_claims_verification ON persona_claims(verification_status);
CREATE INDEX IF NOT EXISTS idx_persona_claims_is_active ON persona_claims(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_persona_claims_twin_active ON persona_claims(twin_id, is_active);

-- Full-text search on claim text
CREATE INDEX IF NOT EXISTS idx_persona_claims_fts ON persona_claims USING gin(to_tsvector('english', claim_text));

-- =============================================================================
-- Table: persona_claim_links
-- Links claims to persona spec layers (many-to-many)
-- =============================================================================

CREATE TABLE IF NOT EXISTS persona_claim_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Link to claim
    claim_id UUID NOT NULL REFERENCES persona_claims(id) ON DELETE CASCADE,
    
    -- Link to persona spec (JSONB path for flexibility)
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    persona_spec_version VARCHAR(20) NOT NULL DEFAULT '2.0.0',
    
    -- Layer mapping
    layer_name VARCHAR(50) NOT NULL CHECK (layer_name IN (
        'identity', 'cognitive', 'values', 'communication', 'memory'
    )),
    layer_item_id VARCHAR(100),  -- ID of specific item within layer (e.g., heuristic_id)
    
    -- How this claim supports the layer item
    link_type VARCHAR(20) NOT NULL DEFAULT 'supporting' CHECK (link_type IN (
        'primary', 'supporting', 'conflicting', 'historical'
    )),
    
    -- Verification requirements (for Layer 2/3)
    verification_required BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Composite unique: one claim can only link once to a layer item
    UNIQUE(claim_id, twin_id, layer_name, layer_item_id)
);

CREATE INDEX IF NOT EXISTS idx_persona_claim_links_claim_id ON persona_claim_links(claim_id);
CREATE INDEX IF NOT EXISTS idx_persona_claim_links_twin_layer ON persona_claim_links(twin_id, layer_name);
CREATE INDEX IF NOT EXISTS idx_persona_claim_links_verification ON persona_claim_links(verification_required);

-- =============================================================================
-- Table: link_compile_jobs
-- Tracks ingestion jobs for Link-First Persona Compiler
-- =============================================================================

CREATE TABLE IF NOT EXISTS link_compile_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id),
    created_by UUID NOT NULL REFERENCES auth.users(id),
    
    -- Job configuration
    mode VARCHAR(10) NOT NULL CHECK (mode IN ('A', 'B', 'C')),
    source_urls TEXT[],  -- For Mode C
    source_files JSONB,  -- For Mode A/B: [{filename, size, type}]
    
    -- Job status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN (
        'pending', 'processing', 'extracting_claims', 'compiling_persona',
        'completed', 'failed', 'cancelled'
    )),
    
    -- Progress tracking
    total_sources INTEGER DEFAULT 0,
    processed_sources INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    extracted_claims INTEGER DEFAULT 0,
    
    -- Results
    result_persona_spec JSONB,
    result_claim_ids UUID[],
    result_bio_variants JSONB,
    
    -- Error tracking
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- Processing metadata
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- RLS policy helper
    CONSTRAINT valid_progress CHECK (processed_sources <= total_sources)
);

CREATE INDEX IF NOT EXISTS idx_link_compile_jobs_twin ON link_compile_jobs(twin_id);
CREATE INDEX IF NOT EXISTS idx_link_compile_jobs_status ON link_compile_jobs(status);
CREATE INDEX IF NOT EXISTS idx_link_compile_jobs_created ON link_compile_jobs(created_at);

-- =============================================================================
-- Table: persona_bio_variants
-- Stores generated bio variants with claim citations
-- =============================================================================

CREATE TABLE IF NOT EXISTS persona_bio_variants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    -- Bio type
    bio_type VARCHAR(20) NOT NULL CHECK (bio_type IN (
        'one_liner', 'short', 'linkedin_about', 'speaker_intro', 'full'
    )),
    
    -- Bio content
    bio_text TEXT NOT NULL,
    
    -- Claim citations (every sentence must cite)
    citations JSONB NOT NULL DEFAULT '[]',  -- [{sentence_index, claim_ids[]}]
    
    -- Validation status
    validation_status VARCHAR(20) DEFAULT 'pending' CHECK (validation_status IN (
        'pending', 'valid', 'invalid_uncited', 'insufficient_data'
    )),
    uncited_sentences INTEGER[],  -- Sentence indices lacking claims
    
    -- Generation metadata
    generated_at TIMESTAMP DEFAULT NOW(),
    generation_version VARCHAR(10) DEFAULT '1.0.0',
    
    -- Tenant isolation
    tenant_id UUID REFERENCES tenants(id)
);

CREATE INDEX IF NOT EXISTS idx_persona_bio_variants_twin ON persona_bio_variants(twin_id);
CREATE INDEX IF NOT EXISTS idx_persona_bio_variants_type ON persona_bio_variants(bio_type);

-- =============================================================================
-- Enable RLS on new tables
-- =============================================================================

ALTER TABLE persona_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE persona_claim_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE link_compile_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE persona_bio_variants ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- RLS Policies
-- =============================================================================

-- Persona Claims: Users can only see claims for twins they own
CREATE POLICY persona_claims_tenant_isolation ON persona_claims
    FOR ALL
    USING (
        twin_id IN (
            SELECT id FROM twins WHERE tenant_id IN (
                SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid()
            )
        )
    );

-- Claim Links: Same as claims
CREATE POLICY persona_claim_links_tenant_isolation ON persona_claim_links
    FOR ALL
    USING (
        twin_id IN (
            SELECT id FROM twins WHERE tenant_id IN (
                SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid()
            )
        )
    );

-- Link Compile Jobs: Tenant isolation
CREATE POLICY link_compile_jobs_tenant_isolation ON link_compile_jobs
    FOR ALL
    USING (
        twin_id IN (
            SELECT id FROM twins WHERE tenant_id IN (
                SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid()
            )
        )
    );

-- Bio Variants: Tenant isolation
CREATE POLICY persona_bio_variants_tenant_isolation ON persona_bio_variants
    FOR ALL
    USING (
        twin_id IN (
            SELECT id FROM twins WHERE tenant_id IN (
                SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid()
            )
        )
    );

-- =============================================================================
-- Comments for documentation
-- =============================================================================

COMMENT ON TABLE persona_claims IS 'Atomic claims extracted from source content for Link-First Persona';
COMMENT ON TABLE persona_claim_links IS 'Links between claims and persona spec layers';
COMMENT ON TABLE link_compile_jobs IS 'Ingestion jobs for Link-First Persona Compiler';
COMMENT ON TABLE persona_bio_variants IS 'Generated bio variants with claim citations';

-- =============================================================================
-- Migration complete
-- =============================================================================
