# Methods text and corrections (decision 5 of CONTRACT.md, 24 Nov 2026)

Replaces the numbers and statements of the 24 Nov plan text that the code and the frozen reports
(`results/`) do not support. Numbers are read from `results/ensemble_*.json` (5–95 % band width = p95 − p05).

## 1. Corrections to the plan text

| Plan text | Correct statement | Source |
|---|---|---|
| Grid 800, 1000, 1200, 1400, 1600 K | 800, 1000, 1100, 1200, 1300, 1375, 1450, 1600 K (8 temperatures) | `DEFAULT_TEMPS` |
| Binary-ensemble scatter "0.3–1.0 kJ mol⁻¹ atom⁻¹ (Nd–Fe–B)" | That range is the **half**-width. Band width (p95 − p05): Nd–Fe–B 0.67–2.00, Al–Fe–Mn 0.44–2.46, Fe–La–Si 2.53–3.60 kJ mol⁻¹ atom⁻¹ over the grid | frozen reports |
| "pre-registered survival or lineage-coverage gates" | Engineering defaults, not pre-registered: G1 ≥ 25 % of combinations survive, G2 ≥ 2 surviving lineages per edge (Stage 4 Cr–Fe–Ni used ≥ 20.8 %, per-class coverage) | `general_ensemble.py` |
| Classes `stable_outside` / `unstable_outside` | `stable_across_band` / `metastable_above_band` (stored names; mapping in `CONTRACT.md`) | `compare_with_calphad_ensemble` |
| "ΔΔG more negative than the lower edge of the band"; half-width pseudo-code | ΔG_f^SISSO < p05 → stable_across_band; > p95 → metastable_above_band; otherwise borderline_within_band. Edge comparison, no half-width | contract decision 4 |
| "if no suitable prototype is found the comparison is not performed" | No entry within the filter: `no_dft_entry`. A nearest prototype is reported as `prototype_indicative_only` (never a stability verdict) with its own-composition check (`verdict_at_prototype`) | contract decision 1 |
| "`gf_sisso()` returns eV; verify the conversion" | The code takes the formation energy per atom from the phase diagram built with `GibbsComputedStructureEntry` and multiplies by 96.485 (eV/atom → kJ/mol-atom); the element references are the pymatgen `g_els` | `dft_sisso_predictor.py` |
| "SISSO deviates from QHA by up to ~0.1 eV/atom by 1800 K" | Not checked here and outside our grid (max 1600 K). What we observe: ΔG_f^SISSO − ΔG_f* grows with T by about +15 J mol⁻¹ atom⁻¹ K⁻¹ for Nd₂Fe₁₄B (a formation entropy of about −15 J K⁻¹ mol⁻¹ atom⁻¹, implausible; cause untested) | 23 Nov Nd₂Fe₁₄B run |
| "A candidate above the binary band is unlikely to be rescued by ternary interactions" | The candidate energy is a DFT value and already contains its own ternary interactions. What is missing are ternary competing phases and ternary terms of the competing assemblage, so a candidate below the band can still lose to a ternary competitor, and one above it is not strictly excluded either. Keep "necessary, not sufficient" and drop the rescue claim | scope of the method |
| Merge order not mentioned | The three edges are merged in the order of the element list and the first file wins on conflicting parameters; the order is part of the specification (Nd–Fe–B: 78/84 survivors in order Fe, Nd, B against 52/84 in alphabetical order) | `edge_priority` |

## 2. Methods paragraphs (ready to use)

**Competing-binary threshold.** For a ternary composition x, all open binary assessments of the three edges were
audited (exclusion of third-generation `-3g` assessments, GHSER consistency, interstitial-site check) and every
combination of one file per edge was merged; the first file's parameters win on conflicts, so the edge order is
part of the specification. A combination is kept only if it reproduces each of its own binary assessments at the
stored reference points (Edge-Check Rule v2: |ΔG| ≤ 1 J mol⁻¹, at most two unverifiable points). For each surviving
combination the threshold ΔG_f*(T) = G_comp(x, T) − Σ x_i GHSER_i(T) is the equilibrium energy of the binary phases at
x (no ternary phase), per mole of atoms, relative to the SGTE element references. The ensemble is summarised by its
median and the 5th–95th percentile band. Gates G1 (≥ 25 % of combinations survive) and G2 (≥ 2 lineages per edge) are
engineering defaults; a failed gate marks the result `ensemble_unreliable`. Temperatures: 800, 1000, 1100, 1200,
1300, 1375, 1450 and 1600 K.

**Candidate energy.** ΔG_f^SISSO(T) is taken from the Materials Project 0 K entry with the Bartel SISSO
vibrational/electronic correction (`GibbsComputedStructureEntry`), as formation energy per atom relative to the
pymatgen elemental references, converted to kJ mol⁻¹ atom⁻¹. Only entries within the prototype filter are used:
an exact composition match, or a nearest prototype (minority-element guard, composition distance ≤ 0.16, optionally with
elements that share a site grouped). A nearest prototype is never a stability verdict at the target; its energy is
compared with the threshold re-evaluated at the prototype's own composition on the surviving combinations
(`verdict_at_prototype`).

**Classification.** The class of an exact match is set by the CALPHAD band alone: ΔG_f^SISSO < p05
(`stable_across_band`), p05 ≤ ΔG_f^SISSO ≤ p95 (`borderline_within_band`), > p95 (`metastable_above_band`). The SISSO
margin ΔΔG = ΔG_f^SISSO − ΔG_f*,median and its value on the SER axis of the CALPHAD side are reported as secondary,
approximate quantities and do not change the class. The temperature of the most negative margin, the temperature
runs with ΔG_f^SISSO ≤ p95 and < p05, and any change of class are reported as the stability window.

**Limitations.** (i) The SISSO margin is approximate: its model error is not part of the class and is usually larger
than the band (band width 0.4–3.6 kJ mol⁻¹ atom⁻¹ over our three systems); for Nd₂Fe₁₄B the difference to the
CALPHAD threshold grows with temperature by about 15 J mol⁻¹ atom⁻¹ K⁻¹. (ii) Only binary competitors are
considered. (iii) Merge order and the gate thresholds are specification choices and are recorded with each result.
(iv) With site groups, a nearest prototype may be far from the target in Euclidean terms (LaFe₉Si₄: 0.252 for
La₇.₁Fe₈₂.₁Si₁₀.₈); its result describes the structure type at its own composition, not the target.

## 3. Numbers for the three frozen systems (800 K)

| System | Survivors | ΔG_f*(800 K), median [p05, p95] kJ mol⁻¹ atom⁻¹ | Band width 800 K / smallest–largest over the grid |
|---|---|---|---|
| Nd₂Fe₁₄B (Fe, Nd, B) | 78/84 (93 %) | −8.79 [−9.20, −8.40] | 0.80 / 0.67–2.00 |
| Al₁₆Fe₅Mn₅ (Al, Fe, Mn) | 313/594 (53 %) | −25.51 [−26.52, −24.06] | 2.46 / 0.44–2.46 |
| La₇.₁Fe₈₂.₁Si₁₀.₈ (Fe, Si, La) | 16/20 (80 %) | −17.78 [−19.00, −16.47] | 2.53 / 2.53–3.60 |

`results/methods_table_800K.md` holds the same table with gates and file hashes.
