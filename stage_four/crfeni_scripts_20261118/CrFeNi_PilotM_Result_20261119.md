# Cr–Fe–Ni Pilot-M — result (19 Nov 2026): negative gate (G3)

**Outcome: gate failed on G3. The class analysis was not run (the script refuses). Recorded as "σ stabilisation not informative for the class question in this system". No rescue, no re-gating.**

## 1. Procedure followed
Pre-registration FROZEN 19 Nov (`CrFeNi_PilotM_PreReg_FROZEN_20261119.md`), hashes in `CrFeNi_PilotM_Freeze_Record_20261119.md`. The user compared the sha256 of the note and all scripts on the running machine (all matched) **before** the first run. Run by the user on 19 Nov (pycalphad 0.11.2, numpy 2.5.3), steps 1–4 once, in order, no partial reruns. No stated deviation from the pre-registration.

## 2. Result
| Gate | Result | Criterion | Pass |
|---|---|---|---|
| G1 survival (rule v2) | 81 of 288 (28 %) | ≥ 60 | yes |
| G2 coverage, best file per class A/B/C | 15 / 15 / 17 survivors | ≥ 5 each | yes |
| G3 σ visible, 900 K | 0 of 81 with S > 0.05 kJ/mol-atom | ≥ 80 % | **no** |

Observable stage: 81 survivors × 3 temperatures = 243 rows, 0 failed points, run valid. Lineage combinations with a survivor: 44 of 140 (sensitivity).

## 3. Is it a result or a fault? (checked before recording)
Read-only summary of `sigma_S.csv` (user's output):
- σ present in the equilibrium at x\* in only 4 of 81 survivors at 900 K, 2 of 81 at 800 K, 0 of 81 at 1000 K; in those cases S is positive but ≤ 5·10⁻⁵ kJ/mol-atom. So the suspension mechanically works; σ is simply not stable there.
- G_with = G_without (identical to the printed digits) per Cr–Fe file; S_raw ≥ −0.0096 at 800 K, inside the 0.05 noise floor (26 of 81 clipped at 800 K, 1 at 900 K, 8 at 1000 K).
- Same picture for all five Cr–Fe files and all three σ conventions (classes A, B, C).
No sign of a script or environment fault, so the fault rule does not apply and the failure stands.

## 4. What it means (and does not)
In the merged databases of this file set, the σ phase is not stable at (Cr 0.45, Fe 0.45, Ni 0.10) at 800–1000 K for any Cr–Fe description, so σ stabilisation energy at this composition cannot discriminate between sublattice conventions. This says nothing about whether the convention matters elsewhere in composition–temperature space (e.g. nearer the Cr–Fe σ field without Ni, or lower temperature). The question "does the σ convention matter" is **unanswered**, not answered "no".
Pre-registered prior expectation ("matters", with a moderate chance of "inconclusive") was not borne out; the possibility of a G1 failure was foreseen, G3 failure was not. Stated plainly.

## 5. Post-hoc, optional (not part of the gate, not to change it)
Which phases are in equilibrium at x\*, 900 K (probably bcc and/or fcc), and whether σ is stable on the Cr–Fe binary of each file at the same T. Only worth doing if it is wanted for the README/talk; labelled post-hoc if done. Any new composition or temperature would be a **new** pre-registration, not a rescue. **Registered 19 Nov as the future experiment Pilot-M2** (own scoping note, pre-registration, freeze and hash; planned after the loop worked example; design rules in `Stage4_Finish_Plan_v1_3_20261119.md` §2). L010 stays a negative gate whatever M2 finds.

## 6. Status
Ledger L010 (test of the stop rule, flag fail). Cr–Fe–Ni closed. Stage 4 time box for the methods pilot not exceeded (about one day instead of 2–3).

## 7. Post-hoc addendum (19 Nov, 11:54; run by the user on the environment of record; POST-HOC, does not change the gate)
Questions Q1–Q3 were fixed before the run (script `crfeni_posthoc_diag.py`). DF = driving force of σ (kJ/mol-atom): 0 or ≈ 0 means σ is in the equilibrium (borderline), negative = distance from stability. DF values within about 0.01 are limited by the energy-grid resolution (pdens 2000) and are best read as borderline.

**Q1 phases at x\* (81 survivors).** 900 K: BCC_A2+FCC_A1 71, BCC_A2+L12_FCC 6, BCC_A2+FCC_A1+SIGMA_D8B 4. 800 K: 74 / 6 / 1. 1000 K: 75 / 6 / 0. So at x\* the equilibrium is bcc + fcc (or bcc + ordered L1₂); σ appears in only 5 point-sets of 243.

**Q2 distance of σ from stability at x\*.** Median DF by Cr–Fe file at 900 K: 18Jac −0.013, 20Ost −0.037, 21Laf −0.017, 23Zha −0.016, 87And-LB −0.104 kJ/mol-atom (range −0.002 to −0.19). At 800 K −0.06 to −0.12, at 1000 K −0.22 to −0.30. So σ is close to stability at 900 K for four of the five Cr–Fe files, most remote for 87And-LB, and further away at 800 K and still further at 1000 K.

**Q3 σ on the Cr–Fe binary.** In all six source files σ is in the equilibrium at x(Cr) = 0.45 and 0.50 at 800, 900 and 1000 K (DF ≈ 0; 21Laf, 18Jac, 20Ost, 23Zha within −0.03 of 0). At 700 K σ is absent in all six (bcc only, DF −0.02 to −0.50; the identical DF at 0.45 and 0.50 suggests a bcc miscibility-gap equilibrium, not looked into). So σ is not missing on the edge; adding 10 at.% Ni (which brings in fcc) is what takes it out of the equilibrium.

**Reading.** (a) The gate result is a real property of x\*: Ni at 10 at.% makes bcc + fcc the stable pair and σ lies a few to a few tens of J/mol-atom above it. (b) **A design lesson for the observable, stated plainly:** where σ *is* in the equilibrium the largest S seen is 5·10⁻⁵ kJ/mol-atom, and even on the Cr–Fe binary σ sits at the tangent (DF ≈ 0) rather than far below it. σ stabilisation energy relative to the competing phases is therefore intrinsically small here, comparable to or below the pre-registered noise floor (0.05 kJ/mol-atom, G3). A different composition alone may not make G3 satisfiable; S as defined may need to be reconsidered for Pilot-M2 (e.g. σ phase fraction or the σ/bcc boundary temperature). This was not known when the gate was written and does not alter L010.
