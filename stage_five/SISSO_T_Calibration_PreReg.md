# SISSO Temperature-Calibration Study — Pre-registration Note

Contract version: 1.5 (Option C, final freeze) · Date: 25 November 2026, completed 26 November 2026  
Status: Ready to hash. No SISSO value for any of the nine compounds has been computed. One earlier SISSO result exists, for the held-out Nd₂Fe₁₄B (23 Nov, not frozen; see Section 1 and Section 9). The CALPHAD-side check of 26 Nov (`--check-calphad`, no SISSO) was run before this freeze; it fixed nothing that was not already in the 25 Nov draft (68 points).

## 1. Purpose

Quantify the temperature dependence of the Bartel SISSO formation-energy correction (`pymatgen` `GibbsComputedStructureEntry`) on a chemically diverse set of experimentally stable binary intermetallics, motivated by the large positive slope observed on held-out Nd₂Fe₁₄B (~+15 J mol⁻¹ atom⁻¹ K⁻¹). That slope was known before this study and is the reason for it; it is not a prediction made in advance. Nd₂Fe₁₄B is not part of this study (not in the fit set, not in the decision rule); see Section 7. Decide whether a simple global linear temperature correction should be applied in later Stage-5 releases or whether SISSO should remain uncorrected.

## 2. Software, database, and provenance

- **Materials Project API:** `mp-api` (version recorded in `freeze_manifest.json` and in the results file), MP database release `2026.09.28` as of the entry search. The SISSO side queries the live database; the script records the database release, the chemical system, every entry seen (id, formula, number of atoms, corrected and uncorrected energy per atom) and the chosen candidate in the results file, because a hash cannot cover a live database.
- **SISSO / `g_els` source:** `pymatgen 2026.5.4` (`pymatgen/analysis/compatibility/data/g_els.json`); verified that `GibbsComputedStructureEntry` uses linear `scipy.interpolate.interp1d` between 100 K knots at `1375 K` and `1450 K`.
- **CALPHAD engine:** `pycalphad 0.11.2` (version of record, enforced by the script: refusal in `--run` if different; 0.12.0 changes ordered/disordered label ties); canonical unary reference check against `unary50.tdb`.
- **Hashed files** (`freeze_manifest.json`, sha256): this note, `sisso_t_calibration.py`, the nine TDB files of Section 3, `unary50.tdb`, `g_els.json` (pymatgen ships two byte-identical copies; the script refuses if they differ), `dft_sisso_predictor.py`, `prototype_match.py`, and the package versions. `--run` refuses when a hash differs from the manifest.
- **Selection rule for TDB files:** for each system a fixed preference list of available assessments was written before any SISSO value was computed; the first file that loads without error in `pycalphad 0.11.2` is used. The file used for each compound is the one named in Section 3. For Fe–Si, two earlier choices failed to load (footnote 1), which is how `FeSi-14Yua.tdb` came to be used and decided the Fe₃Si model class (Section 9).
- **Magnetic classification rule:** `is_magnetic` in MP `2026.09.28` returns `False` (`ordering = Unknown`) for ferromagnetic Fe intermetallics carrying large moments. Magnetic status is therefore recorded from `total_magnetization / nsites` retrieved directly from `SummaryDoc`.
- **Clean MP entry rule:** Ordered stoichiometric ground state (`occ = full`, `theo = False`) with `energy_above_hull == 0.0000 eV/atom` (`stable = True`) in MP `2026.09.28`.

## 3. Primary compound set (fit set)

All 9 accepted compounds sit strictly on the 0 K DFT convex hull (`E_hull = 0.0000 eV/atom`), span 9 independent binary systems (2 magnetic, 7 non-magnetic), and exclude the held-out Nd–Fe–B system. Because the fit set contains 9 compounds across 9 binary families, the small-set lower-bound headline clause (≤ 4 compounds / ≤ 3 families) does not fire.

