# Held-out evaluation: the 12 measured values and their references (23 Nov 2026)

Held-out test set of WP6 ledger rows L001/L002 (Snapshot v2, Track B): the Ni series and the Cr series of La(Fe,Si)13. Per-point CSVs: `heldout_dS.csv`, `heldout_T_tr.csv`, written by `evaluate.py` (heldout mode). The CSVs reproduce L001/L002 exactly.

## Source of the values
- The evaluation's measured values (`y`) are the NIMS records, digitised from the paper figures. Neither paper tabulates per-point Tc or |ΔS|.
- The papers print only fit laws in the text. The NIMS values agree with them (see check below).
- Field change for |ΔS|: 1.9 T. Tc is the transition temperature (dM/dT maximum in the Ni paper).

## Composition: nominal vs EDX (decision 23 Nov)
- Ni series, nominal x = 0.1 ... 0.4. EDX (Table 1 of the paper): Ni = 0.10, 0.18, 0.26, 0.33 per formula unit.
- Cr series: the labels x = 0.12, 0.21, 0.35, 0.42, 0.47, 0.56 are EDX-derived, not nominal. State this wherever the labels are used.
- The paper's Cr Table 1 lists the x=0.42 row with EDX Cr 0.47 and the x=0.47 row with Cr 0.42. This is as printed. To be checked against the published version.

## Table
| # | Series | nims_id | Label | Tc (K) | \|ΔS\| 1.9 T (J/kg/K) | Paper fit Tc / \|ΔS\| |
|---|---|---|---|---|---|---|
| 1 | Ni | 323 | x=0 | 194.2 | 19.1 | Tc 192.6 |
| 2 | Ni | 324 | nominal 0.1 (EDX 0.10) | 193.6 | 19.0 | Tc 193.6 |
| 3 | Ni | 325 | nominal 0.2 (EDX 0.18) | 197.9 | 12.0 | Tc 197.3 |
| 4 | Ni | 326 | nominal 0.3 (EDX 0.26) | 205.4 | 8.4 | Tc 204.0 |
| 5 | Ni | 327 | nominal 0.4 (EDX 0.33) | 214.0 | 4.3 | Tc 214.0 |
| 6 | Cr | 375 | EDX x=0.00 | 188.3 | 22.4 | \|ΔS\| 22.1 |
| 7 | Cr | 376 | EDX x=0.12 | 188.7 | 21.4 | \|ΔS\| 21.8 |
| 8 | Cr | 377 | EDX x=0.21 | 184.0 | 21.1 | \|ΔS\| 20.9 |
| 9 | Cr | 378 | EDX x=0.35 | 178.9 | 17.0 | \|ΔS\| 17.6 |
| 10 | Cr | 379 | EDX x=0.42 | 175.3 | 14.9 | \|ΔS\| 14.9 |
| 11 | Cr | 380 | EDX x=0.47 | 173.0 | 11.5 | \|ΔS\| 12.4 |
| 12 | Cr | 381 | EDX x=0.56 | 170.0 | 6.7 | \|ΔS\| 6.8 |

Fit checks: Ni Tc = 192.6 + 159 x^2.19 (x nominal per formula unit; Ni paper, text), differences from NIMS 0 to 1.6 K. Cr |ΔS| = 22.1 - 69 x^2.6 (Cr paper, text), differences from NIMS up to 0.9. The fit laws are not point measurements; they are a consistency check only.

## References
```
@article{MorenoRamirez2018Ni,
  title = {The role of Ni in modifying the order of the phase transition of La(Fe,Ni,Si)13},
  author = {Moreno-Ram{\'\i}rez, L. M. and Romero-Mu{\~n}iz, C. and Law, J. Y. and Franco, V. and Conde, A. and Radulov, I. A. and Maccari, F. and Skokov, K. P. and Gutfleisch, O.},
  journal = {Acta Materialia}, volume = {160}, pages = {137--146}, year = {2018},
  doi = {10.1016/j.actamat.2018.08.054}
}
@article{MorenoRamirez2019Cr,
  title = {Tunable first order transition in La(Fe,Cr,Si)13 compounds: retaining magnetocaloric response despite a magnetic moment reduction},
  author = {Moreno-Ram{\'\i}rez, L. M. and Romero-Mu{\~n}iz, C. and Law, J. Y. and Franco, V. and Conde, A. and Radulov, I. A. and Maccari, F. and Skokov, K. P. and Gutfleisch, O.},
  journal = {Acta Materialia}, volume = {175}, pages = {406--414}, year = {2019},
  doi = {10.1016/j.actamat.2019.06.022}
}
```
Quote as given in the BibTeX (user, 23 Nov). Machine-readable version: `Heldout_12_measured_values_20261123.csv`.

## Open
- Per-point values come from figure digitisation (NIMS). If original data from the authors exist, replace them and re-run L001/L002.
