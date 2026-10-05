# Code review and fixes — October 2026

A review of Stage 1 and Stage 2 before publication, checking the code
against the Stage 1 paper draft. Where the paper and the code disagreed
and the paper described the intended behaviour, the **code** was changed
to match. Pure wording slips in the paper are listed separately at the
end, as text to change in the paper.

All changes are on branch `claude/gracious-rubin-udtsys`
(pull request #1).

---

## 1. Composition screening (`alloy_screening_v1.py`, `alloy_screening_v2.py`)

### 1.1 Wrong ΔH_mix values in the pairwise table

Every entry of `PAIRWISE_DELTA_H` was compared against matminer's
machine-readable copy of the Takeuchi & Inoue (2005) table
(`matminer/utils/data_files/MiedemaLiquidDeltaHf.tsv`). 16 of 117 entries
did not match:

| Pair  | Before | After (Takeuchi 2005) | Problem |
|-------|-------:|----------------------:|---------|
| C-Co  | 0      | −42   | placeholder 0 |
| C-Cr  | 0      | −61   | placeholder 0 |
| C-Fe  | 0      | −50   | placeholder 0 |
| C-Mo  | 0      | −67   | placeholder 0 |
| C-Ni  | 0      | −39   | placeholder 0 |
| C-Si  | 0      | −39   | placeholder 0 |
| C-W   | 0      | −60   | placeholder 0 |
| B-Zr  | −23    | −71   | wrong value |
| Cu-Mn | −4     | +4    | wrong sign |
| Cu-V  | −5     | +5    | wrong sign |
| La-Mn | −38    | +3    | wrong sign and value |
| Ag-Fe | 13     | 28    | wrong value |
| Ag-La | −38    | −30   | wrong value |
| Au-La | −21    | −73   | wrong value |
| Cr-P  | −34.5  | −49.5 | wrong value |
| Ga-Si | −6     | −17   | wrong value |

The six lanthanide pairs previously marked "low confidence" (Fe-Nd,
Co-Nd, B-Nd, Al-Nd, Nd-Si, La-Si) all matched the reference, so the
flags were removed.

**Added pairs**, same source, for the alloy families in active use
(Mn-Fe-P-Si, La-Fe-Co-Si, Nd-Fe-Ga, Cantor/HEA-type): Fe-Mn, Mn-P, P-Si,
Co-La, Ga-Nd, Co-Ga, Ga-La, Co-Cu, Cr-Cu, Cr-Mn, Al-Ti, Fe-Ti, Cr-Ti,
Al-V, Fe-V, Cr-V, Ni-V, Fe-Nb, Fe-Mo, Cr-Nb, Co-Ge, Ge-Mn.

Result: 138 entries, 0 mismatches against the reference. The built-in
self-test now also checks C-Fe, B-Zr, Cu-Mn, Cu-V and Fe-Nd.

### 1.2 Corrected module copied to Stage 1

`alloy_screening_v1.py` and `alloy_screening_v2.py` are meant to be the
same file. The ΔH_mix correction described in the paper (§4.3.1–4.3.2:
literature table, ×4 regular-solution factor, `IncompletePairDataError`)
had been made only in the Stage 2 copy, so `stage_one/` still held the
original 40-pair table. The corrected module (including the fixes in 1.1)
is now in both folders, and the two files are identical again.

### 1.3 A missing pair crashed sample entry

The GUIs (`alloy_desktop_complete.py`, `alloy_desktop_v2.py`) and the CLI
tools (`alloy_entry_full_v1.py`, `alloy_entry_full_v2.py`) only caught
`IncompleteElementDataError`. The newer `IncompletePairDataError` was
not caught, so for any composition with an untabulated pair, both
*Calculate & Preview* and *Save* failed with an error. All four now
catch both errors and skip screening (columns stored as NULL), as the
paper says.

### 1.4 Wrong interpretation text

`interpret_screening()`:
- **δ:** `calculate_delta()` returns a fraction (e.g. 0.06), but it was
  compared against `5`, so it always printed "small mismatch". It is now
  converted to percent and compared against the 6.6 % solid-solution
  criterion (Yang & Zhang 2012).
- **VEC:** the bands now follow Guo et al. 2011 (the paper's reference
  [1]): VEC ≥ 8 → FCC, 6.87 ≤ VEC < 8 → FCC + BCC, VEC < 6.87 → BCC.

### 1.5 Restored documentation

The last edit of `alloy_screening_v2.py` had dropped the source note for
`melt_K`/`boil_K` (Reade table, As/At anomaly) and the detailed docstring
of `check_synthesis_feasibility()`. Both are restored.

### 1.6 Removed duplicate

`stage_two/alloy/alloy_screening_v2.0.py` was an exact copy of the
pre-fix screening module (with the 16 wrong values), and nothing imported
it. It was deleted to avoid confusion; it remains in git history.

---

## 2. Composition calculator (`alloy_calculator_v1.py`, `alloy_calculator_v2.py`)

The paper (§4.2, §5.1) says every element must be followed by an explicit
number. The parser only enforced this when another element followed:

| Input        | Before                        | After |
|--------------|-------------------------------|-------|
| `Fe65Nd30B`  | B silently set to 1 (~1 at%)  | error: missing number after `B` |
| `Nd2Fe14B`   | B silently set to 1           | error (write `Nd2Fe14B1`) |
| `Fe2P`       | P silently set to 1           | error (write `Fe2P1`) |
| `NdFe`       | error                         | error (unchanged) |
| `Fe`         | 100 % Fe                      | error |
| `65Fe35Nd`   | accepted, numbers mis-paired  | error: number before first element |

The GUI hint for the pre-alloy formula now reads `e.g., Fe2P1`. The
calculator's own example in `__main__` (`LaFe11.6Si1.4`, which had
always failed) was changed to `La1Fe11.6Si1.4`.

