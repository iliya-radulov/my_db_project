# Snapshot v2 — Modelling Protocol

**Date:** 10 November 2026  
**Snapshot:** v2 (frozen 8 November 2026)  
**Author:** Iliya Radulov

This document records all analysis choices for the Track B baseline evaluation.
Every subsequent modelling run must cite this document and use these settings unchanged.
Any deviation requires a new named snapshot and a new version of this document.

---

## 1. Training data

**Source:** NIMS La(Fe,Si)₁₃ dataset only (`nims_lafesi_1_13`, 1,113 records / 1,539 points).

**Rationale (pre-registered):** Adding MCEdatabase, Kelly & Cole 2025, and Court & Cole 2018
to the training set showed no improvement in LOFO cross-validation. The three additional
sources are retained in Snapshot v2 as provenance and independent held-out validation, not
as training data.

---

## 2. Held-out test set (never used for training or cross-validation)

| Paper | DOI | Family | Role |
|---|---|---|---|
| Moreno-Ramírez et al., Acta Mater. 160 (2018) 137 | 10.1016/j.actamat.2018.08.054 | Si+Ni | held-out test |
| Moreno-Ramírez et al., Acta Mater. 175 (2019) 406 | 10.1016/j.actamat.2019.06.022 | Si+Cr | held-out test |

These are co-authored series measured in one lab under one protocol. They are removed from
the training pool before any cross-validation split is generated.

---

## 3. Cross-validation protocol

**Paper-holdout:** 5-fold GroupKFold over paper DOIs. Each fold holds out all rows from
a set of papers unseen during training. No random 80/20 splits are used for the primary
result (reported only for comparison with NIMS scripts).

**Family-holdout (LOFO):** leave-one-family-out over the six families defined in
`evaluate.py`:

| Family label | Description |
|---|---|
| Si+Cr | Cr-substituted La(Fe,Si)₁₃ |
| Si+Ni | Ni-substituted La(Fe,Si)₁₃ |
| Si+Mn | Mn-substituted La(Fe,Si)₁₃ |
| Si+Co | Co-substituted La(Fe,Si)₁₃ |
| Si+Ce | Ce-substituted La(Fe,Si)₁₃ |
| Al | Al-substituted (La(Fe,Al)₁₃ type) |

---

## 4. Test composition rule

**Decision (10 November 2026):** nominal compositions (as reported in the paper).

EDX-measured compositions are not used for the baseline. The `--test-compositions` flag
in `evaluate.py` is left unset. If EDX compositions become available for all test-set
samples and co-author consent is obtained, a separate EDX run will be recorded as a
sensitivity check, not as the primary result.

---

## 5. Hydride policy

**Decision (10 November 2026):** keep as-is.

Hydrogenated compounds are included in training with H encoded as an interstitial in the
composition key (e.g. `Fe81.4-La7.1-Si11.4+H3.6`). No separate flag or exclusion.
If family-holdout results show that hydrides are a distinct regime, the policy will be
revisited and recorded as a new decision.

---

## 6. Targets

Primary: **Tc** (`T_tr`, with `--restore-T-tr`).  
Secondary: **|ΔS|** (`dS`), run if time permits.

---

## 7. Models

| Model | Notes |
|---|---|
| Mean baseline | predict training mean; always reported |
| Ridge (`RidgeCV`) | median imputation + missing indicator + StandardScaler; αs log-spaced 10⁻³–10³ |
| Hist-GradientBoosting | handles missing values natively; hyperparameters from `evaluate.py` GBR_PARAMS |

---

## 8. Missing annealing data

Kept as missing (not dropped). The GBR model handles NaN natively; Ridge gets median
imputation plus a `was-missing` indicator column. `--drop-missing-anneal` is not set.

---

## 9. Exact command lines

```bash
# Paper-holdout and LOFO, Tc target
python stage_four/mce_nims/evaluate.py --target T_tr --restore-T-tr

# Paper-holdout and LOFO, |ΔS| target
python stage_four/mce_nims/evaluate.py --target dS
```

No additional flags. Results are written to `stage_four/mce_nims/data/results/`.

---

## 10. Reporting

Report mean MAE (± std across folds) for paper-holdout.  
Report MAE for each family in the LOFO block.  
Report MAE on the held-out test set split into: all rows / parent alloy (x=0) / substituted (x>0).  
Always show mean and ridge alongside GBR so the model is only credited with what it adds over those baselines.
