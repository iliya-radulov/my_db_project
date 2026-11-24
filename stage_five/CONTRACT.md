# Stage 5 screening contract (frozen 2026-11-24)

The meaning of the numbers that `general_ensemble.py` (CALPHAD side) and `dft_sisso_predictor.py`
(DFT + SISSO side) exchange. The decisions below were taken on 24 Nov 2026; code and database follow them.

## Quantities
* ΔG_f*(T): competing-binary threshold, kJ/mol-atom, relative to the SER (GHSER) references of the binary TDBs.
  Median, p05, p95 over the surviving combinations; survivors and gates G1/G2 are reported with it.
* ΔG_f^SISSO(T): Materials Project 0 K entry + Bartel descriptor (`GibbsComputedStructureEntry`), kJ/mol-atom,
  relative to the pymatgen element references `g_els`.
* Margin ΔΔG = ΔG_f^SISSO − ΔG_f*,median. Secondary, approximate fields (labelled so everywhere):
  `ref_correction_kj` = Σ x_i (g_els_i − GHSER_i), `dgf_sisso_ser_kj` = ΔG_f^SISSO + correction,
  `margin_ser_kj` = that − median.

## Decisions
1. **Prototype margin** is taken against the threshold *at the prototype's own composition*, not at the
   experimental target. The edge check does not depend on composition, so only the threshold is re-evaluated, on the
   surviving combinations (`general_ensemble.rethreshold_at_composition`; at the target composition it reproduces the
   frozen band to 2e-4 kJ/mol-atom). Result per nearest-prototype row: `verdict_at_prototype` (same class rule, band
   edges of the prototype composition; `ensemble_unreliable` if fewer than 25 % of the survivors can be evaluated
   there) and `threshold_composition` (JSONB: composition, matched median/p05/p95, margin, n). The row itself stays
   `prototype_indicative_only`, `comparable = FALSE`; a later promotion rule may use `verdict_at_prototype`.
   An element missing from the prototype is held at 1e-6 and the composition renormalised. No new migration.
2. **SISSO is a soft, secondary axis.** The three classes come from the CALPHAD band only. SISSO error and the
   reference-axis correction never move a row between classes. Known limitation: the observed temperature slope
   of ΔG_f^SISSO against the CALPHAD threshold is about +15 J mol⁻¹ atom⁻¹ K⁻¹ (Nd2Fe14B); the cause is untested
   and nothing in the screening code compensates for it.
3. **Labels.** `stable_across_band` (ΔG_f^SISSO < p05), `borderline_within_band` (p05 ≤ ΔG_f^SISSO ≤ p95),
   `metastable_above_band` (> p95), `ensemble_unreliable` (gates failed: rows are written, margin NULL),
   `sisso_unavailable`, `no_dft_entry`, `prototype_indicative_only`.
   View `alloy_lab.v_stage5_screening` (migration 011) exposes the plan's column names:

   | plan name | stored as |
   |---|---|
   | system, composition, T | `calphad_ensemble_runs.system_name`, `target_composition`, `temperature_k` |
   | delta_g_star_median / p05 / p95 | `threshold_median_kj`, `threshold_p05_kj`, `threshold_p95_kj` |
   | n_survivors | `calphad_ensemble_runs.n_survivors` |
   | delta_g_sisso, delta_delta_g | `dgf_sisso_kj`, `stability_margin_kj` |
   | classification | `verdict` (`stable_outside` = `stable_across_band`, `unstable_outside` = `metastable_above_band`) |
   | prototype_mp_id, prototype_label, notes | `mp_id`, `prototype_formula`, `notes` |
4. **Wording.** The rule compares ΔG_f^SISSO with the band edges (p05, p95). "Half-width" language is
   approximate and not used in the code.
5. Numbers for the temperature grid and band widths in the methods text are corrected later, from the frozen
   reports in `results/`.

## Stability window (`stability_window.py`)
Per exact-match candidate on the temperature grid: temperature of the most negative margin; runs where
ΔG_f^SISSO ≤ p95 and where ΔG_f^SISSO < p05; whether and where the class changes. Rows of nearest prototypes
and `ensemble_unreliable` rows are excluded.

## Other rules in this PR
* Dopants (< 3 at.%) are never prototype anchors; the smallest remaining element is an anchor only if ≤ 25 at.%
  (Mn45Al54C1 → no anchor → MnAl found; Nd2Fe14B → B; La7.1Fe82.1Si10.8 → La).
* The GUI hands Stage 5 the typed formula when it equals the resolved composition, otherwise a 12-digit formula,
  so GUI and CLI share one cache entry.
* `sisso_uncertainty_kJ` and `--sisso-uncertainty-kj` are removed.
