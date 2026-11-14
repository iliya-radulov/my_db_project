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

## Provenance and use

All numbers in `data_niitsu2012/` are transcribed from
**K. Niitsu, R. Kainuma, "Phase equilibria in the Fe–La–Si ternary
system", Intermetallics 20 (2012) 160–169,
doi:10.1016/j.intermet.2011.06.005** (© Elsevier). This is our own
transcription of the paper's factual data tables for research use — cite
the paper in anything built on it. Transcribed **as printed**: rows that
fail the mass-balance check are flagged by the loader and discussed in
`WORKLOG.md`, never silently corrected.
