# Database Schema

Postgres, schema `alloy_lab`. All tables below live in that schema.

## Core tables

### `samples`
The central table. One row per physical sample.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | Real integer id, used for foreign keys elsewhere |
| `sample_id` | TEXT, UNIQUE | Human-chosen id (e.g. `Fe65Nd30Co5-20260707-001`) |
| `composition` | JSONB | Element → atomic fraction, e.g. `{"Fe": 0.65, "Nd": 0.30, "Co": 0.05}` |
| `material_class_id` | FK → `material_classes` | |
| `parent_sample_id` | FK → `samples` (self-reference) | Tracks lineage, e.g. a heat-treated sample pointing back to its as-cast parent |
| `mass_grams` | REAL | |
| `source_type` | TEXT | `'experimental'` or `'literature'` |
| `vec`, `delta`, `delta_h_mix` | REAL | Screening results, added via migration (see below) — previously only existed as text inside `notes` |
| `notes` | TEXT | |
| `created_at` | TIMESTAMP | |

Family-tree traversal uses a recursive CTE (`get_family_tree()` in
`alloy_db.py`):
```sql
WITH RECURSIVE family AS (
    SELECT id, sample_id, parent_sample_id FROM samples WHERE sample_id = %s
    UNION
    SELECT s.id, s.sample_id, s.parent_sample_id
    FROM samples s JOIN family f ON s.parent_sample_id = f.id
)
SELECT sample_id, parent_sample_id FROM family WHERE sample_id != %s
```

### `characterization`
One row per measurement run on a sample (an XRD scan, a VSM loop, etc.).

| Column | Notes |
|---|---|
| `sample_id` | FK → `samples` |
| `char_type` | e.g. `'XRD'`, `'VSM'` |
| `instrument` | e.g. `'Bruker D8'`, `'PPMS/VSM'` — auto-detected from file extension/name in the GUI's import path |
| `file_path` | Path to the raw instrument file |
| `parameters` | JSONB, free-form |

### `properties`
One row per extracted numeric result, linked to a `characterization` run —
this is where XRD/VSM extracted values actually land.

| Column | Notes |
|---|---|
| `characterization_id` | FK → `characterization` |
| `property_name` | e.g. `n_peaks`, `lattice_parameter_a`, `saturation_moment`, `remanence`, `coercivity`, `saturation_moment_per_g` |
| `property_value` | REAL |
| `property_unit` | e.g. `'Å'`, `'emu'`, `'Oe'`, `'emu/g'` |
| `confidence_score` | REAL, default 0.7 — intended for eventually distinguishing own measurements from literature-sourced values |

### `synthesis`
Method, temperature, atmosphere, duration, and success flag per sample.

### `compositions`
Element-level rows (`sample_id`, `element`, `weight_percent`,
`atomic_percent`) — a more query-friendly parallel to the JSONB
`composition` column on `samples`. (Note: a dedicated, ML-oriented
element-fraction table is still planned for Stage 2 — see the main
README's Next Steps — this table predates that plan and may be
superseded by it.)

### `material_classes`
`class_name` (unique), `description`. New classes can be added on the fly
from the GUI (falls back to inserting a new row if the chosen class
doesn't already exist).

### `literature_sources`
DOI (unique), title, authors, year — for papers. Note: this table's shape
assumes papers, not patents; a separate `patent_records` table is planned
for Stage 2 rather than forcing patent data into this shape.

## `literature_checks` (added mid-project)

One row per **deduped candidate phase**, per source database, per sample
— not one row per raw API result (see
[`literature_databases.md`](literature_databases.md) for why the
deduplication step matters).

```sql
CREATE TABLE literature_checks (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER REFERENCES samples(id) ON DELETE CASCADE,
    source_db TEXT NOT NULL,              -- 'materials_project' | 'oqmd' | 'alexandria'
    tier INTEGER NOT NULL,                 -- 1-4, see literature_databases.md
    match_formula TEXT,
    match_id TEXT,                         -- e.g. 'mp-31186', 'oqmd-10464'
    stability REAL,                        -- eV/atom above hull (meaning varies slightly by source, see literature_databases.md)
    experimentally_known BOOLEAN,
    composition_distance REAL,
    checked_at TIMESTAMP DEFAULT NOW()
);
```

## Migrations

`001_screening_and_literature_checks.sql` — adds `vec`/`delta`/
`delta_h_mix` to `samples` and creates `literature_checks`. Full text in
[`appendix_commands.md`](appendix_commands.md).
