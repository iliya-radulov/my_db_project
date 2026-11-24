
# Session Wrap-Up — Stage 5: Corrected and Extended

**Date:** 23 November 2026  
**Directory:** `stage_five/`  
**Pull requests merged:** #28 (fixes), #29 (nearest-prototype fallback and app options), #30 (frozen reports and table)  
**Supersedes:** the statements of `20261121Session Wrap-Up — Stage 5: Generalized.md` that are listed in section 2 (that note stays in the repository, with its errata).

---

## 1. Where Stage 5 stands

| Part | State |
|---|---|
| `general_ensemble.py` — CALPHAD binary-ensemble engine | Fixed and tested; reproduces the Stage 4 Nd–Fe–B reference (78 / 84, median −8.79 kJ/mol-atom at 800 K) with the Stage 4 edge order |
| `dft_sisso_predictor.py` + `prototype_match.py` — Materials Project + Bartel SISSO, nearest-prototype fallback | Built; logic tested offline on synthetic entries; **never run against Materials Project** (no API key in the working environment) |
| `screen_ternary.py` — orchestrator, PostgreSQL persistence | Tested against a throwaway PostgreSQL 16 (before and after migration 010) |
| `desktop_screening_hook.py` + `alloy_desktop_v2.py` — cache and Stage 5 options row | Hook logic tested with a fake and a real database; **the GUI itself was not launched** |
| `009` / `010` SQL migrations | 009 and 010 are applied on the server (`alloy-postgres`) |
| `results/` — three frozen ensemble reports, methods table at 800 K | Committed with `SHA256SUMS`; SISSO columns read "not run" |
| `tests/` | 46 fast tests pass; two slow Fe–Nd–B end-to-end checks pass (`RUN_SLOW=1`, about 7 min) |

---

## 2. Corrections to the 21–22 November note

1. **The 52-vs-78 survivor gap is a merge-order effect, not the audit and not a looser tolerance.** The edge tolerance is 1.0 J/mol in both stages, and the audit excluded 0 files for Nd–Fe–B (84 combinations remain). `merge_databases` keeps the *first* file when two files define a parameter differently (here G(FCC_A1,ND:VA) in NdB-19Che vs FeNd-16Che). With the alphabetical edge order (B–Fe, B–Nd, Fe–Nd) 32 combinations fail the edge check (28 use FeNd-16Che, 4 more use FeB-19Wit) → 52 / 84. With Stage 4's order (Fe–Nd, Fe–B, Nd–B) the same engine gives **78 / 84**, median −8.7896, min/max −9.2623 / −8.3244. The merge priority now follows the element order, is recorded in every report and is part of the specification hash. Stored server run 1 (52 / 84) is superseded.
2. **The 5–95 % band is not Stage 4's range.** Stage 4's [−9.26, −8.33] at 800 K is the min–max of the 78 survivors; their 5–95 % band is [−9.20, −8.40].
3. **Lineages.** "Exactly 7/4/3" holds with the Stage 4 order; with the alphabetical order the surviving Fe–Nd lineages were 2 (the G2 minimum).
4. **`--suppress` did nothing.** The filtered phase list was built and never passed to the solver. It is now passed; the test removes FE17ND2 and checks that the threshold rises.
5. **Cache key.** One function (`compute_spec_sha256`) is shared by engine and hook: normalised and rounded fractions, rules version, gate parameters, suppress list. The prototype options are part of the cache key too (stored in `calphad_ensemble_runs.prototype_filter`).
6. **`--include-subsystems`** lists other ternary phases but no longer compares them with the threshold, which is at the target composition only. `e_above_hull` is computed from the 0 K hull (the entry-data key was not set by mp-api).
7. **Gates are engineering defaults, not pre-registered.** G1 ≥ 25 % survival and G2 ≥ 2 lineages per edge are the developer's choices (the Stage 4 pilot used ≥ 60 / 288). They are written to each report (`preregistered: false`).
8. **The "borderline" verdict does not contain the SISSO model error.** The CALPHAD band is about 1 kJ/mol-atom wide at 800 K; a SISSO estimate is uncertain by several kJ/mol-atom. `sisso_uncertainty_kJ` (default 0 = old behaviour) widens the verdict; the value must come from the validation error of the descriptor (Bartel et al. 2018, not checked here).
9. **The "Complete & Verified" label is too strong for the Nd₂Fe₁₄B benchmark.** The server run gives ΔG_f^SISSO(800 K) = −3.0 kJ/mol-atom against a CALPHAD threshold of −8.8, i.e. +5.8 kJ/mol-atom *above* the competing binaries: Nd₂Fe₁₄B would be called "metastable_above_band", although it is stable experimentally. "Standard GGA f-electron/magnetic offset" is an untested explanation. Record it as a calibration offset to quantify (the SISSO values themselves come from the server run and were not reproduced here).
10. **The "Δx ≤ 0.10" fallback plan is superseded** (section 4).

