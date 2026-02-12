"""
Database schema and migration for pgvector on Supabase.

Run this SQL in your Supabase SQL Editor to set up the schema.
"""

SCHEMA_SQL = """
-- Enable pgvector extension (already available on Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Activities table: one row per curriculum activity
-- ============================================
CREATE TABLE IF NOT EXISTS activities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_name TEXT NOT NULL,
    grade_band TEXT NOT NULL,           -- 'K-2', '3-5', '6-8', '9-12'
    stage TEXT NOT NULL,                -- 'Introduction To Inventing', 'Identifying and Ideating', etc.
    description TEXT,                   -- Optional: LLM-generated summary (stretch goal)
    resource_url TEXT NOT NULL,         -- Google Drive folder/file URL or YouTube URL
    resource_type TEXT NOT NULL,        -- 'drive_folder', 'drive_file', 'google_doc', 'youtube', 'other'
    drive_id TEXT,                      -- Extracted Drive folder/file ID (stable across moves)
    estimated_time_minutes INT,         -- Optional: extracted from lesson plan content
    keywords TEXT[],                    -- Optional: extracted tags
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding vector(384)              -- all-MiniLM-L6-v2 outputs 384 dimensions
);

-- Indexes for filtered + vector search
-- NOTE: IVFFlat index must be created AFTER data is loaded (fails on empty table)
-- Run this after first ingestion:
-- CREATE INDEX idx_activities_embedding ON activities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

CREATE INDEX IF NOT EXISTS idx_activities_grade_stage
    ON activities (grade_band, stage);

CREATE INDEX IF NOT EXISTS idx_activities_active
    ON activities (is_active);

CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_unique_resource
    ON activities (resource_url, activity_name);

-- ============================================
-- Crawl logs: track each crawl run
-- ============================================
CREATE TABLE IF NOT EXISTS crawl_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    triggered_by TEXT NOT NULL DEFAULT 'manual',  -- 'admin', 'health_check', 'manual'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    activities_added INT NOT NULL DEFAULT 0,
    activities_removed INT NOT NULL DEFAULT 0,
    activities_updated INT NOT NULL DEFAULT 0,
    errors JSONB,
    status TEXT NOT NULL DEFAULT 'running'        -- 'running', 'completed', 'failed'
);

-- ============================================
-- Helper function: update updated_at on changes
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS activities_updated_at ON activities;
CREATE TRIGGER activities_updated_at
    BEFORE UPDATE ON activities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
"""
