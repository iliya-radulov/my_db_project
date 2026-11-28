# Stage 5 screening contract, version 1.1 (1.0 frozen 2026-11-24; 1.1 is a documentation update of 2026-11-28)

The meaning of the numbers that `general_ensemble.py` (CALPHAD side) and `dft_sisso_predictor.py`
(DFT + SISSO side) exchange. The decisions below were taken on 24 Nov 2026; code and database follow them.
This file is the reference for the technical note (`TECHNICAL_NOTE.md`) and for the methods text
(`METHODS_TEXT.md`). Anything that changes the meaning of a stored number is a new contract version
(see "Change control").

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
   of ΔG_f^SISSO against the CALPHAD threshold is about +15 J mol⁻¹ atom⁻¹ K⁻¹ (Nd2Fe14B); it comes entirely from the temperature dependence of the SISSO term itself (slope +15.11 against +0.19 for the threshold), its physical cause is untested
   and nothing in the screening code compensates for it. A pre-registered calibration on nine binary intermetallics
   (27 Nov 2026) found no common temperature slope and the correction was not adopted (section "Calibration study").
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

## Verdict labels (the exact meaning of every value of `verdict`)

| label | row type | meaning | margin | `comparable` |
|---|---|---|---|---|
| `stable_across_band` | exact match, gates passed | ΔG_f^SISSO < p05 of the CALPHAD band at the target composition | stored | TRUE |
| `borderline_within_band` | exact match, gates passed | p05 ≤ ΔG_f^SISSO ≤ p95; difference smaller than the assessment scatter, inconclusive | stored | TRUE |
| `metastable_above_band` | exact match, gates passed | ΔG_f^SISSO > p95: above the competing binaries | stored | TRUE |
| `prototype_indicative_only` | nearest prototype | the entry is at another composition; no stability verdict at the target. Read `verdict_at_prototype` | at the target band, for orientation only | FALSE |
| `ensemble_unreliable` | any row | the ensemble failed G1 or G2; the band may be shown, no class and no margin | NULL | FALSE |
| `sisso_unavailable` | one row per temperature, `mp_id = NO_MP_ENTRY` | the Materials Project / SISSO step could not run (key, network, package); the CALPHAD band is complete | none | FALSE |
| `no_dft_entry` | one row per temperature, `mp_id = NO_MP_ENTRY` | no entry at the target composition and none within the prototype filter | none | FALSE |

A run whose gates failed and that has no DFT entry has no comparison rows at all; its run row carries
`gate_passed = FALSE`.

`verdict_at_prototype` (nearest-prototype rows only, with the matched check): `stable_across_band`,
`borderline_within_band`, `metastable_above_band` against the band at the prototype's own composition, or
`ensemble_unreliable` if fewer than 25 % of the surviving combinations can be evaluated there. It describes the
structure type at that composition, not the target.

## Exact versus prototype rows
* `exact_match`: distance ≤ 5·10⁻⁴ in atomic fractions (absorbs rounded at.% input). Gets a class.
* `nearest_prototype`: passes the anchor guard (minority element present, within 0.03; dopants < 3 at.% are never
  anchors) and the composition distance ≤ 0.16, optionally with elements that share a site grouped (opt-in
  `--site-group FE,SI`). Never gets a class at the target; its energy is compared with the band re-evaluated at the
  prototype's own composition. Ranking: exact before nearest, then 0 K hull energy (0.01 eV/atom ties), then
  lowest-temperature ΔG_f^SISSO, then Δx; at most 3 prototypes are kept.
* `listed_other_ternary` (option `include_subsystems`) is listed and never compared or stored.

## Display rules (CLI, desktop preview, Stage 5 tab)
* Provenance label: `mp-1 (Nd2Fe14B, exact_match)`; `mp-2 (LaFe13, nearest_prototype Δx=0.152)`. With site groups,
  when the grouped distance and the Euclidean distance differ by more than 0.005, both are shown:
  `Δx=0.001 (grouped), Euclid 0.252`. The grouped Δx only says that the site-group totals agree; the Euclidean
  distance says how far the Fe:Si split is from the target (LaFe9Si4 is 0.252 from La7.1Fe82.1Si10.8).
* `‡` marks a nearest-prototype row whose median, band, margin and class are those of the prototype's own
  composition; a footnote says so. Without the matched check the target-composition values are shown with the
  note "for orientation only". In the methods table `†` marks an indicative margin.
* `Margin(ref)` is the approximate reference-axis value; it never decides a class.
* Stored values are not changed by display rules: `threshold_*` hold the band at the target composition;
  the matched band, margin, composition and the Euclidean distance are in `threshold_composition` (JSONB).

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