---

## 3. Frozen results (`results/`, committed; hashes in `SHA256SUMS`)

| System (target) | Merge priority | Survivors | 800 K ΔG_f* median [5 %, 95 %], kJ/mol-atom | Competing assemblage |
|---|---|---|---|---|
| B–Fe–Nd (Nd2Fe14B) | FE-ND > B-FE > B-ND | 78 / 84 | −8.79 [−9.20, −8.40] | FE17ND2+ND2B5+NDB4_D1E |
| Al–Fe–Mn (Al16Fe5Mn5) | AL-FE > AL-MN > FE-MN | 313 / 594 | −25.51 [−26.52, −24.06] | AL5FE2+BCC_A2 |
| Fe–La–Si (La7.1Fe82.1Si10.8) | FE-SI > FE-LA > LA-SI | 16 / 20 | −17.78 [−19.00, −16.47] | BCC_A2+LA5SI4 |

- **Al–Fe–Mn** gives the same survivor count (313 / 594) as the server run with 61.6 / 19.2 / 19.2 at.% (median −25.510 here, −25.503 there; the compositions differ in the third decimal). The audit excludes two third-generation FeMn files; FeMn-89Lee fails the edge check in every combination.
- **Fe–La–Si:** both merge orders (FE-SI-LA and FE-LA-SI) give 16 / 20 and the same band. FeSi-91Lac-LB fails the edge check in all 4 of its combinations (rule v2); Track C's older 20-combination band included it without an edge check.
- Code: `general_ensemble.py` as of commit `1fe56e9`; pycalphad 0.11.2; the reports carry `spec_sha256`, `tdb_collection_sha256` and the rules version. Commands: `results/README.md`.

---

## 4. Nearest-prototype fallback

**Plan review (the plan as pasted, with the checks):**
- The minority-element (anchor) guard is valid and more necessary than assumed: the quoted 0.129 for a pure Fe–Si entry leaves out the Fe component; the nearest Fe–Si *composition* to La7.1Fe82.1Si10.8 is 0.087, closer than LaFe13 (0.152). Materials Project Fe–Si entries are farther (Fe 0.221, Fe3Si 0.174).
- The 0.16 cutoff fits one composition: the Euclidean distance of LaFe13 to La(Fe13−xSix) is √2·x_Si, so 0.121 (x = 1.2), 0.152 (1.5), 0.162 (1.6), 0.182 (1.8), 0.202 (2.0). The prototype is lost for three of the five annealing compositions. Option `--site-group FE,SI` treats Fe and Si as one site (Δx < 0.002 over the series); **opt-in only** (decision of 23 Nov; the default stays plain composition distance).
- A prototype's energy is not at the target composition: nearest-prototype rows get `verdict = prototype_indicative_only`, `comparable = FALSE`, a † in the table; only exact matches get a stability verdict.
- Ranking: exact before prototype, then 0 K energy above hull (0.01 eV/atom tie bands), then the lowest-temperature SISSO energy, then Δx. A NaZn13-type structure check is not part of the ranking; the space group is reported as provenance.
- Ties in the minority element make both elements anchors (e.g. LaFe12Si); `--anchor` overrides.

**Provenance everywhere:** `match_type` / `prototype_formula` / `delta_x` / `spacegroup` in the CLI, the desktop preview (`mp-XXXX (LaFe13, nearest_prototype Δx=0.152)`) and PostgreSQL. CLI options: `--no-prototype-fallback --max-dx --anchor-tol --anchor --site-group --max-prototypes`.

**Main app:** the Stage 5 row has a fallback checkbox, a site-groups field (opt-in, e.g. `FE,SI`) and "Force recompute". Invalid input shows a warning. The existing callbacks of the app already marshal to the Tk thread.

---

## 5. Database state

