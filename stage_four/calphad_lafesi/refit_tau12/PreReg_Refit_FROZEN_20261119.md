# La–Fe–Si τ1/τ2 refit — decision rules, FROZEN 19 Nov 2026 (consolidates Addenda A–C of `FROZEN_SPEC.md`; format as the Cr–Fe–Ni Pilot-M pre-registration)

**Status: FROZEN 19 Nov 2026**, sha256 of this note and of the scripts in `PreReg_Refit.sha256`, committed **before** any residual, fitted parameter or held-out loss of the Addendum-B model was computed.

**Disclosure — what had been seen before this freeze (so it can be checked):**
1. Refit 1 (12 parameters, weak regulariser) and refit 2 (6 constants, regulariser 1000) on the 17/7 split: **both rejected** (RESULTS.md, merged PRs #17, #18). These motivated Addendum B.
2. Equilibrium counts of the Addendum-B data (30 train / 17 held-out / 24 excluded) — counts only.
3. Residuals of the **Feng-reconstructed baseline only** on its 24 evaluable equilibria: phase set matches 6/24, within scatter 2/24; no systematic τ1/τ2 Si shift (mean ΔSi −0.5 / −0.25 at.%).
4. **Intermediate training-loss lines** of the Addendum-B runs (at epoch 360: fit 9.7e3, frozen prior baseline 2.5e4) — seen while writing this note. No fitted parameter value, no held-out loss, no residual of the Addendum-B models.
5. **Design consequence of item 4, decided now:** the prior baseline (new phases at an arbitrary −30 kJ/mol-atom) is a weak comparator — any fit of the new phases beats it. A **control run** (new-phase parameters fitted, τ1/τ2 frozen at the published values, otherwise identical) is therefore added (§4.4); the τ1/τ2 verdict is taken against it, not against the prior.

## 1. Question and nature
Do the Niitsu & Kainuma 2012 equilibria contain information that moves the τ1/τ2 parameters of the sign-corrected Feng reconstruction away from the published values, in a way that improves held-out description? Methods/negative-result study; **not** a re-assessment; fitted energies of LaFe2Si2, LaFeSi, LaFeSi2 are effective values, never to be used as thermodynamic data without validation.

## 2. Observables (fixed)
- **L_train, L_held:** eqopt loss on the 30 training (1173, 1273–1523, 1573 K) and 17 held-out (1373 K) equilibria; data part only (stable + unstable terms; regulariser reported separately), same settings and μ′ relaxation for all models.
- **Residuals:** Addendum C — equilibrium at the nominal composition and T; phase-set match; ΔSi, ΔLa of BCC_A2/FCC_A1/LIQUID/TAU1/TAU2 in at.%; **within scatter** = phase set matches and all |ΔSi| ≤ 2.0, |ΔLa| ≤ 1.0 at.%. Reported separately for the 30 training and 17 held-out points and per equilibrium (which reproduced, which outliers, kind of outlier: phase set / composition).
- **Systematic shift:** mean signed ΔSi of TAU1 and TAU2 overall and per temperature; systematic if |mean| > 1.0 at.% and ≥ 75 % same sign.
- **Gate quantities:** A3 (τ1 fraction at La(Fe11.5Si1.5), 1373 K ≥ 0.9), A5 (τ1-dominant window along La(Fe1−xSix)13 overlaps 0.096–0.229), D > 0 at the 15 descriptor points, fitted formation energy of each new phase at 1373 K in [−80, 0] kJ/mol-atom.

## 3. Models (fixed)
- **M0 Feng baseline** (original TDB; 24 evaluable equilibria; residuals only).
- **M1 prior:** M0 + three stoichiometric compounds at the frozen −30 kJ/mol-atom prior, all parameters frozen (lr 1e-9).
- **M2 control:** M1 with the 6 new-phase parameters (w, v per phase) fitted, τ1/τ2 frozen. Regulariser 100, lr 0.1, 1000 epochs, seed 42, latent_mu_lr 100.
- **M3 full:** M2 plus the 6 τ1/τ2 constants free (12 parameters), same settings.

## 4. Procedure and gates (fixed; applied in this order, once)
1. **Run validity (not a gate):** M1, M2, M3 train to epoch 1000; held-out evaluations at 400 epochs with lr 1e-9; residual files have one row per model × evaluable equilibrium. Script/environment faults → fix or pin, qualify and repeat the whole run; failures caused by the data or the model stay failures.
2. **Fit quality (M3 vs M1):** C1 L_train(M3) ≤ 0.90·L_train(M1); C2 L_held(M3) ≤ 1.05·L_held(M1); C3, C4 as Addendum B (gate quantities and |w| ≤ 20, |v| ≤ 1).
3. **Beyond the prior — does τ1/τ2 refitting add anything? (M3 vs M2):**
   - **T1** L_held(M3) ≤ 0.95·L_held(M2);
   - **T2** within-scatter count of M3 on the 17 held-out points ≥ that of M2 (not lower) **and** on all 47 points ≥ that of M2 + 2;
   - **T3** the six fitted τ constants are not all within the solver noise (|Δ| > 50 J/mol for at least two).
4. **Verdict (single rule):**
   - **"τ1/τ2 refit justified"** only if C1–C4 and T1–T3 all hold. Further refit effort is then justified, with the caveat that the competing-phase energies are effective.
   - **otherwise "Niitsu data insufficient to move the model"**: the sign-corrected Feng reconstruction is frozen as "best available given the public data"; no rescue, no further sweeps in this thread.
   - Whatever the verdict, the three requested diagnostics (training reproduction, held-out residuals, systematic shift vs the Feng description) are reported; they cannot change the verdict.
5. **Recording:** every fitted parameter (w, v of each new phase; τ1/τ2 w; the absolute parameter strings in the optimised TDB), the optimised TDBs, train/held-out inputs, logs' final-epoch lines and the per-equilibrium residual tables are committed (as `.txt`/`.tsv` and `.tdb`; the repository ignores `.csv`). Ledger entry either way.

## 5. Prior expectation (written before any computation of the Addendum-B models)
Refits 1 and 2 moved nothing useful; Feng's assessment saw the same data. I expect "Niitsu data insufficient to move the model", with M3 ≈ M2; a chance that the added phases reduce phase-set outliers (the dominant failure of M0) without changing τ1/τ2.

## 6. Scripts and environment (hashed at the freeze)
`make_inputs.py` (options `--constants-only --ternary --no-tau`), `make_valid_tdbs.py`, `evaluate.py`, `residuals.py`, `config_tern.yaml`, `config_tern_base.yaml`, `FROZEN_SPEC.md`; eqopt commit 2b1d4b4 unmodified, torch 2.15.0, pycalphad as installed; seed 42. Data: Niitsu 2012 tielines (own transcription, recovered from git `1b83f71^`).

## 7. Limits
17+30 equilibria of one study at 1173–1573 K; tie-lines give relative energies only; nominal-composition equilibria are sensitive to mass-balance-flagged rows; ternary phases modelled as stoichiometric (no Fe/Si solubility); LaSi2 variants and the AlB2-type phase still excluded (24 equilibria); one regulariser value, no sweep; the scatter band (2.0/1.0 at.%) is a stated judgement.
