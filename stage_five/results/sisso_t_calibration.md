# SISSO temperature calibration — results

Decision rule v1.4: correction **not adopted**.
- Condition 1: mean gain +0.003 >= 1.5 kJ → fail
- Condition 2: max worsening +0.666 <= mean gain +0.003 kJ → fail
- alpha = +1.56 J/mol-atom/K (scatter SD 6.72, n = 9)
- Materials Project database: 2026.09.28; pymatgen 2026.5.4, pycalphad 0.11.2

| Compound | Points | Slope (J/mol-atom/K) | MAE before (kJ) | MAE after (kJ) |
|---|---:|---:|---:|---:|
| Fe3Si | 7 | +11.87 | 2.241 | 1.920 |
| Fe2B | 8 | +10.37 | 3.195 | 2.529 |
| CoSi | 8 | +1.84 | 10.961 | 11.627 |
| TiB2 | 8 | -7.31 | 5.469 | 6.135 |
| LaB6 | 8 | -5.15 | 3.681 | 4.348 |
| NiAl | 8 | +3.29 | 1.192 | 0.550 |
| YAl2 | 8 | +1.61 | 3.896 | 4.562 |
| Ti5Si3 | 8 | +2.90 | 1.123 | 0.472 |
| Mg2Si | 5 | -5.41 | 1.677 | 1.266 |

Residuals (kJ/mol-atom):

| Compound | 800 K | 1000 K | 1100 K | 1200 K | 1300 K | 1375 K | 1450 K | 1600 K |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Fe3Si | -3.28 | -1.79 | -0.82 | +0.48 | +1.88 | +3.08 | +4.35 | — |
| Fe2B | -0.20 | +0.48 | +1.21 | +2.28 | +3.46 | +4.47 | +5.55 | +7.93 |
| CoSi | -10.92 | -11.50 | -11.59 | -11.52 | -11.28 | -10.94 | -10.53 | -9.40 |
| TiB2 | -1.84 | -3.87 | -4.77 | -5.58 | -6.27 | -6.70 | -7.07 | -7.65 |
| LaB6 | -0.89 | -2.59 | -3.30 | -3.90 | -4.37 | -4.62 | -4.80 | -4.98 |
| NiAl | +0.58 | +0.30 | +0.38 | +0.62 | +1.03 | +1.46 | +1.96 | +3.21 |
| YAl2 | -3.84 | -4.40 | -4.47 | -4.38 | -4.15 | -3.85 | -3.49 | -2.57 |
| Ti5Si3 | +0.57 | +0.36 | +0.42 | +0.61 | +0.96 | +1.34 | +1.80 | +2.93 |
| Mg2Si | +3.39 | +1.92 | +1.38 | +0.98 | +0.72 | — | — | — |

Secondary analyses (do not change the decision) are in the JSON file.