| # | Compound | Structure (SG) | MP ID | E_hull (eV/atom) | Magnetic (`Mtot/nsites`) | Named TDB & Assessment (DOI) | Equil. phase in TDB | Grid points (≥ 3 required) |
|---|---|---|---|---:|---|---|---|---|
| 1 | Fe₃Si | D0₃ (Fm-3m) | mp-2199 | 0.0000 | Yes (`1.672 μ_B/atom`, 4 sites) | `FeSi-14Yua.tdb` — Yuan, Pan, Li & Watson (2014), *Calphad* 44, 54–61 (`10.1016/j.calphad.2013.07.007`)¹ | `B2_BCC` | 7/8 (`800–1450 K`; `LIQUID` at 1600 K) |
| 2 | Fe₂B | C16 (I4/mcm) | mp-1915 | 0.0000 | Yes (`1.550 μ_B/atom`, 6 sites) | `FeB-02Rom.tdb` — Van Rompaey, Hari Kumar & Wollants (2002), *J. Alloys Compd.* 334, 173–181 (`10.1016/S0925-8388(01)01777-7`) | `M2B_C16` | 8/8 (`800–1600 K`) |
| 3 | CoSi | B20 (P2₁3) | mp-7577 | 0.0000 | No (`0.000`) | `CoSi-06Zha.tdb` — Zhang, Du, Xu & Pan (2006), *Calphad* 30, 470–481 (`10.1016/j.calphad.2006.06.001`) | `COSI_B20` | 8/8 (`800–1600 K`) |
| 4 | TiB₂ | C32 (P6/mmm) | mp-1145 | 0.0000 | No (`0.000`) | `TiB-04Ma.tdb` — Ma, Li, Du & Zhang (2004), *J. Alloys Compd.* (`10.1016/j.jallcom.2003.09.017`) | `TIB2_C32` | 8/8 (`800–1600 K`) |
| 5 | LaB₆ | D2₁ (Pm-3m) | mp-2680 | 0.0000 | No (`0.000`) | `LaB-13Tan.tdb` — Tang et al. (2013), *J. Phase Equilib. Diffus.* 34, 297–306 (`10.1007/s11669-013-0231-4`) | `LAB6_D21` | 8/8 (`800–1600 K`) |
| 6 | NiAl | B2 (Pm-3m) | mp-1487 | 0.0000 | No (`0.000`) | `AlNi-01Dup-4sl.tdb` — Dupin, Ansara & Sundman (2001), *Calphad* 25, 279–298 (`10.1016/S0364-5916(01)00049-9`) | `B2_BCC` | 8/8 (`800–1600 K`) |
| 7 | YAl₂ | C15 (Fd-3m) | mp-2322 | 0.0000 | No (`0.000`) | `AlY-95Gro-LB.tdb` — Gröbner, Lukas & Aldinger (1995), *J. Alloys Compd.* 220, 8–12 (`10.1016/0925-8388(94)06028-2`) | `AL2Y_C15` | 8/8 (`800–1600 K`) |
| 8 | Ti₅Si₃ | D8₈ (P6₃/mcm) | mp-2108 | 0.0000 | No (`0.000`) | `SiTi-96Sei-LB.tdb` — Seifert, Lukas & Petzow (1996), *Z. Metallkd.* 87, 2–13 (`10.1515/ijmr-1996-870102`) | `SI3TI5_D88` | 8/8 (`800–1600 K`) |
| 9 | Mg₂Si | C1 (Fm-3m) | mp-1367 | 0.0000 | No (`0.000`) | `MgSi-04Kev.tdb` — Kevorkov, Schmid-Fetzer & Zhang (2004), *J. Phase Equilib. Diffus.* 25, 140–151 (`10.1007/s11669-004-0007-y`) | `MG2SI_C1` | 5/8 (`800–1300 K`; `LIQUID` at 1375–1600 K) |

¹ *`FeSi-12Ohn.tdb` and `FeSi-17Cui.tdb` fail `pycalphad 0.11.2` (`ValueError: Order (BCC_4SL) and disordered (A2_BCC) model must have the same interstitial to sublattice ratios. 1.0 != 3.0`). `FeSi-14Yua.tdb` is used instead; its ordered bcc phase at `x_Si = 0.25` is modeled via 2-sublattice `B2_BCC` through `1450 K`.*

Total evaluation points: **68** compound–temperature pairs across 9 compounds (Fe₃Si 7, Mg₂Si 5, the other seven 8 each: 7 + 5 + 56).

