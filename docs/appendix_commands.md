# Appendix: Reference Commands & Configs

Verbatim material worth keeping exactly as-is, pulled out of the main docs
to keep those readable.

## `.env` template

```
POSTGRES_PASSWORD=...
POSTGRES_USER=postgres
POSTGRES_DB=alloy_lab
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

## `.gitignore`

```
.env
venv/
__pycache__/
*.pyc
*.backup
*.messy
.DS_Store
```

## Schema migration: `001_screening_and_literature_checks.sql`

```sql
SET search_path TO alloy_lab;

-- Store VEC / delta / delta_H_mix as real columns instead of only in notes text
ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS vec REAL,
    ADD COLUMN IF NOT EXISTS delta REAL,
    ADD COLUMN IF NOT EXISTS delta_h_mix REAL;

-- One row per deduped candidate phase, per source database, per sample
CREATE TABLE IF NOT EXISTS literature_checks (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER REFERENCES samples(id) ON DELETE CASCADE,
    source_db TEXT NOT NULL,
    tier INTEGER NOT NULL,
    match_formula TEXT,
    match_id TEXT,
    stability REAL,
    experimentally_known BOOLEAN,
    composition_distance REAL,
    checked_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_literature_checks_sample_id ON literature_checks(sample_id);
```

Run with:
```bash
docker cp 001_screening_and_literature_checks.sql postgres:/tmp/
docker exec -it postgres psql -U postgres -d alloy_lab -f /tmp/001_screening_and_literature_checks.sql
```

## Environment setup

```bash
# Core Python packages
pip install psycopg2-binary python-dotenv pandas numpy

# Literature database clients
pip install mp-api
pip install "optimade[http-client]"   # used for both OQMD and Alexandria

# GUI
pip install customtkinter
```

## Common operational commands

```bash
# Start everything
cd /Users/r/Documents/Projects/my_db_project
source venv/bin/activate
docker start postgres

# Run the desktop GUI
python alloy_desktop_complete.py

# Run the CLI workflow
python stage_one/alloy/alloy_entry_full_v1.py

# Direct DB access
docker exec -it postgres psql -U postgres -d alloy_lab

# Check a sample's screening columns
docker exec -it postgres psql -U postgres -d alloy_lab -c \
  "SELECT sample_id, vec, delta, delta_h_mix FROM alloy_lab.samples WHERE sample_id = '...';"

# Check literature checks for a sample (integer id, not the text sample_id)
docker exec -it postgres psql -U postgres -d alloy_lab -c \
  "SELECT source_db, match_formula, tier, stability, experimentally_known \
   FROM alloy_lab.literature_checks WHERE sample_id = <id> ORDER BY source_db, stability;"

# Data sorter (dry run first, recommended)
python stage_one/tools/sort_data_swamp_v2_v1.py ~/desktop/ndfeb_data --dry-run
python stage_one/tools/sort_data_swamp_v2_v1.py ~/desktop/ndfeb_data

# XRD / VSM / SEM import (standalone test invocations)
python stage_one/integrations/xrd_integration_v1.py <path/to/file.xy> <sample_id>
python stage_one/integrations/vsm_integration_v1.py <path/to/file.dat> <sample_id>
python -c "from stage_one.integrations.sem_integration_v1 import import_sem_file; import_sem_file('<path/to/file.tif>', '<sample_id>')"

# SEM batch import (690 files at once is slow one-by-one -- batch instead)
python -c "from stage_one.integrations.sem_integration_v1 import import_sem_files; import_sem_files('<folder_path>', sample_id='<sample_id>')"
```

## Reference data points (real extracted values, for sanity-checking future changes)

**XRD** (post lattice-parameter-bug-fix):

| Sample | n_peaks | lattice_parameter_a (Å) |
|---|---|---|
| RP1a | 101 | 15.627 |
| RP2a | 96 | 15.630 |
| RP3a | 98 | 15.744 |

**VSM** (RP1a, 50 mg sample, post mass-from-filename fix):

| Property | Value |
|---|---|
| Saturation moment (Ms) | 6.883 emu |
| Remanence (Mr) | -0.024 emu |
| Coercivity (Hc) | 198.6 Oe |
| Ms per gram | 137.65 emu/g |

**SEM** (example file, `230705-2_01.tif`):

| Parameter | Value |
|---|---|
| Magnification | 1.00 KX |
| EHT (accelerating voltage) | 10.00 kV |
| Working distance | 7.1 mm |
| Pixel size | 277.3 nm |
| Detector | SE2 / InLens |
| Image size | 1024 × 768 |

Scale note: 690 real SEM files imported in practice; single-file import
was correctness-fine but slow in bulk (~0.5-1 s each, 5-10 min total) —
solved with batch import rather than a parser change.

**Literature cross-check** (Fe70Al15Ni15, AlFe2Ni match, cross-database
agreement):

| Source | Stability (eV/atom above hull) | Experimentally known |
|---|---|---|
| Materials Project (`mp-31186`) | 0.235 | Yes |
| OQMD (`oqmd-10464`) | 0.236 | Yes (ICSD) |