---

## 3. Literature cross-referencing (both GUIs)

### 3.1 Databases queried in parallel

The paper (Figure 1) says the three databases are queried in parallel;
the code queried them one after another. Materials Project, OQMD and
Alexandria now run at the same time in worker threads, so the wait is
the slowest single lookup rather than the sum. A failure in one database
still leaves the other two working.

### 3.2 `literature_sources` is now populated

The paper says `literature_sources` is populated during cross-referencing,
but no code wrote to it. When a sample is saved, the GUI now looks up
Materials Project's text-mined synthesis records for the experimentally
known MP matches (up to three formulas) and stores each source DOI in
`literature_sources` (`ON CONFLICT (doi) DO NOTHING`). This runs after
the sample is saved and is best effort: a failure here is logged and does
not affect the saved sample. New method: `add_literature_source()` in
`alloy_db_v1.py` and `alloy_db_v2.py`.

> **Check:** this assumes `literature_sources.doi` has a UNIQUE
> constraint, as `docs/database_schema.md` states.

### 3.3 API key lookup

`get_api_key()` only looked for `../../back_up/API/MP_API_KEY.txt`,
relative to the folder the program was started from. Started from the
repo root, the GUI silently skipped Materials Project. It now reads the
`MP_API_KEY` environment variable first (the same variable `mp_lookup`
already uses) and falls back to the file.

---

## 4. XRD quick-look lattice parameter (`parse_xrd_v1.py`, `parse_xrd_v2.py`)

This is only a visual check (the validated XRD analysis is the Stage 2
pipeline, `xrd_analyzer_dev1.py`), but it produced clearly wrong numbers:

- **Reference table:** the hand-typed Nd₂Fe₁₄B 2θ values were 20–40° too
  low, e.g. (410) listed at 22.5° instead of 42.3°. Peaks were therefore
  matched to the wrong reflections.
- **Formula:** `a = d·√(h² + k²)` ignores the `l²/c²` term, so it is
  wrong for every reflection with l ≠ 0.

**Now:** reflections are calculated from the reference cell
(a = 8.80 Å, c = 12.20 Å, space group P4₂/mnm, with its reflection
conditions). A peak is used only if exactly one reflection lies within
0.3°. a and c are fitted together by least squares on
1/d² = (h² + k²)/a² + l²/c², with standard errors from the fit; `c` is
now reported and stored as `lattice_parameter_c`.

**Test:** a synthetic pattern with a = 8.82 Å, c = 12.24 Å plus an α-Fe
peak gave a = 8.8200 Å and c = 12.2401 Å; the α-Fe and ambiguous peaks
were excluded.

> **Action needed:** `docs/characterization.md` recorded a ≈ 15.63 Å for
> RP1a–RP3a. Nd₂Fe₁₄B has a ≈ 8.8 Å, so these values came from the old
> table. Any `lattice_parameter_a` stored by Stage 1 should be
> recalculated or deleted.

---

## 5. VSM BH_max (`vsm_bhmax.py`, `vsm_pipeline.py`)

No calculation changed, only documentation, but it matters for how the
sample dimensions are passed in:

- **Field axis:** the docstring said the Prozorov–Kogan formula
  N⁻¹ = 1 + ¾(c/a)(1 + a/b) has the field along **b**. It is along
  **c** (third dimension): c → 0 gives N → 1 (thin plate) and c → ∞
  gives N → 0 (long rod), while a long b would give N ≈ 0.57. Pass the
  edge **parallel to the field** as `full_c`.
- **Applicability:** the formula is derived for diamagnetic (χ = −1)
  samples. For the 1 × 2.5 × 2 mm example, Aharoni's magnetometric
  factor (`vsm_demag_correction.py`) gives 0.267 against 0.323.
