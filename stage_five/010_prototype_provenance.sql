-- Migration 010: provenance of the DFT/SISSO candidate in calphad_dft_comparison
-- (nearest-prototype fallback). Apply after 009. Safe to run twice.
-- Target schema: alloy_lab

SET search_path TO alloy_lab;

ALTER TABLE calphad_dft_comparison ADD COLUMN IF NOT EXISTS match_type TEXT;          -- 'exact_match' | 'nearest_prototype' | 'no_dft_entry'
ALTER TABLE calphad_dft_comparison ADD COLUMN IF NOT EXISTS prototype_formula TEXT;   -- reduced formula of the MP entry used
ALTER TABLE calphad_dft_comparison ADD COLUMN IF NOT EXISTS delta_x REAL;             -- composition distance to the target (atomic fractions; site-group metric if used)
ALTER TABLE calphad_dft_comparison ADD COLUMN IF NOT EXISTS comparable BOOLEAN;       -- TRUE only for exact_match: a stability verdict is meaningful

-- the prototype options of a run are part of its cache key (NULL = fallback off / exact matches only)
ALTER TABLE calphad_ensemble_runs ADD COLUMN IF NOT EXISTS prototype_filter JSONB;

-- rows written before this migration were exact matches or "no entry" rows
UPDATE calphad_dft_comparison SET match_type = 'no_dft_entry', comparable = FALSE
 WHERE match_type IS NULL AND mp_id = 'NO_MP_ENTRY';
UPDATE calphad_dft_comparison SET match_type = 'exact_match', comparable = TRUE,
       prototype_formula = COALESCE(prototype_formula, candidate_formula), delta_x = COALESCE(delta_x, 0)
 WHERE match_type IS NULL;

-- verdict values now also include 'prototype_indicative_only' (nearest_prototype rows)
COMMENT ON COLUMN calphad_dft_comparison.verdict IS
  'stable_across_band | borderline_within_band | metastable_above_band | prototype_indicative_only | no_dft_entry';
