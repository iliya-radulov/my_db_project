'''
009_calphad_dft_screening.sql (Database Integration)
Links both sides directly to your samples table so your GUI (alloy_desktop_v2.py) and Stage 3 advisor can display and query the thermodynamic stability margin:
```

SET search_path TO alloy_lab;

CREATE TABLE IF NOT EXISTS calphad_ensemble_runs (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER REFERENCES samples(id) ON DELETE CASCADE,
    system_name TEXT NOT NULL,               -- e.g. 'Fe-Nd-B'
    target_composition JSONB NOT NULL,       -- {"FE": 0.8235, "ND": 0.1176, "B": 0.0588}
    n_total_combos INTEGER NOT NULL,
    n_survivors INTEGER NOT NULL,
    gate_passed BOOLEAN NOT NULL,
    gate_summary JSONB,                      -- G1/G2/G3 metrics & failure reasons
    spec_sha256 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS calphad_dft_comparison (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES calphad_ensemble_runs(id) ON DELETE CASCADE,
    temperature_k REAL NOT NULL,
    -- CALPHAD binary-ensemble competing hull threshold (kJ/mol-atom vs SER)
    threshold_median_kj REAL,
    threshold_p05_kj REAL,
    threshold_p95_kj REAL,
    competing_assemblage JSONB,
    -- DFT + Bartel SISSO candidate phase formation energy (kJ/mol-atom)
    mp_id TEXT,
    dgf_sisso_kj REAL,
    -- Stability margin: dgf_sisso_kj - threshold_median_kj (< 0 means candidate wins)
    stability_margin_kj REAL,
    UNIQUE (run_id, temperature_k, mp_id)
);
