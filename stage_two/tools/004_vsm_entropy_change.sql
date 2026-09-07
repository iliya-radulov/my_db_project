-- Migration: entropy-change (Delta S_M) support for the vsm_* tables.
-- Adds two file-level columns (suitability -- a fact about the file,
-- same category as instrument_type/mass_g) plus a child table for the
-- actual computed (T, Delta S_M) points, one row per point per target
-- field, following the same long-format pattern as vsm_mt_candidates.
-- Run with: docker exec -i postgres psql -U postgres -d alloy_lab < 004_vsm_entropy_change.sql

SET search_path TO alloy_lab;

ALTER TABLE vsm_files
    ADD COLUMN IF NOT EXISTS entropy_change_suitable BOOLEAN,
    ADD COLUMN IF NOT EXISTS entropy_change_reason TEXT;
-- entropy_change_suitable is NULL when entropy-change wasn't even
-- attempted (fewer than 2 MH segments in the file) -- NOT the same as
-- FALSE (attempted, found unsuitable, e.g. a temperature-coefficient-
-- style full-loop file, or missing mass). Same NULL-vs-FALSE distinction
-- already used for n_self_centering_events in vsm_segments.

CREATE TABLE IF NOT EXISTS vsm_entropy_change (
    id SERIAL PRIMARY KEY,
    vsm_file_id INTEGER REFERENCES vsm_files(id) ON DELETE CASCADE,

    target_field_oe INTEGER NOT NULL,     -- e.g. 10000 (1T), 19000 (1.9T)
    t_mid_k REAL NOT NULL,
    delta_sm_j_per_kg_k REAL NOT NULL,

    computed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vsm_entropy_change_file_id ON vsm_entropy_change(vsm_file_id);
