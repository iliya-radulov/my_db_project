-- Migration: staging tables for magnetocaloric literature data (first
-- source: NIMS La(Fe,Si)13 dataset, doi:10.48505/nims.4909, CC BY 4.0).
--
-- External literature records, not the lab's own samples: they are NOT
-- rows of samples (decision 2 Nov 2026, option B). They are linked to the
-- lab's samples only through the composition key (composition_key.py):
-- sample_composition_keys holds the key of each own sample, and the view
-- mce_literature_matches joins the two. Every literature row carries its
-- source and the source's own ID, so a re-import updates instead of
-- duplicating, and every value can be traced back to the dataset row and
-- paper.
--
-- Duplicates rule (roadmap §4 step D):
--   same source + same external_id   -> update (upsert)
--   same composition_key, other row  -> keep both; they are different
--                                       samples or measurements. Overlaps
--                                       are reported, never merged.
--
-- Run with: docker exec -i alloy-postgres psql -U postgres -d alloy_lab < 007_mce_literature.sql

SET search_path TO alloy_lab;

-- One row per sample as described in the source (one NIMS ID).
CREATE TABLE IF NOT EXISTS mce_literature_records (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,                    -- e.g. 'nims_lafesi_1_13'
    external_id TEXT NOT NULL,               -- the source's own row ID
    doi TEXT,                                -- paper DOI(s); several are newline-separated
    article_ref TEXT,                        -- the source's article ID
    licence TEXT,                            -- licence of the source dataset
    retrieved_at TIMESTAMPTZ DEFAULT NOW(),
    quality_flag TEXT NOT NULL,              -- 'experimental_literature' | 'literature_mined' | 'unverified' | 'dft'

    metal_at_pct JSONB NOT NULL,             -- {"La": 7.14, "Fe": 81.43, "Si": 11.43}, sums to 100
    interstitial_at_pct JSONB,               -- {"H": 3.57}: at.% relative to the metal total, not part of the 100
    composition_key TEXT NOT NULL,           -- composition_key.py, e.g. 'Fe81.4-La7.1-Si11.4+H3.6'
    family TEXT,                             -- substituents other than La/Fe, e.g. 'Si+Mn'
    composition_text TEXT,                   -- formula as written in the paper (note only, often has variables)
    composition_details TEXT,

    method TEXT,
    anneal_time_h REAL,
    anneal_temp_k REAL,
    phase_1_13_pct REAL,
    phase_alpha_fe_pct REAL,
    lattice_a_pm_angstrom REAL,
    density_g_cm3 REAL,
    isothermal_protocol BOOLEAN,             -- source's isoT/isoH flag: 1 = isothermal

    t_tr_k REAL,
    t_tr_source TEXT,                        -- 'reported' | 'dS_peak' | 'dTad_peak' | 'dS_dTad_mean'
    t_hys_k REAL,
    h_tr_t REAL,
    comments TEXT,

    UNIQUE (source, external_id)
);

-- One row per measured quantity per applied field.
CREATE TABLE IF NOT EXISTS mce_literature_points (
    id SERIAL PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES mce_literature_records(id) ON DELETE CASCADE,
    quantity TEXT NOT NULL,                  -- 'dS_max' (J/kg K) | 'dT_ad_max' (K)
    field_t REAL NOT NULL,
    value REAL,
    t_peak_k REAL,
    fwhm_k REAL,                             -- dS_max only
    UNIQUE (record_id, quantity, field_t)
);

CREATE INDEX IF NOT EXISTS idx_mce_points_record ON mce_literature_points(record_id);
CREATE INDEX IF NOT EXISTS idx_mce_records_family ON mce_literature_records(family);
CREATE INDEX IF NOT EXISTS idx_mce_records_key ON mce_literature_records(composition_key);

-- Composition key of each own sample, filled by link_samples.py from
-- samples.composition. A separate small table instead of a new column, so
-- the core samples table stays as it is (roadmap §6).
CREATE TABLE IF NOT EXISTS sample_composition_keys (
    sample_id INTEGER PRIMARY KEY REFERENCES samples(id) ON DELETE CASCADE,
    composition_key TEXT NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sample_keys_key ON sample_composition_keys(composition_key);

-- Own samples with an exactly matching literature record.
CREATE OR REPLACE VIEW mce_literature_matches AS
SELECT s.id AS sample_db_id, s.sample_id, k.composition_key,
       r.id AS record_id, r.source, r.external_id, r.doi, r.quality_flag, r.t_tr_k
FROM samples s
JOIN sample_composition_keys k ON k.sample_id = s.id
JOIN mce_literature_records r ON r.composition_key = k.composition_key;
