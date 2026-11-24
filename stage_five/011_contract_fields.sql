-- 011: secondary / approximate fields of the screening contract + a view with the contract's column names.
-- Safe to re-run. Apply after 009 and 010.
SET search_path TO alloy_lab;

ALTER TABLE calphad_dft_comparison
    ADD COLUMN IF NOT EXISTS threshold_composition JSONB,  -- composition at which the threshold was evaluated (prototype step)
    ADD COLUMN IF NOT EXISTS verdict_at_prototype  TEXT,   -- class from the composition-matched check (prototype step)
    ADD COLUMN IF NOT EXISTS ref_correction_kj     REAL,   -- sum x_i (g_els_i - GHSER_i), kJ/mol-atom (approximate)
    ADD COLUMN IF NOT EXISTS dgf_sisso_ser_kj      REAL,   -- dGf_SISSO + ref_correction (approximate)
    ADD COLUMN IF NOT EXISTS margin_ser_kj         REAL,   -- dgf_sisso_ser_kj - threshold median (approximate)
    ADD COLUMN IF NOT EXISTS notes                 TEXT;

COMMENT ON COLUMN calphad_dft_comparison.verdict IS
  'stable_across_band | borderline_within_band | metastable_above_band (CALPHAD band only: dGf_SISSO < p05 / within / > p95), '
  'prototype_indicative_only, ensemble_unreliable (gates failed), sisso_unavailable, no_dft_entry';
COMMENT ON COLUMN calphad_dft_comparison.margin_ser_kj IS 'Secondary, approximate (reference-axis corrected); the class never depends on it';

CREATE OR REPLACE VIEW v_stage5_screening AS
SELECT r.id                       AS run_id,
       r.system_name              AS system,
       r.target_composition       AS composition,
       c.temperature_k            AS "T",
       c.threshold_median_kj      AS delta_g_star_median,
       c.threshold_p05_kj         AS delta_g_star_p05,
       c.threshold_p95_kj         AS delta_g_star_p95,
       r.n_survivors              AS n_survivors,
       c.dgf_sisso_kj             AS delta_g_sisso,
       c.stability_margin_kj      AS delta_delta_g,
       c.verdict                  AS classification,
       c.mp_id                    AS prototype_mp_id,
       c.prototype_formula        AS prototype_label,
       c.match_type, c.delta_x, c.comparable,
       c.ref_correction_kj, c.dgf_sisso_ser_kj, c.margin_ser_kj,
       c.notes
FROM calphad_ensemble_runs r
JOIN calphad_dft_comparison c ON c.run_id = r.id;
