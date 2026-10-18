-- Migration: align temperature-coefficient names with the permanent-magnet
-- convention: alpha = coefficient of remanence (Mr/Br), beta = coefficient
-- of coercivity (Hc/Hcj).  Previously this project stored the coercivity
-- coefficient as 'alpha_Hc' and the remanence coefficient as 'beta_Mr'
-- (the Greek letters the wrong way round; the fitted numbers were correct).
--
--   alpha_Hc -> beta_Hc      beta_Mr -> alpha_Mr
--
-- Single UPDATE, so both renames happen at once; running it again changes
-- nothing (no old names left).
-- Run with: docker exec -i alloy-postgres psql -U postgres -d alloy_lab < 006_temp_coefficient_names.sql

SET search_path TO alloy_lab;

UPDATE vsm_temperature_coefficients
SET coefficient_type = CASE coefficient_type
        WHEN 'alpha_Hc' THEN 'beta_Hc'
        WHEN 'beta_Mr'  THEN 'alpha_Mr'
    END
WHERE coefficient_type IN ('alpha_Hc', 'beta_Mr');
