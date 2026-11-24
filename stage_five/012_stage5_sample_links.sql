-- 012: link Stage 5 runs to samples (many-to-many).
-- A cached run is reused for every sample with the same composition and options, so one run can belong to
-- several samples; the old single column calphad_ensemble_runs.sample_id cannot express that.
-- Safe to re-run. Apply after 009-011. Without it the app still links a run to ONE sample (the old column).
SET search_path TO alloy_lab;

CREATE TABLE IF NOT EXISTS calphad_run_samples (
    run_id    INTEGER NOT NULL REFERENCES calphad_ensemble_runs(id) ON DELETE CASCADE,
    sample_id INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    linked_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (run_id, sample_id)
);
CREATE INDEX IF NOT EXISTS idx_calphad_run_samples_sample ON calphad_run_samples(sample_id);

-- links that already exist in the old column
INSERT INTO calphad_run_samples (run_id, sample_id)
SELECT id, sample_id FROM calphad_ensemble_runs WHERE sample_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW v_stage5_sample_runs AS
SELECT s.sample_id AS sample_code, r.id AS run_id, r.formula, r.system_name, r.gate_passed,
       r.n_survivors, r.n_total_combos, r.created_at AS run_created_at, l.linked_at
FROM calphad_run_samples l
JOIN samples s ON s.id = l.sample_id
JOIN calphad_ensemble_runs r ON r.id = l.run_id;
