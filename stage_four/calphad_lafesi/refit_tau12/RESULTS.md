# τ1/τ2 refit — results (19 Nov 2026)

Spec: `FROZEN_SPEC.md` (frozen before the run). Tool: authors' `eqopt` 2b1d4b4, unmodified.
Data: 17 training equilibria (1173, 1273–1523, 1573 K), 7 held out (1373 K); 47 of 71
Niitsu equilibria unusable because they contain phases absent from the TDB.

## Outcome: **refit REJECTED — baseline retained**

| criterion | result | verdict |
|---|---|---|
| C1 train loss ≤ 90 % of baseline | 9.20e3 vs 1.02e4 (frozen-parameter, μ′-relaxed) = **90.2 %** | fail (marginal) |
| C2 held-out 1373 K loss ≤ 105 % of baseline | 8.81e3 vs 1.05e3 = **840 %** (unstable-phase term 178 → 6870) | **fail, large** |
| C3 A3/A5 still hold | A3 literally yes, but τ1 falls from single-phase to 21 % of the assemblage (63 % FCC, 16 % LaSi2_X); A5 window 0.08–0.24 → 0.14–0.26 (still overlaps 0.096–0.229) | pass on the letter, substantive degradation |
| C4 corrections sane | max |Δconst| 0.26 kJ/mol, max |ΔT coeff| 2.6 J/mol/K | pass |

Note on the baseline: the raw first-epoch loss (1.37e5) is not a fair baseline, since μ′ is still
unrelaxed; the comparison uses a run with the model learning rate 1e-9 (parameters frozen) and the
same latent-μ settings.

## Fitted corrections (J/mol, J/mol/K)
| parameter | Δconst | ΔT coeff |
|---|---|---|
| τ1 G(La:Fe) | +173.9 | +2.620 |
| τ1 G(La:Si) | −170.0 | −1.238 |
| τ1 L(La:Fe,Si) | −150.6 | −0.956 |
| τ2 G(La:Fe) | −6.2 | +2.074 |
| τ2 G(La:Si) | −261.6 | +0.081 |
| τ2 L(La:Fe,Si) | −159.1 | +0.873 |

## Descriptor (reported)
D = G(competing, τ suspended) − G(all), J/mol-atom, at x = 1.2–2.0, 1050–1200 °C:
baseline 1300–3170, refit 0–635. The refit removes most of τ1's stabilisation at the
magnetocaloric composition. GM at La(Fe11.5Si1.5), 1373 K: −91444 → −89417 J/mol-atom (+2.0 kJ).

## Interpretation and limits
- The training set is tiny and one-sided: 1373 K, where τ1 is best constrained, is the held-out set,
  and the equilibria with LaFe2Si2/LaFeSi/LaFeSi2 are all missing, so nothing in the loss
  penalises τ1 for losing to FCC + LaSi2. The fit reduces the loss mainly by lowering the
  unstable-phase penalty at other temperatures at the expense of the τ1 window.
- Only phase equilibria enter the loss (no DSC, no EPMA). Feng EPMA check not run.
- Not tested: more training data (adding 1373 K, with a different held-out split such as
  leave-one-table-out), phases added to the TDB so more equilibria become usable, a stronger
  regulariser (`regularize_difference`) or fewer free parameters (e.g. only the 6 constants).
  Not tuned here, to keep the frozen spec honest.
- Inputs recovered from git history (the CSVs are gitignored). Run artefacts (logs, optimized TDB)
  are not committed; reproduce with `make_inputs.py`, `eqopt-calphad … --config config.yaml`,
  `make_valid_tdbs.py`, `evaluate.py`.

---
# Addendum A results — constants-only refit, regularisation weight 1000

Setup frozen in `FROZEN_SPEC.md` Addendum A before the run (6 constants, one regulariser value, no sweep).

## Outcome: **rejected again — baseline retained**

| criterion | result | verdict |
|---|---|---|
| C1 train loss ≤ 90 % of baseline | data loss (stable + unstable) 1.002e4 vs 1.020e4 = **98 %** (total 1.01e4 incl. regulariser 41.5) | fail |
| C2 held-out 1373 K loss ≤ 105 % of baseline | 1.13e3 vs 1.05e3 = **107.6 %** (stable 871 → 917, unstable 178 → 209) | fail (marginal) |
| C3 A3/A5 | τ1 stays single-phase at La(Fe11.5Si1.5), 1373 K; dominant window 0.08–0.26 (baseline 0.08–0.24), overlaps 0.096–0.229 | pass |
| C4 corrections sane | max |Δ| 173 J/mol (all six constants listed below) | pass |

Fitted constants (J/mol): τ1 G(La:Fe) −3.6, G(La:Si) −47.0, L −29.4; τ2 G(La:Fe) +173.3, G(La:Si) +75.0, L +52.5.
Descriptor D changes by +10 to +14 J/mol-atom (baseline 1.3–3.2 kJ): the model is essentially unchanged.
GM at La(Fe11.5Si1.5), 1373 K: −91444 → −91456 J/mol-atom.

