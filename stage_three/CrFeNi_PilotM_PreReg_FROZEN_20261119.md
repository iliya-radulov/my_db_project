# Cr–Fe–Ni Pilot-M — pre-registration FROZEN (19 Nov 2026; content of rc2 of 18 Nov plus the two edits listed below)

**Status: FROZEN on 19 Nov 2026. All five decisions of the scoping note confirmed by the user on 18 Nov 17:22; G2 ≥ 5 confirmed by the user on 18 Nov 18:50.** sha256 of this note and of the five scripts is recorded in the decision note and shown to the user **before** the first run. Done before the freeze (stated now so it can be checked): only file-level text and header reading and the audit v2 output (flags per file); **no merge, no edge check, no equilibrium or any computed value for Cr–Fe–Ni**. Scripts are tested on other systems only (Al–Fe–Mn, synthetic data).

**Changes rc1 → rc2** (all before the freeze, none after seeing any result):
1. Scripts written and tested; a fifth file `crfeni_defs.py` (classes, lineages, all gate and decision numbers in one place) is added to the hash list.
2. The unary check (§4.1) is built into `crfeni_edge_check.py` (stops with exit code 4 before any calculation), instead of a separate step.
3. **Rule v3 sensitivity (rc1 §4.6) is dropped:** the edge-check script does not implement rule v3. Sensitivities are 800/1000 K and lineage-balanced medians only.
4. G2 wording **≥ 5** survivors: the user had said "more than 5" (17:22) and confirmed ≥ 5 on 18 Nov 18:50 (the criterion is: at least one Cr–Fe file per class with ≥ 5 survivors, not every file). One number in `crfeni_defs.py` (`G2_MIN_SURVIVORS_PER_FILE`); it is also the file threshold used for N in §4.5.

**Edits at the freeze (19 Nov), no result seen:** status line and G2 confirmation only; no number, file set or script changed.

## 1. Question and nature of the pilot
Does the σ sublattice convention on the Cr–Fe edge (Class A / B / C) shift the derived quantity S by more than the spread caused by the Cr–Ni and Fe–Ni choices? A methods question about the sensitivity of ensemble results to sublattice conventions; **not** a Cr–Fe–Ni validation, **not** the Nd–Fe–B threshold, no property data involved (no ledger "test of a descriptor"; ledger kind `evaluation`/`test` of the stop rule, entered either way).

## 2. Observable (fixed)
S = [G_eq(σ suspended) − G_eq(σ allowed)] / 1000, kJ/mol-atom, at **x\* = (Cr 0.45, Fe 0.45, Ni 0.10)** and **T = 900 K** (user, 17:22: single primary temperature, no post hoc temperature shopping). 800 K and 1000 K: labelled sensitivity only. G_eq = equilibrium Gibbs energy per mole of atoms (pycalphad `GM`), P = 101325 Pa, phase set = all phases of the merged database except: σ suspended = additionally `SIGMA_D8B`; σ allowed = `SIGMA_D8B` kept. `SIGMA_OLD` and `HIGH_SIGMA` (CrFe-87And-LB) are excluded from **both** calculations. Reference state: GHSER. No Cr–Ni or Fe–Ni file carries σ (by file selection and audit), so σ always comes from the Cr–Fe file.
Numerical rules: direct equilibrium; if it does not converge, fallback = leave out one phase at a time, take the lowest converged energy (σ is never left out in the "allowed" calculation). S_raw in [−0.05, 0) → S = 0 (status "clipped"). S_raw < −0.05 → both energies recomputed with the leave-one-out minimum; if still < −0.05 or non-finite → "failed" (row kept, value empty, reported, not dropped). Output must hold exactly survivors × 3 rows, otherwise exit code 3.

## 3. File set (fixed; user confirmed 17:22)
- **Cr–Fe (6):** Class A: 82Her, 87And-LB; Class B: 21Laf; Class C: 18Jac, 20Ost, 23Zha. Excluded: **CrFe-11Xio** (header "Not very compatible with anything. New Fe from 01Che, new magnetic models"; audit v2: its `GHSERFE` differs). **Limit: Class B has a single file (21Laf); a class effect for B cannot be separated from a file effect.**
- **Cr–Ni (4):** 06Hal, 16Tan, 86Din, 92Lee-LB. Excluded: 20Zha and 24Per (carry σ), 21Hao-3g (third generation; GHSERCR/GHSERNI differ).
- **Fe–Ni (12, all):** 00Ans-2SL, 00Ans-4SL, 03Dup-LB, 03Dup-mod, 10Cac, 11Xio, 19Ohn, 23Jac, 23Wit, 23Zha, 85Xin, 95Ans. The edge check decides.
- **Raw combinations: 6 × 4 × 12 = 288** (48 per Cr–Fe file). Full set, no a-priori reduction.
- Exclusion rule in general: exclude only if the common reference function (GHSER) differs or the file carries σ on an edge that must be σ-free. A differing non-ground lattice stability (e.g. 82Her: "pre-SGTE lattice stability used for fcc-Cr") is not a reason to exclude; the edge check decides. 82Her is a known risk.
- **Lineages** (header rule: "based on"/"modified from", or the same author-year tag with suffix variants; judgement from header text, not parameter comparison): Cr–Fe 5: Her82, And87, Laf21, Jac18 (18Jac + 20Ost), Zha23. Cr–Ni 4: Hal06, Tan16, Din86, Lee92. Fe–Ni 7: Ans95; Ans00 (2SL, 4SL); Dup03 (LB, mod); Xin85 (85Xin + 23Jac); Cac10 (10Cac + 23Wit + 23Zha); Xio11; Ohn19. 5 × 4 × 7 = 140 lineage combinations (sensitivity). Encoded in `crfeni_defs.py`.