- Server: PostgreSQL in Docker (`alloy-postgres`, host 192.168.178.10). Migration 009 was applied before; **010 was applied on 23 Nov 2026** (backup `alloy_lab_before_010_20261123.dump`, taken with `pg_dump -Fc`, kept by the user). The check lists the five new columns: `calphad_dft_comparison.{match_type, prototype_formula, delta_x, comparable}`, `calphad_ensemble_runs.prototype_filter`. The two backfill UPDATEs touched 16 rows each (old rows → `no_dft_entry` or `exact_match`).
- Command pattern used (from the Linux machine; the same from the Mac): `git show origin/<branch>:stage_five/010_prototype_provenance.sql | ssh r@192.168.178.10 "docker exec -i alloy-postgres psql -U postgres -d alloy_lab -1 -v ON_ERROR_STOP=1"`.
- Before migration 010 the code still saved exact rows, refused prototype rows with an explicit error and served the cache only with the fallback off; after it all paths work (tested on a throwaway PostgreSQL 16: 009 → 010 twice → app save/cache code, three option sets each returning its own cached run).
- Stored runs 1–3 are from the earlier engine; the cache key now differs, so they are not served. The next preview of each formula recomputes and stores a new run.

---

## 6. Verified and not verified

**Verified (run here):** the engine on Fe–Nd–B (both edge orders), Al–Fe–Mn and Fe–La–Si; suppress; cache-key consistency; the prototype filter, ranking and provenance on synthetic Materials Project entries (including an offline SISSO report with the pymatgen API); the table generator; migration 010 and the save/cache SQL on PostgreSQL 16; 46 fast tests and the two slow end-to-end checks.

**Not verified:** anything against Materials Project (no API key): the SISSO energies of Nd₂Fe₁₄B, of LaFe13 or of any prototype; the e_above_hull behaviour of real mp-api entries; the desktop GUI itself (not launched); the server's cache and save path (tested on a copy of the schema, not on the server); the Bartel SISSO error value.

---

## 7. Open points

1. Set `sisso_uncertainty_kJ` from the validation error of the Bartel descriptor; quantify the Nd₂Fe₁₄B offset before reading any verdict.
2. Register the gate numbers (G1, G2) for a study; they are engineering defaults now.
3. Run the SISSO step (Materials Project key) for the three systems to fill the table; for La7.1Fe82.1Si10.8 check whether LaFe13 / a ternary prototype is found (use `--site-group FE,SI` for the whole series).
4. The edge order can change the survivor count: report it with the result; an order-sensitivity run (all three orders) is possible but costs minutes per order.
5. `.gitignore` line 59 ignores the whole `stage_five` directory although its files are tracked; new files there need `git add -f`.
6. Not touched: the hard-coded LAN database host in `screen_ternary._connect_db` and the API-key fallback path outside the repository in `dft_sisso_predictor`.
7. The Mac clone did not show `010_prototype_provenance.sql` after a checkout of the branch; check `git status` / pull master there.
8. Stand-alone app (later): put the cache behind a `ResultStore` interface (PostgreSQL / local file); copy `tdb_lookup` and `tdb_merge` into the package; check the licence of the binary TDB collection; add progress and cancel for long runs (Al–Fe–Mn took over an hour on 3 workers); `multiprocessing.freeze_support()` for a packaged build.

---

## 8. File inventory (`stage_five/`)

- `general_ensemble.py` — engine (`audit_binary_candidates` with merge priority, `run_binary_ensemble`, `evaluate_gates`, `compute_spec_sha256`)
- `prototype_match.py` — filter, ranking, provenance label (offline)
- `dft_sisso_predictor.py` — candidates, SISSO energies, `compare_with_calphad_ensemble`, prototype CLI options
- `screen_ternary.py` — orchestrator, PostgreSQL persistence (migration-aware)
- `desktop_screening_hook.py` — cache lookup, site-group parsing, background worker
- `methods_table.py` — table from saved reports
- `009_calphad_dft_screening.sql`, `010_prototype_provenance.sql` — migrations
- `results/` — three ensemble reports, `SHA256SUMS`, `methods_table_800K.md/.tsv`, `README.md`
- `tests/` — `test_stage5.py`, `test_prototype.py`, `test_hook_options.py`, `conftest.py`
- `20261121Session Wrap-Up — Stage 5: Generalized.md` — earlier note with errata; `20261123Session Wrap-Up — Stage 5: Corrected and Extended.md` — this note