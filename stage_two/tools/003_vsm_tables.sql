-- Migration: VSM pipeline tables (Option C: shared segment metadata +
-- type-specific detail tables, per project decision -- self-documenting
-- columns over generic reused ones, given VSM data will be reviewed
-- across many different alloys without always recalling schema by heart).
-- Run with: docker exec -i postgres psql -U postgres -d alloy_lab < 003_vsm_tables.sql

SET search_path TO alloy_lab;

-- 1. One row per processed VSM/PPMS/MPMS3/ACMS file.
CREATE TABLE IF NOT EXISTS vsm_files (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER REFERENCES samples(id) ON DELETE CASCADE,

    file_path TEXT,
    instrument_type TEXT,                     -- 'PPMS_VSM' | 'MPMS3' | 'ACMS' | 'unknown'
    mass_g REAL,
    mass_source TEXT,                         -- 'header' | 'filename' | 'not_found'
    mass_confidence TEXT,                     -- 'high' | 'medium' | 'low' | NULL
    n_rows INTEGER,
    processed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vsm_files_sample_id ON vsm_files(sample_id);

-- 2. Shared segment metadata -- one row per segment, any type.
--    Long-format audit trail, same spirit as xrd_peaks: full fidelity,
--    safe to recompute type-specific details from later.
CREATE TABLE IF NOT EXISTS vsm_segments (
    id SERIAL PRIMARY KEY,
    vsm_file_id INTEGER REFERENCES vsm_files(id) ON DELETE CASCADE,

    segment_type TEXT NOT NULL,               -- 'MH' | 'MT' | 'idle' | 'corrupted'
    start_row INTEGER NOT NULL,
    end_row INTEGER NOT NULL,

    n_self_centering_events INTEGER,          -- NULL = not checked (center_position unavailable),
                                               -- NOT the same as 0 = checked, none found
    is_HT_transition BOOLEAN DEFAULT FALSE,   -- segment_type='corrupted': simultaneous H+T
                                               -- variation. Per project decision, this is a
                                               -- flag for downstream review, not an automatic
                                               -- rejection -- may be a genuine transition period
                                               -- between measurement blocks, not bad data.
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vsm_segments_file_id ON vsm_segments(vsm_file_id);
CREATE INDEX IF NOT EXISTS idx_vsm_segments_type ON vsm_segments(segment_type);

-- 3. MH-specific details -- one row per MH segment (1:1 with
--    vsm_segments where segment_type='MH').
CREATE TABLE IF NOT EXISTS vsm_mh_details (
    id SERIAL PRIMARY KEY,
    vsm_segment_id INTEGER UNIQUE REFERENCES vsm_segments(id) ON DELETE CASCADE,

    temperature_K REAL,                       -- nominal T for this loop (mean over the segment)
    field_min_oe REAL,
    field_max_oe REAL,

    hc_oe REAL,                               -- NULL if hc_mr_flag is set (not a trustworthy value)
    mr_emu REAL,                              -- NULL if hc_mr_flag is set
    hc_mr_flag TEXT,                          -- NULL | 'no_branch_found' | 'wrong_crossing_count'
                                               -- | 'unexpected_sign' -- see vsm_mh_features.py
    branch_found BOOLEAN
);

-- 4. MT-specific details -- one row per MT segment (1:1 with
--    vsm_segments where segment_type='MT').
CREATE TABLE IF NOT EXISTS vsm_mt_details (
    id SERIAL PRIMARY KEY,
    vsm_segment_id INTEGER UNIQUE REFERENCES vsm_segments(id) ON DELETE CASCADE,

    field_oe REAL,                            -- nominal fixed field for this MT scan
    temp_min_K REAL,
    temp_max_K REAL
);

-- 5. MT candidate features -- child of vsm_mt_details, since this is a
--    variable-length list per MT segment (0 to several candidates per
--    branch), not fixed columns. Deliberately NOT a classified
--    "transition temperature" -- see vsm_mt_features.py: this project
--    works across many alloy systems without always knowing which
--    physical mechanism applies (Curie drop, Neel peak, blocking
--    temperature all look different), so candidates are stored
--    unclassified for manual/standalone review.
CREATE TABLE IF NOT EXISTS vsm_mt_candidates (
    id SERIAL PRIMARY KEY,
    vsm_mt_details_id INTEGER REFERENCES vsm_mt_details(id) ON DELETE CASCADE,

    branch_direction TEXT,                    -- 'increasing' | 'decreasing'
    branch_T_min REAL,
    branch_T_max REAL,

    candidate_kind TEXT NOT NULL,             -- 'M_extrema' | 'dMdT_extrema'
    T_value REAL NOT NULL,
    value REAL NOT NULL,                      -- M (emu) if M_extrema, dM/dT if dMdT_extrema
    extremum_kind TEXT                        -- 'max' | 'min' -- only set for M_extrema
);

CREATE INDEX IF NOT EXISTS idx_vsm_mt_candidates_details_id ON vsm_mt_candidates(vsm_mt_details_id);

-- 6. Temperature coefficients -- one row per computed coefficient
--    (alpha_Hc, beta_Mr), per file. Only populated when a file has 2+
--    valid MH segments with distinct temperatures (see
--    vsm_temp_coefficient.py / vsm_pipeline.py).
CREATE TABLE IF NOT EXISTS vsm_temperature_coefficients (
    id SERIAL PRIMARY KEY,
    vsm_file_id INTEGER REFERENCES vsm_files(id) ON DELETE CASCADE,

    coefficient_type TEXT NOT NULL,           -- 'alpha_Hc' | 'beta_Mr'
    slope REAL,
    t_ref REAL,
    y_ref REAL,
    coefficient_pct_per_k REAL,
    n_points INTEGER,
    r_squared REAL,
    computed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vsm_temp_coef_file_id ON vsm_temperature_coefficients(vsm_file_id);
