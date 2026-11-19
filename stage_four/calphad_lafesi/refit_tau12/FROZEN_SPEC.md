# τ1/τ2 refit with the differentiable phase-equilibrium loss — frozen spec

Written 19 Nov 2026 **before any training run**. Method: Dong/Zhang et al.,
arXiv 2608.00516v3 (loss on grand potential, auxiliary chemical potential
μ', exponentiated-gradient inner minimisation). Code: authors' `eqopt`
package (MIT, commit 2b1d4b4), used unmodified.

## Model
Baseline = merged TDB (FeLa-23Su + LaSi-10Zho + FeSi-17Cui + Feng 2023 τ1/τ2),
the validated Track C build. Text normalisation needed by the authors' parser
(both documented, neither changes any energy): (1) `; , N !` → `; 6000.0 N !`;
(2) phases DHCP and HCP_A3 dropped (inconsistent sublattice definitions
between the binaries; irrelevant to Fe-rich τ equilibria).

Fit parameters: 12 corrections `1000·w + 10·v·T` (w in kJ/mol, v in 10 J/mol/K, so Adam steps are well scaled) added to the six TAU1/TAU2
parameters G(La:Fe), G(La:Si), L(La:Fe,Si) (each of τ1, τ2). Zero-initialised.
Everything else frozen.

## Data
- Source: Niitsu & Kainuma 2012, our transcription (`tielines.csv`).
- **Train:** all equilibria at 1173 K, 1273–1523 K, 1573 K (tables 2, 4, 7).
- **Held out (validation):** all 1373 K equilibria (table 3). Never used in fitting.
- An equilibrium is used only if **every** phase in it maps to a phase in the
  baseline TDB. Phases not in the TDB (LaFe2Si2, LaFeSi, LaFeSi2, LaFexSi2-x,
  LaSi2 variants — structure assignment ambiguous) → whole equilibrium excluded.
  Excluded equilibria are counted and reported.
- Compositions are passed for solution/τ phases (BCC, FCC, LIQUID, TAU1, TAU2);
  stoichiometric compounds enter with blank composition (grand potential only).
- Training uses only phase equilibria (no DSC).

## Acceptance (decided now)
- **C1 — fit works:** training loss at the end ≤ 90 % of the baseline's.
- **C2 — no overfit:** validation (1373 K) loss ≤ 105 % of the baseline's
  (same loss function, same settings, evaluated on the corrected TDB).
- **C3 — frozen Track C gates still hold:** A3 (τ1 stable at La(Fe11.5Si1.5),
  1373 K) passes, and A5 (τ1 window along La(Fe1-xSix)13 at 1373 K overlaps
  x = 0.096–0.229) still overlaps.
- **C4 — sane corrections:** every |w| ≤ 20 (20 kJ/mol), every |v| ≤ 1 (10 J/mol/K).
- **Reported, not gated:** change in ΔG_f(τ1) at 1373 K (baseline −20.99
  kJ/mol-atom), change in formation driving force (+84.7 kJ/mol-atom, band
  2.1 kJ), Feng EPMA (table4) phase-composition agreement before/after.

Accepted only if C1–C4 all hold. If C1 holds and C2 fails: reported as
overfit, baseline retained. Outcome is reported whichever way it goes.

## Settings
Authors' defaults except: `initial_parameter_scale: 0`, `seed: 42`,
`epochs: 1000`, `lr` 0.1 → tuned only on the **training** loss if needed
(any change logged in RESULTS.md).
