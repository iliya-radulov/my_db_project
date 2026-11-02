# Server setup — magnetocaloric literature tables

What to run on the server that holds the `alloy_lab` database, in order.
Everything below was tested on a throwaway PostgreSQL 16 database with a
minimal `samples` table (2 November 2026); it has not run on the real
server yet.

Migration 007 only **adds** objects: two literature tables, one small
key table for the lab's samples, one view. Migration 008 adds one column
(with a default), two checks for new rows and an index to the existing
`literature_checks` table; existing data is not changed.

## 0. Back up first

```bash
docker exec alloy-postgres pg_dump -U postgres -d alloy_lab -n alloy_lab -Fc > alloy_lab_before_007_$(date +%Y%m%d).dump
```

Adjust `alloy-postgres` to the container name in use (some older
migration files say `postgres`).

## 1. Create the tables (migration 007)

```bash
docker exec -i alloy-postgres psql -U postgres -d alloy_lab -v ON_ERROR_STOP=1 \
    < stage_four/mce_nims/007_mce_literature.sql
```

Creates `mce_literature_records`, `mce_literature_points`,
`sample_composition_keys` (references `samples(id)`) and the view
`mce_literature_matches`. Safe to run twice (`IF NOT EXISTS`,
`CREATE OR REPLACE VIEW`).

## 1b. Provenance for the existing database matches (migration 008)

```bash
docker exec -i alloy-postgres psql -U postgres -d alloy_lab -v ON_ERROR_STOP=1 \
    < stage_four/mce_nims/008_literature_checks_provenance.sql
```

Adds `literature_checks.quality_flag` (default `'dft'`, so existing rows
are filled and the GUIs need no change), checks on `source_db` and
`quality_flag` for new rows, and an index on `(source_db, match_id)`. The
first query it prints lists existing rows the checks would reject —
expected empty; if not, fix those rows by hand. Safe to run twice.

Undo:
```sql
SET search_path TO alloy_lab;
ALTER TABLE literature_checks DROP CONSTRAINT IF EXISTS literature_checks_source_db_known,
                              DROP CONSTRAINT IF EXISTS literature_checks_quality_flag_known,
                              DROP COLUMN IF EXISTS quality_flag;
DROP INDEX IF EXISTS idx_literature_checks_match;
```

## 2. Put the dataset in place

Copy `1-13_dataset.xlsx` (NIMS, doi:10.48505/nims.4909) to
`stage_four/mce_nims/data/` on the machine that runs the scripts. The
folder is gitignored.

Python packages needed (all in `requirements.txt`): pandas, numpy,
openpyxl, psycopg2-binary, python-dotenv.

## 3. Import the literature data

```bash
cd stage_four/mce_nims
python import_nims.py --dry-run     # validates the file, prints counts, writes nothing
python import_nims.py               # writes; one transaction
```

Expected (2 Nov 2026 file): 1,113 records from 221 papers, 1,386 ΔS
points, 153 ΔT_ad points, 660 distinct composition keys,
`Imported 1113 records and 1539 points`. Re-running updates, it does not
duplicate.

Uses the same `.env` connection settings as the rest of the project
(`db_config.py`: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SCHEMA`).

## 4. Link the lab's samples

```bash
python link_samples.py              # computes keys for all samples, prints matches
python link_samples.py --near 1.0   # wider near-match tolerance (at.% per element)
```

Samples whose composition is not a real element mapping (for example
the `{'placeholder': 1.0}` written by the GUI's file import) are listed
as skipped, not keyed. Run again whenever samples are added; it updates.

## 5. Check

```sql
SET search_path TO alloy_lab;
SELECT quality_flag, count(*), count(DISTINCT composition_key) FROM mce_literature_records GROUP BY 1;
SELECT quantity, count(*) FROM mce_literature_points GROUP BY 1;
SELECT sample_id, composition_key, count(*) FROM mce_literature_matches GROUP BY 1, 2 ORDER BY 1;
```

## Undo

```sql
SET search_path TO alloy_lab;
DROP VIEW IF EXISTS mce_literature_matches;
DROP TABLE IF EXISTS sample_composition_keys, mce_literature_points, mce_literature_records;
```

or restore the dump from step 0.
