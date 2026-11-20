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

---
# Addendum D results — τ1 temperature-dependence bias vs the WP4b descriptor (20 Nov 2026)

Plan frozen before the run (`FROZEN_SPEC.md` Addendum D, commit 14449c0). Model M0 = Feng-reconstructed baseline on the merged binaries (nothing fitted). Files: `results_addD/` (M0 TDB, `M0_ranges.tsv`, `M0_D.tsv`, `addD_analysis.txt`, calc log), scripts `tau1_window.py`, `addD_analysis.py`.

## Finding 1 — the calculated τ1 and τ2 windows do not move with temperature
Calculated τ1 single-phase range (y = Si/(Fe+Si) in La(Fe1−ySiy)13): **0.085–0.090 / 0.235–0.240 at every temperature from 1173 to 1573 K.**
Measured (Niitsu): 0.086–0.211 (1173 K), 0.096–0.229 (1373 K), 0.162–0.279 (1573 K), i.e. the window shifts to higher Si with temperature
(stated in Niitsu's abstract). Calc − exp, lower / upper boundary: 1173 K +0.004 / +0.024; 1373 K −0.011 / +0.006; 1573 K −0.077 / −0.039.
τ2: 0.27–0.43 → 0.275–0.42, measured 0.251–0.398, 0.266–0.402, 0.291–0.376. Two separate model errors:
**position** (the missing temperature shift: the bias runs from positive at low T to strongly negative at 1573 K) and **width** (calculated τ1 window 0.145–0.155 vs measured 0.117–0.133, 0.02–0.04 too wide, 0.038 at 1573 K).
Not Si-rich-boundary-only: the Table-7 τ1+τ2 tie-line residuals (+0.4 / −0.4 at.% in 1423/1473 K) describe the **Si-rich** end of τ1, where the calculation is good.

## Finding 2 — descriptor sensitivity: material inside the window (frozen rule)
The descriptor compositions (y = 0.092–0.154) sit near the **Si-poor** boundary, where the model–experiment offset is the large one.
The rule applies the per-temperature offset (not a uniform shift); the experimental boundary at 1323/1423/1473 K is linearly **interpolated** between the measured 1173/1373/1573 K ranges.
| T | exp Si-poor boundary (interp.) | calc | δy | est. ΔD (J/mol-atom) | ΔD/D over x = 1.2 … 2.0 | class |
|---|---|---|---|---|---|---|
| 1323 K (1050 °C) | 0.0935 | 0.085 | −0.0085 | −258 | 20, 14, 11, 9, 8 % | borderline (x ≤ 1.6), not material (x ≥ 1.8) |
| 1423 K (1150 °C) | 0.1125 | 0.085 | −0.0275 | −800 | 62, 44, 35, 30, 26 % | **material** at all x |
| 1473 K (1200 °C) | 0.1290 | 0.085 | −0.0440 | −1246 | 96, 69, 55, 47, 41 % | **material** at all x |
Sign: the model keeps τ1 stable at lower Si than measured, so the descriptor (stability margin of τ1 against its competitors) is **overestimated** at the Si-poor end at the high-temperature end of the window.

## Caveats (read with Finding 2)
- ΔD is a first-order estimate: a composition offset δy converted with the finite-difference slope of D along x (≈ 2.8–3.0 × 10⁴ J/mol-atom per unit y); not a recomputed descriptor.
- There is **no measurement of the lower boundary between 1373 K and 1573 K**; at 1423/1473 K the "experiment" is a linear interpolation, and the size of the bias at 1473 K rests on the single 1573 K range (0.162). The 1373 K datum alone gives δy = −0.011 (borderline/not material). A direct measurement or a Feng-assessment value at 1423–1473 K would settle it.
- The bias is that of **our reconstruction** (merged binaries FeLa-23Su/LaSi-10Zho/FeSi-17Cui); whether Feng's own TDB has the same flat window is not testable with the public data. The 20-binary-combination band of WP4 could be repeated for the window to see how much of it is binary choice.
- The M3 refit left the window unchanged; the refit does not address this bias.

## Limitation statement (the "material" shape of the pre-agreed three)
"The reconstruction does not reproduce the temperature shift of the τ1 single-phase region towards higher Si content (calculated Si-poor boundary 0.085–0.09 at all temperatures vs measured 0.086 → 0.096 → 0.162 at 1173/1373/1573 K), and its τ1 window is 0.02–0.04 too wide. Inside the descriptor window this is material for the stability margin D at 1150–1200 °C (estimated 26–96 % of D, using an interpolated experimental boundary) and borderline at 1050 °C; D at 1150–1200 °C is overestimated at the Si-poor end. D results from 1050 °C are the least affected."

---
# Addendum E results — is the flat τ1 window a binary-choice effect? (20 Nov 2026)

Plan and rules frozen before the run (`FROZEN_SPEC.md` Addendum E, commit ab33236); data and per-combination table in `results_addD/` (`ens_w*.tsv`, `ens_analysis.txt`); scripts `ensemble_window.py`, `ensemble_analysis.py`. All 20 combinations of the WP4 band computed (0 failures); the M0 consistency check passed.

## Result: **20 of 20 combinations are flat** → by the frozen rule, **the flat τ1 window is not a binary-choice effect** (it comes with the Feng τ parameters as reconstructed)
- Shift of the Si-poor boundary between 1173 and 1573 K: −0.005 (15 combinations) or 0.000 (5); measured +0.076. No combination reproduces the measured shift.
- Position and width do depend on the binaries, but only through the **La–Si** file: with LaSi-10Zho the τ1 Si-poor boundary is 0.085–0.090 (width 0.150 at 1373 K); with LaSi-20Xu 0.065–0.070 (width 0.165–0.170). The Fe–La choice changes it by at most 0.005; **the five Fe–Si files give identical windows** at the grid resolution (0.005). Measured at 1373 K: Si-poor boundary 0.096, width 0.133 — the binary choice moves the model *away* from the measured width in both cases (0.150–0.170).
- So the binary choice shifts the window by up to 0.02 in y (comparable to the −0.011 residual at 1373 K) but cannot produce the missing temperature shift (0.076 at 1573 K).
- Adding the three fitted ternary compounds (Addendum B, M2/M3) also left the window essentially unchanged (0.08–0.24 → 0.08–0.24, M3 0.10–0.26 at 1373 K, 0.02 grid), so the missing LaFe2Si2/LaFeSi/LaFeSi2 competitors are not the explanation either.

## What this does and does not establish
- It does **not** show that Feng's published TDB has the flat window: the shared cause is the τ1/τ2 and ternary parameters as transcribed from Table 5 (sign-corrected). The cause could be the published assessment, or a remaining transcription/reconstruction issue in those parameters. The public data cannot separate the two; only the authors' TDB (Data Availability: on request) can.
- τ3–τ6 are absent from the production TDB (unreconstructable, TAU36_RECONSTRUCTION.md); their possible role at the Si-poor boundary is untested.

## Limitation statement for the descriptor (final form)
"In our reconstruction of the Feng assessment (merged SGTE binaries; τ3–τ6 not reconstructable), the calculated τ1 single-phase region does not move with temperature (Si-poor boundary y = 0.085–0.09 at 1173–1573 K; measured 0.086, 0.096, 0.162) and is 0.02–0.04 too wide. All 20 binary combinations of the WP4 band give the same flat window (shift −0.005 to 0 against the measured +0.076); the binary choice only moves it by up to 0.02 through the La–Si file, so the flatness is not a binary-choice effect. Because the descriptor compositions lie near the Si-poor boundary, the stability margin D is overestimated there: by a first-order estimate, 26–62 % of D at 1150 °C and 41–96 % at 1200 °C (material) and 8–20 % at 1050 °C (borderline); at 1423/1473 K the experimental boundary is interpolated between measurements at 1373 and 1573 K and the size at 1473 K rests on the single 1573 K range. Whether the flat window belongs to the published assessment or to our reconstruction of it is not decidable from public data. D at 1050 °C is the least affected."

---
# Final limitation statement (20 Nov 2026) — supersedes the two earlier "limitation statement" paragraphs above

Corrections after review: (i) the descriptor bias is driven by the missing temperature dependence (flatness) of the Si-poor boundary, not by the window position; (ii) the ternary-phase check is an effective-phase, single-temperature, 0.02-grid check; (iii) the 20-combination run is a sensitivity check, not the ensemble method; (iv) "identical" for the Fe–Si files is at the 0.005 grid resolution. No new calculation; no frozen rule changed.

> The reconstructed τ1 window is flat in temperature and too wide. The descriptor bias at 1150–1200 °C comes from the missing temperature dependence of the Si-poor boundary, not from the window position: the measured boundary rises from 0.086 to 0.162 between 1173 and 1573 K, the calculated one stays at 0.085–0.09, and the gap grows with temperature (−0.0085 at 1323 K, −0.0275 at 1423 K, −0.044 at 1473 K; these three offsets use an experimental boundary interpolated between the measurements at 1173, 1373 and 1573 K). By a first-order estimate this is 8–20 % of D at 1050 °C, 26–62 % at 1150 °C and 41–96 % at 1200 °C (D overestimated at the Si-poor end). A 20-combination sensitivity check found the flat window in all 20 combinations, so within this check the flatness is not a binary-choice effect. The La–Si edge moves the window position by up to 0.02 but not its temperature dependence; the five Fe–Si files gave windows identical to the 0.005 grid resolution, and the Fe–La choice moves the window by at most 0.005. Adding fitted effective ternary phases (LaFe₂Si₂, LaFeSi, LaFeSi₂) did not change the window in this check (one temperature, 0.02 grid). The bias is that of our reconstruction; whether Feng's published TDB has the same flat window cannot be decided from public data, and the 1423/1473 K offsets rest on a single measurement (the 1573 K range). The 1050 °C results are least affected.
