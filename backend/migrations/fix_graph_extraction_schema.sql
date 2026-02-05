-- FIX: Graph Extraction Schema Errors
-- Run this in the Supabase SQL Editor

-- 1. Add missing 'source_id' column to 'edges' table
-- This is required because the create_edge_system RPC tries to populate it
ALTER TABLE edges ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES sources(id);
CREATE INDEX IF NOT EXISTS idx_edges_source_id ON edges(source_id);

-- 2. Update 'memory_events' check constraint
-- The current constraint does not allow 'content_extract' event type
ALTER TABLE memory_events DROP CONSTRAINT IF EXISTS memory_events_event_type_check;

ALTER TABLE memory_events ADD CONSTRAINT memory_events_event_type_check 
CHECK (event_type IN (
    'interaction', 
    'correction', 
    'manual_entry', 
    'system_update', 
    'content_extract',  -- Added this
    'slot_extract',     -- Added this (used in slot extraction)
    'auto_extract'      -- Added this (used in auto extraction)
));

-- 3. Verify RPC function (optional, just ensuring it exists)
-- This assumes create_edge_system exists. If it needs updating to use source_id, 
-- that definition should be checked, but the error suggested the RPC *already* tries to use the column.
