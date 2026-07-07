-- Migration: add screening columns to samples, add literature_checks table
-- Run with: docker exec -i postgres psql -U postgres -d alloy_lab < 001_screening_and_literature_checks.sql

SET search_path TO alloy_lab;

-- 1. Store VEC / delta / delta_H_mix as real columns instead of only in notes text
ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS vec REAL,
    ADD COLUMN IF NOT EXISTS delta REAL,
    ADD COLUMN IF NOT EXISTS delta_h_mix REAL;

-- 2. One row per deduped candidate phase, per source database, per sample
CREATE TABLE IF NOT EXISTS literature_checks (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER REFERENCES samples(id) ON DELETE CASCADE,
    source_db TEXT NOT NULL,              -- 'materials_project' or 'oqmd'
    tier INTEGER NOT NULL,                 -- 1-4
    match_formula TEXT,
    match_id TEXT,                         -- e.g. 'mp-31186' or 'oqmd-10464'
    stability REAL,                        -- eV/atom above hull
    experimentally_known BOOLEAN,
    composition_distance REAL,
    checked_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_literature_checks_sample_id ON literature_checks(sample_id);
