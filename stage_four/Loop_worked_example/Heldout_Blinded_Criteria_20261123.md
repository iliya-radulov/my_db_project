# Blinded held-out step: criteria note (23 Nov 2026)

Written before the measured values are joined to the predictions. Part of the loop worked example (Track B, WP6).

## What is tested
Predictions of Tc (K) and |ΔS| (J/kg/K, field change 1.9 T) for the 12 held-out points of the Moreno-Ramírez Ni (nims_id 323–327) and Cr (375–381) series. Models: Snapshot v2 recipe from `evaluate.py` (mean, ridge, GBR), NIMS-only training, test papers excluded from training (967 rows for Tc, 1374 for |ΔS|).

## Criteria
- Tc: MAE ≤ 10 K, primary model ridge.
- |ΔS|: MAE ≤ 4 J/kg/K, primary model GBR.
- Flag per ledger row: pass if the primary model meets its threshold, fail otherwise. **Confirmed by the user, 23 Nov 11:50.**
- All three models are reported for each target; only the primary model decides the flag.

## Limits (stated before the join)
1. **Not blind thresholds.** Thresholds and primary models were chosen after the 12 Nov baselines were known (Tc ridge 7.5 K, |ΔS| GBR 3.2). They were set with margin above those values.
2. **Not an independent test.** The data, models and settings are those of L001/L002. The predictions are identical to the 12 Nov ones (checked to 3 decimals). The 12 Nov MAEs already satisfy both thresholds, so the outcome is known in advance. The rows L011/L012 record the procedure (frozen predictions, hash, then join). They carry no new evidence about the model.
3. **Procedural blind only.** The measured values are in the public NIMS file and were seen by both authors (the user and Claude) before this note. The script hides them from the code path and the prediction files; it cannot hide them from the people.
4. **Composition basis.** Ni series nominal 0.1–0.4 (EDX 0.10–0.33). Cr series: the labels in NIMS (0.12–0.56) are the EDX Cr contents of the paper, not nominal. Predictions use the compositions as stored in NIMS.
5. **Measured values** are NIMS values, digitised from the paper figures (see `Heldout_12_Measured_Values_20261123.md`); the papers themselves give no per-point table.
6. **Environment.** This re-run used Python 3.13.18, scikit-learn 1.9.1, numpy 2.5.3, pandas 3.0.5. The environment of the 12 Nov run is not recorded; the predictions agree exactly.
7. **Pipeline check.** During construction the join step was run once to verify the pipeline. The numbers matched L001/L002 (Tc ridge 7.47 K, |ΔS| GBR 3.16). No threshold or model choice was changed afterwards.
8. **Provenance gap closed (23 Nov).** `join_measured.py` is not listed in `manifest.json`; its sha256 is recorded here instead: 309ca3612633ac6102ceaa80df0e2a472fc43e2a760c958c10a553648e186a70. The measured-values file is `Heldout_12_Measured_Values_20261123.csv` (this note's procedure spells the name with lower-case "measured_values"; same file).

## Procedure
1. `python blinded_heldout_predict.py --out blind_out` writes `predictions_T_tr.csv`, `predictions_dS.csv`, `manifest.json` (sha256 of all inputs and outputs) and two `pending` ledger rows.
2. Hash of the manifest and the prediction files go into the ledger rows L011 and L012 (`WP6_ledger_append_pending_20261123.csv`).
3. `python join_measured.py --out blind_out --measured Heldout_12_Measured_Values_20261123.csv` checks the hashes, joins the measured values, prints MAEs and the flag.
4. The flags are then written into L011/L012 as a new append row; the pending rows are not edited (append-only).

## Frozen hashes (23 Nov 2026)
- predictions_T_tr.csv: 53871390dbb45cdfd867b5eddcb9b901eba43cc7079c8952de19b63063c2e1a5
- predictions_dS.csv: 1ad59cef1bad3ca2b43d065ca42e9a8abfe5fdc44d2a87cbdd5ae8559048dafe
- manifest.json: 94ba36d60327af218ca3a8df760e9408885e74fe01ec7dcf1a02e39b6f72dc1d
