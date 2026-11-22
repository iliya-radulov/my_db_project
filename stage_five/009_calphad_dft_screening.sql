-- Migration 009: Generalized CALPHAD Binary-Ensemble + Bartel SISSO Screening Tables
-- Target schema: alloy_lab

SET search_path TO alloy_lab;

CREATE TABLE IF NOT EXISTS calphad_ensemble_runs (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER REFERENCES samples(id) ON DELETE SET NULL,
    formula TEXT NOT NULL,
    system_name TEXT NOT NULL,                  -- Sorted canonical elements, e.g. 'B-FE-ND'
    target_composition JSONB NOT NULL,          -- {"B": 0.058824, "FE": 0.823529, "ND": 0.117647}
    n_total_combos INTEGER NOT NULL,
    n_survivors INTEGER NOT NULL,
    gate_passed BOOLEAN NOT NULL,
    gate_summary JSONB NOT NULL,                -- G1_survival & G2_lineage_coverage details
    audit_summary JSONB,                        -- Excluded files & reasons
    spec_sha256 TEXT NOT NULL,
    pycalphad_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calphad_runs_system ON calphad_ensemble_runs(system_name);
CREATE INDEX IF NOT EXISTS idx_calphad_runs_sample ON calphad_ensemble_runs(sample_id);
CREATE INDEX IF NOT EXISTS idx_calphad_runs_sha ON calphad_ensemble_runs(spec_sha256);

CREATE TABLE IF NOT EXISTS calphad_dft_comparison (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES calphad_ensemble_runs(id) ON DELETE CASCADE,
    temperature_k REAL NOT NULL,
    -- CALPHAD binary-ensemble competing hull threshold (kJ/mol-atom vs SER)
    threshold_median_kj REAL,
    threshold_q25_kj REAL,
    threshold_q75_kj REAL,
    threshold_p05_kj REAL,
    threshold_p95_kj REAL,
    eta2_by_edge JSONB,
    competing_assemblage TEXT,
    -- DFT + Bartel SISSO candidate phase formation energy (kJ/mol-atom)
    mp_id TEXT NOT NULL DEFAULT 'NO_MP_ENTRY',
    candidate_formula TEXT,
    e_above_hull_0k_ev REAL,
    dgf_sisso_kj REAL,
    -- Stability margin: dgf_sisso_kj - threshold_median_kj (< 0 => candidate favored)
    stability_margin_kj REAL,
    verdict TEXT,                               -- 'stable_across_band', 'borderline_within_band', 'metastable_above_band', 'no_dft_entry'
    UNIQUE (run_id, temperature_k, mp_id)
);

CREATE INDEX IF NOT EXISTS idx_calphad_comp_run ON calphad_dft_comparison(run_id);
