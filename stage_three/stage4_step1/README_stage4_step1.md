# Stage 4 Step 1 — ensemble of open binary CALPHAD assessments (Nd–Fe–B)

Track A of the Alloy Lab project. Paper, supplementary information and archived release:
doi:10.5281/zenodo.24034300 (software), doi:10.5281/zenodo.24034003 (paper).

## Reproducing the results

Environment: Python 3 with `pycalphad==0.11.2`, `numpy`, `pandas`, `tinydb`, `matplotlib`
(see `requirements.txt`). Run from `stage_three/stage4_step1/`.
Inputs: the 14 binary TDB files in `data/tdb/sgte_binary/` (SHA-256 in Supplementary Table S1a);
the ternary files used for the overlay are listed in Supplementary Table S1b.

1. All 84 combinations: merge, edge check, threshold (8 workers, about one minute):
   `python run_batch_v2.py`
   → `results_v2/batch_results.csv`, `results_v2/detail/<combo_id>.json`, `results_v2/summary.json`, `results_v2/merged_tdbs/`
2. Thresholds of the 78 survivors at all eight temperatures:
   `python diagnostics/extract_all_T.py` → `results_v2/ensemble_all_T.csv`
3. Tolerance sensitivity (re-admit the six failures):
   `python diagnostics/sensitivity_relaxed.py` → `results_v2/sensitivity_relaxed.csv`
4. Full ternary assessments (overlay), one call per file (`--suppress` names the compound phase to be removed):
   `python ternary_threshold.py <file.tdb> --suppress FE14ND2B --out ternary_results/<name>.json`
   (`--suppress ND2FE14B` for the Nd-mag-STAM file). Files and hashes: Supplementary Table S1b.
5. Failure mechanism: run the scripts in `diagnostics/` in the order of `diagnostics/README.md`
   (Supplementary Information S2). The decisive test is `constituent_union_test.py`.
6. Figures 1–3: `python make_plots_v2.py` (reads `results_v2/batch_results.csv`, writes `figures/`).

Expected: 78 of 84 combinations survive; the threshold at 800 K spans −9.26 to −8.33 kJ/mol
(per mole of atoms; median −8.79). Chen 2019 (ternary) −9.10, Hallemans 1995 (ternary) −8.78 at 800 K.

## Contents
| Path | Purpose |
|---|---|
| `run_batch_v2.py`, `tdb_merge.py` | batch screen and parsed-database merge (with `tag` per combination) |
| `ternary_threshold.py`, `ternary_results/` | threshold of full ternary descriptions and their outputs |
| `diagnostics/` | failure-mechanism scripts (see its README) |
| `results_v2/` | outputs of the final run (78 survivors) |
| `make_plots_v2.py` | Figures 1–3 |
| `run_batch.py`, `run_batch_v2_old.py`, `results/`, `mechanism2_results/`, `compare_tdbs.py` | earlier versions and exploratory work, kept for the record |