- **Worked example:** 86.87 emu/g × 7.61 g/cm³ × 4π·10⁻⁴ = 0.831 T, not
  0.828 T as previously noted.

> **Action needed:** check which edge your measured samples had along
> the field, and that it was passed as the third dimension.

---

## 6. Other

- `requirements.txt` was missing `customtkinter`, `mp-api` and
  `psycopg2-binary`, which the code imports. They were added unpinned;
  pin them to your installed versions with `pip freeze`. The file is
  otherwise a full environment dump (tensorflow, torch, jupyter,
  macOS-only packages) and could be trimmed before publishing.
- Docs updated to match: `docs/screening.md` (ΔH_mix history and current
  behaviour), `docs/calculator.md` (strict parser),
  `docs/characterization.md` (XRD correction).

---

## 7. Existing database rows

Samples saved before these fixes have `vec`/`delta`/`delta_h_mix`
computed with an older table: the original 40-pair table without the
×4 factor (entries saved through the Stage 1 GUI/CLI), or the Stage 2
table with the 16 wrong values in 1.1.
`vec` and `delta` did not change, but `delta_h_mix` did. A sketch to
recompute them (not run against your database; try it on a backup first):

```python
from stage_two.alloy.alloy_db_v2 import get_db
from stage_two.alloy.alloy_screening_v2 import (
    screen_composition, IncompleteElementDataError, IncompletePairDataError)

db = get_db()
db.cursor.execute("SELECT id, composition FROM samples WHERE composition IS NOT NULL")
for row in db.cursor.fetchall():
    try:
        r = screen_composition(row['composition'])
        values = (r['VEC'], r['delta'], r['Delta_H_mix'])
    except (IncompleteElementDataError, IncompletePairDataError):
        values = (None, None, None)
    db.cursor.execute(
        "UPDATE samples SET vec = %s, delta = %s, delta_h_mix = %s WHERE id = %s",
        (*values, row['id']))
db.commit()
db.close()
```

---

## 8. Text to change in the Stage 1 paper

| Where | Current text | Change |
|-------|--------------|--------|
| §2 | "(Section 4.5)" for MP/OQMD/Alexandria | Section 4.4 |
| §5.2 | `dedup_by_functions` | `dedup_by_formula` |
| §4.4.2 title | "Four-tier synthesis-feasibility classification" | e.g. "Four-tier literature-match classification" |
| §4.3.1 | "provenance tracked per entry and lower-confidence entries flagged for follow-up" | all entries are from Takeuchi & Inoue 2005 [3], cross-checked entry by entry against a machine-readable copy of that table; no entries remain flagged |
| §4.3.1 | "expanded well beyond the original 40" | fine as is (now 138) |
| Fig. 2 caption, §6 | `literature_sources` "is queried by" / "populated during" cross-referencing | populated with source DOIs from Materials Project's text-mined synthesis records when a sample is saved; still no foreign key from `literature_checks` |
| §4.2 (optional) | — | add an example of the strict syntax, e.g. `Nd2Fe14B1` |
| §3 Scope boundary | Stage 1 "does not yet ingest raw characterization files" | contradicts README §2 and the XRD/VSM/SEM code in `stage_one/`; decide which is right and align README or paper |