**Retention rule (checked by the script at every grid point):** the expected phase must be present with phase fraction **≥ 0.999** and the equilibrium must contain nothing else above that tolerance; otherwise the point is dropped. A compound needs at least 3 retained points. Result of the 26 Nov CALPHAD check: all 68 retained points have phase fraction 1.000000; the rejected points are Fe₃Si at 1600 K and Mg₂Si at 1375, 1450 and 1600 K (all `LIQUID`). Highest retained / first rejected grid temperature: Fe₃Si 1450 K / 1600 K; Mg₂Si 1300 K / 1375 K; the other seven compounds keep the whole grid (no rejection up to 1600 K). Retention is decided on the grid only; no finer temperature scan enters the study.

### Excluded candidates (MP `2026.09.28` provenance)

| Compound | MP ID | E_hull (eV/atom) | Reason for exclusion |
|---|---|---:|---|
| Cr₂Nb | mp-548 | 0.1548 | Off 0 K convex hull (`stable = False`) |
| MnSi | mp-1431 | 0.0159 | Off 0 K convex hull (≈ 1.5 kJ/mol-atom; equals decision threshold) |
| Fe₂Si | mp-22787 | 0.0283 | Off 0 K convex hull; high-T-only phase |
| AlFe | mp-2658 | 0.0922 | Off 0 K convex hull (≈ 8.9 kJ/mol-atom) |
| Al₅Fe₂ | none | — | Partial occupancy; no clean MP entry |

## 4. Temperature grid

Stage-5 grid: `800, 1000, 1100, 1200, 1300, 1375, 1450, 1600 K` (8 points). Each compound is evaluated only on the grid points where the retention rule above is met in its named TDB (column 9 above). Reference temperature of the correction: `T₀ = 800 K`.

## 5. Quantities and SER-axis treatment (Option C — fixed before any calculation)

Because `pymatgen`'s `g_els` follows each element's lowest-Gibbs-energy phase at temperature $T$ (including `G_mag` and melting above $T_m$), while SGTE bare `GHSER` is a fixed solid-phase non-magnetic lattice function, bare `GHSER` cannot be compared directly against `g_els`.

Pre-hash verification against `unary50.tdb` showed that comparing `g_els(T)` against **`pycalphad` equilibrium pure-element `GM_eq(el, T)`** (lowest-G condensed phase including `G_mag`, with `BETA_RHOMBO_B` for B) eliminates both phase-transition offsets and the Fe (−1.94 kJ/mol) / Co (−3.10 kJ/mol) magnetic offsets completely (`0.00 kJ/mol` residual for Fe, Si, Co, La, Ni, Mg ≤ 1300 K, and Nd).

Therefore, for every compound $c$ and retained temperature $T$:
- **$\Delta G_{\text{SISSO}}(T)$:** From the existing Stage-5 pipeline (`GibbsComputedStructureEntry`, relative to `g_els`).
- **$\Delta G_{\text{CALPHAD}}(T)$:** Computed directly in the compound's named TDB as:
  $$\Delta G_{\text{CALPHAD}}(T) = G_{\text{eq}}(\text{compound}, T) - \sum_i x_i \, G_{\text{eq}}(\text{element } i, T)$$
  where $G_{\text{eq}}(\text{element } i, T)$ is the lowest-G condensed equilibrium phase of pure element $i$ (including `G_mag`; `BETA_RHOMBO_B` for B) at temperature $T$.
- **$\text{Residual}(T) = \Delta G_{\text{SISSO}}(T) - \Delta G_{\text{CALPHAD}}(T)$** (kJ mol⁻¹ atom⁻¹).
- **Linear slope:** Ordinary least-squares slope of $\text{Residual}(T)$ vs $T$ (J mol⁻¹ atom⁻¹ K⁻¹) over the compound's retained grid points.

The small residual differences between FactSage `g_els` and SGTE `unary50.tdb` `GM_eq` (table below, ≤ 0.57 kJ/mol across all fit elements on their active grids) are recorded as fixed reference-table noise and are **not** further adjusted. The script computes the element `GM_eq` in each compound's own TDB; the 26 Nov check found `GM_eq(TDB) − GM_eq(unary50) = 0.000 kJ/mol` for every element in all nine files, so the table below describes the reference actually used. For boron the equilibrium is restricted to `BETA_RHOMBO_B` in the script.

