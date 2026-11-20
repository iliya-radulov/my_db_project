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

---
## Addendum A (19 Nov 2026) — constants-only refit with a stronger regulariser
Written after the first refit was rejected (RESULTS.md) and **before** this run.
- Free parameters: the 6 constants `1000·w` only (no T coefficients `v`).
- Regulariser: `regularization_weight: 1000` (was 1e-10) on the w symbols (kJ units; w = 1 costs 1e3,
  about 10 % of the baseline training loss). One value, chosen now; **no sweep, no tuning on validation**.
- Everything else, data split and criteria C1–C4 unchanged. Baseline losses reused from the first
  refit (train 1.02e4, validation 1.05e3, same loss settings; the regulariser term is ~0 at w = 0).
- C1 may be unreachable with a tighter model; it is reported as failed if so. Acceptance still
  needs all of C1–C4. One run, one outcome.

---
## Addendum B (19 Nov 2026) — add LaFe2Si2, LaFeSi, LaFeSi2 as fitted stoichiometric phases ("last chance")
Written **before** the run. Only equilibrium counts were looked at, no losses.

**Model change.** Three stoichiometric compounds (La)(Fe)(Si) with site counts 1:2:2, 1:1:1, 1:1:2 are added to
the TDB. Their energies are *not* from any assessment (Feng's τ3–τ6 could not be reconstructed); they are
**effective, fitted** parameters: G = ΣGHSER + n·(−30 kJ + 1000·w + 10·v·T) per formula unit, n = atoms per
formula unit; −30 kJ/mol-atom is a frozen prior of the right order (τ1 ≈ −21, La silicides ≈ −35 kJ/mol-atom),
w in kJ/mol-atom, v in 10 J/mol-atom/K. Their structures and Niitsu's label identities are as in `phase_registry.csv`.

**Free parameters (12):** w,v for each of the 3 new phases; the 6 τ1/τ2 constants (as in Addendum A).
**Regulariser:** `regularization_weight: 100` on all w,v (one value, no sweep). Lr 0.1, 1000 epochs, seed 42, latent_mu_lr 100.

**Data.** Same rule as before (an equilibrium is used only if all its phases exist in the TDB); the new phases
make 30 train (was 17) and 17 held-out 1373 K (was 7) equilibria usable. Still excluded: LaSi2a1/a2,
LaFexSi2-x (AlB2), n.d. (24 equilibria). New phases enter with blank composition.

**Baseline for C1/C2** = the *prior model*: new phases at the −30 kJ prior (w = v = 0), τ1/τ2 as published,
parameters frozen (lr 1e-9), same μ′ settings, on the same train/held-out sets. (The original TDB cannot
evaluate these equilibria.)

**Acceptance (all required):**
- C1 train data loss ≤ 90 % of the prior baseline. C2 held-out 1373 K loss ≤ 105 % of the prior baseline.
- C3 at La(Fe11.5Si1.5), 1373 K τ1 phase fraction ≥ 0.9; A5 window along La(Fe1−xSix)13 still overlaps 0.096–0.229;
  descriptor D > 0 at all 15 points.
- C4 |w| ≤ 20, |v| ≤ 1; each new phase's fitted formation energy at 1373 K between −80 and 0 kJ/mol-atom
  (formation energy = (G − ΣGHSER)/n, from the fitted parameters).
- Beyond the gate, reported: the fitted τ1/τ2 changes, fitted new-phase energies, and which equilibria stay
  worst-fitted. An accepted outcome means "τ1/τ2 refit supported *given* fitted competing phases" — the new
  phase energies are effective, not assessed, and are not to be used as thermodynamic data without validation.

---
## Addendum C (19 Nov 2026) — per-equilibrium residual analysis (decides whether further refit effort is justified)
Fixed **before** any residual was computed. For every usable Niitsu equilibrium (47 with Addendum B's phases;
24 for the original TDB), compute the equilibrium at the alloy's *nominal* composition and temperature and compare with the measured tie-line:
- **phase-set match:** calculated phases (NP > 1e-3) equal the measured set → else the point is an **outlier of kind "phase set"**.
- **composition residual** for matched solution/τ phases (BCC_A2, FCC_A1, LIQUID, TAU1, TAU2): ΔSi and ΔLa in at.% (calc − exp).
  **Reproduced within scatter** = phase set matches and every |ΔSi| ≤ 2.0 at.% and |ΔLa| ≤ 1.0 at.% (a stated, generous
  EPMA-scatter band; Niitsu's own tie-line spread between repeat anneals is of that order).
- **Systematic residual:** mean signed ΔSi of TAU1 and TAU2 (a) over all points, (b) per temperature; a shift is called
  systematic if |mean| > 1.0 at.% and the sign is the same in ≥ 75 % of the points.
- Models compared: Feng-reconstructed baseline (24 equilibria it can evaluate); Addendum B prior model and fitted model (47).
Decision rule: further refit effort is justified only if the fitted model reproduces ≥ 10 percentage points more of the
points within scatter than its baseline **and** passes Addendum B's C1–C4. Otherwise: freeze the reconstructed Feng
description as "best available given the public data".

---
## Addendum D (20 Nov 2026) — does the τ1 temperature-dependence bias matter for the WP4b descriptor?
Question raised after Addendum B/C: the residual analysis found calc − exp ΔSi(τ1) = +4.9 at.% at 1173 K and −2.1 at.% at 1573 K.
**Disclosure (seen before this plan):** the Addendum-C residual tables, including for the Feng baseline M0 the τ1/τ2 rows of
Niitsu Table 7 (1273/1423/1473/1523 K: ΔSi(τ1) +1.9/+0.4/−0.4/−0.9, ΔSi(τ2) +1.5/+0.3/−0.1/−0.5 at.%) and Niitsu's stated
single-phase ranges (τ1: x = 0.086–0.211 at 1173 K, 0.096–0.229 at 1373 K, 0.162–0.279 at 1573 K; τ2 0.251–0.398, 0.266–0.402,
0.291–0.376). The new calculation below has not been run.
**Model:** M0 = the Feng-reconstructed baseline that the WP4b descriptor uses (`results_addD/M0_feng_baseline_eq.tdb`), nothing fitted.
**Calculation:** for T = 1173, 1273, 1323, 1373, 1423, 1473, 1523, 1573 K along La(Fe1−ySiy)13 (La = 1/14), y = 0…0.45 step 0.005: the
τ1-single-phase range (τ1 fraction ≥ 0.98) and τ2 range; compare with Niitsu's ranges (measured at 1173, 1373, 1573 K; between those
temperatures the experimental boundary is linearly interpolated, labelled interpolation). Boundary bias δy = calc − exp, lower and upper boundary.
**Descriptor sensitivity:** D(x,T) (the WP4b definition, x = 1.2…2.0 Si per La(Fe13−xSix), 1323/1423/1473 K, M0). dD/dy by finite difference
of D along x (y = x/13), then estimated ΔD = (dD/dy) · δy_lower-boundary (the Si-poor edge is the nearest one to the descriptor compositions y = 0.092–0.154).
**Rule:** the bias is called *material for the descriptor* at a point if |ΔD| > 0.25·D there, *not material* if ≤ 0.10·D, otherwise *borderline*. Applied per temperature, reported either way. Estimates, not recomputed descriptors.

---
## Addendum E (20 Nov 2026) — is the flat τ1 window a binary-choice effect? (20-combination sensitivity check, one page)
Scope fixed by the user: a diagnostic of the reconstruction, **not** an ensemble of La–Fe–Si, no refit, no new τ1/τ2 parameters (Feng's τ1/τ2 parameters are identical in all combinations).
**Combinations:** the 20 of the WP4 band (`wp4b_descriptor.py`): FeLa {09Pov, 23Su} × LaSi {10Zho, 20Xu} × FeSi {12Ohn, 14Yua, 17Cui, 23Wit, 91Lac-LB}, merged with `build_merged_tdb_fixed.build` (SGTE_BINARY_DIR=…/sgte_binary). Combinations that fail to build or compute are counted and reported, not dropped silently.
**Calculation:** per combination and T = 1173, 1373, 1573 K, equilibrium along La(Fe1−ySiy)13 (La = 1/14), y = 0.060…0.300 step 0.005 (same τ1-single-phase criterion, τ1 fraction ≥ 0.98, same pdens 800 as for M0): Si-poor boundary y_lo(T), Si-rich boundary y_hi(T), width. Check: the M0 combination (23Su + 10Zho + 17Cui) must reproduce the M0 boundaries (0.090/0.235, 0.085/0.235, 0.085/0.240) within 0.005, else the run is invalid (fault rule: fix script/environment and repeat).
**Classification (per combination), shift s = y_lo(1573 K) − y_lo(1173 K)** (measured: +0.076; M0: −0.005): **flat** if |s| ≤ 0.01; **temperature-dependent** if s ≥ 0.04 (about half the measured shift); otherwise **intermediate**; s ≤ −0.01 is **reversed**.
**Decision for the sentence in the limitation statement:** with N = number of flat combinations of those that computed (n): N/n ≥ 0.90 → "the flat window is not a binary-choice effect (it comes with the Feng τ parameters)"; N/n ≤ 0.10 → "the flat window is specific to the M0 binary choice"; otherwise "the flatness is partly a binary-choice effect". Also reported (no rule): range of y_lo(1373 K) and of the window width across the combinations, and whether any combination reproduces the measured shift (s ≥ 0.04).
**Disclosure:** M0 values (above) known; no other combination computed before this plan.