## 4. Procedure and gate (fixed)
1. **Unary pre-check** (inside `crfeni_edge_check.py`): FUNCTION GHSERCR/GHSERFE/GHSERNI must be textually identical in all 22 files that contain the element; otherwise exit code 4 before any calculation, run stops for a decision. (Text-level check on the 22 real files already done: identical.)
2. **Edge check**: rule v2 (phase-name + energy comparison on binary edges, tolerance 1 J/mol, MAX_UNVERIFIED 2, fallback solver). A combination that fails to merge or whose calculation fails counts as not surviving and is logged.
3. **Observable** S for every survivor (§2).
4. **Gate**, applied once, before any class analysis (`crfeni_gate.py`):
   - **G1 survival:** ≥ 60 of 288 raw combinations pass rule v2 (≈ 21 %). A-priori number.
   - **G2 coverage:** each class (A, B, C) has ≥ 1 Cr–Fe file with ≥ 5 surviving combinations (see rc2 change 4).
   - **G3 σ visible:** S > 0.05 kJ/mol-atom at 900 K in ≥ 80 % of the survivors with a valid S. **Run validity (not a gate):** edge_check.csv has 288 rows, sigma_S.csv has 3 × survivors rows, ≥ 80 % of the survivors have a valid S at 900 K; otherwise INVALID RUN, exit code 3, fault rule (script/environment faults → fix or pin, qualify, repeat the whole run; file-caused failures stay failures).
   - If any gate fails: record "σ stabilisation not informative for the class question in this system", close, ledger entry (negative gate). No rescue. The analysis script refuses to run.
5. **Class analysis** (`crfeni_analysis.py`, only if the gate passes): class medians of S over valid surviving raw combinations at 900 K. Class effect **C** = max − min of the three class medians. Noise **N** = median over Cr–Fe files with ≥ 5 survivors of the within-file IQR of S; N_eff = max(N, 0.05). **C ≥ 2·N_eff → "convention matters"; C ≤ N_eff → "does not matter"; otherwise "inconclusive".** Secondary (no pass/fail): η² of S for Cr–Fe, Cr–Ni, Fe–Ni file.
6. **Sensitivities (labelled, cannot change the verdict):** 800 K and 1000 K; lineage-balanced class medians (median of per-lineage-combination medians). Rule v3: not implemented (rc2 change 3).

## 5. Prior expectation (written before any computation)
Class C files differ among themselves (20Ost header: "the sigma phase field is much more narrow"), and the class medians separate: I expect "matters", with a moderate chance of "inconclusive" because Class B has one file and Class A two. A low survival (G1) is possible (82Her, Fe–Ni ordering descriptions). Any outcome is recorded.

## 6. Scripts and environment (to be hashed at the freeze)
- `crfeni_defs.py`, `crfeni_edge_check.py`, `crfeni_sigma.py`, `crfeni_gate.py`, `crfeni_analysis.py`; `tdb_merge.py` (Track A, unchanged, importable) is not modified.
- Environment of record: user's machine, pycalphad 0.11.2, numpy 2.5.3. The analysis is deterministic; no seed.
- **Tests done before the freeze (no Cr–Fe–Ni computation):** unary pre-check on the real 22 files (text level) and on two known-bad Al–Fe–Mn/Cr–Fe files (detected); `crfeni_sigma.py` on 6 Al–Fe–Mn survivors with AL8MN5_D810 in the σ role (18 rows, 0 failed), independent plain-pycalphad cross-check on 3 combinations (exact), simulated failure paths (fallback, all-fail, persistent bias, transient miss); `crfeni_gate.py` and `crfeni_analysis.py` on synthetic data (planted class effect → pass / MATTERS; null → not MATTERS; flat → G3 fail; low survival → G1 fail; class B uncovered → G2 fail; too many failed S → invalid run exit 3; truncated edge check → exit 3; analysis refuses without a passed gate); smoke test of `crfeni_edge_check.py --system alfemn_2g` on 3 combinations (all PASS, identical to the validation run). **Consistency check 19 Nov (names only, no computation):** the file lists in `crfeni_edge_check.py` equal the keys of the lineage and class tables in `crfeni_defs.py` (6/4/12 files, 288 combinations, 5/4/7 lineages); all 22 TDB files exist. **Not done in this container:** the full 78/144 reproduction with the final script (done earlier on the user's machine with the Ni–Mn–Sn sibling script; the Cr–Fe–Ni script keeps rule v2 unchanged). Optional before the run: repeat it with `crfeni_edge_check.py --system alfemn_2g`.
- Freeze procedure (done 19 Nov): file renamed FROZEN, sha256 of this note and of the five scripts written to the decision note and to `.sha256` files **before** the first run; the run starts only after the user has seen the hashes.

## 7. Limits
Single composition and temperature; one observable; Class B n = 1 (Class A n = 2); σ modelled by one edge only, by design; model-sensitivity result, not a prediction of any measurement; solver noise floor O(10–50 J/mol); exclusions and lineages are judgements from file headers; Fe–Ni survival may be low; no full ternary assessment is used.
