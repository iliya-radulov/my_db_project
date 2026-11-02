# Magnetocaloric literature data: NIMS La(Fe,Si)₁₃ dataset

Parallel workflow to the Nd–Fe–B work of Stage 4: a property model for
La(Fe,Si)₁₃ compounds trained on a large, published literature dataset and
tested on small, consistently measured series. The idea (from colleagues):
train on the big but heterogeneous collection, and use consistent
measurements only for testing and correction, never for training.

## Data source

NIMS Materials Data Repository, La(Fe,Si)₁₃ dataset,
[doi:10.48505/nims.4909](https://doi.org/10.48505/nims.4909), file
`1-13_dataset.xlsx`. Licence: Creative Commons Attribution 4.0
International — cite the dataset in any work that uses it.

The file is not committed. Put it in `stage_four/mce_nims/data/`
(gitignored, like every `data/` folder in this repository).

What the file contains (checked on the real file, not its description):
1,113 samples from 221 papers (counted by DOI), almost all La(Fe,Si)₁₃
variants in about 25 substituent families (Si, Si+Co, Si+Mn, Si+Ce, Al, …);
313 samples contain interstitial H, C, N or B.

## Files

| File | Purpose |
|---|---|
| `nims_dataset.py` | Load and validate the file; fill down DOIs; composition from the element columns; expand field lists into one row per field |
| `evaluate.py` | Mean / ridge / gradient-boosting baselines: random split (comparison only), whole papers held out, one family held out, and the held-out test papers |
| `007_mce_literature.sql` | Staging tables `mce_literature_records` and `mce_literature_points` (with source, external ID, DOI, licence) |
| `import_nims.py` | Load the dataset into those tables (`--dry-run` to only validate and count) |

```bash
cd stage_four/mce_nims
python evaluate.py --target T_tr --restore-T-tr
python evaluate.py --target dS
docker exec -i alloy-postgres psql -U postgres -d alloy_lab < 007_mce_literature.sql
python import_nims.py --dry-run
python import_nims.py
```

## Pitfalls in the file that the loader handles

- **Exact headers.** The entropy-change column is `'|ΔSM|max (J/kg K) '`
  (trailing space) and density is `'Density (g/cm3)'`. Looking these up by
  their "obvious" names returns nothing, without an error. The loader
  checks every expected header and stops if one is missing.
- **Composition.** `Composition in the article` is filled in for only 533
  of 1,113 rows and often contains variables (`La(FexSi(1-x))13`, `…Hy`);
  the Stage 1 strict parser would reject most of it. The 24 element
  columns are complete and sum to 100 at.% over the metal sites, so they
  are the composition used.
- **Interstitials** (H, C, N, B) are at.% relative to the metal total and
  not part of the 100 (H = 3.57 for y = 0.5). They are stored separately.
- **DOI and article ID** are only on the first row of each paper's block;
  some cells hold two DOIs. They are filled down.
- **Field lists** such as `HS = [1, 2, 5]` with `|ΔSM|max = [10.5, 14.3,
  19.4]` become one point per field. Two rows (530, 531) have a peak-
  temperature list of a different length; those values are left empty.
- **Transition temperature** is reported for 835 samples; another 145 are
  estimated from the peak temperature at the lowest field (≤ 2 T). The
  source of each value is stored (`t_tr_source`).

## Notes on the NIMS example scripts (`ml_1_13.py`, `ml_1_13_functions.py`)

Not used here; `evaluate.py` is a fresh implementation. Found while
reviewing them:
- They fail with current libraries: `mean_squared_error(squared=False)`
  (removed from scikit-learn) and `plt.cm.get_cmap` (removed from
  matplotlib).
- When merging duplicates, IDs such as `"132_4.0"` (sample 132 at 4 T) go
  through `float()`, which reads the underscore as a digit separator:
  the ID silently becomes 1324. Only IDs are affected, not values.
- A condition meant to skip rounding for lattice constants is always true,
  so they are rounded to 0.01 Å anyway.
- Evaluation uses random 80/20 splits only (see below).

## Test set

The two series co-authored by I. Radulov, measured in one lab with one
protocol, are held out of all training and cross-validation:

- Moreno-Ramírez et al., Acta Mater. 160 (2018) 137, LaFe₁₁.₆₋ₓNiₓSi₁.₄ —
  doi:10.1016/j.actamat.2018.08.054 (NIMS IDs 323–327)
- Moreno-Ramírez et al., Acta Mater. 175 (2019) 406, LaFe₁₁.₆₋ₓCrₓSi₁.₄ —
  doi:10.1016/j.actamat.2019.06.022 (NIMS IDs 375–381)

NIMS stores nominal Ni contents (x = 0.1–0.4) and Si = 1.4 throughout;
EDX of the 1:13 phase gives x(Ni) = 0.10, 0.18, 0.26, 0.33 and Si up to
1.59. The Cr x = 0 row has no annealing temperature in NIMS and is
dropped by the feature filter.

## First results (2 November 2026)

Features: 24 metal at.%, H/C/N/B, annealing time and temperature (rows
without annealing data are dropped: 313 for T_tr, 397 for ΔS), plus the
field for ΔS. Mean absolute error; models fitted with the NIMS scripts'
hyperparameters.

**Transition temperature** (655 training rows, 166 papers):

| Evaluation | mean | ridge | gradient boosting |
|---|---|---|---|
| random 80/20 (as NIMS scripts) | 43.0 K | 14.3 K | 7.8 K |
| whole papers held out | 43.4 K | 14.7 K | 11.3 K |
| test papers, Ni + Cr (n = 11) | 36.2 K | 6.6 K | 7.1 K |

**|ΔS_M|max** (978 training points, 155 papers):

| Evaluation | mean | ridge | gradient boosting |
|---|---|---|---|
| random 80/20 (as NIMS scripts) | 6.24 | 3.80 | 1.79 J/kg K |
| whole papers held out | 6.29 | 4.34 | 3.61 J/kg K |
| test papers, Ni + Cr (n = 11) | 5.07 | 4.42 | 3.67 J/kg K |

Reading:
- The random split halves the apparent ΔS error compared with unseen
  papers (1.8 vs 3.6 J/kg K); only grouped evaluations are meaningful.
- On the Cr series, gradient boosting predicts a nearly constant
  ΔS ≈ 15–16 J/kg K and T_tr ≈ 188 K for x ≥ 0.35, where the measured
  values fall to 6.7 J/kg K and 170 K: with about five Cr rows left in
  training it cannot learn the trend, and trees do not extrapolate. Ridge
  follows the T_tr trend (6.4 K MAE on the substituted samples).
- Per-point predictions: `data/results/heldout_T_tr.csv`,
  `data/results/heldout_dS.csv` (written by `evaluate.py`, not committed).

## Next steps

1. Replace the test-set compositions with the EDX values and the test-set
   targets with the original measured values (Origin exports of the
   Darmstadt stay reports).
2. Correction step on the consistent data: fit the residuals of the
   NIMS-trained model on the consistent series (a constant offset or a
   small Gaussian process), evaluated leave-one-out.
3. High-Mn series (x ≈ 0.65–1.87 by EDX, positive ΔS): not in NIMS; use as
   an out-of-range test, expected to fail.
4. Decide how to treat rows without annealing data (currently dropped)
   and hydrides (currently in, with H as a feature).