### Verified reference-axis residual: `g_els(T) − GM_eq_unary50(T)` [kJ/mol]

| Element | 800 K | 1000 K | 1100 K | 1200 K | 1300 K | 1375 K | 1450 K | 1600 K | Eq condensed phases (800–1600 K) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Fe | -0.00 | -0.00 | +0.10 | -0.00 | -0.00 | -0.02 | -0.03 | -0.00 | BCC_A2, FCC_A1 |
| Si | -0.01 | -0.01 | -0.01 | -0.01 | -0.01 | -0.03 | -0.04 | -0.01 | DIAMOND_A4 |
| B² | +0.06 | +0.06 | +0.06 | +0.06 | +0.06 | +0.05 | +0.04 | +0.07 | BETA_RHOMBO_B |
| Co | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | -0.04 | -0.04 | -0.00 | FCC_A1 |
| Ti | +0.00 | +0.09 | +0.16 | +0.25 | +0.31 | +0.32 | +0.36 | +0.47 | HCP_A3, BCC_A2 |
| La | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | -0.02 | -0.03 | -0.00 | FCC_A1, LIQUID |
| Ni | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | -0.02 | -0.03 | -0.00 | FCC_A1 |
| Al | +0.04 | +0.08 | +0.10 | +0.12 | +0.15 | +0.14 | +0.15 | +0.21 | FCC_A1, LIQUID |
| Y | +0.27 | +0.33 | +0.37 | +0.40 | +0.44 | +0.44 | +0.47 | +0.57 | HCP_A3 |
| Mg³ | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | (-2.29) | (-7.68) | (-21.46) | HCP_A3, LIQUID (gas > 1363 K in `g_els`) |
| Nd (held-out) | +0.00 | -0.00 | -0.00 | -0.00 | -0.00 | -0.03 | -0.04 | -0.00 | DHCP, BCC_A2, LIQUID |

² *For B, `unary50.tdb` places `ALPHA_RHOMBO_B` slightly below `BETA_RHOMBO_B` below ~1375 K (`+0.81` to `+0.07 kJ/mol`); `g_els` and the boride TDBs reference `BETA_RHOMBO_B` (`GHSERB`), where the residual is flat at `+0.04` to `+0.07 kJ/mol`.*  
³ *`Mg₂Si` melts between `1300 K` and `1375 K`, so Mg is evaluated only on `800–1300 K` where `g_els − GM_eq = 0.00 kJ/mol` and Mg remains condensed. The gas branch of `g_els` is never used in this study.*

**Notes on the table.**
- **Ti:** the two tables are consistent. Below about 1155 K Ti is hcp in both and the rows agree (0.00 / 0.09 / 0.16 kJ/mol at 800 / 1000 / 1100 K). Above it, `GM_eq` takes bcc, which lies below the hcp `GHSER`, so `g_els − GM_eq` (+0.25 to +0.47) must exceed `g_els − GHSER` (+0.09 to −0.72), as it does; `g_els` lies between hcp and bcc SGTE. The Ti and Y noise grows with temperature (about +0.20 J mol⁻¹ atom⁻¹ K⁻¹ for TiB₂, +0.37 for Ti₅Si₃, +0.12 for YAl₂, recomputed from the table). This is small against the ~15 under study but not zero, and it is recorded, not corrected.
- **La:** above about 1193 K both `g_els` and `GM_eq` follow the liquid (residual about 0). Only the elemental reference is liquid there; LaB₆ itself stays solid to about 2988 K.
- **Fe, Co:** the large `g_els − GHSER` offsets of the traceability table (Fe −1.94, Co −3.10 kJ/mol at 800 K) vanish on the `GM_eq` axis because both include the magnetic term.

### Traceability table: `g_els(T) − GHSER(T)` [kJ/mol] (bare non-magnetic `GHSER` from `unary50.tdb`)

Recorded for traceability to v1.4 (`sisso_reference_offset_kJ`); **not** applied on top of `GM_eq`-referenced CALPHAD values.

