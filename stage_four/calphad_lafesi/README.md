# Stage 4, Track C — CALPHAD audit of the La–Fe–Si ternary

Goal: a tested thermodynamic description of the Fe–La–Si system for
hypothesis testing (τ₁ annealing windows, formation paths), built the way
the ORCHID consortium does it — reproduce a published assessment, audit it
against independent measurements, then extend it. The working plan and the
state of every step are in `WORKLOG.md`.

| File | Purpose |
|---|---|
| `data_niitsu2012/tielines.csv` | Tables 2–4 and 7 of Niitsu & Kainuma (2012): 71 measured equilibria at 1173–1573 K |
| `data_niitsu2012/dsc_reactions.csv` | Table 8: DSC reaction temperatures along the La(Fe₁₋ₓSiₓ)₁₃ section |
| `data_niitsu2012/lattice_parameters.csv` | Table 6 |
| `data_niitsu2012/phase_registry.csv` | every phase label of the paper → identity, structure, future TDB name |
| `data_niitsu2012/text_facts.csv` | statements from the running text (τ₁/τ₂ ranges, reactions, kinetics) |
| `niitsu2012.py` | loader, validation battery, ESPEI ZPF export (`--espei`) |
| `espei_datasets/` | generated ESPEI zero-phase-fraction datasets |
| `plot_tielines.py` | ternary tie-line plots per temperature (visual check against the paper's Fig. 3) |
| `data_feng2023/table5_parameters.md` | Feng et al. (2023) — every CALPHAD parameter (the assessment to audit) |
| `data_feng2023/table4_epma.csv` | Feng's 21 validation alloys, EPMA phase compositions at 1373 K |
| `data_feng2023/table6_comparison.csv` | Feng's own experiment-vs-calculation comparison |

```bash
python niitsu2012.py            # run all validation checks
python niitsu2012.py --espei    # regenerate the ESPEI datasets
python plot_tielines.py         # write results/tielines_<T>K.png
```
## Environment variable `SGTE_BINARY_DIR`

`build_merged_tdb_fixed.py` (used by `wp4b_descriptor.py`, whose `band` mode runs the 20 binary combinations, and by `refit_tau12/ensemble_window.py`) reads the folder with the binary TDB files from the environment variable `SGTE_BINARY_DIR`:

    export SGTE_BINARY_DIR=/path/to/data/tdb/sgte_binary

If the variable is not set, or the folder has no `.tdb` files, the script stops with an error. Before 18 Nov 2026 it fell back to a hard-coded path; on 16 Nov this produced an all-empty band result that was caught only by the test step.

## Superseded results and missing files (21 Nov 2026)

- `tdb_build/build_merged_tdb.py`, `tdb_build/wp4_band.py`, `wp4_probe.py` and the results in `tdb_build/RESULTS_MERGED.md` come from a defective merge (details and corrected values in the banner of `RESULTS_MERGED.md`); the old builder now stops with a pointer to `build_merged_tdb_fixed.py`.
- The self-contained Table-5 database (`tdb_build/LaFeSi_feng2023.tdb`) is not in the repository: `tdb_build/build_tdb.py` needs a file (`stage_three/FENDB_merged_v4.tdb`) that no longer exists, and `wp4_bcc.py`, `wp4_fecompare.py` and `wp4b_descriptor.py self` point to paths of another environment. The reproducible equivalent is the merged build `FeLa-23Su + LaSi-10Zho + FeSi-12Ohn` (D = 1.76 kJ/mol-atom at La(Fe11.5Si1.5), 1373 K; `refit_tau12/results_addD/paperbuild_*.tdb`).
- `*.tdb` is git-ignored; TDB files that belong to a result must be added with `git add -f`.

## Provenance and use

All numbers in `data_niitsu2012/` are transcribed from
**K. Niitsu, R. Kainuma, "Phase equilibria in the Fe–La–Si ternary
system", Intermetallics 20 (2012) 160–169,
doi:10.1016/j.intermet.2011.06.005** (© Elsevier). This is our own
transcription of the paper's factual data tables for research use — cite
the paper in anything built on it. Transcribed **as printed**: rows that
fail the mass-balance check are flagged by the loader and discussed in
`WORKLOG.md`, never silently corrected.