The account of the original defect in §4.3.1 ("cross-checking all 40
original pairs… four pairs differed in sign") is still accurate as
history: against the reference, Fe-Nd, La-Fe and Al-Ga had the opposite
sign, and Co-Ni was −2 instead of 0.

---

## 9. Still open

- **Stage 3** (`stage_three/feasibility.py`): `dG = GM_eq − GM_target`
  can never be positive (equilibrium is the minimum), so the legend
  "> 0 means metastable" never applies; the generated `PHASE` line does
  not look like valid TDB syntax; errors are shown only as "ERR";
  `add_hypothetical_phase()` is dead code with a placeholder.
- **Hard-coded paths:** 13 files use absolute `/Users/r/...` paths
  (stage-one/two parser `__main__` blocks and several stage-three
  phase-diagram scripts).
- **Backups:** `alloy_desktop_v2_20260914.py` and
  `alloy_desktop_v2.py.bak` are older GUI copies without these fixes.
- **`db_config.py`:** only `POSTGRES_PASSWORD` is required; host, port,
  database, user and schema fall back to defaults. This matches the
  paper's wording ("a required variable"), so it was left as is.
- **Not run here:** the GUIs were not started (no display or database in
  the review environment); all changed files compile, and the screening,
  calculator and XRD changes were tested directly.

---

## 10. VSM standalone tool (`vsm_mh_analyzer_standalone.py`) — Stage 2 draft check

Checked against the Stage 2 paper draft (§3, §5). The tool did not do
what §3 says ("Save to DB persists only what the operator has reviewed
and accepted"), and there was no way to get BH_max from the app at all.

### 10.1 What was wrong

| Problem | Effect |
|---------|--------|
| No BH_max input. The main-app import calls `process_vsm_file()` without density/dimensions, and the tool had no fields for them | BH_max (§5.2) could only be produced by calling the pipeline by hand; nothing in the app ever stored it |
| Save only updated accepted segments | A segment the operator **rejected** kept the automatic Hc/Mr from import, looking valid |
| Save never touched `vsm_temperature_coefficients` | α(Hc)/β(Mr) still included rejected segments |
| Save never touched `bhmax_kj_m3`/`demag_factor_n` | after re-analysis with other prominence/distance, BH_max came from a different branch than the saved Hc/Mr |
| Plot used `find_descending_branch()` with default settings | the green "descending branch" was not the one analyzed when prominence/distance were changed |
| Segments were never annotated | the self-centering count in the list (promised in the docstring and `docs/standalone_tools.md`) was never shown |
| Segment matching counted unmatched segments as saved, and took an arbitrary row if a path was imported twice | silent partial saves |
| Docstring and READMEs said "no database saving" | contradicted the code and the paper |
| Layout: bottom bars packed after the expanding plot, transparent list buttons | Save bar and result line pushed off-screen at 1300×800; segment names nearly invisible in light mode |

### 10.2 What changed

- **`vsm_pipeline.analyze_mh_segment()`** (new): per-MH-segment analysis
  (Hc/Mr, mean T, field range, branch used, BH_max) used by both
  `process_vsm_file()` and the tool, so they cannot drift apart. It
  also guards BH_max against a missing mass (previously a crash).
- **Tool, BH_max:** density + full a, b, c (c = edge parallel to the
  field). Shows N for Prozorov–Kogan (used and saved) and Aharoni, and
  BH_max with both, so the open caveat of §5.2 can be quantified per
  sample.
- **Tool, Save to DB:** one transaction; accepted segments get the new
  values, all other MH segments NULL Hc/Mr/BH_max with a flag
  (`operator_rejected` if rejected by hand); geometry stored on
  `vsm_files`; temperature coefficients refitted from accepted segments;
  aborts without writing if any MH segment has no stored match or the
  path is stored twice; stored geometry is loaded and re-analyzed for
  review rather than saved blindly.
- **`vsm_db_builder.py`:** fills `temperature_k`, `field_min_oe`,
  `field_max_oe` (in the schema since `003_vsm_tables.sql`, never
  written) and stores NULL Hc/Mr for flagged segments, as the schema
  comment says (`unexpected_sign` used to store the numbers).
- Docs: `docs/standalone_tools.md`, `standalone/stand-alone_README.md`,
  README §6.2 (VSM schema is 7 tables, not 6).

**Tested** (Python 3.12, PostgreSQL 16, Xvfb): synthetic three-loop file
(300/350/400 K, Hc = 12000/9000/6000 Oe). Hc recovered to < 0.1 Oe,
α(Hc) = −0.500 %/K as built in, BH_max = 177.93 kJ/m³ against an
independent SI calculation of 177.93 kJ/m³. Imported with the builder,
then in the GUI: partial geometry rejected, one segment rejected, saved
→ that row NULL + `operator_rejected`, coefficients refitted from 2
points, geometry stored; stored-geometry reload and segment-mismatch
abort (nothing written) both checked.

> **Action needed:** rows already in `vsm_mh_details` were written by
> the old builder: `temperature_k`/field range are NULL, and
> `unexpected_sign` rows still carry Hc/Mr. Re-import, or open each file
> in the tool and save. `operator_rejected` is a new `hc_mr_flag` value;
> update anything that lists the allowed values.

### 10.3 Text to check in the Stage 2 paper

| Where | Issue |
|-------|-------|
| Abstract, Contributions (2) | "eight new tables": the Stage 2 SQL creates nine (`xrd_peaks`, `xrd_features` + seven `vsm_*`); SEM writes to the older `characterization`/`properties` tables, so "one schema extension shared by XRD, VSM and SEM" needs checking |
| §3 item 3 | true for the VSM tool now; worth adding that the main-app import stores the automatic result first and the tool's save then replaces it |
| §5.1/§5.2 | say where BH_max is computed (the standalone tool, or `process_vsm_file(..., density_g_cm3, demag_dimensions_mm)`); the normal import does not compute it |
| §5.2 "Open caveats", §8 | the tool now shows the Aharoni BH_max next to the Prozorov–Kogan one; running it on the 1 × 2.5 × 2 mm sample gives the second number to quote instead of only the N values (0.323 vs 0.267) |
| §8 | "other stored BH_max values": the import never stored any, so only values saved by hand or with this tool exist; easy to check with `SELECT count(*) FROM vsm_mh_details WHERE bhmax_kj_m3 IS NOT NULL` |