## Reading
Strong regularisation does what it should for safety — τ1 is no longer destroyed (the first refit's failure) —
but the 17 training equilibria with 6 constants then offer only a ~2 % loss reduction, and the held-out
loss rises slightly. Together with the first refit this says the usable Niitsu data do not constrain the
τ1/τ2 parameters beyond the published ones: the loss is dominated by terms (unstable-phase penalties
from LaSi2/La–Si compounds, stable-phase offsets of the Fe–Si phases) that τ1/τ2 constants cannot move.
Not tried: adding the missing ternary phases (LaFe2Si2, LaFeSi, LaFeSi2) so the 47 excluded
equilibria become usable — the data most informative for τ1/τ2 competition — or a different split.
Run artefacts are in the session scratchpad, not committed.

---
# Addendum B/C results — fitted ternary compounds, residual analysis (19 Nov 2026)

Rules: `PreReg_Refit_FROZEN_20261119.md` (hashes `PreReg_Refit.sha256`, commit cbd7fc4, before any Addendum-B result).
Models: M1 prior (new phases at −30 kJ/mol-atom, frozen) · M2 control (new-phase parameters fitted, τ1/τ2 published) · M3 full (new phases + 6 τ constants fitted).
All values, TDBs, inputs and residual tables: `results_addB/` (`all_parameters.tsv`, `new_phase_parameters.tsv`, `tau_constants.tsv`, `final_epoch_losses.tsv`, `residuals_*.tsv`, `*_optimized.tdb`).
Helper `make_valid_b.py` was added after the freeze (dummy symbol for held-out evaluation; no rule change).

## Verdict: **"Niitsu data insufficient to move the model"** — the Feng reconstruction stays frozen as best available.

| rule | quantity | result | |
|---|---|---|---|
| C1 | L_train(M3) ≤ 0.90·L_train(M1) (data part) | 7.79e3 vs 2.45e4 = 32 % | pass |
| C2 | L_held(M3) ≤ 1.05·L_held(M1) | 2.45e3 vs 3.03e4 = 8 % | pass |
| C3 | A3 (τ1 fraction ≥ 0.9), A5 overlap, D > 0 | τ1 = 1.00; window 0.10–0.26 (M2: 0.08–0.24); D 99–2385 J/mol-atom, all > 0 | pass |
| C4 | \|w\| ≤ 20, \|v\| ≤ 1; ΔG_f(1373 K) ∈ [−80, 0] | ΔG_f −57 … −67 kJ/mol-atom ok, but **\|v\| = 1.96–2.65 for all three new phases** | **fail** |
| T1 | L_held(M3) ≤ 0.95·L_held(M2) | 2.45e3 vs 2.35e3 = 104 % | **fail** |
| T2 | within scatter: M3 ≥ M2 on held-out and ≥ M2 + 2 on all 47 | held-out 1 vs 2; all 47: 3 vs 4 | **fail** |
| T3 | ≥ 2 τ constants move > 50 J/mol | 5 of 6 do (see below) | pass |

Verdict rule: "justified" needs C1–C4 and T1–T3 all → not met (C4, T1, T2 fail).

## The three requested diagnostics
1. **Training points (30):** loss falls 2.45e4 → 7.8e3 (M1 → M3) but only M3: 2 of 30 reproduced within scatter (set match 4 of 30); M2: 2 (6); M1: 1 (4).
2. **Held-out points (17, 1373 K):** within scatter M1 1, M2 2, M3 1; phase set matches 2 / 4 / 2. M3 ≈ M2 in loss (104 %), slightly worse in residuals. On all 47: 2 / 4 / 3. (Feng baseline M0 on its 24 evaluable points: 2.)
3. **Systematic shifts:** by the frozen rule none: M3 τ1 mean ΔSi +1.48 at.% (69 % same sign, below the 75 % threshold); τ2 +0.30. Descriptive (not a rule): in M0–M2 the calculated τ1 Si content runs from **+4.9 at.% (1173 K) to −2.1 at.% (1573 K)** relative to experiment — the temperature dependence of the τ1 boundary is too weak in the model; **M3 leaves it unchanged** (+4.87 at 1173 K, −1.68 at 1573 K). The dominant failure everywhere is the phase set (≤ 10 of 47 sets match), not the τ1/τ2 compositions.

## Fitted values (all recorded in `results_addB/`)
New phases (M3 / M2): LaFe2Si2 G = ΣGHSER − 151710.8 − 122.63·T (M2: −151502.4 − 125.45·T); LaFeSi −91168.3 − 79.32·T (M2 −91141.8 − 79.65·T); LaFeSi2 −120666.7 − 78.20·T (both runs identical to 10 digits — observation: the optimum was the same irrespective of the τ constants; not interpreted). ΔG_f(1373 K) −64.0 / −66.7 / −57.0 kJ/mol-atom (M3). These are effective numbers, not thermodynamic data.
τ constants (M3, published → fitted, J/mol): τ1 La:Fe 2300 → 2675.8 (+376); τ1 La:Si 37000 → 36964.2 (−36); τ1 L −242114 → −242120.5 (−6); τ2 La:Fe 6500 → 7096.4 (+596); τ2 La:Si 22500 → 22682.2 (+182); τ2 L −241114 → −240968.5 (+146). T-coefficients not free (constants-only).

## Reading and limits
- τ1/τ2 refitting adds nothing measurable beyond fitting the competing phases alone (M3 vs M2: held-out loss +4 %, residuals no better). Adding the three phases is what removes most of the loss, but the new-phase T-slopes go beyond the frozen sanity bound, so those energies are not credible as data.
- The regulariser term is large (1.8e3 of 9.5e3), so the fit is regulariser-limited, not data-limited; one value (100), no sweep, by rule.
- 17 + 30 equilibria, tie-lines (relative energies), 1173–1573 K, nominal-composition equilibria sensitive to mass-balance-flagged rows, ternary phases stoichiometric, LaSi2 variants / AlB2 phase still excluded (24 equilibria). Thread closed under the frozen rule: reconstructed Feng τ1/τ2 stays.