## Linking a run to a sample (migration 012)
`Submit to Database` links the Stage 5 run of the submitted preview to the new sample (only if the run belongs to
that exact preview; if Stage 5 is still running, the link is made when it finishes). `calphad_run_samples` is
many-to-many because a cached run is reused for every sample with the same composition and options; the view
`v_stage5_sample_runs` lists run, system, gates and survivors per sample code, and Quick Lookup shows them. Without
012 the old single column is used and a run that already belongs to another sample is not re-linked.

## Calibration study (27 Nov 2026; recorded in contract version 1.1)
A pre-registered test of whether a global linear temperature correction α of ΔG_f^SISSO helps, with the CALPHAD
assessments as the reference: nine binary intermetallics (Fe₃Si, Fe₂B, CoSi, TiB₂, LaB₆, NiAl, YAl₂, Ti₅Si₃, Mg₂Si),
68 compound–temperature points, one Materials Project entry per compound (E_hull 0), database release 2026.09.28.
Decision rule v1.4 (frozen before the run): adopt α only if the mean absolute error falls by at least
1.5 kJ mol⁻¹ atom⁻¹ and no compound worsens by more than the mean gain.

* **Outcome: the correction is not adopted; SISSO stays uncorrected.** α = +1.56 J mol⁻¹ atom⁻¹ K⁻¹ (scatter SD 6.72);
  mean gain +0.003 kJ mol⁻¹ atom⁻¹ against the required 1.5; largest worsening 0.666 kJ mol⁻¹ atom⁻¹. Without Fe₃Si
  α = +0.27; for 800–1300 K only α = −0.42 (exploratory; neither would be adopted).
* **There is no common slope**: six compounds have positive and three negative slopes, between −7.3 and +11.9
  J mol⁻¹ atom⁻¹ K⁻¹. The error is mainly an offset (mean absolute residual 2.8 kJ mol⁻¹ atom⁻¹ at 800 K; CoSi about
  −11, cause not investigated), which a temperature term cannot remove. The +15 of Nd₂Fe₁₄B is larger than any slope in
  the set.
* **Hypothesis, not a finding** (noticed after the result, two compounds): the two magnetic compounds have slopes of
  about +10 to +12 and the seven non-magnetic ones average −1.2, which could point to a magnetic contribution on the
  CALPHAD side that the SISSO temperature term does not know. Testing it needs a new pre-registration with more
  magnetic compounds that have a CALPHAD description.
* **Consequence for the screening:** nothing changes. Classes, margins and stored values are as in 1.0; the observed
  slopes and their scatter are a documented limitation.

## Frozen artefacts (contract versions 1.0 and 1.1)

| item | value |
|---|---|
| engine rules version | `stage5-engine/edge-rule-v2/fix1-2026-11-23` (`ENGINE_RULES_VERSION`) |
| ensemble reports | `results/ensemble_*.json`, hashes in `results/SHA256SUMS`; produced with pycalphad 0.11.2 |
| screening export | `results/screen_Fe-La-Si_La7.1Fe82.1Si10.8_sitegroup_FE-SI.json` (ensemble, SISSO report, comparison rows with the composition-matched check, windows); same hash file |
| three-system table | `results/methods_table_800K.md` / `.tsv` (regenerated from the reports above) |
| migrations | 009 tables; 010 prototype provenance and `prototype_filter`; 011 secondary fields and view `v_stage5_screening`; 012 run-sample links and view `v_stage5_sample_runs` |
| reproduction | the three reports are reproduced by the current engine (survivors per combination, bands; see `results/README.md`) |
| release tag | `v5.0-stage5` (proposed; the tag, not this file, identifies the archived code) |
| calibration study (1.1) | pre-registration `SISSO_T_Calibration_PreReg.md` (sha256 `22e867c3…`, rule v1.4, freeze commit `6e0014a`), manifest `SISSO_T_Calibration_Manifest.json`, script `sisso_t_calibration.py` (sha256 `96e797e9…`), results `results/sisso_t_calibration.md` / `.json` and `results/sisso_t_calibration_calphad_check.json` |

## Change control
Versions 1.0 and 1.1 fix the definitions above (1.1 changes no definition). A change to a label, a class rule, the gate defaults, the merge-order rule,
the prototype filter or the units is a new contract version with a changelog entry here, and old results stay
labelled with the version they were produced under (`engine_rules_version`, `spec_sha256`). Additive display
changes do not need a new version. Not part of 1.0 or 1.1: any promotion of nearest-prototype rows to verdicts, and
any SISSO temperature correction (the calibration of 27 Nov 2026 did not support one).

### Changelog
* 1.0 (2026-11-24): first frozen version.
* 1.1 (2026-11-28): documentation update. The SISSO temperature calibration of 27 Nov 2026 (nine compounds, α = +1.56
  J mol⁻¹ atom⁻¹ K⁻¹, SD 6.7; correction not adopted) is recorded under decision 2 and in "Calibration study", the
  frozen study files are listed, and the planned items are updated. No label, class rule, gate, merge-order rule,
  prototype filter, unit, engine rules version or stored value changed.