| Element | 800 K | 1000 K | 1100 K | 1200 K | 1300 K | 1375 K | 1450 K | 1600 K |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Fe | -1.94 | -0.82 | -0.44 | -0.39 | -0.33 | -0.32 | -0.28 | -0.15 |
| Si | -0.01 | -0.01 | -0.01 | -0.01 | -0.01 | -0.03 | -0.04 | -0.01 |
| B | +0.06 | +0.06 | +0.06 | +0.06 | +0.06 | +0.05 | +0.04 | +0.07 |
| Co | -3.10 | -2.07 | -1.64 | -1.28 | -1.01 | -0.93 | -0.87 | -0.80 |
| Ti | +0.00 | +0.09 | +0.16 | +0.09 | -0.17 | -0.36 | -0.52 | -0.72 |
| La | -0.17 | -0.36 | -0.48 | -0.87 | -1.87 | -2.65 | -3.42 | -4.93 |
| Ni | -0.04 | -0.02 | -0.01 | -0.01 | -0.01 | -0.03 | -0.03 | -0.00 |
| Al | +0.04 | -0.68 | -1.79 | -2.89 | -4.00 | -4.85 | -5.68 | -7.31 |
| Y | +0.27 | +0.33 | +0.37 | +0.40 | +0.44 | +0.44 | +0.47 | +0.57 |
| Mg | -0.00 | -0.71 | -1.65 | -2.58 | -3.52 | -6.51 | -12.61 | -27.80 |
| Nd (held-out) | +0.00 | -0.00 | -0.00 | -0.19 | -0.49 | -1.11 | -1.69 | -2.80 |

## 6. Decision rule (fixed before any calculation; decision rule v1.4)

**Definitions.**
- Per-compound slope: ordinary least-squares slope of Residual(T) against T over the retained points of that compound, in J mol⁻¹ atom⁻¹ K⁻¹.
- **α = unweighted mean of the nine per-compound slopes** (one vote per compound, whatever its number of points).
- Correction: $\Delta G_{\text{corrected}}(T) = \Delta G_{\text{SISSO}}(T) - \alpha\,(T - T_0)/1000$ in kJ mol⁻¹ atom⁻¹, $T_0 = 800$ K.
- **Sign convention:** a positive α means that SISSO becomes too positive (relative to CALPHAD) with rising temperature, and the correction lowers it. Residual = SISSO − CALPHAD throughout.
- **MAE per compound** = mean of |Residual| over the retained points of that compound, before and after the correction. **Mean MAE** = unweighted mean of the nine per-compound MAEs (equal weight per compound, the same weighting as α). The mean over all 68 points is not used for the decision.
- **Gain** of a compound = MAE before − MAE after (positive = improvement). **Mean gain** = unweighted mean of the nine gains.

The correction is adopted **only if both conditions hold** on the nine primary compounds:
1. **Mean gain ≥ 1.5 kJ mol⁻¹ atom⁻¹.**
2. **The largest worsening of any single compound (the most negative gain, as a positive number) does not exceed the mean gain.** This replaces the weaker v1.0 wording ("no more than one compound worsened by more than 2.0 kJ"): with nine chemically different compounds, one strongly worsened compound is a result that must not be hidden by a count.

If either condition fails, SISSO remains uncorrected, and the observed mean slope, the per-compound slopes and their scatter (nine compounds) are documented as a known Stage-5 limitation. The rule is applied once, to the nine-compound fit as defined in Section 3; the sensitivity runs of Section 7 do not replace it.

**Limit of the design:** α is fitted on the nine compounds and the rule is evaluated on the same nine (in-sample), so condition 1 is easier to pass than it would be on unseen compounds. The leave-one-out analysis in Section 7 is the pre-registered answer to this.

## 7. Secondary analyses (exploratory, labelled as such; none alters the Section 6 decision)

Implemented in the script and run in the same call as the main analysis:
- **Without Fe₃Si** (α and the decision rule recomputed on eight compounds). Reason: the Fe₃Si CALPHAD description is a B2 model while the Materials Project entry is D0₃ (Section 9). If the Section 6 decision differs with and without Fe₃Si, both outcomes are reported and the main (nine-compound) outcome stays the registered one.
- **Leave-one-out:** α from eight compounds applied to the ninth, for each compound; report the out-of-sample MAE change.
- **Restriction to 800–1300 K** (the common grid of all nine compounds): α and the Section 6 decision recomputed on the retained points up to 1300 K.
- **Residual at 800 K** of each compound, listed (no second fit).
- **Magnetic (Fe₃Si, Fe₂B) vs non-magnetic (seven compounds):** the mean per-compound slope of each group. Magnetic status is by `Mtot/nsites`, not by `is_magnetic`.

