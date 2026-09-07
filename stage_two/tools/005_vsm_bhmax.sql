-- Migration: BH_max (maximum energy product) support.
-- Adds sample-level geometry/density (same category as mass_g -- a
-- fact about the physical sample, only populated for cuboid samples
-- where the demagnetizing correction is actually needed) plus
-- segment-level demagnetizing factor and BH_max (same category as
-- hc_oe/mr_emu -- a fact about one specific MH loop).
-- Run with: docker exec -i postgres psql -U postgres -d alloy_lab < 005_vsm_bhmax.sql

SET search_path TO alloy_lab;

ALTER TABLE vsm_files
    ADD COLUMN IF NOT EXISTS density_g_cm3 REAL,
    ADD COLUMN IF NOT EXISTS dimension_a_mm REAL,
    ADD COLUMN IF NOT EXISTS dimension_b_mm REAL,
    ADD COLUMN IF NOT EXISTS dimension_c_mm REAL;
-- All four NULL for the majority of samples (needle-shaped, where
-- shape anisotropy is negligible and this correction isn't needed at
-- all) -- NOT defaulted to any assumed value. Density confirmed to
-- vary meaningfully by real composition (7.51-7.61 g/cm^3 depending on
-- recycled-material fraction) -- a genuine per-sample input, never a
-- default. Dimensions follow vsm_bhmax.demag_factor_prozorov_kogan()'s
-- exact (full_a, full_b, full_c) convention -- confirmed on real data
-- that swapping which physical dimension plays which role changes the
-- demagnetizing factor by roughly 2x, so these must be recorded
-- exactly as the caller assigned them, not re-derived later.

ALTER TABLE vsm_mh_details
    ADD COLUMN IF NOT EXISTS demag_factor_n REAL,
    ADD COLUMN IF NOT EXISTS bhmax_kj_m3 REAL;
-- Both NULL when density/dimensions weren't supplied for this file, OR
-- when this segment's own Hc/Mr extraction already failed (hc_mr_flag
-- is set) -- BH_max is not attempted on a branch whose own crossing
-- detection wasn't trustworthy either way.
