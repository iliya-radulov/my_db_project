-- Migration: provenance for the Materials Project / OQMD / Alexandria
-- matches in literature_checks (roadmap my_alloy_db_General_Road_Map_v2.md,
-- §3 priority 1: "harden the mapping and add provenance flags").
--
-- 1. quality_flag, same vocabulary as mce_literature_records
--    ('experimental_literature' | 'literature_mined' | 'unverified' | 'dft').
--    All three current sources store computed values (energy above hull),
--    so existing and new rows get 'dft'. Whether the phase itself has been
--    observed stays in the existing experimentally_known column; the
--    roadmap's example of flagging Materials Project rows 'experimental'
--    would mix the two.
--    The DEFAULT means the GUIs and CLI tools keep working unchanged.
-- 2. CHECK constraints on source_db and quality_flag, added NOT VALID:
--    they apply to new rows only, existing rows are not touched. The query
--    at the end lists any existing row that would violate them.
-- 3. Index on (source_db, match_id) for "which samples matched mp-31186?".
--
-- Safe to run twice.
-- Run with: docker exec -i alloy-postgres psql -U postgres -d alloy_lab -v ON_ERROR_STOP=1 < 008_literature_checks_provenance.sql

SET search_path TO alloy_lab;

ALTER TABLE literature_checks
    ADD COLUMN IF NOT EXISTS quality_flag TEXT NOT NULL DEFAULT 'dft';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'literature_checks_source_db_known') THEN
        ALTER TABLE literature_checks ADD CONSTRAINT literature_checks_source_db_known
            CHECK (source_db IN ('materials_project', 'oqmd', 'alexandria')) NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'literature_checks_quality_flag_known') THEN
        ALTER TABLE literature_checks ADD CONSTRAINT literature_checks_quality_flag_known
            CHECK (quality_flag IN ('experimental_literature', 'literature_mined', 'unverified', 'dft')) NOT VALID;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_literature_checks_match ON literature_checks(source_db, match_id);

-- Existing rows that the new constraints would reject (expected: none).
SELECT id, sample_id, source_db, quality_flag
FROM literature_checks
WHERE source_db NOT IN ('materials_project', 'oqmd', 'alexandria')
   OR quality_flag NOT IN ('experimental_literature', 'literature_mined', 'unverified', 'dft');

-- Overview.
SELECT source_db, quality_flag, count(*) AS rows, count(DISTINCT sample_id) AS samples,
       count(*) FILTER (WHERE experimentally_known) AS experimentally_known
FROM literature_checks GROUP BY 1, 2 ORDER BY 1;
