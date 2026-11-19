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
