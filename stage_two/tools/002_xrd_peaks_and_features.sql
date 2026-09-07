-- Migration: add xrd_peaks (long format, one row per peak) and
-- xrd_features (one row per sample, fixed-width, ML-ready) tables.
-- Run with: docker exec -i postgres psql -U postgres -d alloy_lab < 002_xrd_peaks_and_features.sql

SET search_path TO alloy_lab;

-- 1. Long-format ground truth: every fitted peak, one row each.
--    This is the audit trail — full fidelity, variable length per
--    sample, safe to recompute features from later without re-parsing
--    raw files.
CREATE TABLE IF NOT EXISTS xrd_peaks (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER REFERENCES samples(id) ON DELETE CASCADE,

    peak_rank INTEGER,                        -- 1 = strongest peak in the pattern, by intensity
    two_theta REAL NOT NULL,
    d_spacing_angstrom REAL,
    fwhm_deg REAL,
    r_squared REAL,                           -- fit-quality metric; NULL if fit did not converge
    amplitude REAL,
    intensity REAL,                           -- raw intensity at the peak index (not fit amplitude)
    crystallite_size_nm REAL,                 -- Scherrer, from this peak's own fit (default method)

    is_doublet_candidate BOOLEAN DEFAULT FALSE, -- flagged by find_ka2_candidate: position AND
                                                 -- amplitude-ratio both matched a Ka2 companion
    doublet_partner_peak_id INTEGER REFERENCES xrd_peaks(id),

    anode TEXT,                               -- e.g. 'Cu'
    wavelength_ka1_angstrom REAL,
    ka2_stripped BOOLEAN,                     -- whether Rachinger stripping ran before this
                                               -- peak was found/fit (affects FWHM & crystallite size)
    fitted_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_xrd_peaks_sample_id ON xrd_peaks(sample_id);

-- 2. Fixed-width, one row per sample — the actual ML training input.
--    Top-5 peaks by intensity, padded with NULL if a sample has fewer.
--    Aggregates (mean_*) computed ONLY from peaks meeting the quality
--    threshold, since ~10-15% of "successfully fitted" peaks in real
--    test data scored R² < 0.7 and shouldn't silently pull down the
--    sample-level averages a model would train on.
CREATE TABLE IF NOT EXISTS xrd_features (
    sample_id INTEGER PRIMARY KEY REFERENCES samples(id) ON DELETE CASCADE,

    n_peaks_total INTEGER,
    n_peaks_high_quality INTEGER,             -- count with r_squared >= quality_r_squared_threshold
    quality_r_squared_threshold REAL DEFAULT 0.9,

    peak1_two_theta REAL, peak1_d_spacing REAL, peak1_fwhm REAL,
    peak1_intensity REAL, peak1_r_squared REAL, peak1_crystallite_size_nm REAL,

    peak2_two_theta REAL, peak2_d_spacing REAL, peak2_fwhm REAL,
    peak2_intensity REAL, peak2_r_squared REAL, peak2_crystallite_size_nm REAL,

    peak3_two_theta REAL, peak3_d_spacing REAL, peak3_fwhm REAL,
    peak3_intensity REAL, peak3_r_squared REAL, peak3_crystallite_size_nm REAL,

    peak4_two_theta REAL, peak4_d_spacing REAL, peak4_fwhm REAL,
    peak4_intensity REAL, peak4_r_squared REAL, peak4_crystallite_size_nm REAL,

    peak5_two_theta REAL, peak5_d_spacing REAL, peak5_fwhm REAL,
    peak5_intensity REAL, peak5_r_squared REAL, peak5_crystallite_size_nm REAL,

    mean_crystallite_size_nm REAL,            -- from high-quality peaks only
    mean_r_squared REAL,

    anode TEXT,
    ka2_stripped BOOLEAN,
    computed_at TIMESTAMP DEFAULT NOW()
);