**Nd₂Fe₁₄B (held out; consistency check, not a validation).** Nd₂Fe₁₄B has no CALPHAD description of its own, and its +15 J mol⁻¹ atom⁻¹ K⁻¹ was measured against a competing-binary threshold, not a compound reference. Nd₂Fe₁₄B is therefore not part of this study. After the Section 6 decision has been made, α is applied by arithmetic (no new calculation) to the existing 23 Nov SISSO values for Nd₂Fe₁₄B, and the change in the Stage-5 margin is reported. That run of 23 Nov was not frozen; the statement is a consistency check. Two numbers frame it:
- The reference axis explains only a small part of the +15: Σx(g_els − GHSER) for Nd₂Fe₁₄B changes from −1.59 kJ (800 K) to −0.45 kJ (1600 K), that is **+1.4 J mol⁻¹ atom⁻¹ K⁻¹**. The study is therefore still needed.
- Above about 1375 K the Nd₂Fe₁₄B threshold carries the Fe–B liquid spread between files, up to 1.25 kJ mol⁻¹ atom⁻¹ at 1600 K (`NdFeB_Liquid_Spread_Check_20261125`), close to the 1.5 kJ decision threshold. A correction of that size cannot be told apart from file choice there.

## 8. Freeze requirements

- This document is saved and SHA-256 hashed prior to running the first SISSO evaluation on any compound in Section 3.
- Any modification to the compound list, TDB assignments, reference-axis definition, or decision rule after the first SISSO calculation increments the contract version.

## 9. Known limits (stated before the run)

- **Fe₃Si model class.** `FeSi-14Yua` describes ordered bcc with a two-sublattice B2 model, which cannot represent D0₃; the Materials Project entry (mp-2199) is D0₃. Below the D0₃ → B2 transition the CALPHAD reference lacks the D0₃ ordering energy (part of it may be absorbed in the fitted parameters), and the effect depends on temperature, so it acts on the slope, not only on the offset. Fe₃Si stays in the primary fit set; the without-Fe₃Si analysis (Section 7) shows its influence. The size of the effect was not computed.
- **Reference-table noise.** `g_els − GM_eq` is up to 0.57 kJ/mol (Y), 0.47 (Ti), 0.21 (Al) on the active grids, growing with temperature for Ti and Y; recorded, not corrected.
- **One CALPHAD description per compound.** Differences between assessments (for example the Fe–B liquid) are not sampled. For Fe–B the spread of liquid descriptions is documented separately (see Section 7).
- **In-sample decision** (Section 6) and nine compounds only; the result describes this set, not intermetallics in general.
- **Live database.** The SISSO side depends on the Materials Project release at the time of the run; the release and the entries are stored with the result.
- **Prior knowledge.** The +15 slope on Nd₂Fe₁₄B was known before the study (Section 1).

## 10. Changes since the 25 Nov draft (all before any SISSO value for the nine compounds; none after seeing a result)

1. Decision rule: condition 2 changed from the v1.0 count wording to the v1.4 wording (largest worsening ≤ mean gain); MAE, α, gain and sign convention defined (Section 6).
2. Retention rule with phase-fraction tolerance 0.999 and minimum of 3 points; grid-level limits stated (Section 3).
3. Hash list extended to all nine TDB files, `g_els.json`, the scripts and package versions; `pycalphad` version enforced (Section 2).
4. Selection rule for TDB files written down (Section 2).
5. Element `GM_eq` computed in each compound's own TDB; equality with `unary50.tdb` verified on 26 Nov (Section 5).
6. Notes on Ti, La, Mg, Fe and Co added (Section 5).
7. Secondary analyses: leave-one-out and without-Fe₃Si added; Nd₂Fe₁₄B restated as an arithmetic consistency check after the decision; the "comparison against 0 K DFT formation energies" and the "re-evaluation of Nd₂Fe₁₄B on the `GM_eq` axis" of the 25 Nov draft removed (not part of the script; no new Nd₂Fe₁₄B calculation).
8. Materials Project release and entries recorded with the result (Section 2).
9. Known limits section added (Section 9).
