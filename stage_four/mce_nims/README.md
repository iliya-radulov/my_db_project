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
| `origin_from_pptx.py` | Extract the worksheet data of Origin graphs embedded in a PowerPoint file, without Origin |
| `audit_checks.py` | Reproduces the data checks behind the decisions (overlap with the hand-extracted records, test series vs originals) |
| `WORKLOG.md` | Full record of this workflow: inputs, checks, decisions, results, open questions |

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
1.59. The Cr x = 0 row has no annealing temperature in NIMS (the stay
report gives 1100 °C).

The original values, read from the Origin graphs in the TU Darmstadt stay
reports with `origin_from_pptx.py`, agree with NIMS: for Ni, T_tr =
193.94, 193.77, 197.27, 204.49, 214.25 K and |ΔS| = 19.8, 18.98, 12.08,
8.48, 4.3 J/kg K (NIMS: 194.2, 193.6, 197.9, 205.4, 214.0 K; 19.1, 19.0,
12.0, 8.4, 4.3); for Cr the peaks of the ΔS(T) curves are 22.43, 21.52,
21.18, 17.32, 14.97, 11.53, 6.65 J/kg K (NIMS: 22.4, 21.4, 21.1, 17.0,
14.9, 11.5, 6.7).

## Results (2 November 2026)

Features: 24 metal at.%, H/C/N/B, annealing time and temperature, plus
the field for ΔS. Rows without annealing data (313 for T_tr, 397 for ΔS)
are kept: histogram gradient boosting (scikit-learn
`HistGradientBoostingRegressor`, NIMS hyperparameters translated) handles
missing values natively, ridge uses median imputation with was-missing
indicators. Mean absolute error.

**Transition temperature** (967 training rows, 206 papers):

| Evaluation | mean | ridge | gradient boosting |
|---|---|---|---|
| random 80/20 (as NIMS scripts) | 48.8 K | 13.3 K | 8.2 K |
| whole papers held out | 49.5 K | 14.3 K | 11.1 K |
| test papers, Ni + Cr (n = 12) | 46.9 K | 7.5 K | 9.3 K |

**|ΔS_M|max** (1,374 training points, 192 papers):

| Evaluation | mean | ridge | gradient boosting |
|---|---|---|---|
| random 80/20 (as NIMS scripts) | 6.17 | 3.50 | 1.74 J/kg K |
| whole papers held out | 6.24 | 4.03 | 3.32 J/kg K |
| test papers, Ni + Cr (n = 12) | 5.46 | 4.83 | 3.16 J/kg K |

With `--drop-missing-anneal` (rows without annealing data dropped, 978
training points) the same ΔS model gives 3.73 J/kg K on unseen papers
and 2.87 on the test papers: keeping the rows helps on the larger,
paper-level evaluation; the test-set difference (11–12 points) is within
noise.

Reading:
- The random split halves the apparent ΔS error compared with unseen
  papers (1.7 vs 3.3 J/kg K); only grouped evaluations are meaningful.
- On the Cr series, a tree model trained with only about five other Cr
  rows predicts a nearly flat T_tr and ΔS for x ≥ 0.35, where the
  measured values fall to 170 K and 6.7 J/kg K: trees do not extrapolate.
  Ridge, linear in the Cr content, follows the T_tr trend better (6.9 K
  MAE on the substituted test samples vs 10.3 K).
- Per-point predictions: `data/results/heldout_T_tr.csv`,
  `data/results/heldout_dS.csv` (written by `evaluate.py`, not committed).

## Next steps

1. Replace the test-set compositions with the EDX values; the original
   measured values are now readable from the stay reports with
   `origin_from_pptx.py` (they agree with NIMS, see above).
2. Correction step on the consistent data: fit the residuals of the
   NIMS-trained model on the consistent series (a constant offset or a
   small Gaussian process), evaluated leave-one-out.
3. High-Mn series (x ≈ 0.65–1.87 by EDX, positive ΔS): not in NIMS; use as
   an out-of-range test, expected to fail.
4. Decide how to treat hydrides (currently in, with H as a feature).
